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


def _matrix_with_runtime_evidence(
    package: dict,
    *,
    orchestration_proof: dict | None = None,
    llm_narrative_proof: dict | None = None,
    storage_proof: dict | None = None,
) -> dict:
    matrix = _real_matrix_from_case(package)
    matrix["agent_a_runtime_evidence"] = {
        "vertical_package_payload": package,
        "orchestration_proof": orchestration_proof or {},
        "llm_narrative_proof": llm_narrative_proof or {},
        "storage_proof": storage_proof or {},
    }
    return matrix


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


def test_windmill_historical_stub_proof_does_not_count_as_pass() -> None:
    bundle = PolicyEconomicMechanismCaseService().build_case_bundle()
    direct = _case(bundle, "direct_cost_case")
    matrix = _matrix_with_runtime_evidence(
        direct["primary_package"],
        orchestration_proof={
            "proof_status": "pass",
            "proof_mode": "historical_stub_flow_proof",
            "linked_to_current_vertical_package": True,
            "windmill_run_id": "wm-run-historical",
            "windmill_job_id": "wm-job-historical",
            "blocker": None,
        },
    )

    service = PolicyEvidenceQualitySpineEconomicsService()
    result = service.evaluate(
        matrix_input=MatrixInput(
            payload=matrix,
            source_path="horizontal_matrix.json",
            source_mode="agent_a_horizontal_matrix",
        )
    )

    windmill = result["scorecard"]["taxonomy"]["Windmill/orchestration"]
    assert windmill["status"] == "not_proven"
    assert "Historical Windmill stub proof" in windmill["details"]


def test_llm_narrative_requires_canonical_run_id() -> None:
    bundle = PolicyEconomicMechanismCaseService().build_case_bundle()
    direct = _case(bundle, "direct_cost_case")
    matrix = _matrix_with_runtime_evidence(
        direct["primary_package"],
        llm_narrative_proof={
            "proof_status": "not_proven",
            "canonical_pipeline_run_id": "",
            "canonical_pipeline_step_id": "",
            "blocker": "canonical_llm_run_id_missing",
            "source": "deterministic_quality_spine",
        },
    )

    service = PolicyEvidenceQualitySpineEconomicsService()
    result = service.evaluate(
        matrix_input=MatrixInput(
            payload=matrix,
            source_path="horizontal_matrix.json",
            source_mode="agent_a_horizontal_matrix",
        )
    )

    llm = result["scorecard"]["taxonomy"]["LLM narrative"]
    assert llm["status"] == "not_proven"
    assert "canonical_llm_run_id_missing" in llm["details"]


def test_storage_readback_requires_non_memory_storage_proof() -> None:
    bundle = PolicyEconomicMechanismCaseService().build_case_bundle()
    direct = _case(bundle, "direct_cost_case")
    matrix = _matrix_with_runtime_evidence(direct["primary_package"])

    service = PolicyEvidenceQualitySpineEconomicsService()
    result = service.evaluate(
        matrix_input=MatrixInput(
            payload=matrix,
            source_path="horizontal_matrix.json",
            source_mode="agent_a_horizontal_matrix",
        )
    )

    storage = result["scorecard"]["taxonomy"]["storage/read-back"]
    assert storage["status"] == "not_proven"
    assert "non-memory Postgres/MinIO storage proof is not provided" in storage["details"]


def test_storage_readback_passes_with_non_memory_storage_proof() -> None:
    bundle = PolicyEconomicMechanismCaseService().build_case_bundle()
    direct = _case(bundle, "direct_cost_case")
    matrix = _matrix_with_runtime_evidence(
        direct["primary_package"],
        storage_proof={
            "proof_status": "pass",
            "proof_mode": "postgres_minio_live",
            "store_backend": "postgres",
            "artifact_probe_backend": "minio",
            "persisted_record_id": "row-123",
            "minio_readback_proven": True,
        },
    )

    service = PolicyEvidenceQualitySpineEconomicsService()
    result = service.evaluate(
        matrix_input=MatrixInput(
            payload=matrix,
            source_path="horizontal_matrix.json",
            source_mode="agent_a_horizontal_matrix",
        )
    )

    storage = result["scorecard"]["taxonomy"]["storage/read-back"]
    assert storage["status"] == "pass"
    assert "Non-memory storage proof present" in storage["details"]


