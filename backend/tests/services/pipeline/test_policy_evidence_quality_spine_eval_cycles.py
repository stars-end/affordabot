from __future__ import annotations

from scripts.verification.verify_policy_evidence_quality_spine_eval_cycles import (
    build_eval_cycles_report,
)


def _scorecard_fixture() -> dict:
    return {
        "matrix_attempt": {
            "attempt_id": "bd-3wefe.13-retry-4",
            "retry_round": 4,
            "targeted_tweak": "railway_dev_current_run_storage_probe",
        },
        "matrix_source": {
            "mode": "agent_a_horizontal_matrix",
        },
        "overall_verdict": "partial",
        "failure_classification": {
            "failed_categories": [],
            "not_proven_categories": [
                "storage/read-back",
                "Windmill/orchestration",
                "LLM narrative",
            ],
        },
        "taxonomy": {
            "scraped/search": {"status": "pass", "details": "ok"},
            "reader": {"status": "pass", "details": "ok"},
            "structured-source": {"status": "pass", "details": "ok"},
            "identity/dedupe": {"status": "pass", "details": "ok"},
            "storage/read-back": {"status": "not_proven", "details": "no live readback"},
            "Windmill/orchestration": {"status": "not_proven", "details": "no current run id"},
            "sufficiency gate": {"status": "pass", "details": "ready"},
            "economic reasoning": {"status": "pass", "details": "ready"},
            "LLM narrative": {"status": "not_proven", "details": "canonical run id missing"},
            "frontend/read-model auditability": {"status": "pass", "details": "display-only"},
        },
    }


def test_eval_cycle_report_defaults_to_ten_cycles_and_partial_verdict() -> None:
    report = build_eval_cycles_report(
        scorecard=_scorecard_fixture(),
        retry_ledger=None,
        live_storage_probe=None,
        max_cycles=10,
    )

    assert report["max_cycles"] == 10
    assert report["final_verdict"] == "partial"
    assert len(report["cycle_ledger"]) == 10
    assert report["cycle_ledger"][0]["attempt_id"] == "baseline"
    assert report["cycle_ledger"][4]["attempt_id"] == "retry_4"
    assert report["cycle_ledger"][4]["status"] == "completed"
    assert report["proof_scope"]["local_deterministic_proof"] is True
    assert report["proof_scope"]["live_product_proof"] is False
    assert report["gate_categories"]["economic_analysis_readiness"]["status"] == "pass"


def test_eval_cycle_report_marks_live_minio_access_denied_as_not_proven_storage_blocker() -> None:
    live_probe = {
        "status": "blocked",
        "blocker": "minio_write_or_readback_failed",
        "error_summary": "S3Error AccessDenied bucket_name=affordabot-artifacts",
    }
    report = build_eval_cycles_report(
        scorecard=_scorecard_fixture(),
        retry_ledger=None,
        live_storage_probe=live_probe,
        max_cycles=10,
    )

    storage = report["gate_categories"]["storage/read-back"]
    assert storage["status"] == "not_proven"
    assert "minio_write_or_readback_failed" in storage["details"]
    assert "AccessDenied" in storage["details"]
    assert report["final_verdict"] == "partial"


def test_eval_cycle_report_respects_existing_retry_ledger_records() -> None:
    retry_ledger = {
        "attempts": [
            {
                "attempt_id": "baseline",
                "status": "completed_superseded",
                "result_verdict": "fail",
                "failed_categories": ["economic reasoning"],
                "not_proven_categories": [],
                "tweaks_applied": [],
                "result_note": "legacy",
                "score_delta": None,
            },
            {
                "attempt_id": "retry_1",
                "status": "completed_superseded",
                "result_verdict": "partial",
                "failed_categories": [],
                "not_proven_categories": ["Windmill/orchestration"],
                "tweaks_applied": ["source_bound_model_card_projection"],
                "result_note": "legacy",
                "score_delta": None,
            },
        ]
    }
    report = build_eval_cycles_report(
        scorecard=_scorecard_fixture(),
        retry_ledger=retry_ledger,
        live_storage_probe=None,
        max_cycles=3,
    )

    assert report["max_cycles"] == 3
    assert [item["attempt_id"] for item in report["cycle_ledger"]] == [
        "baseline",
        "retry_1",
        "retry_2",
    ]
    assert report["cycle_ledger"][0]["status"] == "completed_superseded"
    assert report["cycle_ledger"][1]["status"] == "completed_superseded"
