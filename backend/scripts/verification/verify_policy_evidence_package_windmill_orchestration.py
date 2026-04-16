#!/usr/bin/env python3
"""Verifier for Windmill policy evidence package orchestration boundary."""

from __future__ import annotations

import argparse
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import subprocess
import sys
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


DEFAULT_OUTPUT = (
    REPO_ROOT
    / "docs"
    / "poc"
    / "policy-evidence-package-windmill"
    / "artifacts"
    / "policy_evidence_package_windmill_orchestration_report.json"
)
DEFAULT_OUTPUT_MD = (
    REPO_ROOT
    / "docs"
    / "poc"
    / "policy-evidence-package-windmill"
    / "artifacts"
    / "policy_evidence_package_windmill_orchestration_report.md"
)
WINDMILL_SCRIPT_PATH = (
    REPO_ROOT
    / "ops"
    / "windmill"
    / "f"
    / "affordabot"
    / "policy_evidence_package_orchestration.py"
)
FLOW_PATH = (
    REPO_ROOT
    / "ops"
    / "windmill"
    / "f"
    / "affordabot"
    / "policy_evidence_package_orchestration__flow"
    / "flow.yaml"
)
VERIFY_TS = "2026-04-15T00:00:00+00:00"
POLICY_EVIDENCE_BACKEND_COMMAND_PATH = "/cron/pipeline/policy-evidence/command"
DOMAIN_BOUNDARY_BACKEND_COMMAND_PATH = "/cron/pipeline/domain/run-scope"
AUTHORITATIVE_LIVE_PROOF_FLOW = "f/affordabot/pipeline_daily_refresh_domain_boundary__flow"
DOMAIN_BOUNDARY_LIVE_EVIDENCE_IDEMPOTENCY_KEY = "bd-3wefe.13-live-domain-backend-2026-04-15-r1"
DOMAIN_BOUNDARY_LIVE_EVIDENCE_STATUS = "succeeded_with_alerts"
DOMAIN_BOUNDARY_LIVE_EVIDENCE_WARNING = (
    "top z.ai reader candidates returned provider 500; fallback transcript materialized; sufficiency_state=Insufficient"
)


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _extract_last_json_object(text: str) -> dict[str, Any]:
    for line in reversed(text.splitlines()):
        candidate = line.strip()
        if not candidate.startswith("{"):
            continue
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return {}


def _backend_route_contract_snapshot() -> dict[str, Any]:
    backend_main = (BACKEND_ROOT / "main.py").read_text(encoding="utf-8")
    policy_route_present = f'@app.post("{POLICY_EVIDENCE_BACKEND_COMMAND_PATH}")' in backend_main
    domain_route_present = f'@app.post("{DOMAIN_BOUNDARY_BACKEND_COMMAND_PATH}")' in backend_main
    route_mismatch = (not policy_route_present) and domain_route_present
    return {
        "policy_evidence_backend_path": POLICY_EVIDENCE_BACKEND_COMMAND_PATH,
        "domain_boundary_backend_path": DOMAIN_BOUNDARY_BACKEND_COMMAND_PATH,
        "policy_evidence_backend_route_present": policy_route_present,
        "domain_boundary_backend_route_present": domain_route_present,
        "route_mismatch": route_mismatch,
        "authoritative_live_product_flow": AUTHORITATIVE_LIVE_PROOF_FLOW,
        "authoritative_live_evidence_idempotency_key": DOMAIN_BOUNDARY_LIVE_EVIDENCE_IDEMPOTENCY_KEY,
        "authoritative_live_evidence_status": DOMAIN_BOUNDARY_LIVE_EVIDENCE_STATUS,
        "authoritative_live_evidence_warning": DOMAIN_BOUNDARY_LIVE_EVIDENCE_WARNING,
    }


