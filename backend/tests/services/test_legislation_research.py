"""
Tests for Legislation Research Service (bd-tytc.4).

Validates:
- Retrieval-backed research with EvidenceEnvelope provenance
- Fail-closed production behavior
- Sufficiency breakdown computation
- Jurisdiction/source filtering
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from services.legislation_research import (
    LegislationResearchService,
    LegislationResearchResult,
)
from llm_common.retrieval import RetrievedChunk


def _make_mock_llm_client():
    client = MagicMock()
    client.chat_completion = AsyncMock(return_value=MagicMock(content="{}"))
    return client


def _make_mock_search_client(results=None):
    client = MagicMock()
    client.search = AsyncMock(return_value=results or [])
    return client


def _make_mock_retrieval_backend(chunks=None):
    backend = MagicMock()
    backend.retrieve = AsyncMock(return_value=chunks or [])
    return backend


def _make_retrieved_chunk(
    chunk_id="c1",
    content="SB 277 bill text excerpt",
    score=0.85,
    metadata=None,
):
    return RetrievedChunk(
        chunk_id=chunk_id,
        content=content,
        embedding=None,
        metadata=metadata or {"jurisdiction": "california", "bill_number": "SB 277"},
        score=score,
        source="https://leginfo.legislature.ca.gov",
    )


class TestLegislationResearchServiceInit:
    def test_init_with_required_dependencies(self):
        service = LegislationResearchService(
            llm_client=_make_mock_llm_client(),
            search_client=_make_mock_search_client(),
        )
        assert service.retrieval_backend is None
        assert service.embedding_fn is None

    def test_init_with_all_dependencies(self):
        mock_db = MagicMock()
        backend = _make_mock_retrieval_backend()

        async def embed_fn(text):
            return [0.1] * 1536

        service = LegislationResearchService(
            llm_client=_make_mock_llm_client(),
            search_client=_make_mock_search_client(),
            retrieval_backend=backend,
            embedding_fn=embed_fn,
            db_client=mock_db,
        )
        assert service.retrieval_backend is backend
        assert service.embedding_fn is embed_fn


class TestResearchReturnsStructuredResult:
    @pytest.mark.asyncio
    async def test_research_returns_legislation_research_result(self):
        service = LegislationResearchService(
            llm_client=_make_mock_llm_client(),
            search_client=_make_mock_search_client(),
            retrieval_backend=_make_mock_retrieval_backend(),
        )

        result = await service.research(
            bill_id="SB 277",
            bill_text="Test bill text",
            jurisdiction="california",
            top_k=10,
            min_score=0.5,
        )

        assert isinstance(result, LegislationResearchResult)
        assert result.bill_id == "SB 277"
        assert result.jurisdiction == "california"
        assert isinstance(result.rag_chunks, list)
        assert isinstance(result.web_sources, list)
        assert isinstance(result.evidence_envelopes, list)
        assert isinstance(result.sufficiency_breakdown, dict)
        assert isinstance(result.is_sufficient, bool)

    @pytest.mark.asyncio
    async def test_research_with_rag_chunks_populates_evidence(self):
        chunk = _make_retrieved_chunk(
            content="SB 277 fiscal impact analysis shows $50M cost",
            score=0.92,
        )
        service = LegislationResearchService(
            llm_client=_make_mock_llm_client(),
            search_client=_make_mock_search_client(),
            retrieval_backend=_make_mock_retrieval_backend(chunks=[chunk]),
        )

        result = await service.research(
            bill_id="SB 277",
            bill_text="A" * 120,
            jurisdiction="california",
        )

        assert len(result.rag_chunks) == 1
        assert result.rag_chunks[0].chunk_id == "c1"
        assert len(result.evidence_envelopes) >= 1
        envelope = result.evidence_envelopes[0]
        assert envelope.source_tool == "retriever"
        assert len(envelope.evidence) >= 1
        assert envelope.evidence[0].kind == "internal"
        assert envelope.evidence[0].content != ""

    @pytest.mark.asyncio
    async def test_research_with_web_results_populates_evidence(self):
        web_results = [
            {
                "title": "SB 277 Fiscal Analysis",
                "url": "https://lao.ca.gov/sb277",
                "snippet": "Fiscal impact estimated at $50M",
            }
        ]
        service = LegislationResearchService(
            llm_client=_make_mock_llm_client(),
            search_client=_make_mock_search_client(results=web_results),
            retrieval_backend=_make_mock_retrieval_backend(),
        )

        result = await service.research(
            bill_id="SB 277",
            bill_text="A" * 120,
            jurisdiction="california",
        )

        assert len(result.web_sources) == 1
        web_envelopes = [
            e for e in result.evidence_envelopes if e.source_tool == "web_search"
        ]
        assert len(web_envelopes) == 1
        assert web_envelopes[0].evidence[0].url == "https://lao.ca.gov/sb277"

    @pytest.mark.asyncio
    async def test_rag_excerpt_prefers_supportive_text_over_transmission_boilerplate(self):
        chunk = _make_retrieved_chunk(
            content=(
                "The secretary of the Senate shall transmit chaptered copies to the "
                "Chief Clerk of the Assembly. This bill requires local educational "
                "agencies to notify guardians, maintain records, and implement new "
                "immunization compliance procedures that increase administrative workload."
            ),
            score=0.88,
        )
        service = LegislationResearchService(
            llm_client=_make_mock_llm_client(),
            search_client=_make_mock_search_client(),
            retrieval_backend=_make_mock_retrieval_backend(chunks=[chunk]),
        )

        result = await service.research(
            bill_id="SB 277",
            bill_text="A" * 120,
            jurisdiction="california",
        )

        rag_envelope = [e for e in result.evidence_envelopes if e.source_tool == "retriever"][0]
        excerpt = rag_envelope.evidence[0].excerpt.lower()
        assert "implement new immunization compliance procedures" in excerpt
        assert "secretary of the senate shall transmit" not in excerpt

    @pytest.mark.asyncio
    async def test_rag_excerpt_strips_markup_and_skips_resolution_transmission_clause(self):
        chunk = _make_retrieved_chunk(
            chunk_id="acr-1",
            content=(
                'Whereas" id="id_4FFF2AB2-6484-4A20-B71C-BC9998A5EEEF"> WHEREAS, '
                "The United States ranks highest among industrialized nations in "
                "maternal mortality; and WHEREAS, the California Maternal Quality "
                "Care Collaborative has reduced maternal mortality through quality "
                "improvement efforts; and be it further Resolved, That the Chief "
                "Clerk of the Assembly transmit copies of this resolution to the "
                "author for appropriate distribution."
            ),
            metadata={
                "jurisdiction": "state of california",
                "bill_number": "ACR 117",
            },
        )
        service = LegislationResearchService(
            llm_client=_make_mock_llm_client(),
            search_client=_make_mock_search_client(),
            retrieval_backend=_make_mock_retrieval_backend(chunks=[chunk]),
        )

        result = await service.research(
            bill_id="ACR 117",
            bill_text="A" * 120,
            jurisdiction="california",
        )

        rag_envelope = [e for e in result.evidence_envelopes if e.source_tool == "retriever"][0]
        excerpt = rag_envelope.evidence[0].excerpt.lower()
        assert "maternal mortality" in excerpt
        assert "chief clerk of the assembly" not in excerpt


class TestSufficiencyComputation:
    @pytest.mark.asyncio
    async def test_sufficient_with_multiple_rag_chunks(self):
        chunks = [
            _make_retrieved_chunk(chunk_id=f"c{i}", content=f"Chunk {i} content")
            for i in range(3)
        ]
        service = LegislationResearchService(
            llm_client=_make_mock_llm_client(),
            search_client=_make_mock_search_client(),
            retrieval_backend=_make_mock_retrieval_backend(chunks=chunks),
        )

        result = await service.research(
            bill_id="SB 277",
            bill_text="A" * 120,
            jurisdiction="california",
        )

        assert result.is_sufficient is True
        assert result.sufficiency_breakdown["rag_chunks_retrieved"] == 3

    @pytest.mark.asyncio
    async def test_insufficient_without_bill_text(self):
        service = LegislationResearchService(
            llm_client=_make_mock_llm_client(),
            search_client=_make_mock_search_client(
                results=[
                    {"title": "t", "url": "http://x", "snippet": "s"} for _ in range(10)
                ]
            ),
            retrieval_backend=_make_mock_retrieval_backend(),
        )

        result = await service.research(
            bill_id="SB 277",
            bill_text="A" * 120,
            jurisdiction="california",
        )

        assert result.is_sufficient is False
        assert result.insufficiency_reason is not None

    def test_check_sufficiency_logic(self):
        service = LegislationResearchService(
            llm_client=MagicMock(),
            search_client=MagicMock(),
        )

        assert service._check_sufficiency({"source_text_present": False}) is False
        assert (
            service._check_sufficiency(
                {"source_text_present": True, "rag_chunks_retrieved": 3}
            )
            is True
        )
        assert (
            service._check_sufficiency(
                {
                    "source_text_present": True,
                    "rag_chunks_retrieved": 1,
                    "web_research_sources_found": 2,
                }
            )
            is True
        )


class TestRetrievalFilters:
    @pytest.mark.asyncio
    async def test_retrieve_uses_jurisdiction_and_bill_filters(self):
        mock_backend = _make_mock_retrieval_backend()
        service = LegislationResearchService(
            llm_client=_make_mock_llm_client(),
            search_client=_make_mock_search_client(),
            retrieval_backend=mock_backend,
            embedding_fn=AsyncMock(return_value=[0.1] * 1536),
        )

        await service.research(
            bill_id="SB 277",
            bill_text="test",
            jurisdiction="california",
        )

        calls = mock_backend.retrieve.call_args_list
        assert len(calls) >= 1
        for call in calls:
            filters = call.kwargs.get("filters") or (
                call[1].get("filters") if len(call) > 1 else None
            )
            if filters:
                assert filters.get("jurisdiction") == "california"
                assert filters.get("bill_number") == "SB 277"

    @pytest.mark.asyncio
    async def test_retrieve_deduplicates_chunks(self):
        chunk = _make_retrieved_chunk(chunk_id="c1")
        service = LegislationResearchService(
            llm_client=_make_mock_llm_client(),
            search_client=_make_mock_search_client(),
            retrieval_backend=_make_mock_retrieval_backend(chunks=[chunk, chunk]),
        )

        result = await service.research(
            bill_id="SB 277",
            bill_text="A" * 120,
            jurisdiction="california",
        )

        unique_ids = set(c.chunk_id for c in result.rag_chunks)
        assert len(unique_ids) == 1

    @pytest.mark.asyncio
    async def test_retrieve_falls_back_to_zero_threshold_for_bill_scoped_chunks(self):
        chunk = _make_retrieved_chunk(chunk_id="fallback-1")
        backend = MagicMock()
        backend.retrieve = AsyncMock(side_effect=[[], [], [], [chunk]])
        service = LegislationResearchService(
            llm_client=_make_mock_llm_client(),
            search_client=_make_mock_search_client(),
            retrieval_backend=backend,
        )

        result = await service.research(
            bill_id="SB 277",
            bill_text="A" * 120,
            jurisdiction="california",
        )

        assert [c.chunk_id for c in result.rag_chunks] == ["fallback-1"]
        fallback_call = backend.retrieve.call_args_list[-1]
        assert fallback_call.kwargs["query"] == "SB 277"
        assert fallback_call.kwargs["min_score"] == 0.0
        assert fallback_call.kwargs["filters"]["bill_number"] == "SB 277"


class TestErrorHandling:
    @pytest.mark.asyncio
    async def test_research_graceful_on_retrieval_error(self):
        failing_backend = MagicMock()
        failing_backend.retrieve = AsyncMock(side_effect=RuntimeError("DB down"))
        service = LegislationResearchService(
            llm_client=_make_mock_llm_client(),
            search_client=_make_mock_search_client(),
            retrieval_backend=failing_backend,
        )

        result = await service.research(
            bill_id="SB 277",
            bill_text="test",
            jurisdiction="california",
        )

        assert result.error is None
        assert result.rag_chunks == []
