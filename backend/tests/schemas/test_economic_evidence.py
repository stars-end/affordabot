import os
import sys
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from schemas.analysis import FailureCode, SourceHierarchyStatus, SourceTier  # noqa: E402
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


def test_evidence_card_serializes_to_json():
    card = EvidenceCard(
        id="ev-1",
        source_url="https://example.gov/fiscal-note",
        source_type=EvidenceSourceType.FISCAL_NOTE,
        content_hash="abcdef123456",
        excerpt="Estimated annual appropriation cost is $8.1 million beginning FY2027.",
        retrieved_at=datetime(2026, 4, 14, tzinfo=timezone.utc),
        source_tier=SourceTier.TIER_A,
        provenance_label="official_fiscal_note",
        artifact_id="artifact-1",
    )
    payload = card.model_dump(mode="json")
    assert payload["id"] == "ev-1"
    assert payload["source_type"] == "fiscal_note"
    assert payload["source_tier"] == "tier_a"


def test_parameter_card_fail_closed_when_resolved_missing_evidence():
    with pytest.raises(ValidationError):
        ParameterCard(
            id="param-1",
            parameter_name="fiscal_amount",
            state=ParameterState.RESOLVED,
            value=5_000_000.0,
            source_hierarchy_status=SourceHierarchyStatus.BILL_OR_REG_TEXT,
        )


def test_assumption_card_rejects_non_monotonic_bounds():
    with pytest.raises(ValidationError):
        AssumptionCard(
            id="assump-1",
            family=MechanismFamily.FEE_OR_TAX_PASS_THROUGH,
            low=0.7,
            central=0.6,
            high=0.8,
            unit="share",
            source_url="https://example.org/study",
            source_excerpt="Estimated pass-through for comparable cases is around 60%.",
            applicability_tags=["housing"],
            external_validity_notes="Not valid for owner-only incidence.",
            confidence=0.7,
            version="v1",
        )


def test_model_card_fail_closed_on_invalid_quantification_configuration():
    with pytest.raises(ValidationError):
        ModelCard(
            id="model-1",
            mechanism_family=MechanismFamily.COMPLIANCE_COST,
            formula_id="compliance.cost.v1",
            input_parameter_ids=["population", "frequency", "time_burden", "wage_rate"],
            assumption_ids=["compliance_cost.loaded_wage_multiplier.v1"],
            quantification_eligible=True,
            arithmetic_valid=True,
            unit_validation_status=UnitValidationStatus.UNVERIFIED,
        )


def test_gate_report_rejects_blocking_gate_when_no_failed_stage():
    with pytest.raises(ValidationError):
        GateReport(
            case_id="case-1",
            provider="searxng",
            verdict=GateVerdict.FAIL_CLOSED,
            stage_results=[
                GateStageResult(
                    stage=QualityGateStage.SEARCH_RECALL,
                    passed=True,
                )
            ],
            blocking_gate=QualityGateStage.PARAMETERIZATION,
            failure_codes=[FailureCode.PARAMETER_MISSING],
            artifact_counts={"evidence_cards": 1},
            unsupported_claim_count=0,
        )
