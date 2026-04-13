#!/usr/bin/env python3
"""Live Windmill San Jose validation harness for bd-9qjof.6.

This harness validates Windmill CLI access, deployment surface, and optional
manual flow execution for:
f/affordabot/pipeline_daily_refresh_domain_boundary__flow

It intentionally distinguishes:
- stub_orchestration_pass: orchestration flow passes but still uses stub command path
- full_product_pass: orchestration pass plus storage/runtime evidence gates
"""

from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.util import module_from_spec, spec_from_file_location
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_JSON_ARTIFACT = (
    REPO_ROOT
    / "docs"
    / "poc"
    / "windmill-domain-boundary-integration"
    / "artifacts"
    / "sanjose_live_gate_report.json"
)
DEFAULT_MD_ARTIFACT = (
    REPO_ROOT
    / "docs"
    / "poc"
    / "windmill-domain-boundary-integration"
    / "artifacts"
    / "sanjose_live_gate_report.md"
)
DEFAULT_FLOW_PATH = "f/affordabot/pipeline_daily_refresh_domain_boundary__flow"
DEFAULT_SCRIPT_PATH = "f/affordabot/pipeline_daily_refresh_domain_boundary"
DEFAULT_WORKSPACE = "affordabot"
FEATURE_KEY = "bd-9qjof.6"
HARNESS_VERSION = "2026-04-13.worker-b.v2"
STUB_SUMMARY_MARKER = "Path B orchestration skeleton. Product writes belong to affordabot commands."
EXPECTED_STEP_SEQUENCE = [
    "search_materialize",
    "freshness_gate",
    "read_fetch",
    "index",
    "analyze",
    "summarize_run",
]
WINDMILL_DOMAIN_SCRIPT_PATH = (
    REPO_ROOT / "ops" / "windmill" / "f" / "affordabot" / "pipeline_daily_refresh_domain_boundary.py"
)


