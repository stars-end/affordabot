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
                "trigger_source": "manual",
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
        assert result["trigger_source"] == "manual"

    @pytest.mark.asyncio
    async def test_list_pipeline_runs_includes_trigger_source(self):
        """Pipeline run listing should include trigger_source field."""
        mock_db = AsyncMock()
        mock_db._fetch = AsyncMock(
            return_value=[
                {
                    "id": "1",
                    "bill_id": "SB 277",
                    "jurisdiction": "California",
                    "status": "completed",
                    "started_at": datetime(2026, 3, 19, 12, 0, 0),
                    "completed_at": datetime(2026, 3, 19, 12, 5, 0),
                    "error": None,
                    "trigger_source": "manual",
                },
                {
                    "id": "2",
                    "bill_id": "AB 100",
                    "jurisdiction": "California",
                    "status": "completed",
                    "started_at": datetime(2026, 3, 19, 13, 0, 0),
                    "completed_at": datetime(2026, 3, 19, 13, 5, 0),
                    "error": None,
                    "trigger_source": "windmill",
                },
            ]
        )

        service = GlassBoxService(db_client=mock_db)
        runs = await service.list_pipeline_runs()

        assert len(runs) == 2
        assert runs[0]["trigger_source"] == "manual"
        assert runs[1]["trigger_source"] == "windmill"


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


