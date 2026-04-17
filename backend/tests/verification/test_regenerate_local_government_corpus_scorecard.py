from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
import sys

from services.pipeline.local_government_corpus_benchmark import (
    LocalGovernmentCorpusBenchmarkService,
    build_local_government_corpus_matrix_seed,
)


ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = (
    ROOT
    / "backend"
    / "scripts"
    / "verification"
    / "regenerate_local_government_corpus_scorecard.py"
)

spec = spec_from_file_location(
    "regenerate_local_government_corpus_scorecard",
    SCRIPT_PATH,
)
regenerate_module = module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = regenerate_module
spec.loader.exec_module(regenerate_module)


def _write_json(path: Path, payload: dict[str, object]) -> Path:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def _first_orchestration_intent_row_id(matrix: dict[str, object]) -> str:
    for row in matrix.get("rows", []):
        if not isinstance(row, dict):
            continue
        if row.get("row_type") != "corpus_package":
            continue
        mode = str(
            (row.get("infrastructure_status") or {}).get("orchestration_mode") or ""
        )
        if mode == "orchestration_intent":
            return str(row["corpus_row_id"])
    raise AssertionError(
        "expected at least one orchestration_intent row in seed matrix"
    )


def test_run_uses_overlay_and_records_artifact_inputs(tmp_path: Path) -> None:
    service = LocalGovernmentCorpusBenchmarkService()
    matrix = build_local_government_corpus_matrix_seed()
    baseline = service.evaluate(matrix=matrix)
    row_id = _first_orchestration_intent_row_id(matrix)

    overlay_artifact = {
        "generated_at": "2026-04-17T09:02:17+00:00",
        "c13_verdict_candidate": "not_proven_unverified_live_refs",
        "post_metrics": {
            "seeded_placeholder_rows": ["lgm-seeded-a", "lgm-seeded-b"],
            "missing_live_refs_rows": ["lgm-missing"],
            "blocker_rows": [{"corpus_row_id": "lgm-blocked"}],
        },
        "rows": [
            {
                "corpus_row_id": row_id,
                "row_status": "proven",
                "orchestration_mode": "windmill_live",
                "windmill_flow_path": (
                    "f/affordabot/pipeline_daily_refresh_domain_boundary__flow"
                ),
                "windmill_run_id": "01J9KJ5FK0XQ7CG1WM89AZ6RY4",
                "windmill_job_id": "01J9KJ5FK0XQ7CG1WM89AZ6RY4",
            }
        ],
        "attempts": [
            {
                "corpus_row_id": row_id,
                "status": "proven",
                "orchestration_mode": "windmill_live",
                "windmill_run_id": "01J9KJ5FK0XQ7CG1WM89AZ6RY4",
                "windmill_job_id": "01J9KJ5FK0XQ7CG1WM89AZ6RY4",
            },
            {
                "corpus_row_id": "lgm-blocked",
                "status": "blocked",
                "blocker_class": "backend_scope_not_succeeded",
                "flow_response_status": "failed",
                "windmill_run_id": "01J9KJ5FK0XQ7CG1WM89AZ6RY5",
                "windmill_job_id": "01J9KJ5FK0XQ7CG1WM89AZ6RY5",
            }
        ],
    }

    matrix_path = _write_json(tmp_path / "matrix.json", matrix)
    orchestration_path = _write_json(tmp_path / "orchestration.json", overlay_artifact)
    scorecard_path = tmp_path / "scorecard.json"
    report_path = tmp_path / "report.md"

    result = regenerate_module.run(
        matrix_path=matrix_path,
        windmill_orchestration_path=orchestration_path,
        scorecard_output_path=scorecard_path,
        report_output_path=report_path,
    )

    scorecard = result["scorecard"]
    artifact_inputs = scorecard["artifact_inputs"]
    assert artifact_inputs["overlay_applied"] is True
    assert artifact_inputs["windmill_orchestration_artifact"].endswith(
        "orchestration.json"
    )
    assert (
        artifact_inputs["windmill_orchestration_verdict"]
        == "not_proven_unverified_live_refs"
    )
    assert artifact_inputs["windmill_live_attempt_rows"] == [row_id]
    assert artifact_inputs["windmill_blocked_attempt_rows"] == ["lgm-blocked"]
    assert artifact_inputs["windmill_overlay_burndown_summary"] == {
        "seeded_placeholder_rows_remaining": 2,
        "seeded_placeholder_rows_sample": ["lgm-seeded-a", "lgm-seeded-b"],
        "seeded_not_live_proven_rows_remaining": 0,
        "seeded_not_live_proven_rows_sample": [],
        "orchestration_intent_rows_remaining": 0,
        "orchestration_intent_rows_sample": [],
        "missing_live_refs_rows_remaining": 1,
        "blocked_row_count": 1,
        "live_attempt_rows_proven": 1,
        "next_seeded_ref_target_rows": ["lgm-seeded-a", "lgm-seeded-b"],
    }
    assert scorecard["gates"]["C13"]["metrics"]["seeded_not_live_proven_rows"] == (
        baseline["gates"]["C13"]["metrics"]["seeded_not_live_proven_rows"] - 1
    )
    assert (
        scorecard["gates"]["C13"]["metrics"]["live_proof_coverage_ratio"]
        > baseline["gates"]["C13"]["metrics"]["live_proof_coverage_ratio"]
    )
    assert row_id not in scorecard["gates"]["C13"]["metrics"]["next_seeded_ref_target_rows"]
    assert scorecard["corpus_state"] == "corpus_ready_with_gaps"
    report = report_path.read_text(encoding="utf-8")
    assert "C13: `not_proven`" in report
    assert "## C13 Burn-down" in report
    assert "orchestration-intent rows awaiting live proof" in report
    assert "remaining seeded ref rows" in report