class HarnessError(RuntimeError):
    def __init__(self, category: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.category = category
        self.details = details or {}


@dataclass
class HarnessContext:
    windmill_api_token: str
    windmill_dev_login_url: str
    windmill_base_url: str
    windmill_workspace: str
    config_dir: str


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _run(cmd: list[str], *, check: bool = True, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        check=check,
        capture_output=True,
        text=True,
        input=input_text,
    )


def _json_or_raise(stdout: str, stage: str) -> Any:
    try:
        return json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise HarnessError(
            "windmill_cli",
            f"{stage} returned non-JSON output",
            {"stage": stage, "stdout_head": stdout[:300]},
        ) from exc


def _get_cached_secret(secret_ref: str) -> str:
    cmd = [
        "bash",
        "-lc",
        (
            "set -euo pipefail; "
            "source \"$HOME/agent-skills/scripts/lib/dx-auth.sh\"; "
            f'DX_AUTH_CACHE_ONLY=1 dx_auth_read_secret_cached "{secret_ref}"'
        ),
    ]
    try:
        result = _run(cmd)
    except subprocess.CalledProcessError as exc:
        raise HarnessError(
            "infra/auth",
            f"cached secret unavailable: {secret_ref}",
            {"stderr": exc.stderr[-400:] if exc.stderr else ""},
        ) from exc
    value = result.stdout.strip()
    if not value:
        raise HarnessError("infra/auth", f"empty cached secret: {secret_ref}")
    return value


def _build_context(workspace: str) -> HarnessContext:
    token = _get_cached_secret("op://dev/Agent-Secrets-Production/WINDMILL_API_TOKEN")
    login_url = _get_cached_secret("op://dev/Agent-Secrets-Production/WINDMILL_DEV_LOGIN_URL")
    base_url = login_url.removesuffix("/user/login")
    if base_url == login_url:
        base_url = login_url.rstrip("/")
    if not base_url.startswith("http"):
        raise HarnessError("infra/auth", "invalid WINDMILL_DEV_LOGIN_URL shape", {"login_url": login_url})
    config_dir = tempfile.mkdtemp(prefix="wmill-live-gate-")
    return HarnessContext(
        windmill_api_token=token,
        windmill_dev_login_url=login_url,
        windmill_base_url=base_url,
        windmill_workspace=workspace,
        config_dir=config_dir,
    )


def _wmill(ctx: HarnessContext, *args: str, expect_json: bool = False) -> str | Any:
    cmd = ["npx", "--yes", "windmill-cli", *args, "--workspace", ctx.windmill_workspace, "--config-dir", ctx.config_dir]
    try:
        result = _run(cmd)
    except subprocess.CalledProcessError as exc:
        raise HarnessError(
            "windmill_cli",
            f"windmill-cli command failed: {' '.join(args)}",
            {"stderr": exc.stderr[-600:] if exc.stderr else "", "stdout": exc.stdout[-300:] if exc.stdout else ""},
        ) from exc
    return _json_or_raise(result.stdout, " ".join(args)) if expect_json else result.stdout


def _setup_workspace_profile(ctx: HarnessContext) -> None:
    cmd = [
        "npx",
        "--yes",
        "windmill-cli",
        "workspace",
        "add",
        ctx.windmill_workspace,
        ctx.windmill_workspace,
        ctx.windmill_base_url,
        "--token",
        ctx.windmill_api_token,
        "--config-dir",
        ctx.config_dir,
    ]
    try:
        _run(cmd)
    except subprocess.CalledProcessError as exc:
        raise HarnessError(
            "infra/auth",
            "failed to create temporary Windmill workspace profile",
            {"stderr": exc.stderr[-500:] if exc.stderr else ""},
        ) from exc


def _find_job_for_idempotency(jobs: list[dict[str, Any]], idempotency_key: str) -> dict[str, Any] | None:
    for job in jobs:
        args = job.get("args") or {}
        if args.get("idempotency_key") == idempotency_key:
            return job
    return None


def _find_recent_flow_job(jobs: list[dict[str, Any]], *, flow_path: str, run_started_at: datetime) -> dict[str, Any] | None:
    candidates: list[tuple[datetime, dict[str, Any]]] = []
    for job in jobs:
        if job.get("script_path") != flow_path:
            continue
        if job.get("job_kind") != "flow":
            continue
        created_at = _parse_dt(job.get("created_at"))
        if not created_at:
            continue
        if created_at < run_started_at:
            continue
        candidates.append((created_at, job))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def _summarize_flow_status(flow_status: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(flow_status, dict):
        return {}
    modules = []
    for module in flow_status.get("modules") or []:
        if not isinstance(module, dict):
            continue
        modules.append(
            {
                "id": module.get("id"),
                "type": module.get("type"),
                "skipped": module.get("skipped"),
                "branch_chosen": module.get("branch_chosen"),
            }
        )
    return {
        "step": flow_status.get("step"),
        "modules": modules,
        "failure_module": flow_status.get("failure_module"),
    }


def _summarize_job(job: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": job.get("id"),
        "script_path": job.get("script_path"),
        "job_kind": job.get("job_kind"),
        "created_at": job.get("created_at"),
        "completed_at": job.get("completed_at"),
        "duration_ms": job.get("duration_ms"),
        "canceled": job.get("canceled"),
        "deleted": job.get("deleted"),
        "flow_status": _summarize_flow_status(job.get("flow_status")),
    }


def _extract_step_sequence(result_payload: dict[str, Any]) -> list[str]:
    scope_results = result_payload.get("scope_results") or []
    if not scope_results:
        return []
    steps = scope_results[0].get("steps") or {}
    if not isinstance(steps, dict):
        return []
    present = set(steps.keys())
    ordered = [step for step in EXPECTED_STEP_SEQUENCE if step in present]
    extras = sorted(step for step in present if step not in EXPECTED_STEP_SEQUENCE)
    return ordered + extras


def _all_step_envelopes_have_contract(result_payload: dict[str, Any]) -> bool:
    scope_results = result_payload.get("scope_results") or []
    if not scope_results:
        return False
    for scope_result in scope_results:
        steps = scope_result.get("steps") or {}
        for step_payload in steps.values():
            env = step_payload.get("envelope") or {}
            if not env.get("contract_version"):
                return False
            if env.get("orchestrator") != "windmill":
                return False
            if not env.get("windmill_workspace"):
                return False
            if not env.get("windmill_flow_path"):
                return False
    return True


def _build_storage_evidence_gates(result_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    scope_results = result_payload.get("scope_results") or []
    summarize_summary = ""
    if scope_results:
        summarize_summary = (
            scope_results[0]
            .get("steps", {})
            .get("summarize_run", {})
            .get("summary", "")
        )

    stub_mode = STUB_SUMMARY_MARKER in summarize_summary

    pending_note = (
        "not proven in Windmill stub run; requires Worker A product bridge + live storage adapters"
    )
    return {
        "postgres_rows_written": {"status": "pending", "note": pending_note},
        "pgvector_index_probe": {"status": "pending", "note": pending_note},
        "minio_object_refs": {"status": "pending", "note": pending_note},
        "reader_output_ref": {"status": "pending", "note": pending_note},
        "analysis_provenance_chain": {"status": "pending", "note": pending_note},
        "idempotent_rerun": {"status": "pending", "note": pending_note},
        "stale_drill_stale_but_usable": {"status": "pending", "note": pending_note},
        "stale_drill_stale_blocked": {"status": "pending", "note": pending_note},
        "failure_handler_drill": {"status": "pending", "note": pending_note},
        "bridge_mode": {"status": "stub" if stub_mode else "unknown", "note": summarize_summary},
    }


def _load_windmill_domain_script_module() -> Any:
    spec = spec_from_file_location("windmill_domain_boundary", WINDMILL_DOMAIN_SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise HarnessError(
            "product_bridge",
            "unable to load windmill domain script for backend endpoint probe",
            {"script_path": str(WINDMILL_DOMAIN_SCRIPT_PATH)},
        )
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_backend_endpoint_local_probe(backend_endpoint_auth_token: str) -> dict[str, Any]:
    module = _load_windmill_domain_script_module()
    expected_auth = f"Bearer {backend_endpoint_auth_token}"

    class _ProbeHandler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            auth_header = self.headers.get("Authorization", "")
            content_length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(content_length)
            try:
                payload = json.loads(body.decode("utf-8") if body else "{}")
            except json.JSONDecodeError:
                payload = {}
            if auth_header != expected_auth:
                self.send_response(401)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "failed", "error": "unauthorized"}).encode("utf-8"))
                return
            response = {
                "status": "succeeded",
                "decision_reason": "scope_completed",
                "probe": "backend_endpoint_local_mock",
                "jurisdiction": payload.get("jurisdiction"),
                "source_family": payload.get("source_family"),
                "steps": {
                    "search_materialize": {"status": "succeeded"},
                    "freshness_gate": {"status": "succeeded", "decision_reason": "fresh"},
                    "read_fetch": {"status": "succeeded"},
                    "index": {"status": "succeeded"},
                    "analyze": {"status": "succeeded"},
                    "summarize_run": {"status": "succeeded"},
                },
                "storage_mode": "in_memory_domain_ports",
                "missing_runtime_adapters": [
                    "postgres_pipeline_state_store_adapter",
                    "minio_artifact_store_adapter",
                    "pgvector_chunk_store_adapter",
                ],
            }
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(response).encode("utf-8"))

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), _ProbeHandler)
    endpoint_url = f"http://127.0.0.1:{server.server_port}/domain-command"
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    try:
        result = module.main(
            step="run_scope_pipeline",
            idempotency_key=f"{FEATURE_KEY}-backend-probe",
            scope_item={"jurisdiction": "San Jose CA", "source_family": "meeting_minutes"},
            scope_index=0,
            stale_status="fresh",
            search_query="San Jose CA city council meeting minutes housing",
            analysis_question="Summarize housing-related signals.",
            command_client="backend_endpoint",
            backend_endpoint_url=endpoint_url,
            backend_endpoint_auth_token=backend_endpoint_auth_token,
            backend_endpoint_timeout_seconds=10,
        )
        expected_steps = {"search_materialize", "freshness_gate", "read_fetch", "index", "analyze", "summarize_run"}
        if result.get("status") != "succeeded":
            return {"status": "failed", "note": "local mock probe did not complete", "result_status": result.get("status")}
        observed_steps = set((result.get("steps") or {}).keys())
        if observed_steps != expected_steps:
            return {
                "status": "failed",
                "note": "local mock probe missing expected command sequence",
                "observed_steps": sorted(observed_steps),
            }
        return {"status": "passed", "note": "local mock backend endpoint probe passed"}
    except Exception as exc:  # noqa: BLE001
        return {"status": "failed", "note": "local mock backend endpoint probe failed", "detail": str(exc)}
    finally:
        server.shutdown()
        server_thread.join(timeout=2)
        server.server_close()


