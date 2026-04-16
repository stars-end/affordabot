import os
import sys
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from schemas.analysis import (  # noqa: E402
    FailureCode,
    ScenarioBounds,
    SourceHierarchyStatus,
    SourceTier,
    SufficiencyState,
)
from schemas.economic_evidence import (  # noqa: E402
    AssumptionCard,
    EvidenceCard,
    EvidenceSourceType,
    GateReport,
    GateStageResult,
    GateVerdict,
    MechanismFamily,
    ModelCard,
    ParameterCard,
    ParameterState,
    QualityGateStage,
    UnitValidationStatus,
)
from schemas.policy_evidence_package import (  # noqa: E402
    AssumptionUsageStatus,
    FreshnessStatus,
    GateProjection,
    PackageFailureReason,
    PolicyEvidencePackage,
    ScrapedSourceProvenance,
    SearchProvider,
    SourceLane,
    StorageRef,
    StorageSystem,
    StorageTruthRole,
    StructuredSourceProvenance,
)


def _evidence_card(card_id: str) -> EvidenceCard:
    return EvidenceCard(
        id=card_id,
        source_url="https://records.sanjoseca.gov/agenda/item-1",
        source_type=EvidenceSourceType.AGENDA_PACKET,
        content_hash="9f24afcd00112233",
        excerpt="The staff report estimates direct cost of $5.2M over the first year.",
        retrieved_at=datetime(2026, 4, 15, tzinfo=timezone.utc),
        source_tier=SourceTier.TIER_A,
        provenance_label="legistar_artifact",
    )


def _resolved_parameter(parameter_id: str) -> ParameterCard:
    return ParameterCard(
        id=parameter_id,
        parameter_name="annual_direct_cost",
        state=ParameterState.RESOLVED,
        value=5_200_000.0,
        unit="usd_per_year",
        source_url="https://records.sanjoseca.gov/agenda/item-1",
        source_excerpt="Estimated direct annual cost is $5.2M.",
        source_hierarchy_status=SourceHierarchyStatus.FISCAL_OR_REG_IMPACT_ANALYSIS,
    )


def _assumption_card(assumption_id: str, stale_after_days: int = 365) -> AssumptionCard:
    return AssumptionCard(
        id=assumption_id,
        family=MechanismFamily.FEE_OR_TAX_PASS_THROUGH,
        low=0.50,
        central=0.65,
        high=0.80,
        unit="share",
        source_url="https://example.org/paper/pass-through",
        source_excerpt="Estimated pass-through incidence in similar regulated markets.",
        applicability_tags=["housing", "fees"],
        external_validity_notes="Urban markets with moderate supply constraints.",
        confidence=0.7,
        version="v1",
        stale_after_days=stale_after_days,
    )


def _quant_model(model_id: str, assumption_id: str) -> ModelCard:
    return ModelCard(
        id=model_id,
        mechanism_family=MechanismFamily.FEE_OR_TAX_PASS_THROUGH,
        formula_id="model.pass_through.v1",
        input_parameter_ids=["annual_direct_cost"],
        assumption_ids=[assumption_id],
        scenario_bounds=ScenarioBounds(
            conservative=2_000_000.0,
            central=3_000_000.0,
            aggressive=4_000_000.0,
        ),
        arithmetic_valid=True,
        unit_validation_status=UnitValidationStatus.VALID,
        quantification_eligible=True,
    )


def _pass_gate_report() -> GateReport:
    return GateReport(
        case_id="case-1",
        provider="private_searxng",
        verdict=GateVerdict.QUANTIFIED_PASS,
        stage_results=[
            GateStageResult(stage=QualityGateStage.SEARCH_RECALL, passed=True),
            GateStageResult(stage=QualityGateStage.READER_SUBSTANCE, passed=True),
            GateStageResult(stage=QualityGateStage.PARAMETERIZATION, passed=True),
            GateStageResult(stage=QualityGateStage.QUANTIFICATION, passed=True),
        ],
        failure_codes=[],
        artifact_counts={"evidence_cards": 1},
    )