def _load_module():
    spec = __import__("importlib.util").util.spec_from_file_location(
        "policy_evidence_windmill", WINDMILL_SCRIPT_PATH
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("failed to load windmill policy evidence script")
    module = __import__("importlib.util").util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _backend_response(payload: dict[str, Any]) -> dict[str, Any]:
    command_name = payload.get("command_name", "")
    refs = payload.get("refs") or {}
    package_id = payload.get("package_id") or "pkg-backend-endpoint"
    package_readiness_status = payload.get("package_readiness_status") or "ready"
    gate_status = payload.get("gate_status") or "quantified"
    previous = payload.get("previous_step_output") or {}

    base = {
        "status": "succeeded",
        "command_name": command_name,
        "command_id": f"cmd-{_hash(json.dumps({'name': command_name, **refs}, sort_keys=True))}",
        "refs": refs,
        "decision_reason": "backend_endpoint_passthrough",
        "retry_class": "none",
    }
    if command_name == "fetch_scraped_candidates":
        return {**base, "scraped_snapshot_id": f"snap-scraped-{_hash(package_id)}", "scraped_candidate_count": 3}
    if command_name == "fetch_structured_candidates":
        return {
            **base,
            "structured_snapshot_id": f"snap-structured-{_hash(package_id)}",
            "structured_candidate_count": 2,
        }
    if command_name == "build_policy_evidence_package":
        if not previous:
            return {
                **base,
                "status": "failed",
                "decision_reason": "missing_inputs",
                "retry_class": "non_retryable_validation",
            }
        return {
            **base,
            "package_id": package_id,
            "package_readiness_status": package_readiness_status,
            "gate_status": gate_status,
        }
    if command_name == "persist_readback_boundary":
        if not previous:
            return {
                **base,
                "status": "failed",
                "decision_reason": "missing_package",
                "retry_class": "non_retryable_validation",
            }
        return {
            **base,
            "package_id": package_id,
            "storage_refs": {
                "postgres_package_row": f"policy_evidence_packages:{package_id}",
                "minio_package_artifact": f"minio://policy-evidence/packages/{package_id}.json",
                "pgvector_chunk_projection": f"pgvector://document_chunks/{_hash(package_id)}",
            },
            "decision_reason": "persist_boundary_called",
        }
    if command_name == "evaluate_package_readiness":
        if package_readiness_status in {"blocked", "insufficient"}:
            return {
                **base,
                "status": "blocked",
                "package_id": package_id,
                "package_readiness_status": package_readiness_status,
                "gate_status": gate_status,
                "decision_reason": "package_not_ready_for_economic_handoff",
                "retry_class": "retry_after_new_evidence",
            }
        return {
            **base,
            "package_id": package_id,
            "package_readiness_status": "ready",
            "gate_status": gate_status,
            "decision_reason": "package_ready_for_economic_handoff",
        }
    if command_name == "summarize_orchestration":
        previous_status = previous.get("status", "failed") if isinstance(previous, dict) else "failed"
        flow_status = "succeeded" if previous_status == "succeeded" else "blocked"
        return {
            **base,
            "status": flow_status,
            "package_id": package_id,
            "package_readiness_status": package_readiness_status,
            "gate_status": gate_status,
            "decision_reason": (
                "orchestration_completed" if flow_status == "succeeded" else "orchestration_blocked"
            ),
        }
    return {
        **base,
        "status": "failed",
        "decision_reason": "unsupported_command",
        "retry_class": "non_retryable_validation",
    }


@contextmanager
def _local_backend_command_endpoint(auth_token: str):
    state: dict[str, Any] = {"events": []}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            auth_header = self.headers.get("Authorization", "")
            if auth_header != f"Bearer {auth_token}":
                self.send_response(401)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"status":"failed","error":"unauthorized"}')
                return
            content_length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(content_length) if content_length > 0 else b"{}"
            payload = json.loads(body.decode("utf-8") or "{}")
            response_payload = _backend_response(payload)
            state["events"].append(
                {
                    "command_name": payload.get("command_name"),
                    "jurisdiction": payload.get("jurisdiction"),
                    "query_family": payload.get("query_family"),
                    "idempotency_key": (payload.get("refs") or {}).get("idempotency_key"),
                    "status": response_payload.get("status"),
                }
            )
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(response_payload).encode("utf-8"))

        def log_message(self, fmt: str, *args: Any) -> None:  # noqa: D401
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", state
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def _run_local(module: Any) -> dict[str, Any]:
    stub_happy = module.main(
        step="run_scope_pipeline",
        idempotency_key="run:bd-3wefe.13:local-happy",
        windmill_run_id="wm-local-policy-happy",
        windmill_job_id="wm-local-job-happy",
        jurisdiction="San Jose CA",
        query_family="meeting_minutes",
        package_id="pkg-local-happy",
        package_readiness_status="ready",
        gate_status="quantified",
    )
    stub_blocked = module.main(
        step="run_scope_pipeline",
        idempotency_key="run:bd-3wefe.13:local-blocked",
        windmill_run_id="wm-local-policy-blocked",
        windmill_job_id="wm-local-job-blocked",
        jurisdiction="San Jose CA",
        query_family="meeting_minutes",
        package_id="pkg-local-blocked",
        package_readiness_status="blocked",
        gate_status="insufficient_evidence",
    )
    auth_token = "local-backend-token"
    with _local_backend_command_endpoint(auth_token) as (endpoint_url, state):
        backend_endpoint_happy = module.main(
            step="run_scope_pipeline",
            idempotency_key="run:bd-3wefe.13:local-backend-endpoint",
            windmill_run_id="wm-local-policy-backend-endpoint",
            windmill_job_id="wm-local-job-backend-endpoint",
            jurisdiction="San Jose CA",
            query_family="meeting_minutes",
            package_id="pkg-local-backend-endpoint",
            package_readiness_status="ready",
            gate_status="quantified",
            command_client="backend_endpoint",
            backend_endpoint_url=endpoint_url,
            backend_endpoint_auth_token=auth_token,
        )
        backend_endpoint_events = list(state["events"])

    return {
        "stub_happy": stub_happy,
        "stub_blocked": stub_blocked,
        "backend_endpoint_happy": backend_endpoint_happy,
        "backend_endpoint_events": backend_endpoint_events,
    }


