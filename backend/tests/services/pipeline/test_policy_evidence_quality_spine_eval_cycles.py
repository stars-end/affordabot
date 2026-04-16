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
        "vertical_package": {
            "package_id": "pkg-sj-parking-minimum-amendment",
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


def _cycle_fixture() -> dict:
    return {
        "manual_run": {
            "windmill_job_id": "019d94d2-81ef-1117-0353-4c40719876ed",
            "final_status": "succeeded",
        },
        "result_payload": {
            "scope_results": [
                {
                    "backend_response": {
                        "refs": {
                            "run_id": "6695fe26-eaaf-47d1-9100-7eb861a7aa2f",
                        }
                    },
                    "scope_item": {
                        "source_family": "meeting_minutes",
                    },
                    "steps": {
                        "read_fetch": {
                            "details": {
                                "candidate_audit": [
                                    {
                                        "outcome": "materialized_raw_scrape",
                                        "url": "https://sanjose.legistar.com/View.ashx?M=A&ID=1345653",
                                    }
                                ]
                            },
                            "refs": {
                                "artifact_refs": [
                                    "artifacts/live/reader_output.md",
                                ]
                            },
                        }
                    },
                }
            ]
        },
    }


def test_eval_cycle_report_defaults_to_ten_cycles_and_partial_verdict() -> None:
    report = build_eval_cycles_report(
        scorecard=_scorecard_fixture(),
        retry_ledger=None,
        live_storage_probe=None,
        live_cycle=_cycle_fixture(),
        economic_status=None,
        max_cycles=10,
        deploy_sha="735022f74ebddc0064717b59921a99bd9950f893",
    )

    assert report["max_cycles"] == 10
    assert report["final_verdict"] == "partial"
    assert len(report["cycle_ledger"]) == 10
    assert report["cycle_ledger"][0]["cycle_number"] == 1
    assert report["cycle_ledger"][0]["status"] == "completed"
    assert report["cycle_ledger"][0]["deploy_sha"] == "735022f74ebddc0064717b59921a99bd9950f893"
    assert report["cycle_ledger"][0]["windmill_job_id"] == "019d94d2-81ef-1117-0353-4c40719876ed"
    assert report["cycle_ledger"][0]["backend_run_id"] == "6695fe26-eaaf-47d1-9100-7eb861a7aa2f"
    assert report["gate_categories"]["economic_analysis"]["status"] == "pass"
    assert report["cycle_1_assessment"]["status"] == "partial"


def test_eval_cycle_report_marks_live_minio_access_denied_as_not_proven_storage_blocker() -> None:
    live_probe = {
        "gates": {
            "minio_object_readback": {
                "status": "fail",
                "details": "one_or_more_artifact_readbacks_failed",
            }
        }
    }
    report = build_eval_cycles_report(
        scorecard=_scorecard_fixture(),
        retry_ledger=None,
        live_storage_probe=live_probe,
        live_cycle=_cycle_fixture(),
        economic_status=None,
        max_cycles=10,
        deploy_sha=None,
    )

    minio = report["gate_categories"]["minio"]
    assert minio["status"] == "fail"
    assert "artifact_readbacks_failed" in minio["details"]
    assert report["final_verdict"] == "fail"


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
        live_cycle=_cycle_fixture(),
        economic_status=None,
        max_cycles=3,
        deploy_sha=None,
    )

    assert report["max_cycles"] == 3
    assert [item["cycle_number"] for item in report["cycle_ledger"]] == [1, 2, 3]
    assert report["cycle_ledger"][0]["status"] == "completed"
    assert report["cycle_ledger"][1]["status"] == "not_executed"
