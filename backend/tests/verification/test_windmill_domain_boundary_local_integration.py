from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[3]
WINDMILL_SCRIPT_PATH = (
    ROOT
    / "ops"
    / "windmill"
    / "f"
    / "affordabot"
    / "pipeline_daily_refresh_domain_boundary.py"
)
VERIFY_SCRIPT_PATH = (
    ROOT
    / "backend"
    / "scripts"
    / "verification"
    / "verify_windmill_domain_boundary_local_integration.py"
)


def _load_module(name: str, path: Path):
    spec = spec_from_file_location(name, path)
    module = module_from_spec(spec)
    assert spec is not None
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_local_integration_harness_proves_happy_rerun_and_stale_blocked() -> None:
    module = _load_module("windmill_domain_boundary_local", WINDMILL_SCRIPT_PATH)
    result = module.main(
        step="run_local_integration_harness",
        idempotency_key="run:verify-local",
        scope_item={"jurisdiction": "San Jose CA", "source_family": "meeting_minutes"},
        search_query="San Jose housing minutes",
        analysis_question="Summarize housing policy updates.",
        windmill_run_id="wm-run-local",
        windmill_job_id="wm-job-local",
    )

    assert result["status"] == "succeeded"
    assert result["evidence"]["rerun_index_idempotent_reuse"] is True
    assert result["evidence"]["rerun_chunk_count_stable"] is True
    assert result["evidence"]["stale_blocked_short_circuit"] is True
    assert result["scenarios"]["happy_first"]["status"] == "succeeded"
    assert result["scenarios"]["happy_rerun"]["status"] == "succeeded"
    assert result["scenarios"]["stale_blocked"]["status"] == "blocked"
    read_step = result["scenarios"]["happy_first"]["steps"]["read_fetch"]
    assert read_step["envelope"]["windmill_run_id"] == "wm-run-local"
    assert read_step["refs"]["windmill_run_id"] == "wm-run-local"


def test_verify_script_produces_report_payload_shape() -> None:
    module = _load_module("verify_windmill_domain_boundary_local", VERIFY_SCRIPT_PATH)
    report = module.run_verification()
    assert report["status"] == "succeeded"
    assert report["evidence"]["windmill_refs_propagated"] is True
    assert "happy_first" in report["scenarios"]
    assert "happy_rerun" in report["scenarios"]
    assert "stale_blocked" in report["scenarios"]
