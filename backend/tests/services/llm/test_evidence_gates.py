import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from schemas.analysis import (  # noqa: E402
    ExcerptValidationStatus,
    FailureCode,
    ImpactEvidence,
    ImpactMode,
    SourceHierarchyStatus,
    SufficiencyState,
)
from services.llm.evidence_gates import (  # noqa: E402
    _is_placeholder_text,
    assess_impact_sufficiency,
    assess_sufficiency,
    strip_quantification,
)


class TestPlaceholderDetection:
    def test_placeholder_detection(self):
        assert _is_placeholder_text("") is True
        assert _is_placeholder_text("Introduced") is True
        assert _is_placeholder_text("SECTION 1. This Act amends...") is False


class TestImpactLevelSufficiency:
    def _base_retrieval_status(self):
        return {
            "source_text_present": True,
            "rag_chunks_retrieved": 3,
            "web_research_sources_found": 2,
            "has_verifiable_url": True,
        }

    def test_supported_direct_fiscal_quantifies_when_clean(self):
        summary = assess_impact_sufficiency(
            impact_id="imp-1",
            selected_mode=ImpactMode.DIRECT_FISCAL,
            parameter_resolution={
                "required_parameters": ["fiscal_amount"],
                "resolved_parameters": {
                    "fiscal_amount": {
                        "name": "fiscal_amount",
                        "value": 15000000.0,
                        "source_url": "https://example.gov/fiscal-note",
                        "source_excerpt": "Estimated cost is $15M annually.",
                    }
                },
                "missing_parameters": [],
                "source_hierarchy_status": {
                    "fiscal_amount": SourceHierarchyStatus.BILL_OR_REG_TEXT
                },
                "excerpt_validation_status": {
                    "fiscal_amount": ExcerptValidationStatus.PASS
                },
                "literature_confidence": {"fiscal_amount": 0.2},
                "dominant_uncertainty_parameters": ["fiscal_amount"],
            },
            parameter_validation={
                "schema_valid": True,
                "arithmetic_valid": True,
                "bound_construction_valid": True,
                "claim_support_valid": True,
                "validation_failures": [],
            },
            retrieval_prerequisite_status=self._base_retrieval_status(),
        )
        assert summary.selected_mode == ImpactMode.DIRECT_FISCAL
        assert summary.quantification_eligible is True
        assert summary.sufficiency_state == SufficiencyState.QUANTIFIED
        assert summary.gate_failures == []

    def test_unsupported_mode_degrades_to_qualitative_only(self):
        summary = assess_impact_sufficiency(
            impact_id="imp-2",
            selected_mode="market_pass_through",
            parameter_resolution=None,
            parameter_validation=None,
            retrieval_prerequisite_status=self._base_retrieval_status(),
        )
        assert summary.selected_mode == ImpactMode.QUALITATIVE_ONLY
        assert summary.quantification_eligible is False
        assert summary.sufficiency_state == SufficiencyState.QUALITATIVE_ONLY

    def test_compliance_cost_frequency_source_hierarchy_fail_closed(self):
        summary = assess_impact_sufficiency(
            impact_id="imp-3",
            selected_mode=ImpactMode.COMPLIANCE_COST,
            parameter_resolution={
                "required_parameters": ["population", "frequency", "time_burden", "wage_rate"],
                "resolved_parameters": {},
                "missing_parameters": [],
                "source_hierarchy_status": {
                    "population": SourceHierarchyStatus.BILL_OR_REG_TEXT,
                    "frequency": SourceHierarchyStatus.FAILED_CLOSED,
                    "time_burden": SourceHierarchyStatus.BILL_OR_REG_TEXT,
                    "wage_rate": SourceHierarchyStatus.BILL_OR_REG_TEXT,
                },
                "excerpt_validation_status": {
                    "population": ExcerptValidationStatus.PASS,
                    "frequency": ExcerptValidationStatus.PASS,
                    "time_burden": ExcerptValidationStatus.PASS,
                    "wage_rate": ExcerptValidationStatus.PASS,
                },
                "literature_confidence": {"wage_rate": 0.1},
                "dominant_uncertainty_parameters": ["time_burden"],
            },
            parameter_validation={
                "schema_valid": True,
                "arithmetic_valid": True,
                "bound_construction_valid": True,
                "claim_support_valid": True,
                "validation_failures": [],
            },
            retrieval_prerequisite_status=self._base_retrieval_status(),
        )
        assert summary.quantification_eligible is False
        assert FailureCode.SOURCE_HIERARCHY_FAILED in summary.gate_failures

    def test_invalid_bound_construction_fails_closed(self):
        summary = assess_impact_sufficiency(
            impact_id="imp-4",
            selected_mode=ImpactMode.DIRECT_FISCAL,
            parameter_resolution={
                "required_parameters": ["fiscal_amount"],
                "resolved_parameters": {},
                "missing_parameters": [],
                "source_hierarchy_status": {
                    "fiscal_amount": SourceHierarchyStatus.BILL_OR_REG_TEXT
                },
                "excerpt_validation_status": {
                    "fiscal_amount": ExcerptValidationStatus.PASS
                },
                "literature_confidence": {},
                "dominant_uncertainty_parameters": [],
            },
            parameter_validation={
                "schema_valid": True,
                "arithmetic_valid": True,
                "bound_construction_valid": False,
                "claim_support_valid": True,
                "validation_failures": [],
            },
            retrieval_prerequisite_status=self._base_retrieval_status(),
        )
        assert summary.quantification_eligible is False
        assert FailureCode.INVALID_SCENARIO_CONSTRUCTION in summary.gate_failures