def test_valid_package_scraped_and_structured_handoff_ready():
    package = PolicyEvidencePackage(
        package_id="pkg-1",
        jurisdiction="san_jose_ca",
        canonical_document_key="san_jose_ca|2026-0415|agenda-001",
        policy_identifier="SJ-2026-0415",
        created_at=datetime(2026, 4, 15, tzinfo=timezone.utc),
        source_lanes=[SourceLane.SCRAPED, SourceLane.STRUCTURED],
        scraped_sources=[
            ScrapedSourceProvenance(
                search_provider=SearchProvider.PRIVATE_SEARXNG,
                query_family="meeting_minutes",
                query_text="san jose housing fees april 2026",
                search_snapshot_id="snap-1",
                candidate_rank=1,
                selected_candidate_url="https://records.sanjoseca.gov/agenda/item-1",
                reader_substance_passed=True,
                reader_artifact_url="https://storage.example/reader/item-1.json",
            )
        ],
        structured_sources=[
            StructuredSourceProvenance(
                source_family="legistar",
                access_method="rest_api",
                endpoint_or_file_url="https://records.sanjoseca.gov/api/v1/events/100",
                field_count=5,
            )
        ],
        evidence_cards=[_evidence_card("ev-1")],
        parameter_cards=[_resolved_parameter("annual_direct_cost")],
        assumption_cards=[_assumption_card("assump-1")],
        model_cards=[_quant_model("model-1", "assump-1")],
        gate_report=_pass_gate_report(),
        gate_projection=GateProjection(
            runtime_sufficiency_state=SufficiencyState.QUANTIFIED,
            runtime_failure_codes=[],
            canonical_breakdown_ref="breakdown-1",
            canonical_pipeline_run_id="run-1",
            canonical_pipeline_step_id="step-quant",
        ),
        assumption_usage=[
            AssumptionUsageStatus(
                assumption_id="assump-1",
                used_for_quantitative_claim=True,
                applicable=True,
                stale=False,
            )
        ],
        storage_refs=[
            StorageRef(
                storage_system=StorageSystem.POSTGRES,
                truth_role=StorageTruthRole.SOURCE_OF_TRUTH,
                reference_id="pipeline_runs:run-1",
            ),
            StorageRef(
                storage_system=StorageSystem.MINIO,
                truth_role=StorageTruthRole.ARTIFACT_OF_RECORD,
                reference_id="minio://raw/agenda/item-1.pdf",
            ),
            StorageRef(
                storage_system=StorageSystem.PGVECTOR,
                truth_role=StorageTruthRole.DERIVED_INDEX,
                reference_id="chunk:123",
            ),
        ],
        freshness_status=FreshnessStatus.FRESH,
        economic_handoff_ready=True,
    )
    assert package.economic_handoff_ready is True
    assert package.schema_version.value == "1.0.0"


def test_fail_closed_package_allowed_when_not_handoff_ready():
    package = PolicyEvidencePackage(
        package_id="pkg-fail-closed",
        jurisdiction="san_jose_ca",
        canonical_document_key="san_jose_ca|2026-0415|agenda-002",
        policy_identifier="SJ-2026-0416",
        created_at=datetime(2026, 4, 15, tzinfo=timezone.utc),
        source_lanes=[SourceLane.SCRAPED],
        scraped_sources=[
            ScrapedSourceProvenance(
                search_provider=SearchProvider.PRIVATE_SEARXNG,
                query_family="agenda_item",
                query_text="san jose permit fee agenda",
                search_snapshot_id="snap-2",
                candidate_rank=1,
                selected_candidate_url="https://records.sanjoseca.gov/agenda/item-2",
                reader_substance_passed=False,
            )
        ],
        evidence_cards=[_evidence_card("ev-2")],
        gate_report=GateReport(
            case_id="case-2",
            provider="private_searxng",
            verdict=GateVerdict.FAIL_CLOSED,
            stage_results=[
                GateStageResult(stage=QualityGateStage.PARAMETERIZATION, passed=False)
            ],
            blocking_gate=QualityGateStage.PARAMETERIZATION,
            failure_codes=[FailureCode.PARAMETER_MISSING],
        ),
        gate_projection=GateProjection(
            runtime_sufficiency_state=SufficiencyState.QUALITATIVE_ONLY,
            runtime_insufficiency_reason="Missing parameter support",
            runtime_failure_codes=[FailureCode.PARAMETER_MISSING],
        ),
        freshness_status=FreshnessStatus.STALE_BLOCKED,
        economic_handoff_ready=False,
        insufficiency_reasons=[PackageFailureReason.BLOCKING_GATE_PRESENT],
    )
    assert package.economic_handoff_ready is False
    assert package.gate_report.blocking_gate == QualityGateStage.PARAMETERIZATION


