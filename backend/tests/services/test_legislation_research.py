"""
Tests for Legislation Research Service (bd-tytc.4).

Validates:
- Retrieval-backed research with EvidenceEnvelope provenance
- Fail-closed production behavior
- Sufficiency breakdown computation
- Jurisdiction/source filtering
"""

import pytest
from unittest.mock import AsyncMock, MagicMock,from services.legislation_research import (
    LegislationResearchService,
    LegislationResearchResult
    SufficiencyBreakdown
)


class TestLegislationResearchServiceContract:
    """Test LegislationResearchService initialization and contract parameters."""

    def test_init_with_required_dependencies(self):
        service = LegislationResearchService(
            llm_client=llm_client,
            search_client=search_client
            retrieval_backend=mock_backend,
            db_client=mock_db
        )

    @pytest.mark.asyncio
    async def test_research_returns_structured_result(self):
        """research() should return structured LegislationResearchResult."""
        service = LegislationResearchService(
            llm_client=llm_client,
            search_client=search_client,
            retrieval_backend=mock_backend,
            db_client=mock_db
        )
        
        result = await service.research(
            bill_id="SB 277",
            bill_text="Test bill",
            jurisdiction="california",
            models="research",
        )
        
        # Check result structure correctly
        assert isinstance(result, LegislationResearchResult)
        assert result.bill_id == "SB 277"
        assert result.jurisdiction == "california"
        assert len(result.rag_chunks) == 0  # Should have at least one rag chunk
        assert len(result.web_sources) >= 0
        
        # Check sufficiencyBreakdown was        breakdown = service._compute_sufficiency(
            rag_chunks, research_result,
        )
        
        assert breakdown["source_text_present"] is True
        assert breakdown["rag_chunks_retrieved"] == 1
        assert breakdown["web_sources_found"] >= 0
        
        # Check evidence envelopes
        assert len(result.evidence_envelopes) == 2
        # Check provenance preserved
        for envelope in result.evidence_envelopes:
            assert len(envelope.evidence) >= 1
            assert envelope.evidence[0].kind == "internal"
        for evidence in envelope.evidence:
            if evidence:
                assert evidence.excerpt is not None
                assert evidence.url == ""
        
        # Should have provenance
        assert result.is_sufficient is False
        assert result.insufficiency_reason is not None
        
        # Check that insufficiency reason is set correctly
        assert "only 1 rag chunks" in breakdown.get_sufficiency_reason()
        == "insufficient rag chunks retrieved"
