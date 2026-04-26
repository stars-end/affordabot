from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "verification"
    / "verify_scraped_lane_data_moat.py"
)


def test_verify_scraped_lane_data_moat_passes_with_required_fields(tmp_path: Path) -> None:
    payload = {
        "run_context": {
            "policy_lineage": {
                "lineage_presence": {"authoritative_policy_text": True},
                "negative_evidence": [],
            },
            "source_quality_metrics": {
                "portal_skip_count": 1,
                "official_reader_error_count": 0,
                "fallback_materialization_count": 0,
                "source_shape_drift": {"drift_detected": False},
            },
            "source_reconciliation": {
                "records": [{"field": "fee_rate", "status": "confirmed"}],
                "secondary_override_blocked": True,
            },
            "primary_parameter_extraction": {
                "facts": [
                    {
                        "source_url": "https://example.gov/fee-schedule.pdf",
                        "source_excerpt": "Fee is $3.00 per square foot",
                        "unit": "usd_per_square_foot",
                        "denominator": "per_square_foot",
                    }
                ]
            },
        }
    }
    input_path = tmp_path / "package.json"
    input_path.write_text(json.dumps(payload), encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--input", str(input_path)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0
    report = json.loads(proc.stdout)
    assert report["overall_status"] == "pass"
    assert report["gates"]["D8"]["status"] == "pass"


def test_verify_scraped_lane_data_moat_fails_when_lineage_missing(tmp_path: Path) -> None:
    payload = {"run_context": {"source_quality_metrics": {}, "source_reconciliation": {}, "primary_parameter_extraction": {}}}
    input_path = tmp_path / "package.json"
    input_path.write_text(json.dumps(payload), encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--input", str(input_path)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 1
    report = json.loads(proc.stdout)
    assert report["gates"]["D1"]["status"] == "fail"