def _build_backend_endpoint_readiness(
    *,
    backend_endpoint_url: str | None,
    backend_endpoint_auth_token: str | None,
) -> dict[str, Any]:
    endpoint_url = (backend_endpoint_url or "").strip()
    auth_token = (backend_endpoint_auth_token or "").strip()
    missing: list[str] = []
    if not endpoint_url:
        missing.append("backend_endpoint_url")
    if not auth_token:
        missing.append("backend_endpoint_auth_token")

    if missing:
        return {
            "status": "not_configured",
            "note": "backend endpoint mode is opt-in and currently not configured",
            "missing_inputs": missing,
            "local_mock_probe": {"status": "skipped", "note": "missing required backend endpoint inputs"},
        }

    local_probe = _run_backend_endpoint_local_probe(auth_token)
    if local_probe.get("status") == "passed":
        return {
            "status": "ready_for_opt_in",
            "note": "backend endpoint config is present and local mock probe passed",
            "missing_inputs": [],
            "local_mock_probe": local_probe,
        }
    return {
        "status": "probe_failed",
        "note": "backend endpoint config is present but local mock probe failed",
        "missing_inputs": [],
        "local_mock_probe": local_probe,
    }


def _derive_classification(
    *,
    result_payload: dict[str, Any] | None,
    storage_gates: dict[str, dict[str, Any]],
    backend_endpoint_readiness: dict[str, Any],
    blockers: list[dict[str, Any]],
) -> tuple[str, str]:
    hard_blockers = [b for b in blockers if b.get("blocking", True)]
    if hard_blockers:
        return "blocked", "blocked"
    if not result_payload:
        if backend_endpoint_readiness.get("status") == "ready_for_opt_in":
            return "backend_bridge_surface_ready", "partial"
        return "read_only_surface_pass", "partial"

    run_status = result_payload.get("status")
    if run_status != "succeeded":
        return "failed_run", "partial"

    scope_results = result_payload.get("scope_results") or []
    if not scope_results:
        return "failed_run", "partial"

    pending_storage_gates = [
        gate_name
        for gate_name, gate in storage_gates.items()
        if gate_name != "bridge_mode" and gate.get("status") == "pending"
    ]
    if not pending_storage_gates and storage_gates.get("bridge_mode", {}).get("status") not in {"stub", "unknown"}:
        return "full_product_pass", "ready"

    summary = (
        scope_results[0]
        .get("steps", {})
        .get("summarize_run", {})
        .get("summary", "")
    )
    if backend_endpoint_readiness.get("status") == "ready_for_opt_in":
        return "backend_bridge_surface_ready", "partial"
    if STUB_SUMMARY_MARKER in summary:
        return "stub_orchestration_pass", "partial"
    return "failed_run", "partial"


