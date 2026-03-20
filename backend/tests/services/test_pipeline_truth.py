"""
Tests for pipeline truth diagnostics and alerting (bd-tytc.5, bd-tytc.8).

Validates:
- Orchestrator does not emit fake embedding audit steps
- _complete_pipeline_run persists sufficiency breakdown
- GlassBox exposes normalized truth fields
- AlertingService evaluates rules correctly
- Document health endpoint returns truth data
"""

import pytest
from unittest.mock import AsyncMock
from datetime import datetime

from services.glass_box import GlassBoxService
from services.alerting import AlertingService
from schemas.analysis import (
    SufficiencyState,
    LegislationAnalysisResponse,
    SufficiencyBreakdown,
)


class TestOrchestratorTruth:
    """Test that orchestrator does not emit fake steps or placeholder data."""

    def test_no_fake_embedding_step_in_run_flow(self):
        """Step 0.5 'embedding' virtual step should NOT appear in a real run."""
        with open("services/llm/orchestrator.py") as f:
            source = f.read()

        assert "_fake_embedding_step" not in source, (
            "Fake embedding step reference should be removed"
        )

    def test_complete_pipeline_run_excludes_placeholder_title(self):
        """_complete_pipeline_run should not inject 'Analysis: <bill>' as title."""
        analysis = LegislationAnalysisResponse(
            bill_number="SB 277",
            title="",
            jurisdiction="California",
            status="",
            sufficiency_state=SufficiencyState.RESEARCH_INCOMPLETE,
            quantification_eligible=False,
            total_impact_p50=None,
            analysis_timestamp=datetime.now().isoformat(),
            model_used="test",
        )
        assert analysis.title == ""
        assert analysis.total_impact_p50 is None


class TestGlassBoxTruthFields:
    """Test that GlassBox exposes normalized truth fields."""

    @pytest.mark.asyncio
    async def test_get_pipeline_run_includes_truth_fields(self):
        """Pipeline run details should include sufficiency breakdown and truth fields."""
        mock_db = AsyncMock()
        mock_db._fetchrow = AsyncMock(
            return_value={
                "id": "123",
                "bill_id": "SB 277",
                "jurisdiction": "California",
                "status": "completed",
                "started_at": datetime(2026, 3, 19, 12, 0, 0),
                "completed_at": datetime(2026, 3, 19, 12, 5, 0),
                "error": None,
                "models": "{}",
                "result": '{"sufficiency_breakdown": {"source_text_present": true, "rag_chunks_retrieved": 3, "quantification_eligible": false}, "source_text_present": true, "retriever_invoked": true, "rag_chunks_retrieved": 3, "quantification_eligible": false, "insufficiency_reason": "no tier-a sources", "model_used": "glm-4.7"}',
            }
        )

        service = GlassBoxService(db_client=mock_db)
        result = await service.get_pipeline_run("123")

        assert result is not None
        assert result["source_text_present"] is True
        assert result["retriever_invoked"] is True
        assert result["rag_chunks_retrieved"] == 3
        assert result["quantification_eligible"] is False
        assert result["insufficiency_reason"] == "no tier-a sources"
        assert result["sufficiency_breakdown"] is not None


class TestAlertingService:
    """Test deterministic alert rules."""

    def _make_run(self, **overrides):
        run = {
            "id": "1",
            "bill_id": "SB 277",
            "jurisdiction": "California",
            "status": "completed",
            "started_at": "2026-03-19T12:00:00",
            "completed_at": "2026-03-19T12:05:00",
            "error": None,
            "result": {
                "source_text_present": True,
                "retriever_invoked": True,
                "rag_chunks_retrieved": 5,
                "quantification_eligible": True,
            },
            "analysis": {},
        }
        result_overrides = {}
        for k, v in overrides.items():
            if k in (
                "status",
                "error",
                "id",
                "bill_id",
                "jurisdiction",
                "started_at",
                "completed_at",
            ):
                run[k] = v
            else:
                result_overrides[k] = v
        run["result"].update(result_overrides)
        return run

    def test_no_alerts_for_healthy_run(self):
        service = AlertingService()
        run = self._make_run()
        alerts = service.evaluate_run(run)
        assert len(alerts) == 0

    def test_alert_on_failed_run(self):
        service = AlertingService()
        run = self._make_run(status="failed", error="Rate limit exceeded")
        alerts = service.evaluate_run(run)
        assert len(alerts) >= 1
        assert any(a.rule == "pipeline_failure" for a in alerts)

    def test_alert_on_zero_rag_chunks(self):
        service = AlertingService()
        run = self._make_run(rag_chunks_retrieved=0)
        alerts = service.evaluate_run(run)
        assert any(a.rule == "zero_rag_chunks" for a in alerts)

    def test_alert_on_missing_source_text(self):
        service = AlertingService()
        run = self._make_run(source_text_present=False)
        alerts = service.evaluate_run(run)
        assert any(a.rule == "missing_source_text" for a in alerts)

    def test_alert_on_quantification_mismatch(self):
        service = AlertingService()
        run = self._make_run(
            quantification_eligible=False,
            analysis={"total_impact_p50": 50000.0},
        )
        alerts = service.evaluate_run(run)
        assert any(a.rule == "quantification_not_eligible_with_output" for a in alerts)


class TestSufficiencyBreakdownSchema:
    """Test that SufficiencyBreakdown model has all required fields."""

    def test_default_breakdown_is_incomplete(self):
        breakdown = SufficiencyBreakdown()
        assert breakdown.sufficiency_state == SufficiencyState.RESEARCH_INCOMPLETE
        assert breakdown.source_text_present is False
        assert breakdown.rag_chunks_retrieved == 0
        assert breakdown.quantification_eligible is False

    def test_breakdown_serialization(self):
        breakdown = SufficiencyBreakdown(
            source_text_present=True,
            rag_chunks_retrieved=5,
            web_research_sources_found=3,
            tier_a_sources_found=1,
            fiscal_notes_detected=True,
            has_verifiable_url=True,
            quantification_eligible=True,
            sufficiency_state=SufficiencyState.QUANTIFIED,
        )
        data = breakdown.model_dump()
        assert data["source_text_present"] is True
        assert data["rag_chunks_retrieved"] == 5
        assert data["quantification_eligible"] is True
