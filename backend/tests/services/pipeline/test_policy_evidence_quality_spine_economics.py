from __future__ import annotations

from services.pipeline.policy_economic_mechanism_cases import (
    PolicyEconomicMechanismCaseService,
)
from services.pipeline.policy_evidence_quality_spine_economics import (
    MatrixInput,
    PolicyEvidenceQualitySpineEconomicsService,
)


def _case(bundle: dict, case_id: str) -> dict:
    for item in bundle["cases"]:
        if item["case_id"] == case_id:
            return item
    raise AssertionError(f"missing case_id={case_id}")


def _real_matrix_from_case(package: dict) -> dict:
    return {
        "artifact_rows": [
            {
                "artifact_id": package["package_id"],
                "windmill_run_id": "wm-run-123",
                "windmill_job_id": "wm-job-123",
                "vertical_candidate": {
                    "package": package,
                },
            }
        ]
    }


def test_taxonomy_contains_all_required_quality_buckets() -> None:
    service = PolicyEvidenceQualitySpineEconomicsService()
    result = service.evaluate(
        matrix_input=MatrixInput(
            payload=None,
            source_path="docs/poc/policy-evidence-quality-spine/artifacts/horizontal_matrix.json",
            source_mode="missing",
        )
    )
    taxonomy = result["scorecard"]["taxonomy"]
    assert set(taxonomy.keys()) == {
        "scraped/search",
        "reader",
        "structured-source",
        "identity/dedupe",
        "storage/read-back",
        "Windmill/orchestration",
        "sufficiency gate",
        "economic reasoning",
        "LLM narrative",
        "frontend/read-model auditability",
    }


def test_fail_closed_unsupported_claims_are_rejected() -> None:
    bundle = PolicyEconomicMechanismCaseService().build_case_bundle()
    control = _case(bundle, "unsupported_fail_closed_control")
    matrix = _real_matrix_from_case(control["primary_package"])

    service = PolicyEvidenceQualitySpineEconomicsService()
    result = service.evaluate(
        matrix_input=MatrixInput(
            payload=matrix,
            source_path="horizontal_matrix.json",
            source_mode="agent_a_horizontal_matrix",
        )
    )

    assert result["scorecard"]["sufficiency_result"]["readiness_level"] == "fail_closed"
    unsupported = result["vertical_economic_output"]["unsupported_claim_rejection"]
    assert unsupported["status"] == "rejected"
    assert "Unsupported quantitative claim blocked" in unsupported["reason"]


def test_source_bound_economic_claim_rows_require_source_fields() -> None:
    service = PolicyEvidenceQualitySpineEconomicsService()
    result = service.evaluate(
        matrix_input=MatrixInput(
            payload=None,
            source_path="horizontal_matrix.json",
            source_mode="missing",
        )
    )
    rows = result["vertical_economic_output"]["parameter_table"]
    assert rows, "expected at least one resolved source-bound parameter"
    for row in rows:
        assert row["source_url"]
        assert row["source_excerpt"]
        assert row["evidence_card_id"]


def test_read_model_output_is_display_only_no_recompute() -> None:
    service = PolicyEvidenceQualitySpineEconomicsService()
    result = service.evaluate(
        matrix_input=MatrixInput(
            payload=None,
            source_path="horizontal_matrix.json",
            source_mode="missing",
        )
    )
    read_model = result["read_model_audit_output"]
    assert read_model["frontend_contract"]["requires_recomputation"] is False
    assert read_model["admin_contract"]["requires_recomputation"] is False
    assert read_model["analysis_handoff"]["parallel_engine_created"] is False


def test_fallback_vs_real_matrix_labeling() -> None:
    bundle = PolicyEconomicMechanismCaseService().build_case_bundle()
    direct = _case(bundle, "direct_cost_case")

    service = PolicyEvidenceQualitySpineEconomicsService()
    fallback = service.evaluate(
        matrix_input=MatrixInput(
            payload=None,
            source_path="horizontal_matrix.json",
            source_mode="missing",
        )
    )
    real = service.evaluate(
        matrix_input=MatrixInput(
            payload=_real_matrix_from_case(direct["primary_package"]),
            source_path="horizontal_matrix.json",
            source_mode="agent_a_horizontal_matrix",
        )
    )

    assert fallback["scorecard"]["matrix_source"]["mode"] == "fallback_fixture"
    assert fallback["scorecard"]["matrix_source"]["fallback_note"] is not None
    assert real["scorecard"]["matrix_source"]["mode"] == "agent_a_horizontal_matrix"
    assert real["scorecard"]["matrix_source"]["fallback_note"] is None
