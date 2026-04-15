from __future__ import annotations

from services.pipeline.policy_evidence_quality_spine import (
    build_data_runtime_evidence,
    build_horizontal_matrix,
)


def test_horizontal_matrix_meets_minimum_scope_contract() -> None:
    matrix = build_horizontal_matrix(
        attempt_id="test-attempt",
        retry_round=0,
        targeted_tweak="baseline_no_tweak",
        before_score=None,
    )

    assert matrix["feature_key"] == "bd-3wefe.13"
    assert matrix["summary"]["total_cases"] >= 6
    assert matrix["summary"]["jurisdiction_count"] >= 2
    assert len(matrix["summary"]["mechanism_family_counts"]) >= 3
    assert matrix["attempt_metadata"]["attempt_id"] == "test-attempt"
    assert matrix["attempt_metadata"]["retry_round"] == 0


def test_matrix_rows_preserve_provider_fallback_and_eval_identity() -> None:
    matrix = build_horizontal_matrix(
        attempt_id="test-provider-identity",
        retry_round=1,
        targeted_tweak="portal_penalty_increase",
        before_score=70.0,
    )
    rows = matrix["rows"]

    assert all("private_searxng" in row["provider_results"] for row in rows)
    assert any(row["provider_results"]["tavily_fallback"]["executed"] for row in rows)
    exa_eval_rows = [row for row in rows if row["provider_results"]["exa_eval"]["executed"]]
    assert len(exa_eval_rows) == 2
    assert all(row["provider_results"]["exa_eval"]["reason_code"] == "eval_subset_row" for row in exa_eval_rows)


def test_matrix_classification_contains_quantified_and_fail_closed_examples() -> None:
    matrix = build_horizontal_matrix(
        attempt_id="test-classification",
        retry_round=0,
        targeted_tweak="baseline_no_tweak",
        before_score=None,
    )
    readiness = [row["package_readiness_classification"] for row in matrix["rows"]]
    assert "quantified_ready" in readiness
    assert "fail_closed" in readiness


def test_vertical_runtime_builds_package_and_proves_storage_readback() -> None:
    matrix = build_horizontal_matrix(
        attempt_id="test-runtime",
        retry_round=0,
        targeted_tweak="baseline_no_tweak",
        before_score=None,
    )
    runtime = build_data_runtime_evidence(
        matrix=matrix,
        vertical_case_id="sj-parking-minimum-amendment",
        live_mode="off",
    )

    assert runtime["vertical_candidate_case_id"] == "sj-parking-minimum-amendment"
    assert runtime["package_build"]["evidence_card_count"] >= 1
    assert runtime["package_build"]["parameter_card_count"] >= 1
    assert runtime["vertical_package_payload"]["model_cards"]
    assert runtime["vertical_package_payload"]["assumption_usage"]
    assert runtime["storage_readback"]["stored"] is True
    assert runtime["storage_readback"]["artifact_readback_status"] == "proven"
    assert runtime["storage_readback"]["record_present"] is True
    assert runtime["live_probe"]["status"] == "skipped"


def test_runtime_live_auto_fails_closed_when_env_missing() -> None:
    matrix = build_horizontal_matrix(
        attempt_id="test-live",
        retry_round=2,
        targeted_tweak="reader_threshold_raise",
        before_score=72.5,
    )
    runtime = build_data_runtime_evidence(
        matrix=matrix,
        vertical_case_id="sj-parking-minimum-amendment",
        live_mode="auto",
    )

    assert runtime["live_probe"]["status"] == "blocked"
    assert runtime["live_probe"]["fail_closed"] is True
    assert runtime["live_probe"]["failure_class"] in {
        "live_storage_env_missing",
        "offline_first_harness_no_live_write",
    }
