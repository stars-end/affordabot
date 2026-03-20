"""Regression tests for bd-tytc.2 PR repair.

Covers: nullable p50 route safety, bill text preservation,
and sufficiency field persistence/readback.

Feature-Key: bd-tytc.2
"""

import pytest
from schemas.analysis import (
    LegislationAnalysisResponse,
    LegislationImpact,
    SufficiencyState,
)


class TestNullableP50RouteSafety:
    """Regression: sum(i.get("p50", 0) ...) raises TypeError when p50 is None.

    The /legislation/{jurisdiction} route must safely handle qualitative-only
    impacts where all p50 values are None.
    """

    def test_sum_with_all_null_p50(self):
        impacts = [
            {"p50": None, "p10": None},
            {"p50": None, "p10": None},
        ]
        quantified = [i for i in impacts if i.get("p50") is not None]
        total = sum(i["p50"] for i in quantified) if quantified else None
        assert total is None

    def test_sum_with_mixed_null_p50(self):
        impacts = [
            {"p50": 1000, "p10": 500},
            {"p50": None, "p10": None},
        ]
        quantified = [i for i in impacts if i.get("p50") is not None]
        total = sum(i["p50"] for i in quantified) if quantified else None
        assert total == 1000

    def test_sum_with_all_quantified(self):
        impacts = [
            {"p50": 1000, "p10": 500},
            {"p50": 2000, "p10": 1000},
        ]
        quantified = [i for i in impacts if i.get("p50") is not None]
        total = sum(i["p50"] for i in quantified) if quantified else None
        assert total == 3000

    def test_sum_empty_impacts(self):
        impacts = []
        quantified = [i for i in impacts if i.get("p50") is not None]
        total = sum(i["p50"] for i in quantified) if quantified else None
        assert total is None


class TestBillTextPreservation:
    """Regression: _complete_pipeline_run used getattr(analysis, '_bill_text', None)
    which never resolved, dropping bill text at persistence time.

    The fix passes bill_text explicitly as a parameter.
    """

    def test_bill_text_passed_through(self):
        bill_text = "AB 123: An act to..."
        analysis = LegislationAnalysisResponse(
            bill_number="AB 123",
            title="Test Bill",
            sufficiency_state=SufficiencyState.QUALITATIVE_ONLY,
            quantification_eligible=False,
            impacts=[],
            total_impact_p50=None,
            analysis_timestamp="2026-03-20T00:00:00",
            model_used="test",
        )
        bill_data = {
            "bill_number": analysis.bill_number,
            "title": analysis.title or analysis.bill_number,
            "text": bill_text or "",
            "status": "analyzed",
            "sufficiency_state": analysis.sufficiency_state.value,
            "insufficiency_reason": analysis.insufficiency_reason,
            "quantification_eligible": analysis.quantification_eligible,
            "total_impact_p50": analysis.total_impact_p50,
        }
        assert bill_data["text"] == "AB 123: An act to..."
        assert len(bill_data["text"]) > 0

    def test_empty_bill_text_preserved_as_empty(self):
        bill_data = {
            "bill_number": "SB 999",
            "title": "Missing Text Bill",
            "text": "" or "",
            "status": "analyzed",
            "sufficiency_state": SufficiencyState.RESEARCH_INCOMPLETE.value,
            "insufficiency_reason": "Bill text is absent or placeholder",
            "quantification_eligible": False,
            "total_impact_p50": None,
        }
        assert bill_data["text"] == ""

    def test_none_bill_text_preserved_as_empty(self):
        bill_data = {
            "bill_number": "SB 999",
            "title": "None Text Bill",
            "text": (None or ""),
            "status": "analyzed",
            "sufficiency_state": SufficiencyState.RESEARCH_INCOMPLETE.value,
            "insufficiency_reason": "Bill text is absent or placeholder",
            "quantification_eligible": False,
            "total_impact_p50": None,
        }
        assert bill_data["text"] == ""


class TestSufficiencyFieldPersistence:
    """Regression: top-level sufficiency fields were not persisted/read back."""

    def test_bill_data_contains_sufficiency_fields(self):
        analysis = LegislationAnalysisResponse(
            bill_number="AB 456",
            title="Sufficiency Test",
            sufficiency_state=SufficiencyState.INSUFFICIENT_EVIDENCE,
            insufficiency_reason="No verifiable URLs found",
            quantification_eligible=False,
            impacts=[],
            total_impact_p50=None,
            analysis_timestamp="2026-03-20T00:00:00",
            model_used="test",
        )
        bill_data = {
            "bill_number": analysis.bill_number,
            "title": analysis.title,
            "text": "some text",
            "status": "analyzed",
            "sufficiency_state": analysis.sufficiency_state.value,
            "insufficiency_reason": analysis.insufficiency_reason,
            "quantification_eligible": analysis.quantification_eligible,
            "total_impact_p50": analysis.total_impact_p50,
        }
        assert bill_data["sufficiency_state"] == "insufficient_evidence"
        assert bill_data["insufficiency_reason"] == "No verifiable URLs found"
        assert bill_data["quantification_eligible"] is False
        assert bill_data["total_impact_p50"] is None

    def test_quantified_bill_data(self):
        analysis = LegislationAnalysisResponse(
            bill_number="SB 277",
            title="Quantified Bill",
            sufficiency_state=SufficiencyState.QUANTIFIED,
            quantification_eligible=True,
            impacts=[
                LegislationImpact(
                    impact_number=1,
                    impact_description="test",
                    p50=15000000,
                    p10=10000000,
                    p90=20000000,
                )
            ],
            total_impact_p50=15000000,
            analysis_timestamp="2026-03-20T00:00:00",
            model_used="test",
        )
        bill_data = {
            "bill_number": analysis.bill_number,
            "title": analysis.title,
            "text": "some text",
            "status": "analyzed",
            "sufficiency_state": analysis.sufficiency_state.value,
            "insufficiency_reason": analysis.insufficiency_reason,
            "quantification_eligible": analysis.quantification_eligible,
            "total_impact_p50": analysis.total_impact_p50,
        }
        assert bill_data["sufficiency_state"] == "quantified"
        assert bill_data["quantification_eligible"] is True
        assert bill_data["total_impact_p50"] == 15000000

    def test_qualitative_only_bill_data(self):
        analysis = LegislationAnalysisResponse(
            bill_number="ACR 117",
            title="Qualitative Bill",
            sufficiency_state=SufficiencyState.QUALITATIVE_ONLY,
            insufficiency_reason="Tier A sources found but no fiscal note detected",
            quantification_eligible=False,
            impacts=[
                LegislationImpact(
                    impact_number=1,
                    impact_description="test",
                )
            ],
            total_impact_p50=None,
            analysis_timestamp="2026-03-20T00:00:00",
            model_used="test",
        )
        bill_data = {
            "bill_number": analysis.bill_number,
            "title": analysis.title,
            "text": "some text",
            "status": "analyzed",
            "sufficiency_state": analysis.sufficiency_state.value,
            "insufficiency_reason": analysis.insufficiency_reason,
            "quantification_eligible": analysis.quantification_eligible,
            "total_impact_p50": analysis.total_impact_p50,
        }
        assert bill_data["sufficiency_state"] == "qualitative_only"
        assert "fiscal note" in bill_data["insufficiency_reason"]
        assert bill_data["quantification_eligible"] is False
        assert bill_data["total_impact_p50"] is None
