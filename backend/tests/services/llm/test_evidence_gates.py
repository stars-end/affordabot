import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

import pytest
from schemas.analysis import (
    ImpactEvidence,
    SourceTier,
    SufficiencyState,
    LegislationImpact,
    LegislationAnalysisResponse,
    PersistedEvidence,
    SufficiencyBreakdown,
)
from services.llm.evidence_gates import (
    assess_sufficiency,
    strip_quantification,
    _is_placeholder_text,
    _has_verifiable_url,
    _detect_fiscal_notes,
)


class TestPlaceholderDetection:
    def test_empty_string_is_placeholder(self):
        assert _is_placeholder_text("") is True

    def test_whitespace_only_is_placeholder(self):
        assert _is_placeholder_text("   ") is True

    def test_none_like_is_placeholder(self):
        assert _is_placeholder_text(None) is True

    def test_introduced_is_placeholder(self):
        assert _is_placeholder_text("Introduced") is True

    def test_title_only_is_placeholder(self):
        assert _is_placeholder_text("Title only") is True

    def test_n_a_is_placeholder(self):
        assert _is_placeholder_text("N/A") is True

    def test_real_bill_text_is_not_placeholder(self):
        text = "SECTION 1. The Legislature hereby finds and declares that housing affordability is a matter of statewide concern."
        assert _is_placeholder_text(text) is False

    def test_placeholder_case_insensitive(self):
        assert _is_placeholder_text("INTRODUCED") is True
        assert _is_placeholder_text("introduced") is True


class TestVerifiableURL:
    def test_no_evidence(self):
        assert _has_verifiable_url([]) is False

    def test_empty_url(self):
        assert (
            _has_verifiable_url(
                [ImpactEvidence(url="", source_name="test", excerpt="")]
            )
            is False
        )

    def test_non_http_url(self):
        with pytest.raises(Exception):
            ImpactEvidence(url="ftp://bad", source_name="test", excerpt="")

    def test_valid_http_url(self):
        evidence = ImpactEvidence(
            url="https://leginfo.legislature.ca.gov/faces/billTextClient.xhtml",
            source_name="CA Legislature",
            excerpt="Bill text",
        )
        assert _has_verifiable_url([evidence]) is True

    def test_short_url_rejected(self):
        evidence = ImpactEvidence(url="https://a.b", source_name="test", excerpt="")
        assert _has_verifiable_url([evidence]) is False


class TestFiscalNoteDetection:
    def test_detects_fiscal_note_in_excerpt(self):
        evidence = ImpactEvidence(
            url="https://lao.ca.gov",
            source_name="LAO",
            excerpt="The fiscal impact of this bill is estimated at $15M annually.",
        )
        assert _detect_fiscal_notes([evidence]) is True

    def test_detects_fiscal_in_source_name(self):
        evidence = ImpactEvidence(
            url="https://example.com",
            source_name="Fiscal Committee Analysis",
            excerpt="Some text",
        )
        assert _detect_fiscal_notes([evidence]) is True

    def test_no_fiscal_note(self):
        evidence = ImpactEvidence(
            url="https://example.com",
            source_name="News Article",
            excerpt="This bill was discussed in committee.",
        )
        assert _detect_fiscal_notes([evidence]) is False

    def test_detects_cost_estimate(self):
        evidence = ImpactEvidence(
            url="https://example.gov",
            source_name="Budget Office",
            excerpt="Cost estimate analysis for the program.",
        )
        assert _detect_fiscal_notes([evidence]) is True


