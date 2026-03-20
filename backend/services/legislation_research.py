"""
Shared Legislation Research Service (bd-tytc.4).

This service provides a canonical research runtime for legislation analysis,
built on llm-common primitives. It replaces the generic ResearchAgent with
legislation-aware research that:

1. Uses retrieval-backed context from the vector store
2. Performs bill-specific web searches
3. Returns structured EvidenceEnvelope provenance
4. Signals explicit insufficiency when evidence is lacking

Used by:
- AnalysisPipeline (legislation analysis)
- PolicyAgent (chat/conversational analysis)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable, Awaitable
from uuid import uuid4

from llm_common.core import LLMClient
from llm_common.web_search import WebSearchClient
from llm_common.agents.provenance import Evidence, EvidenceEnvelope
from llm_common.retrieval import RetrievedChunk

logger = logging.getLogger(__name__)


@dataclass
class LegislationResearchResult:
    """Result of legislation research with structured evidence."""

    bill_id: str
    jurisdiction: str
    evidence_envelopes: List[EvidenceEnvelope] = field(default_factory=list)
    rag_chunks: List[RetrievedChunk] = field(default_factory=list)
    web_sources: List[Dict[str, Any]] = field(default_factory=list)
    sufficiency_breakdown: Dict[str, Any] = field(default_factory=dict)
    is_sufficient: bool = False
    insufficiency_reason: Optional[str] = None
    error: Optional[str] = None


@dataclass
class SufficiencyBreakdown:
    """Breakdown of evidence sufficiency for research."""

    source_text_present: bool = False
    rag_chunks_retrieved: int = 0
    web_research_sources_found: int = 0
    fiscal_notes_detected: bool = False
    bill_text_chunks: int = 0


LEGISLATION_RESEARCH_PROMPT = """You are a legislative policy researcher.

Your task is to gather evidence about a specific bill to assess its cost-of-living impacts.

Research Strategy:
1. FIRST, check the internal knowledge base for the bill text and related documents
2. THEN, search for official fiscal notes, committee analyses, and government cost estimates
3. FINALLY, search for news coverage and stakeholder positions

Focus on:
- Official fiscal impact reports (Legislative Analyst, Department of Finance)
- Committee analysis documents
- Implementation cost estimates
- Arguments from supporters and opponents
- Similar legislation in other jurisdictions

For California bills, prioritize:
- Legislative Analyst's Office (LAO) reports
- Department of Finance fiscal estimates
- Committee floor analyses

Bill: {bill_id}
Jurisdiction: {jurisdiction}
Bill Context (from knowledge base):
{bill_context}