def test_scraped_search_is_not_proven_without_selected_artifact_metrics() -> None:
    bundle = PolicyEconomicMechanismCaseService().build_case_bundle()
    direct = _case(bundle, "direct_cost_case")
    matrix = _real_matrix_from_case(direct["primary_package"])

    service = PolicyEvidenceQualitySpineEconomicsService()
    result = service.evaluate(
        matrix_input=MatrixInput(
            payload=matrix,
            source_path="horizontal_matrix.json",
            source_mode="agent_a_horizontal_matrix",
        )
    )

    scraped = result["scorecard"]["taxonomy"]["scraped/search"]
    assert scraped["status"] == "not_proven"
    assert "selected-artifact provider-quality metrics" in scraped["details"]


def test_scraped_search_fails_when_selected_candidate_is_not_artifact_grade() -> None:
    bundle = PolicyEconomicMechanismCaseService().build_case_bundle()
    direct = _case(bundle, "direct_cost_case")
    matrix = _matrix_with_runtime_evidence(direct["primary_package"])
    matrix["rows"] = [
        {
            "case_id": direct["primary_package"]["policy_identifier"],
            "selected_candidate": {
                "provider": "private_searxng",
                "rank": 1,
                "url": "https://example.gov/portal",
                "selection_reason": "rank_top1",
            },
            "provider_results": {
                "private_searxng": {
                    "status": "ambiguous",
                    "reason_code": "portal_top1",
                    "candidates": [
                        {
                            "rank": 1,
                            "url": "https://example.gov/portal",
                            "artifact_grade": False,
                            "official_domain": True,
                        }
                    ],
                }
            },
        }
    ]

    service = PolicyEvidenceQualitySpineEconomicsService()
    result = service.evaluate(
        matrix_input=MatrixInput(
            payload=matrix,
            source_path="horizontal_matrix.json",
            source_mode="agent_a_horizontal_matrix",
        )
    )

    scraped = result["scorecard"]["taxonomy"]["scraped/search"]
    assert scraped["status"] == "fail"
    assert "did not meet artifact-quality threshold" in scraped["details"]


def test_retry_ledger_defaults_to_ten_cycles() -> None:
    service = PolicyEvidenceQualitySpineEconomicsService()
    result = service.evaluate(
        matrix_input=MatrixInput(
            payload=None,
            source_path="horizontal_matrix.json",
            source_mode="missing",
        )
    )

    ledger = result["retry_ledger"]
    assert ledger["max_retry_rounds"] == 10
    assert len(ledger["attempts"]) == 10
    assert ledger["attempts"][0]["attempt_id"] == "baseline"
    assert ledger["attempts"][-1]["attempt_id"] == "retry_9"
    assert result["scorecard"]["evaluation_cycle_policy"]["max_cycles"] == 10


def test_retry_ledger_respects_lower_cycle_cap() -> None:
    service = PolicyEvidenceQualitySpineEconomicsService()
    result = service.evaluate(
        matrix_input=MatrixInput(
            payload=None,
            source_path="horizontal_matrix.json",
            source_mode="missing",
        ),
        max_cycles=3,
    )

    ledger = result["retry_ledger"]
    assert ledger["max_retry_rounds"] == 3
    assert [attempt["attempt_id"] for attempt in ledger["attempts"]] == [
        "baseline",
        "retry_1",
        "retry_2",
    ]
    assert result["scorecard"]["evaluation_cycle_policy"]["max_cycles"] == 3