def _render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Windmill San Jose Live Validation Gate",
        "",
        f"- generated_at: `{report['generated_at']}`",
        f"- feature_key: `{report['feature_key']}`",
        f"- harness_version: `{report['harness_version']}`",
        f"- run_mode: `{report['run_mode']}`",
        f"- classification: `{report['classification']}`",
        f"- full_run_readiness: `{report['full_run_readiness']}`",
        "",
        "## Deployment Surface",
        f"- flow_deployed: `{report['deployment_surface']['flow_deployed']}`",
        f"- script_deployed: `{report['deployment_surface']['script_deployed']}`",
        f"- flow_unscheduled: `{report['deployment_surface']['flow_unscheduled']}`",
        "",
        "## Manual Run",
    ]
    manual_run = report.get("manual_run") or {}
    if manual_run.get("attempted"):
        lines.extend(
            [
                f"- attempted: `true`",
                f"- idempotency_key: `{manual_run.get('idempotency_key', '')}`",
                f"- windmill_job_id: `{manual_run.get('windmill_job_id', 'not_found')}`",
                f"- final_status: `{manual_run.get('final_status', 'unknown')}`",
                f"- scope_totals: `{manual_run.get('scope_totals', {})}`",
                f"- step_sequence: `{manual_run.get('step_sequence', [])}`",
                f"- step_sequence_matches_expected: `{manual_run.get('step_sequence_matches_expected', False)}`",
                f"- contract_metadata_present: `{manual_run.get('contract_metadata_present', False)}`",
            ]
        )
    else:
        lines.append("- attempted: `false`")

    lines.extend(["", "## Storage Evidence Gates"])
    for gate_name, gate in report["storage_evidence_gates"].items():
        lines.append(f"- {gate_name}: `{gate['status']}` ({gate['note']})")

    backend_readiness = report.get("backend_endpoint_readiness") or {}
    lines.extend(
        [
            "",
            "## Backend Endpoint Readiness",
            f"- status: `{backend_readiness.get('status', 'unknown')}`",
            f"- note: {backend_readiness.get('note', '')}",
            f"- missing_inputs: `{backend_readiness.get('missing_inputs', [])}`",
            f"- local_mock_probe: `{backend_readiness.get('local_mock_probe', {})}`",
        ]
    )

    lines.extend(["", "## Blockers"])
    if report["blockers"]:
        for blocker in report["blockers"]:
            lines.append(f"- `{blocker['category']}`: {blocker['message']}")
    else:
        lines.append("- none")

    return "\n".join(lines) + "\n"