class TestAssessSufficiency:
    def test_empty_bill_text_returns_research_incomplete(self):
        result = assess_sufficiency("", [])
        assert result.sufficiency_state == SufficiencyState.RESEARCH_INCOMPLETE
        assert result.quantification_eligible is False
        assert not result.bill_text_present

    def test_placeholder_bill_text_returns_research_incomplete(self):
        result = assess_sufficiency("Introduced", [])
        assert result.sufficiency_state == SufficiencyState.RESEARCH_INCOMPLETE
        assert result.bill_text_is_placeholder is True

    def test_real_text_no_evidence_returns_insufficient(self):
        result = assess_sufficiency(
            "SECTION 1. The Legislature finds housing affordability is critical.",
            [],
        )
        assert result.sufficiency_state == SufficiencyState.INSUFFICIENT_EVIDENCE
        assert result.quantification_eligible is False

    def test_real_text_with_tier_b_only_returns_qualitative_only(self):
        evidence = [
            ImpactEvidence(
                url="https://thinktank.org/report",
                source_name="Think Tank Report",
                excerpt="Analysis of housing costs.",
            )
        ]
        result = assess_sufficiency(
            "SECTION 1. Housing affordability is critical.",
            evidence,
        )
        assert result.sufficiency_state == SufficiencyState.QUALITATIVE_ONLY
        assert result.quantification_eligible is False

    def test_tier_a_without_fiscal_returns_qualitative_only(self):
        evidence = [
            ImpactEvidence(
                url="https://leginfo.legislature.ca.gov/bill",
                source_name="CA Legislature",
                excerpt="Full bill text available.",
                source_tier=SourceTier.TIER_A,
            )
        ]
        result = assess_sufficiency(
            "SECTION 1. The Legislature finds...",
            evidence,
        )
        assert result.sufficiency_state == SufficiencyState.QUALITATIVE_ONLY
        assert result.quantification_eligible is False
        assert any("fiscal" in r.lower() for r in result.insufficiency_reasons)

    def test_tier_a_with_fiscal_note_returns_quantified(self):
        evidence = [
            ImpactEvidence(
                url="https://lao.ca.gov/fiscal-note",
                source_name="Legislative Analyst",
                excerpt="Fiscal impact: estimated $50M annual cost to state.",
                source_tier=SourceTier.TIER_A,
            )
        ]
        result = assess_sufficiency(
            "SECTION 1. Housing affordability is critical.",
            evidence,
        )
        assert result.sufficiency_state == SufficiencyState.QUANTIFIED
        assert result.quantification_eligible is True
        assert result.fiscal_notes_detected is True

    def test_sb277_title_only_cannot_quantify(self):
        result = assess_sufficiency("Introduced", [])
        assert result.quantification_eligible is False

    def test_no_web_research_and_no_rag_with_no_evidence_adds_reason(self):
        result = assess_sufficiency(
            "SECTION 1. Bill text here.",
            [],
            rag_chunks_retrieved=0,
            web_research_count=0,
        )
        assert "No evidence items collected" in result.insufficiency_reasons


class TestStripQuantification:
    def test_removes_all_percentile_fields(self):
        impacts = [
            {
                "impact_number": 1,
                "p10": 100.0,
                "p25": 200.0,
                "p50": 300.0,
                "p75": 400.0,
                "p90": 500.0,
                "numeric_basis": "fiscal note",
                "estimate_method": "linear extrapolation",
                "assumptions": "constant rate",
                "description": "test",
            }
        ]
        result = strip_quantification(impacts)
        assert result[0].get("p10") is None
        assert result[0].get("p50") is None
        assert result[0].get("p90") is None
        assert result[0].get("numeric_basis") is None
        assert result[0].get("description") == "test"

    def test_empty_list(self):
        assert strip_quantification([]) == []


class TestSchemaOptionalFields:
    def test_impact_without_quantification_is_valid(self):
        impact = LegislationImpact(
            impact_number=1,
            impact_description="Qualitative analysis only",
        )
        assert impact.p50 is None
        assert impact.is_quantified is False
        assert impact.model_dump()["p10"] is None

    def test_impact_with_quantification(self):
        impact = LegislationImpact(
            impact_number=1,
            impact_description="Cost impact",
            p10=100.0,
            p25=200.0,
            p50=300.0,
            p75=400.0,
            p90=500.0,
        )
        assert impact.is_quantified is True
        assert impact.p50 == 300.0

    def test_response_defaults_to_research_incomplete(self):
        resp = LegislationAnalysisResponse(
            bill_number="SB-277",
            analysis_timestamp="2026-01-01T00:00:00",
            model_used="test",
        )
        assert resp.sufficiency_state == SufficiencyState.RESEARCH_INCOMPLETE
        assert resp.quantification_eligible is False
        assert resp.total_impact_p50 is None

    def test_evidence_url_validation_rejects_non_http(self):
        with pytest.raises(Exception):
            ImpactEvidence(
                url="fake-url-not-http",
                source_name="Bad Source",
                excerpt="test",
            )

    def test_empty_evidence_list_valid(self):
        impact = LegislationImpact(
            impact_number=1,
            impact_description="test",
            evidence=[],
        )
        assert impact.evidence == []
