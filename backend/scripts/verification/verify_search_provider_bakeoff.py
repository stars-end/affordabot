#!/usr/bin/env python3
"""Search provider bakeoff verifier for bd-9qjof.6."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "backend"))

from scripts.verification.verify_windmill_sanjose_live_gate import (
    DEFAULT_SEARX_ENDPOINTS,
    FEATURE_KEY,
    _run_search_provider_bakeoff,
)


DEFAULT_JSON_ARTIFACT = (
    REPO_ROOT
    / "docs"
    / "poc"
    / "windmill-domain-boundary-integration"
    / "artifacts"
    / "search_provider_bakeoff_report.json"
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run search provider bakeoff probes.")
    parser.add_argument(
        "--query",
        default="San Jose CA city council meeting minutes housing",
    )
    parser.add_argument(
        "--searx-endpoint",
        action="append",
        default=[],
    )
    parser.add_argument("--out-json", type=Path, default=DEFAULT_JSON_ARTIFACT)
    args = parser.parse_args()

    searx_endpoints = args.searx_endpoint or DEFAULT_SEARX_ENDPOINTS
    probes, _ = _run_search_provider_bakeoff(query=args.query, searx_endpoints=searx_endpoints)
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "feature_key": FEATURE_KEY,
        "query": args.query,
        "searx_endpoints": searx_endpoints,
        "providers": probes,
    }
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(f"Wrote search provider bakeoff report: {args.out_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