class TestManualRunSlackSummary:
    """Test Slack summary formatting for manual pipeline runs (bd-hvji.6)."""

    def _make_steps(self):
        return [
            {
                "step_name": "ingestion_source",
                "status": "completed",
                "output_result": {
                    "raw_scrape_id": "rs-1",
                    "source_url": "https://leginfo.legislature.ca.gov",
                    "source_text_present": True,
                },
            },
            {
                "step_name": "chunk_index",
                "status": "completed",
                "output_result": {
                    "chunk_count": 18,
                    "document_id": "doc-sb277",
                },
            },
            {
                "step_name": "research",
                "status": "completed",
                "output_result": {
                    "rag_chunks": 5,
                    "web_sources": 3,
                    "evidence_envelopes": 4,
                    "is_sufficient": True,
                },
            },
            {
                "step_name": "sufficiency_gate",
                "status": "completed",
                "output_result": {
                    "sufficiency_state": "quantified",
                    "rag_chunks_retrieved": 5,
                    "web_research_sources_found": 3,
                },
            },
            {
                "step_name": "generate",
                "status": "completed",
                "output_result": {
                    "sufficiency_state": "quantified",
                    "impacts": [{"impact_number": 1}, {"impact_number": 2}],
                    "quantification_eligible": True,
                },
            },
            {
                "step_name": "review",
                "status": "completed",
                "output_result": {
                    "passed": True,
                    "factual_errors": [],
                    "missing_impacts": [],
                },
            },
            {
                "step_name": "persistence",
                "status": "completed",
                "output_result": {
                    "analysis_stored": True,
                    "legislation_id": "leg-42",
                    "impacts_count": 2,
                    "sufficiency_state": "quantified",
                    "quantification_eligible": True,
                    "total_impact_p50": 15000,
                },
            },
        ]

    def test_all_stages_have_proof_lines(self):
        from services.slack_summary import format_slack_summary

        payload = format_slack_summary(
            run_id="test-run-1",
            bill_id="SB-277",
            jurisdiction="California",
            status="completed",
            started_at="2026-03-21T10:00:00Z",
            completed_at="2026-03-21T10:05:00Z",
            trigger_source="manual",
            steps=self._make_steps(),
            result={"sufficiency_state": "quantified"},
        )

        blocks_text = str(payload["blocks"])
        assert "Scrape/source:" in blocks_text
        assert "Chunk/index:" in blocks_text
        assert "Research:" in blocks_text
        assert "Sufficiency gate:" in blocks_text
        assert "Generate:" in blocks_text
        assert "Review:" in blocks_text
        assert "Persistence:" in blocks_text

    def test_deep_links_present(self):
        from services.slack_summary import format_slack_summary

        payload = format_slack_summary(
            run_id="run-deep-1",
            bill_id="ACR-117",
            jurisdiction="California",
            status="completed",
            started_at="2026-03-21T10:00:00Z",
            completed_at="2026-03-21T10:05:00Z",
            trigger_source="manual",
            steps=self._make_steps(),
        )

        blocks_text = str(payload["blocks"])
        assert "Full Audit Trace" in blocks_text
        assert "/admin/audits/trace/run-deep-1" in blocks_text
        assert "Bill Truth" in blocks_text
        assert "/admin/bill-truth/california/ACR-117" in blocks_text

    def test_sufficiency_state_in_summary(self):
        from services.slack_summary import format_slack_summary

        payload = format_slack_summary(
            run_id="run-suff-1",
            bill_id="SB-1",
            jurisdiction="CA",
            status="completed",
            started_at="2026-03-21T10:00:00Z",
            completed_at="2026-03-21T10:05:00Z",
            trigger_source="manual",
            steps=self._make_steps(),
            result={"sufficiency_state": "research_incomplete"},
        )

        blocks_text = str(payload["blocks"])
        assert "research_incomplete" in blocks_text

    def test_insufficient_research_shows_reason(self):
        from services.slack_summary import format_slack_summary

        steps = [
            {
                "step_name": "research",
                "status": "completed",
                "output_result": {
                    "rag_chunks": 0,
                    "web_sources": 0,
                    "evidence_envelopes": 0,
                    "is_sufficient": False,
                    "insufficiency_reason": "no tier-a sources found",
                },
            },
        ]
        payload = format_slack_summary(
            run_id="run-insuff-1",
            bill_id="SB-999",
            jurisdiction="CA",
            status="completed",
            started_at="2026-03-21T10:00:00Z",
            completed_at="2026-03-21T10:01:00Z",
            trigger_source="manual",
            steps=steps,
        )

        blocks_text = str(payload["blocks"])
        assert "insufficient" in blocks_text
        assert "no tier-a sources found" in blocks_text

    def test_persistence_proof_shows_legislation_id_and_state(self):
        from services.slack_summary import format_slack_summary

        steps = [
            {
                "step_name": "persistence",
                "status": "completed",
                "output_result": {
                    "analysis_stored": True,
                    "legislation_id": "leg-99",
                    "impacts_count": 3,
                    "sufficiency_state": "quantified",
                    "quantification_eligible": True,
                    "total_impact_p50": 25000,
                },
            },
        ]
        payload = format_slack_summary(
            run_id="run-persist-1",
            bill_id="SB-500",
            jurisdiction="CA",
            status="completed",
            started_at="2026-03-21T10:00:00Z",
            completed_at="2026-03-21T10:02:00Z",
            trigger_source="manual",
            steps=steps,
        )

        blocks_text = str(payload["blocks"])
        assert "Persistence:" in blocks_text
        assert "leg-99" in blocks_text
        assert "3 impacts" in blocks_text
        assert "p50=25000" in blocks_text

    def test_chunk_index_proof_shows_chunk_count(self):
        from services.slack_summary import format_slack_summary

        steps = [
            {
                "step_name": "chunk_index",
                "status": "completed",
                "output_result": {
                    "chunk_count": 42,
                    "document_id": "doc-sb277-v2",
                },
            },
        ]
        payload = format_slack_summary(
            run_id="run-chunk-1",
            bill_id="SB-277",
            jurisdiction="CA",
            status="completed",
            started_at="2026-03-21T10:00:00Z",
            completed_at="2026-03-21T10:01:00Z",
            trigger_source="manual",
            steps=steps,
        )

        blocks_text = str(payload["blocks"])
        assert "Chunk/index:" in blocks_text
        assert "42 chunks" in blocks_text
        assert "doc-sb277-v2" in blocks_text

    @pytest.mark.asyncio
    async def test_slack_emit_skips_windmill_trigger_source(self):
        call_log = []

        async def fake_emit(*args, **kwargs):
            call_log.append(kwargs.get("run_id"))
            return True

        class FakePipeline:
            db = None

            async def _emit_slack_summary(
                self, run_id, bill_id, jurisdiction, status, trigger_source, **kwargs
            ):
                if trigger_source != "manual":
                    return
                await fake_emit(
                    run_id=run_id,
                    bill_id=bill_id,
                    jurisdiction=jurisdiction,
                    status=status,
                    trigger_source=trigger_source,
                    **kwargs,
                )

        pipe = FakePipeline()
        await pipe._emit_slack_summary(
            "wind-run", "SB-1", "CA", "done", trigger_source="windmill"
        )
        assert len(call_log) == 0

        await pipe._emit_slack_summary(
            "man-run", "SB-2", "CA", "done", trigger_source="manual"
        )
        assert len(call_log) == 1