def test_run_keeps_c13_strict_when_overlay_contains_seeded_refs(tmp_path: Path) -> None:
    service = LocalGovernmentCorpusBenchmarkService()
    matrix = build_local_government_corpus_matrix_seed()
    baseline = service.evaluate(matrix=matrix)
    rows = [row for row in matrix["rows"] if row.get("row_type") == "corpus_package"]

    seeded_rows = []
    for row in rows:
        mode = str(
            (row.get("infrastructure_status") or {}).get("orchestration_mode") or ""
        )
        if mode != "orchestration_intent":
            continue
        row_id = str(row["corpus_row_id"])
        seeded_rows.append(
            {
                "corpus_row_id": row_id,
                "row_status": "proven",
                "orchestration_mode": mode,
                "windmill_flow_path": (
                    "f/affordabot/pipeline_daily_refresh_domain_boundary__flow"
                ),
                "windmill_run_id": f"wm::{row_id}",
                "windmill_job_id": f"wm-job::{row_id}",
            }
        )

    matrix_path = _write_json(tmp_path / "matrix.json", matrix)
    orchestration_path = _write_json(
        tmp_path / "orchestration.json",
        {"rows": seeded_rows},
    )
    scorecard_path = tmp_path / "scorecard.json"
    report_path = tmp_path / "report.md"

    result = regenerate_module.run(
        matrix_path=matrix_path,
        windmill_orchestration_path=orchestration_path,
        scorecard_output_path=scorecard_path,
        report_output_path=report_path,
    )
    scorecard = result["scorecard"]

    assert scorecard["gates"]["C13"]["status"] == "not_proven"
    assert "windmill_refs_seeded_not_live_proven" in scorecard["gates"]["C13"][
        "blockers"
    ]
    assert scorecard["gates"]["C13"]["metrics"]["seeded_not_live_proven_rows"] == (
        baseline["gates"]["C13"]["metrics"]["seeded_not_live_proven_rows"]
    )
    assert (
        scorecard["gates"]["C13"]["metrics"]["live_proof_coverage_ratio"]
        == baseline["gates"]["C13"]["metrics"]["live_proof_coverage_ratio"]
    )
    assert scorecard["gates"]["C13"]["metrics"]["next_seeded_ref_target_rows"] == scorecard[
        "gates"
    ]["C13"]["metrics"]["remaining_seeded_ref_rows"][:10]
    assert scorecard["corpus_state"] == "corpus_ready_with_gaps"