def run_harness(
    *,
    run_mode: str,
    workspace: str,
    flow_path: str,
    script_path: str,
    jurisdiction: str,
    source_family: str,
    search_query: str,
    analysis_question: str,
    stale_status: str,
    scope_parallelism: int,
    idempotency_key: str | None,
    backend_endpoint_url: str | None,
    backend_endpoint_auth_token: str | None,
) -> dict[str, Any]:
    blockers: list[dict[str, Any]] = []
    result_payload: dict[str, Any] | None = None

    context = _build_context(workspace)
    _setup_workspace_profile(context)

    try:
        workspace_profiles = _wmill(context, "workspace", "list")
        flow = _wmill(context, "flow", "get", flow_path, "--json", expect_json=True)
        script = _wmill(context, "script", "get", script_path, "--json", expect_json=True)
        schedules = _wmill(context, "schedule", "list", "--json", expect_json=True)
        jobs_before = _wmill(context, "job", "list", "--script-path", flow_path, "--limit", "20", "--json", expect_json=True)
    except HarnessError as err:
        blockers.append({"category": err.category, "message": str(err), "details": err.details, "blocking": True})
        workspace_profiles = ""
        flow = {}
        script = {}
        schedules = []
        jobs_before = []

    flow_unscheduled = True
    if isinstance(schedules, list):
        schedule_paths = {item.get("path", "") for item in schedules}
        flow_unscheduled = flow_path not in schedule_paths
    if not flow:
        blockers.append(
            {
                "category": "deployment",
                "message": "target flow is not deployed in workspace",
                "details": {"flow_path": flow_path},
                "blocking": True,
            }
        )
    if not script:
        blockers.append(
            {
                "category": "deployment",
                "message": "target script is not deployed in workspace",
                "details": {"script_path": script_path},
                "blocking": True,
            }
        )
    if not flow_unscheduled:
        blockers.append(
            {
                "category": "deployment",
                "message": "target flow has a schedule and is not safe as manual-only POC",
                "details": {"flow_path": flow_path},
                "blocking": True,
            }
        )

    manual_run: dict[str, Any] = {"attempted": False}
    if not blockers and run_mode == "stub-run":
        manual_run["attempted"] = True
        idempotency = idempotency_key or f"{FEATURE_KEY}-live-gate-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}"
        manual_run["idempotency_key"] = idempotency
        payload = {
            "idempotency_key": idempotency,
            "mode": "manual",
            "jurisdictions": [jurisdiction],
            "source_families": [source_family],
            "scope_parallelism": scope_parallelism,
            "search_query": search_query,
            "analysis_question": analysis_question,
            "stale_status": stale_status,
        }
        try:
            run_started_at = datetime.now(UTC)
            result_payload = _wmill(
                context,
                "flow",
                "run",
                flow_path,
                "-s",
                "-d",
                json.dumps(payload),
                expect_json=True,
            )
            jobs_after = _wmill(
                context,
                "job",
                "list",
                "--all",
                "--limit",
                "200",
                "--json",
                expect_json=True,
            )
            matched_job = _find_job_for_idempotency(jobs_after, idempotency) or _find_job_for_idempotency(jobs_before, idempotency)
            if not matched_job:
                fallback_jobs = _wmill(
                    context,
                    "job",
                    "list",
                    "--script-path",
                    script_path,
                    "--all",
                    "--limit",
                    "80",
                    "--json",
                    expect_json=True,
                )
                matched_job = _find_job_for_idempotency(fallback_jobs, idempotency)
            if not matched_job:
                matched_job = _find_recent_flow_job(jobs_after, flow_path=flow_path, run_started_at=run_started_at)
            if matched_job:
                job_id = matched_job.get("id", "")
                manual_run["windmill_job_id"] = job_id
                job_get = _wmill(context, "job", "get", job_id, "--json", expect_json=True)
                manual_run["job_get"] = _summarize_job(job_get)
                manual_run["job_logs_excerpt"] = str(_wmill(context, "job", "logs", job_id))[-1200:]
            else:
                manual_run["windmill_job_id"] = "not_found"

            step_sequence = _extract_step_sequence(result_payload)
            manual_run["final_status"] = result_payload.get("status")
            manual_run["scope_totals"] = {
                "scope_total": result_payload.get("scope_total"),
                "scope_succeeded": result_payload.get("scope_succeeded"),
                "scope_failed": result_payload.get("scope_failed"),
                "scope_blocked": result_payload.get("scope_blocked"),
            }
            manual_run["step_sequence"] = step_sequence
            manual_run["step_sequence_matches_expected"] = step_sequence == EXPECTED_STEP_SEQUENCE
            manual_run["contract_metadata_present"] = _all_step_envelopes_have_contract(result_payload)
        except HarnessError as err:
            blockers.append({"category": err.category, "message": str(err), "details": err.details, "blocking": True})
    elif run_mode == "read-only":
        manual_run["attempted"] = False

    storage_gates = _build_storage_evidence_gates(result_payload or {})
    backend_endpoint_readiness = _build_backend_endpoint_readiness(
        backend_endpoint_url=backend_endpoint_url,
        backend_endpoint_auth_token=backend_endpoint_auth_token,
    )
    if result_payload and storage_gates.get("bridge_mode", {}).get("status") == "stub":
        blockers.append(
            {
                "category": "product_bridge",
                "message": "flow run is still stub-backed; full product validation not yet possible",
                "details": {"bridge_mode": "stub"},
                "blocking": False,
            }
        )

    if result_payload and run_mode == "stub-run":
        missing_storage = [name for name, gate in storage_gates.items() if gate["status"] == "pending" and name != "bridge_mode"]
        if missing_storage:
            blockers.append(
                {
                    "category": "storage/runtime",
                    "message": "storage/runtime evidence gates are pending",
                    "details": {"pending_gates": missing_storage},
                    "blocking": False,
                }
            )

    if backend_endpoint_readiness.get("status") == "not_configured":
        blockers.append(
            {
                "category": "product_bridge",
                "message": "backend endpoint client is not configured for live Windmill validation",
                "details": {"missing_inputs": backend_endpoint_readiness.get("missing_inputs", [])},
                "blocking": False,
            }
        )
    elif backend_endpoint_readiness.get("status") == "probe_failed":
        blockers.append(
            {
                "category": "product_bridge",
                "message": "backend endpoint local mock probe failed",
                "details": backend_endpoint_readiness.get("local_mock_probe", {}),
                "blocking": False,
            }
        )

    classification, readiness = _derive_classification(
        result_payload=result_payload,
        storage_gates=storage_gates,
        backend_endpoint_readiness=backend_endpoint_readiness,
        blockers=blockers,
    )
    report: dict[str, Any] = {
        "generated_at": _now_iso(),
        "feature_key": FEATURE_KEY,
        "harness_version": HARNESS_VERSION,
        "run_mode": run_mode,
        "classification": classification,
        "full_run_readiness": readiness,
        "canonical_variables": {
            "WINDMILL_API_TOKEN": "op://dev/Agent-Secrets-Production/WINDMILL_API_TOKEN",
            "WINDMILL_DEV_LOGIN_URL": "op://dev/Agent-Secrets-Production/WINDMILL_DEV_LOGIN_URL",
            "WINDMILL_BASE_URL": "derived as WINDMILL_DEV_LOGIN_URL without /user/login",
            "WINDMILL_WORKSPACE": workspace,
            "TMP_WMILL_CONFIG": "auto-created temporary profile directory",
            "BACKEND_ENDPOINT_URL": "optional flow input; full backend command endpoint URL",
            "BACKEND_ENDPOINT_AUTH_TOKEN": "optional flow input; endpoint bearer token",
        },
        "deployment_surface": {
            "flow_path": flow_path,
            "script_path": script_path,
            "flow_deployed": bool(flow),
            "script_deployed": bool(script),
            "flow_unscheduled": flow_unscheduled,
        },
        "surface_checks": {
            "workspace_profile_listed": bool(workspace_profiles),
            "schedule_count": len(schedules) if isinstance(schedules, list) else 0,
            "jobs_checked_count": len(jobs_before) if isinstance(jobs_before, list) else 0,
        },
        "manual_run": manual_run,
        "result_payload": result_payload,
        "storage_evidence_gates": storage_gates,
        "backend_endpoint_readiness": backend_endpoint_readiness,
        "blockers": blockers,
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify Windmill San Jose live gate.")
    parser.add_argument("--run-mode", choices=["read-only", "stub-run"], default="stub-run")
    parser.add_argument("--workspace", default=DEFAULT_WORKSPACE)
    parser.add_argument("--flow-path", default=DEFAULT_FLOW_PATH)
    parser.add_argument("--script-path", default=DEFAULT_SCRIPT_PATH)
    parser.add_argument("--jurisdiction", default="San Jose CA")
    parser.add_argument("--source-family", default="meeting_minutes")
    parser.add_argument("--search-query", default="San Jose CA city council meeting minutes housing")
    parser.add_argument(
        "--analysis-question",
        default="Summarize housing-related signals from recent San Jose meeting minutes.",
    )
    parser.add_argument("--stale-status", default="fresh")
    parser.add_argument("--scope-parallelism", type=int, default=1)
    parser.add_argument("--idempotency-key", default=None)
    parser.add_argument("--backend-endpoint-url", default=None)
    parser.add_argument("--backend-endpoint-auth-token", default=None)
    parser.add_argument("--out-json", type=Path, default=DEFAULT_JSON_ARTIFACT)
    parser.add_argument("--out-md", type=Path, default=DEFAULT_MD_ARTIFACT)
    args = parser.parse_args()

    report = run_harness(
        run_mode=args.run_mode,
        workspace=args.workspace,
        flow_path=args.flow_path,
        script_path=args.script_path,
        jurisdiction=args.jurisdiction,
        source_family=args.source_family,
        search_query=args.search_query,
        analysis_question=args.analysis_question,
        stale_status=args.stale_status,
        scope_parallelism=args.scope_parallelism,
        idempotency_key=args.idempotency_key,
        backend_endpoint_url=args.backend_endpoint_url,
        backend_endpoint_auth_token=args.backend_endpoint_auth_token,
    )

    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_md.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    args.out_md.write_text(_render_markdown(report), encoding="utf-8")

    print(f"Wrote JSON report: {args.out_json}")
    print(f"Wrote Markdown report: {args.out_md}")
    print(f"classification={report['classification']}")
    print(f"full_run_readiness={report['full_run_readiness']}")
    return 0 if report["classification"] in {"read_only_surface_pass", "stub_orchestration_pass", "backend_bridge_surface_ready", "full_product_pass"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
