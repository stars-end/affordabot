#!/usr/bin/env python3
"""Verify scraped-lane data-moat package fields for D1/D2/D4/D5/D8."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("expected JSON object")
    return payload


def _get_run_context(payload: dict[str, Any]) -> dict[str, Any]:
    if isinstance(payload.get("run_context"), dict):
        return dict(payload["run_context"])
    package_payload = payload.get("package_payload")
    if isinstance(package_payload, dict) and isinstance(package_payload.get("run_context"), dict):
        return dict(package_payload["run_context"])
    return {}


def _gate(status: bool, details: str) -> dict[str, str]:
    return {"status": "pass" if status else "fail", "details": details}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="PolicyEvidencePackage payload JSON")
    args = parser.parse_args()

    payload = _load_json(args.input)
    run_context = _get_run_context(payload)
    source_quality = run_context.get("source_quality_metrics") if isinstance(run_context, dict) else None
    lineage = run_context.get("policy_lineage") if isinstance(run_context, dict) else None
    reconciliation = run_context.get("source_reconciliation") if isinstance(run_context, dict) else None
    extraction = run_context.get("primary_parameter_extraction") if isinstance(run_context, dict) else None

    d1 = _gate(
        isinstance(lineage, dict)
        and isinstance(lineage.get("lineage_presence"), dict)
        and isinstance(lineage.get("negative_evidence"), list),
        "policy_lineage includes lineage_presence and negative_evidence",
    )
    d2 = _gate(
        isinstance(source_quality, dict)
        and "portal_skip_count" in source_quality
        and "official_reader_error_count" in source_quality
        and "fallback_materialization_count" in source_quality,
        "source_quality_metrics includes portal/fallback/runtime counters",
    )
    d4 = _gate(
        isinstance(extraction, dict)
        and isinstance(extraction.get("facts"), list)
        and all(
            isinstance(item, dict)
            and ("source_url" in item)
            and ("source_excerpt" in item)
            and ("unit" in item)
            and ("denominator" in item)
            for item in extraction.get("facts", [])
        ),
        "primary extraction facts include citation+unit+denominator keys",
    )
    d5 = _gate(
        isinstance(reconciliation, dict)
        and isinstance(reconciliation.get("records"), list)
        and isinstance(reconciliation.get("secondary_override_blocked"), bool),
        "source_reconciliation captures records and override policy",
    )
    d8 = _gate(
        isinstance(source_quality, dict)
        and isinstance(source_quality.get("source_shape_drift"), dict)
        and "drift_detected" in source_quality.get("source_shape_drift", {}),
        "source_shape_drift emitted for source-shape robustness",
    )

    gates = {"D1": d1, "D2": d2, "D4": d4, "D5": d5, "D8": d8}
    overall_pass = all(item["status"] == "pass" for item in gates.values())
    print(json.dumps({"overall_status": "pass" if overall_pass else "fail", "gates": gates}, indent=2))
    return 0 if overall_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