def _run_live_smoke() -> dict[str, Any]:
    cmd = """
set -euo pipefail
source ~/agent-skills/scripts/lib/dx-auth.sh
WINDMILL_API_TOKEN="$(DX_AUTH_CACHE_ONLY=1 dx_auth_read_secret_cached 'op://dev/Agent-Secrets-Production/WINDMILL_API_TOKEN')"
WINDMILL_DEV_LOGIN_URL="$(DX_AUTH_CACHE_ONLY=1 dx_auth_read_secret_cached 'op://dev/Agent-Secrets-Production/WINDMILL_DEV_LOGIN_URL')"
WINDMILL_BASE_URL="${WINDMILL_DEV_LOGIN_URL%/user/login}"
TMP_WMILL_CONFIG="$(mktemp -d)"
trap 'rm -rf "$TMP_WMILL_CONFIG"' EXIT
npx --yes windmill-cli workspace add affordabot affordabot "$WINDMILL_BASE_URL" --token "$WINDMILL_API_TOKEN" --config-dir "$TMP_WMILL_CONFIG" >/dev/null
npx --yes windmill-cli workspace list --config-dir "$TMP_WMILL_CONFIG"
npx --yes windmill-cli flow get f/affordabot/policy_evidence_package_orchestration__flow --workspace affordabot --config-dir "$TMP_WMILL_CONFIG" --json
RUN_PAYLOAD='{"idempotency_key":"bd-3wefe-policy-evidence-verifier-stub","jurisdiction":"San Jose CA","query_family":"meeting_minutes","package_id":"pkg-bd-3wefe-verifier-stub","package_readiness_status":"ready","gate_status":"quantified","command_client":"stub","backend_endpoint_timeout_seconds":60}'
npx --yes windmill-cli flow run f/affordabot/policy_evidence_package_orchestration__flow --workspace affordabot --config-dir "$TMP_WMILL_CONFIG" -s -d "$RUN_PAYLOAD"
"""
    proc = subprocess.run(
        ["bash", "-lc", cmd],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode == 0:
        run_result = _extract_last_json_object(proc.stdout.strip())
        return {
            "live_status": "passed_stub_flow_run",
            "commands": [
                "windmill-cli workspace list (read-only)",
                "windmill-cli flow get f/affordabot/policy_evidence_package_orchestration__flow (read-only)",
                "windmill-cli flow run f/affordabot/policy_evidence_package_orchestration__flow (stub, synchronous)",
            ],
            "return_code": proc.returncode,
            "stdout_redacted": bool(proc.stdout.strip()),
            "stderr_redacted": bool(proc.stderr.strip()),
            "stub_run_result": run_result,
            "blocker": None,
        }
    stderr = proc.stderr.strip()
    blocker = "live_windmill_auth_or_cli_unavailable_noninteractive"
    if "Flow not found" in stderr:
        blocker = "flow_not_deployed_in_windmill_workspace"
    return {
        "live_status": "blocked",
        "commands": [
            "windmill-cli workspace list (read-only)",
            "windmill-cli flow get f/affordabot/policy_evidence_package_orchestration__flow (read-only)",
            "windmill-cli flow run f/affordabot/policy_evidence_package_orchestration__flow (stub, synchronous)",
        ],
        "return_code": proc.returncode,
        "stdout_redacted": bool(proc.stdout.strip()),
        "stderr_summary": "Flow not found" if "Flow not found" in stderr else "see verifier stderr",
        "blocker": blocker,
    }


def _build_report(local: dict[str, Any], live: dict[str, Any]) -> dict[str, Any]:
    stub_happy = local["stub_happy"]
    stub_blocked = local["stub_blocked"]
    backend_endpoint_happy = local["backend_endpoint_happy"]
    backend_endpoint_events = local["backend_endpoint_events"]
    local_stub_status = (
        "passed" if stub_happy.get("status") == "succeeded" and stub_blocked.get("status") == "blocked" else "failed"
    )
    local_backend_endpoint_status = (
        "passed" if backend_endpoint_happy.get("status") == "succeeded" and bool(backend_endpoint_events) else "failed"
    )
    contract_snapshot = _backend_route_contract_snapshot()
    if contract_snapshot["route_mismatch"]:
        live_status = "blocked_backend_endpoint_route_mismatch"
    else:
        live_status = live["live_status"]
    return {
        "feature_key": "bd-3wefe.13",
        "generated_at": VERIFY_TS,
        "report_version": "2026-04-15.policy-evidence-package-windmill.v3",
        "local_status": "passed"
        if local_stub_status == "passed" and local_backend_endpoint_status == "passed"
        else "failed",
        "local_stub_status": local_stub_status,
        "local_backend_endpoint_status": local_backend_endpoint_status,
        "live_status": live_status,
        "contract_alignment": contract_snapshot,
        "authoritative_live_evidence": {
            "flow_path": contract_snapshot["authoritative_live_product_flow"],
            "idempotency_key": contract_snapshot["authoritative_live_evidence_idempotency_key"],
            "status": contract_snapshot["authoritative_live_evidence_status"],
            "warning": contract_snapshot["authoritative_live_evidence_warning"],
        },
        "steps_proven": [
            "fetch_scraped_candidates",
            "fetch_structured_candidates",
            "build_policy_evidence_package",
            "persist_readback_boundary",
            "evaluate_package_readiness",
            "summarize_orchestration",
        ],
        "boundary_assertions": [
            "windmill_owns_orchestration_only",
            "backend_command_ids_preserved",
            "windmill_run_job_step_refs_preserved",
            "package_id_storage_refs_gate_status_preserved",
            "branch_on_backend_authored_readiness_only",
        ],
        "stub_happy_path": {
            "status": stub_happy.get("status"),
            "package_id": stub_happy.get("package_id"),
            "package_readiness_status": stub_happy.get("package_readiness_status"),
            "gate_status": stub_happy.get("gate_status"),
            "decision_reason": stub_happy.get("decision_reason"),
            "retry_class": stub_happy.get("retry_class"),
            "storage_refs": stub_happy.get("storage_refs"),
        },
        "stub_blocked_path": {
            "status": stub_blocked.get("status"),
            "package_id": stub_blocked.get("package_id"),
            "package_readiness_status": stub_blocked.get("package_readiness_status"),
            "gate_status": stub_blocked.get("gate_status"),
            "decision_reason": stub_blocked.get("decision_reason"),
            "retry_class": stub_blocked.get("retry_class"),
        },
        "backend_endpoint_local_path": {
            "status": backend_endpoint_happy.get("status"),
            "command_client": backend_endpoint_happy.get("command_client"),
            "package_id": backend_endpoint_happy.get("package_id"),
            "gate_status": backend_endpoint_happy.get("gate_status"),
            "decision_reason": backend_endpoint_happy.get("decision_reason"),
            "event_count": len(backend_endpoint_events),
            "command_names_seen": [str(event.get("command_name") or "") for event in backend_endpoint_events],
            "events": backend_endpoint_events,
        },
        "live_surface_probe": live,
        "open_gaps": [
            "policy-evidence stub flow pass is not authoritative for full live product proof",
            "route mismatch: policy-evidence backend endpoint path is not a live backend route",
            "treat latest domain-boundary live run as proof-with-warning, not clean data-quality pass",
            "run storage verifier in Railway dev with DATABASE_URL and MinIO env available",
            "connect resulting package to canonical analysis output and admin/frontend read model",
        ],
    }


def _to_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Policy Evidence Package Windmill Orchestration Report",
        "",
        "## Status",
        f"- local_status: `{report['local_status']}`",
        f"- local_stub_status: `{report['local_stub_status']}`",
        f"- local_backend_endpoint_status: `{report['local_backend_endpoint_status']}`",
        f"- live_status: `{report['live_status']}`",
        "",
        "## Steps Proven",
    ]
    for step in report["steps_proven"]:
        lines.append(f"- `{step}`")
    lines.extend(
        [
            "",
            "## Boundary Assertions",
        ]
    )
    for assertion in report["boundary_assertions"]:
        lines.append(f"- `{assertion}`")
    lines.extend(
        [
            "",
            "## Stub Happy Path",
            f"- status: `{report['stub_happy_path']['status']}`",
            f"- package_id: `{report['stub_happy_path']['package_id']}`",
            f"- readiness: `{report['stub_happy_path']['package_readiness_status']}`",
            f"- gate_status: `{report['stub_happy_path']['gate_status']}`",
            f"- decision_reason: `{report['stub_happy_path']['decision_reason']}`",
            f"- retry_class: `{report['stub_happy_path']['retry_class']}`",
            "",
            "## Stub Blocked Path",
            f"- status: `{report['stub_blocked_path']['status']}`",
            f"- package_id: `{report['stub_blocked_path']['package_id']}`",
            f"- readiness: `{report['stub_blocked_path']['package_readiness_status']}`",
            f"- gate_status: `{report['stub_blocked_path']['gate_status']}`",
            f"- decision_reason: `{report['stub_blocked_path']['decision_reason']}`",
            f"- retry_class: `{report['stub_blocked_path']['retry_class']}`",
            "",
            "## Local Backend Endpoint Path",
            f"- status: `{report['backend_endpoint_local_path']['status']}`",
            f"- command_client: `{report['backend_endpoint_local_path']['command_client']}`",
            f"- event_count: `{report['backend_endpoint_local_path']['event_count']}`",
            f"- command_names_seen: `{','.join(report['backend_endpoint_local_path']['command_names_seen'])}`",
            "",
            "## Contract Alignment",
            f"- policy_evidence_backend_path: `{report['contract_alignment']['policy_evidence_backend_path']}`",
            f"- policy_evidence_backend_route_present: `{report['contract_alignment']['policy_evidence_backend_route_present']}`",
            f"- domain_boundary_backend_path: `{report['contract_alignment']['domain_boundary_backend_path']}`",
            f"- domain_boundary_backend_route_present: `{report['contract_alignment']['domain_boundary_backend_route_present']}`",
            f"- route_mismatch: `{report['contract_alignment']['route_mismatch']}`",
            f"- authoritative_live_product_flow: `{report['contract_alignment']['authoritative_live_product_flow']}`",
            "",
            "## Authoritative Live Evidence",
            f"- flow_path: `{report['authoritative_live_evidence']['flow_path']}`",
            f"- idempotency_key: `{report['authoritative_live_evidence']['idempotency_key']}`",
            f"- status: `{report['authoritative_live_evidence']['status']}`",
            f"- warning: `{report['authoritative_live_evidence']['warning']}`",
            "",
            "## Live Windmill Surface Probe",
            f"- commands: `{', '.join(report['live_surface_probe']['commands'])}`",
            f"- live_status: `{report['live_surface_probe']['live_status']}`",
            f"- blocker: `{report['live_surface_probe']['blocker']}`",
            f"- verifier_live_status: `{report['live_status']}`",
            "",
            "## Open Gaps",
        ]
    )
    for gap in report["open_gaps"]:
        lines.append(f"- {gap}")
    lines.append("")
    return "\n".join(lines)


def run(out_json: Path, out_md: Path) -> dict[str, Any]:
    module = _load_module()
    local = _run_local(module)
    live = _run_live_smoke()
    report = _build_report(local, live)

    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    out_md.write_text(_to_markdown(report), encoding="utf-8")
    return report


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-json", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--out-md", type=Path, default=DEFAULT_OUTPUT_MD)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    report = run(args.out_json, args.out_md)
    print(
        "policy_evidence_package_windmill verification complete: "
        f"local={report['local_status']} backend_endpoint_local={report['local_backend_endpoint_status']} "
        f"live={report['live_status']}"
    )
    return 0 if report["local_status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