Begin your research.
"""


class LegislationResearchService:
    """
    Shared service for legislation research using llm-common primitives.

    This service provides retrieval-backed research for legislation analysis,
    returning structured evidence with provenance.
    """

    def __init__(
        self,
        llm_client: LLMClient,
        search_client: WebSearchClient,
        retrieval_backend: Any = None,
        embedding_fn: Optional[Callable[[str], Awaitable[List[float]]]] = None,
        db_client: Any = None,
    ):
        """
        Initialize LegislationResearchService.

        Args:
            llm_client: LLM client for query generation and synthesis
            search_client: Web search client for external research
            retrieval_backend: Vector retrieval backend (LocalPgVectorBackend)
            embedding_fn: Async function to embed queries
            db_client: Database client for fetching bill context
        """
        self.llm = llm_client
        self.search = search_client
        self.retrieval_backend = retrieval_backend
        self.embedding_fn = embedding_fn
        self.db = db_client

        if not self.retrieval_backend:
            logger.warning(
                "LegislationResearchService initialized without retrieval_backend. "
                "RAG retrieval will return zero chunks."
            )

    async def research(
        self,
        bill_id: str,
        bill_text: str,
        jurisdiction: str,
        top_k: int = 10,
        min_score: float = 0.5,
    ) -> LegislationResearchResult:
        """
        Perform legislation research with retrieval and web search.

        Args:
            bill_id: Bill identifier (e.g., "SB 277")
            bill_text: Full bill text for context
            jurisdiction: Target jurisdiction (e.g., "california")
            top_k: Maximum number of RAG chunks to retrieve
            min_score: Minimum similarity score for retrieval

        Returns:
            LegislationResearchResult with structured evidence
        """
        result = LegislationResearchResult(
            bill_id=bill_id,
            jurisdiction=jurisdiction,
            sufficiency_breakdown=SufficiencyBreakdown().__dict__,
        )

        try:
            rag_chunks = await self._retrieve_bill_context(
                bill_id, jurisdiction, top_k, min_score
            )
            result.rag_chunks = rag_chunks

            bill_context = self._format_rag_context(rag_chunks)

            web_results = await self._web_research(bill_id, jurisdiction, bill_context)
            result.web_sources = web_results

            evidence_envelopes = self._build_evidence_envelopes(
                rag_chunks, web_results, bill_id, jurisdiction
            )
            result.evidence_envelopes = evidence_envelopes

            result.sufficiency_breakdown = self._compute_sufficiency(
                rag_chunks, web_results, bill_text
            ).__dict__

            result.is_sufficient = self._check_sufficiency(result.sufficiency_breakdown)
            if not result.is_sufficient:
                result.insufficiency_reason = self._get_insufficiency_reason(
                    result.sufficiency_breakdown
                )

            logger.info(
                f"LegislationResearch: {bill_id} - "
                f"rag_chunks={len(rag_chunks)}, web_sources={len(web_results)}, "
                f"sufficient={result.is_sufficient}"
            )

            return result

        except Exception as e:
            logger.error(f"LegislationResearch failed for {bill_id}: {e}")
            result.error = str(e)
            return result

    async def _retrieve_bill_context(
        self,
        bill_id: str,
        jurisdiction: str,
        top_k: int,
        min_score: float,
    ) -> List[RetrievedChunk]:
        """Retrieve bill context from vector store."""
        if not self.retrieval_backend:
            logger.warning(f"No retrieval_backend configured for {bill_id}")
            return []

        filters = {
            "jurisdiction": jurisdiction.lower(),
            "bill_number": bill_id,
        }

        queries = [
            f"{bill_id} bill text analysis",
            f"{bill_id} fiscal impact cost estimate",
            f"{bill_id} committee analysis",
        ]

        all_chunks = []
        seen_chunk_ids = set()

        for query in queries:
            try:
                chunks = await self.retrieval_backend.retrieve(
                    query=query,
                    top_k=top_k,
                    min_score=min_score,
                    filters=filters,
                )
                for chunk in chunks:
                    if chunk.chunk_id and chunk.chunk_id not in seen_chunk_ids:
                        all_chunks.append(chunk)
                        seen_chunk_ids.add(chunk.chunk_id)
            except Exception as e:
                logger.warning(f"Retrieval query failed for '{query}': {e}")

        return all_chunks[:top_k]

    async def _web_research(
        self,
        bill_id: str,
        jurisdiction: str,
        bill_context: str,
    ) -> List[Dict[str, Any]]:
        """Perform web research for the bill."""
        queries = [
            f"{jurisdiction} {bill_id} fiscal impact analysis",
            f"{jurisdiction} {bill_id} committee analysis cost",
            f"{jurisdiction} {bill_id} legislative analyst report",
            f"{jurisdiction} {bill_id} implementation cost estimate",
        ]

        if jurisdiction.lower() == "california":
            queries.extend(
                [
                    f"California {bill_id} LAO analysis",
                    f"California {bill_id} Department of Finance estimate",
                ]
            )

        all_results = []
        seen_urls = set()

        for query in queries:
            try:
                results = await self.search.search(query, num_results=5)
                for item in results:
                    url = item.get("url") or item.get("link")
                    if url and url not in seen_urls:
                        all_results.append(item)
                        seen_urls.add(url)
            except Exception as e:
                logger.warning(f"Web search failed for '{query}': {e}")

        return all_results[:20]

    def _format_rag_context(self, chunks: List[RetrievedChunk]) -> str:
        """Format retrieved chunks into context string."""
        if not chunks:
            return "No relevant documents found in knowledge base."

        parts = []
        for i, chunk in enumerate(chunks, 1):
            source = (
                chunk.metadata.get("source_url")
                or chunk.metadata.get("source_id")
                or "unknown"
            )
            parts.append(f"[Document {i}] (Source: {source})\n{chunk.content[:500]}")

        return "\n\n".join(parts)

    def _build_evidence_envelopes(
        self,
        rag_chunks: List[RetrievedChunk],
        web_results: List[Dict[str, Any]],
        bill_id: str,
        jurisdiction: str,
    ) -> List[EvidenceEnvelope]:
        """Build EvidenceEnvelope objects from research results."""
        envelopes = []

        if rag_chunks:
            rag_evidence = []
            for i, chunk in enumerate(rag_chunks):
                rag_evidence.append(
                    Evidence(
                        id=f"rag-{bill_id}-{i}",
                        kind="internal",
                        label=f"Retrieved Document {i + 1}",
                        url=chunk.metadata.get("source_url")
                        or chunk.metadata.get("url")
                        or "",
                        content=chunk.content[:1000] if chunk.content else "",
                        excerpt=chunk.content[:300] if chunk.content else "",
                        confidence=chunk.score if chunk.score else 0.5,
                        metadata={
                            "chunk_id": chunk.chunk_id,
                            "score": chunk.score,
                            "jurisdiction": chunk.metadata.get("jurisdiction"),
                        },
                    )
                )

            envelopes.append(
                EvidenceEnvelope(
                    id=f"rag-{bill_id}-{uuid4().hex[:8]}",
                    source_tool="retriever",
                    source_query=bill_id,
                    evidence=rag_evidence,
                )
            )

        if web_results:
            web_evidence = []
            for i, item in enumerate(web_results):
                web_evidence.append(
                    Evidence(
                        id=f"web-{bill_id}-{i}",
                        kind="external",
                        label=item.get("title", f"Web Result {i + 1}"),
                        url=item.get("url") or item.get("link") or "",
                        content=item.get("content") or item.get("snippet") or "",
                        excerpt=item.get("snippet", "")[:300],
                        confidence=0.6,
                        metadata={
                            "source": "web_search",
                            "jurisdiction": jurisdiction,
                        },
                    )
                )

            envelopes.append(
                EvidenceEnvelope(
                    id=f"web-{bill_id}-{uuid4().hex[:8]}",
                    source_tool="web_search",
                    source_query=f"{jurisdiction} {bill_id}",
                    evidence=web_evidence,
                )
            )

        return envelopes

    def _compute_sufficiency(
        self,
        rag_chunks: List[RetrievedChunk],
        web_results: List[Dict[str, Any]],
        bill_text: str,
    ) -> SufficiencyBreakdown:
        """Compute evidence sufficiency breakdown."""
        bill_text_chunks = sum(
            1
            for c in rag_chunks
            if c.metadata.get("content_type") == "bill_text"
            or "bill" in c.metadata.get("source_type", "").lower()
        )

        fiscal_keywords = [
            "fiscal",
            "cost",
            "budget",
            "appropriation",
            "revenue",
            "expenditure",
        ]
        fiscal_notes_detected = any(
            any(
                kw in (r.get("title", "") + r.get("snippet", "")).lower()
                for kw in fiscal_keywords
            )
            for r in web_results
        )

        return SufficiencyBreakdown(
            source_text_present=bool(bill_text and len(bill_text) > 100),
            rag_chunks_retrieved=len(rag_chunks),
            web_research_sources_found=len(web_results),
            fiscal_notes_detected=fiscal_notes_detected,
            bill_text_chunks=bill_text_chunks,
        )

    def _check_sufficiency(self, breakdown: Dict[str, Any]) -> bool:
        """Check if research has sufficient evidence."""
        source_present = breakdown.get("source_text_present", False)
        rag_chunks = breakdown.get("rag_chunks_retrieved", 0)
        web_sources = breakdown.get("web_research_sources_found", 0)

        if not source_present:
            return False

        if rag_chunks >= 3:
            return True

        if rag_chunks >= 1 and web_sources >= 2:
            return True

        if web_sources >= 5:
            return True

        return False

    def _get_insufficiency_reason(self, breakdown: Dict[str, Any]) -> str:
        """Get human-readable reason for insufficiency."""
        reasons = []

        if not breakdown.get("source_text_present"):
            reasons.append("bill text not available or too short")

        if breakdown.get("rag_chunks_retrieved", 0) < 3:
            reasons.append(
                f"only {breakdown.get('rag_chunks_retrieved', 0)} RAG chunks found"
            )

        if breakdown.get("web_research_sources_found", 0) < 2:
            reasons.append("insufficient web research sources")

        if reasons:
            return "; ".join(reasons)

        return "insufficient evidence for quantification"
