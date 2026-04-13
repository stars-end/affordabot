#!/usr/bin/env python3
"""Local integration verifier for Windmill-shaped domain boundary orchestration.

This script does not perform network or external storage calls. It runs a deterministic
in-memory chain:
Windmill script shape -> coarse domain commands -> in-memory state -> evidence artifact.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _load_windmill_script() -> Any:
    repo_root = Path(__file__).resolve().parents[3]
    script_path = (
        repo_root
        / "ops"
        / "windmill"
        / "f"
        / "affordabot"
        / "pipeline_daily_refresh_domain_boundary.py"
    )
    spec = __import__("importlib.util").util.spec_from_file_location(
        "pipeline_daily_refresh_domain_boundary", script_path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("failed to load windmill script module")
    module = __import__("importlib.util").util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _default_json_path(repo_root: Path) -> Path:
    return (
        repo_root
        / "docs"
        / "poc"
        / "windmill-domain-boundary-integration"
        / "artifacts"
        / "local_integration_report.json"
    )


def _default_md_path(repo_root: Path) -> Path:
    return (
        repo_root
        / "docs"
        / "poc"
        / "windmill-domain-boundary-integration"
        / "artifacts"
        / "local_integration_report.md"
    )


def run_verification() -> dict[str, Any]:
    module = _load_windmill_script()
    return module.main(
        step="run_local_integration_harness",
        idempotency_key="run:bd-9qjof.6:san-jose",
        scope_item={"jurisdiction": "San Jose CA", "source_family": "meeting_minutes"},
        search_query="San Jose city council meeting minutes housing",
        analysis_question="Summarize housing and planning actions from the minutes.",
        windmill_run_id="wm-local-bd9qjof6",
        windmill_job_id="wm-local-job-bd9qjof6",
    )


def _to_markdown(report: dict[str, Any]) -> str:
    evidence = report["evidence"]
    scenarios = report["scenarios"]
    happy = scenarios["happy_first"]
    rerun = scenarios["happy_rerun"]
    blocked = scenarios["stale_blocked"]
    lines = [
        "# Windmill Domain Boundary Local Integration Evidence",
        "",
        "## Run Verdict",
        f"- status: `{report['status']}`",
        "",
        "## Evidence Checks",
        f"- happy_status: `{evidence['happy_status']}`",
        f"- rerun_status: `{evidence['rerun_status']}`",
        f"- stale_blocked_status: `{evidence['stale_blocked_status']}`",
        f"- rerun_index_idempotent_reuse: `{evidence['rerun_index_idempotent_reuse']}`",
        f"- rerun_chunk_count_stable: `{evidence['rerun_chunk_count_stable']}`",
        f"- stale_blocked_short_circuit: `{evidence['stale_blocked_short_circuit']}`",
        f"- windmill_refs_propagated: `{evidence['windmill_refs_propagated']}`",
        "",
        "## Scenario Summaries",
        f"- happy_first steps: `{', '.join(happy['steps'].keys())}`",
        f"- happy_rerun steps: `{', '.join(rerun['steps'].keys())}`",
        f"- stale_blocked steps: `{', '.join(blocked['steps'].keys())}`",
        "",
        "## Notes",
        "- Windmill path uses coarse commands only.",
        "- No external network/database/object/vector service calls were made.",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-json", type=Path, default=None)
    parser.add_argument("--out-md", type=Path, default=None)
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[3]
    out_json = args.out_json or _default_json_path(repo_root)
    out_md = args.out_md or _default_md_path(repo_root)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)

    report = run_verification()
    out_json.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    out_md.write_text(_to_markdown(report), encoding="utf-8")

    print(f"Wrote JSON report: {out_json}")
    print(f"Wrote Markdown report: {out_md}")
    print(f"Run status: {report['status']}")
    return 0 if report["status"] == "succeeded" else 1


if __name__ == "__main__":
    raise SystemExit(main())
