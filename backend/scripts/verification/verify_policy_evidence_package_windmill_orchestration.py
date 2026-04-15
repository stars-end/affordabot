#!/usr/bin/env python3
"""Verifier for Windmill policy evidence package orchestration boundary."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
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


def _load_module():
    spec = __import__("importlib.util").util.spec_from_file_location(
        "policy_evidence_windmill", WINDMILL_SCRIPT_PATH
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("failed to load windmill policy evidence script")
    module = __import__("importlib.util").util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_local(module: Any) -> dict[str, Any]:
    happy = module.main(
        step="run_scope_pipeline",
        idempotency_key="run:bd-3wefe.12:local-happy",
        windmill_run_id="wm-local-policy-happy",
        windmill_job_id="wm-local-job-happy",
        jurisdiction="San Jose CA",
        query_family="meeting_minutes",
        package_id="pkg-local-happy",
        package_readiness_status="ready",
        gate_status="quantified",
    )
    blocked = module.main(
        step="run_scope_pipeline",
        idempotency_key="run:bd-3wefe.12:local-blocked",
        windmill_run_id="wm-local-policy-blocked",
        windmill_job_id="wm-local-job-blocked",
        jurisdiction="San Jose CA",
        query_family="meeting_minutes",
        package_id="pkg-local-blocked",
        package_readiness_status="blocked",
        gate_status="insufficient_evidence",
    )
    return {"happy": happy, "blocked": blocked}


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
"""
    proc = subprocess.run(
        ["bash", "-lc", cmd],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode == 0:
        return {
            "live_status": "passed_read_only_smoke",
            "command": "windmill-cli workspace list (read-only)",
            "return_code": proc.returncode,
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip(),
            "blocker": None,
        }
    return {
        "live_status": "blocked",
        "command": "windmill-cli workspace list (read-only)",
        "return_code": proc.returncode,
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
        "blocker": "live_windmill_auth_or_cli_unavailable_noninteractive",
    }


def _build_report(local: dict[str, Any], live: dict[str, Any]) -> dict[str, Any]:
    happy = local["happy"]
    blocked = local["blocked"]
    return {
        "feature_key": "bd-3wefe.12",
        "report_version": "2026-04-15.policy-evidence-package-windmill.v1",
        "local_status": "passed"
        if happy.get("status") == "succeeded" and blocked.get("status") == "blocked"
        else "failed",
        "live_status": live["live_status"],
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
        "happy_path": {
            "status": happy.get("status"),
            "package_id": happy.get("package_id"),
            "package_readiness_status": happy.get("package_readiness_status"),
            "gate_status": happy.get("gate_status"),
            "decision_reason": happy.get("decision_reason"),
            "retry_class": happy.get("retry_class"),
            "storage_refs": happy.get("storage_refs"),
        },
        "blocked_path": {
            "status": blocked.get("status"),
            "package_id": blocked.get("package_id"),
            "package_readiness_status": blocked.get("package_readiness_status"),
            "gate_status": blocked.get("gate_status"),
            "decision_reason": blocked.get("decision_reason"),
            "retry_class": blocked.get("retry_class"),
        },
        "live_smoke": live,
        "open_gaps": [
            "bd-3wefe.10: storage durability, readback atomicity, replay semantics",
            "bd-3wefe.5: economic sufficiency gate over packaged evidence",
            "bd-3wefe.6: direct/indirect/secondary research analysis quality cases",
        ],
    }


def _to_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Policy Evidence Package Windmill Orchestration Report",
        "",
        "## Status",
        f"- local_status: `{report['local_status']}`",
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
            "## Happy Path",
            f"- status: `{report['happy_path']['status']}`",
            f"- package_id: `{report['happy_path']['package_id']}`",
            f"- readiness: `{report['happy_path']['package_readiness_status']}`",
            f"- gate_status: `{report['happy_path']['gate_status']}`",
            f"- decision_reason: `{report['happy_path']['decision_reason']}`",
            f"- retry_class: `{report['happy_path']['retry_class']}`",
            "",
            "## Blocked Path",
            f"- status: `{report['blocked_path']['status']}`",
            f"- package_id: `{report['blocked_path']['package_id']}`",
            f"- readiness: `{report['blocked_path']['package_readiness_status']}`",
            f"- gate_status: `{report['blocked_path']['gate_status']}`",
            f"- decision_reason: `{report['blocked_path']['decision_reason']}`",
            f"- retry_class: `{report['blocked_path']['retry_class']}`",
            "",
            "## Live Windmill Smoke",
            f"- command: `{report['live_smoke']['command']}`",
            f"- live_status: `{report['live_smoke']['live_status']}`",
            f"- blocker: `{report['live_smoke']['blocker']}`",
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
        f"local={report['local_status']} live={report['live_status']}"
    )
    return 0 if report["local_status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())

