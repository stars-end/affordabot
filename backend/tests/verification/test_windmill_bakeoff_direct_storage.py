from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_module():
    repo_root = Path(__file__).resolve().parents[3]
    script_path = (
        repo_root
        / "backend"
        / "scripts"
        / "verification"
        / "windmill_bakeoff_direct_storage.py"
    )
    spec = importlib.util.spec_from_file_location("windmill_bakeoff_direct_storage", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("failed to load windmill_bakeoff_direct_storage module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_idempotent_rerun_no_duplicate_documents_or_chunks(tmp_path):
    module = _load_module()
    runner = module.DirectStoragePipelineRunner(state_dir=tmp_path)
    run_date = "2026-04-12"

    first = runner.run(run_date=run_date, scenario="normal")
    second = runner.run(run_date=run_date, scenario="normal")

    assert first["status"] == module.STATUS_SUCCEEDED
    assert second["status"] == module.STATUS_SUCCEEDED
    assert first["counts"]["documents_total"] == second["counts"]["documents_total"]
    assert first["counts"]["chunks_total"] == second["counts"]["chunks_total"]
    assert first["counts"]["analyses_total"] == second["counts"]["analyses_total"]


def test_failure_drill_statuses(tmp_path):
    module = _load_module()
    runner = module.DirectStoragePipelineRunner(state_dir=tmp_path)
    run_date = "2026-04-12"

    searx = runner.run(run_date=run_date, scenario="searx_failure")
    reader = runner.run(run_date=run_date, scenario="reader_failure")
    storage = runner.run(run_date=run_date, scenario="storage_failure")

    assert searx["status"] == module.STATUS_SOURCE_ERROR
    assert reader["status"] == module.STATUS_READER_ERROR
    assert storage["status"] == module.STATUS_STORAGE_ERROR


def test_stale_gate_statuses(tmp_path):
    module = _load_module()
    runner = module.DirectStoragePipelineRunner(state_dir=tmp_path)
    run_date = "2026-04-12"

    baseline = runner.run(run_date=run_date, scenario="normal")
    stale_usable = runner.run(run_date=run_date, scenario="normal", force_stale_hours=36)
    stale_blocked = runner.run(run_date=run_date, scenario="normal", force_stale_hours=96)

    assert baseline["status"] == module.STATUS_SUCCEEDED
    assert stale_usable["status"] == module.STATUS_SUCCEEDED
    assert "stale_backed=true" in stale_usable.get("alerts", [])
    freshness_step_usable = next(
        step for step in stale_usable["steps"] if step["step"] == "freshness_gate"
    )
    assert freshness_step_usable["status"] == module.STATUS_STALE_USABLE

    assert stale_blocked["status"] == module.STATUS_STALE_BLOCKED
    freshness_step_blocked = next(
        step for step in stale_blocked["steps"] if step["step"] == "freshness_gate"
    )
    assert freshness_step_blocked["status"] == module.STATUS_STALE_BLOCKED