class TestBillLevelSufficiency:
    def test_bill_summary_is_derived_from_impacts(self):
        evidence = [
            ImpactEvidence(
                url="https://example.gov/fiscal-note",
                source_name="Official Fiscal Note",
                excerpt="Estimated cost is $10M annually.",
            )
        ]
        result = assess_sufficiency(
            bill_text="SECTION 1. The legislature finds...",
            evidence_list=evidence,
            rag_chunks_retrieved=3,
            web_research_count=1,
            candidate_impacts=[
                {
                    "impact_id": "imp-1",
                    "selected_mode": "direct_fiscal",
                    "parameter_resolution": {
                        "required_parameters": ["fiscal_amount"],
                        "resolved_parameters": {},
                        "missing_parameters": [],
                        "source_hierarchy_status": {
                            "fiscal_amount": "bill_or_reg_text"
                        },
                        "excerpt_validation_status": {"fiscal_amount": "pass"},
                        "literature_confidence": {},
                        "dominant_uncertainty_parameters": ["fiscal_amount"],
                    },
                    "parameter_validation": {
                        "schema_valid": True,
                        "arithmetic_valid": True,
                        "bound_construction_valid": True,
                        "claim_support_valid": True,
                        "validation_failures": [],
                    },
                },
                {
                    "impact_id": "imp-2",
                    "selected_mode": "market_pass_through",
                    "parameter_resolution": None,
                    "parameter_validation": None,
                },
            ],
        )
        assert result.overall_quantification_eligible is True
        assert result.overall_sufficiency_state == SufficiencyState.QUANTIFIED
        assert len(result.impact_gate_summaries) == 2
        assert result.impact_gate_summaries[1].selected_mode == ImpactMode.QUALITATIVE_ONLY

    def test_empty_candidate_impacts_fail_closed(self):
        result = assess_sufficiency(
            bill_text="SECTION 1. The legislature finds...",
            evidence_list=[],
            candidate_impacts=[],
            rag_chunks_retrieved=0,
            web_research_count=0,
        )
        assert result.overall_quantification_eligible is False
        assert FailureCode.IMPACT_DISCOVERY_FAILED in result.bill_level_failures


class TestStripQuantification:
    def test_quantitative_payloads_are_removed(self):
        impacts = [
            {
                "impact_id": "imp-1",
                "impact_mode": "direct_fiscal",
                "modeled_parameters": {"x": 1},
                "component_breakdown": [{"component_name": "x"}],
                "scenario_bounds": {"conservative": 1, "central": 2, "aggressive": 3},
            }
        ]
        cleaned = strip_quantification(impacts)
        assert cleaned[0]["impact_mode"] == "qualitative_only"
        assert "modeled_parameters" not in cleaned[0]
        assert "scenario_bounds" not in cleaned[0]