def test_invalid_pgvector_as_source_of_truth():
    with pytest.raises(ValidationError):
        PolicyEvidencePackage(
            package_id="pkg-bad-pgvector",
            jurisdiction="san_jose_ca",
            canonical_document_key="san_jose_ca|bad|pgvector",
            policy_identifier="SJ-bad-1",
            created_at=datetime(2026, 4, 15, tzinfo=timezone.utc),
            source_lanes=[SourceLane.STRUCTURED],
            structured_sources=[
                StructuredSourceProvenance(
                    source_family="leginfo",
                    access_method="raw_file",
                    endpoint_or_file_url="https://leginfo.legislature.ca.gov/file.csv",
                )
            ],
            evidence_cards=[_evidence_card("ev-3")],
            gate_report=_pass_gate_report(),
            gate_projection=GateProjection(
                runtime_sufficiency_state=SufficiencyState.QUANTIFIED,
            ),
            storage_refs=[
                StorageRef(
                    storage_system=StorageSystem.PGVECTOR,
                    truth_role=StorageTruthRole.SOURCE_OF_TRUTH,
                    reference_id="chunk:999",
                )
            ],
            economic_handoff_ready=False,
        )


def test_missing_scraped_provider_identity_fails():
    with pytest.raises(ValidationError):
        PolicyEvidencePackage(
            package_id="pkg-missing-provider",
            jurisdiction="san_jose_ca",
            canonical_document_key="san_jose_ca|missing|provider",
            policy_identifier="SJ-missing-provider",
            created_at=datetime(2026, 4, 15, tzinfo=timezone.utc),
            source_lanes=[SourceLane.SCRAPED],
            scraped_sources=[],
            evidence_cards=[_evidence_card("ev-4")],
            gate_report=_pass_gate_report(),
            gate_projection=GateProjection(
                runtime_sufficiency_state=SufficiencyState.QUANTIFIED,
            ),
            economic_handoff_ready=False,
        )


def test_stale_or_unsupported_quant_assumption_blocks_handoff():
    with pytest.raises(ValidationError):
        PolicyEvidencePackage(
            package_id="pkg-stale-assumption",
            jurisdiction="san_jose_ca",
            canonical_document_key="san_jose_ca|stale|assumption",
            policy_identifier="SJ-stale-assumption",
            created_at=datetime(2026, 4, 15, tzinfo=timezone.utc),
            source_lanes=[SourceLane.SCRAPED],
            scraped_sources=[
                ScrapedSourceProvenance(
                    search_provider=SearchProvider.TAVILY,
                    query_family="meeting_minutes",
                    query_text="san jose housing impact",
                    search_snapshot_id="snap-stale",
                    candidate_rank=1,
                    selected_candidate_url="https://records.sanjoseca.gov/agenda/item-3",
                    reader_substance_passed=True,
                )
            ],
            evidence_cards=[_evidence_card("ev-5")],
            parameter_cards=[_resolved_parameter("param-5")],
            assumption_cards=[_assumption_card("assump-stale", stale_after_days=90)],
            model_cards=[_quant_model("model-5", "assump-stale")],
            gate_report=_pass_gate_report(),
            gate_projection=GateProjection(
                runtime_sufficiency_state=SufficiencyState.QUANTIFIED,
            ),
            assumption_usage=[
                AssumptionUsageStatus(
                    assumption_id="assump-stale",
                    used_for_quantitative_claim=True,
                    applicable=False,
                    stale=True,
                    stale_reason="source older than staleness policy",
                )
            ],
            economic_handoff_ready=True,
        )
