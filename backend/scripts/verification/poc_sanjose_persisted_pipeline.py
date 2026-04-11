#!/usr/bin/env python3
"""Run the bd-jxclm.12 San Jose persisted pipeline vertical POC."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_ROOT.parent
sys.path.append(str(BACKEND_ROOT))

from services.persisted_pipeline_poc import PersistedPipelineStore  # noqa: E402
from services.persisted_pipeline_poc import render_markdown_report  # noqa: E402
from services.persisted_pipeline_poc import run_three_pass_verification  # noqa: E402


def parse_args() -> argparse.Namespace:
    default_out = REPO_ROOT / "backend/artifacts/poc_sanjose_persisted_pipeline"
    parser = argparse.ArgumentParser(
        description=(
            "Capture-only San Jose meeting-minutes persisted pipeline POC. "
            "Creates pipeline_runs, pipeline_steps, search_result_snapshots, "
            "and content_artifacts in a local SQLite proof DB."
        )
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=default_out,
        help="Directory for the SQLite proof DB, content files, and report.",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=None,
        help="SQLite proof DB path. Defaults to OUT_DIR/poc.sqlite3.",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=None,
        help="Markdown evidence report path. Defaults to OUT_DIR/report.md.",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Remove prior generated POC DB/artifacts under OUT_DIR before running.",
    )
    parser.add_argument(
        "--no-network",
        action="store_true",
        help="Disable live HTTP fetch and use the built-in San Jose event fixture.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the machine-readable verification summary.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    out_dir = args.out_dir.resolve()
    db_path = (args.db or (out_dir / "poc.sqlite3")).resolve()
    report_path = (args.report or (out_dir / "report.md")).resolve()
    artifact_dir = out_dir / "object_store"

    if args.reset:
        store = PersistedPipelineStore.fresh(db_path=db_path, artifact_dir=artifact_dir)
    else:
        store = PersistedPipelineStore(db_path=db_path, artifact_dir=artifact_dir)

    try:
        summary = run_three_pass_verification(
            store=store,
            network_enabled=not args.no_network,
        )
        report = render_markdown_report(
            summary=summary,
            store=store,
            db_path=db_path,
            report_path=report_path,
        )
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(report)
        payload = {
            **summary,
            "db_path": str(db_path),
            "artifact_dir": str(artifact_dir),
            "report_path": str(report_path),
            "verdict": "PASS" if all(summary["checks"].values()) else "FAIL",
        }
        if args.json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print(f"VERDICT: {payload['verdict']}")
            print(f"DB: {db_path}")
            print(f"ARTIFACT_DIR: {artifact_dir}")
            print(f"REPORT: {report_path}")
            print("ROW_COUNTS:", json.dumps(summary["row_counts"], sort_keys=True))
            for name, passed in summary["checks"].items():
                print(f"CHECK {name}: {'PASS' if passed else 'FAIL'}")
        return 0 if payload["verdict"] == "PASS" else 1
    finally:
        store.close()


if __name__ == "__main__":
    raise SystemExit(main())
