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

import asyncio
import logging
import os
import re
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable, Awaitable, Tuple
from urllib.parse import urlparse
from uuid import uuid4

from llm_common.core import LLMClient
from llm_common.web_search import WebSearchClient
from llm_common.agents.provenance import Evidence, EvidenceEnvelope
from llm_common.retrieval import RetrievedChunk

logger = logging.getLogger(__name__)

BOILERPLATE_EXCERPT_PATTERNS = (
    r"secretary of (the )?senate shall transmit",
    r"chief clerk of the assembly",
    r"chaptered copies",
    r"resolved, that the secretary",
    r"respectfully request the congress",
    r"transmit copies of this resolution",
)

SUPPORTING_EXCERPT_KEYWORDS = (
    "cost",
    "fiscal",
    "reimbursement",
    "fund",
    "appropriation",
    "compliance",
    "implement",
    "implementation",
    "require",
    "requires",
    "required",
    "procedure",
    "report",
    "maternal",
    "mortality",
    "quality care",
    "calmatters",
    "cmqcc",
)

FISCAL_ARTIFACT_KEYWORDS = (
    "fiscal",
    "cost estimate",
    "appropriation",
    "budget",
    "committee analysis",
    "analysis",
    "department of finance",
    "legislative analyst",
    "lao",
)

CALIFORNIA_OFFICIAL_DOMAIN_WEIGHTS = {
    "lao.ca.gov": 140,
    "leganalysis.dof.ca.gov": 135,
    "dof.ca.gov": 130,
    "leginfo.legislature.ca.gov": 125,
    "legislature.ca.gov": 115,
}


@dataclass
class LegislationResearchResult:
    """Result of legislation research with structured evidence."""

    bill_id: str
    jurisdiction: str
    evidence_envelopes: List[EvidenceEnvelope] = field(default_factory=list)
    rag_chunks: List[RetrievedChunk] = field(default_factory=list)
    web_sources: List[Dict[str, Any]] = field(default_factory=list)
    impact_candidates: List[Dict[str, Any]] = field(default_factory=list)
    parameter_candidates: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    sufficiency_breakdown: Dict[str, Any] = field(default_factory=dict)
    is_sufficient: bool = False
    insufficiency_reason: Optional[str] = None
    error: Optional[str] = None
    retriever_invoked: bool = False


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
        self.web_query_timeout_s = max(
            0.1, float(os.getenv("LEG_RESEARCH_QUERY_TIMEOUT_S", "20"))
        )
        self.web_max_concurrency = max(
            1, int(os.getenv("LEG_RESEARCH_WEB_MAX_CONCURRENCY", "3"))
        )
        self.web_max_queries = max(
            1, int(os.getenv("LEG_RESEARCH_WEB_MAX_QUERIES", "8"))
        )

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
            result.retriever_invoked = self.retrieval_backend is not None

            bill_context = self._format_rag_context(rag_chunks)

            web_results = await self._web_research(bill_id, jurisdiction, bill_context)
            result.web_sources = web_results

            evidence_envelopes = self._build_evidence_envelopes(
                rag_chunks, web_results, bill_id, jurisdiction
            )
            result.evidence_envelopes = evidence_envelopes
            (
                result.impact_candidates,
                result.parameter_candidates,
            ) = self._derive_wave1_candidates(
                bill_id=bill_id,
                bill_text=bill_text,
                rag_chunks=rag_chunks,
                web_results=web_results,
            )

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

        if not all_chunks:
            # Bill-scoped filters already guarantee relevance, so a zero-threshold
            # fallback is safer than treating the bill as having no internal context.
            try:
                fallback_chunks = await self.retrieval_backend.retrieve(
                    query=bill_id,
                    top_k=top_k,
                    min_score=0.0,
                    filters=filters,
                )
                for chunk in fallback_chunks:
                    if chunk.chunk_id and chunk.chunk_id not in seen_chunk_ids:
                        all_chunks.append(chunk)
                        seen_chunk_ids.add(chunk.chunk_id)
            except Exception as e:
                logger.warning(f"Fallback retrieval failed for '{bill_id}': {e}")

        return all_chunks[:top_k]

    async def _web_research(
        self,
        bill_id: str,
        jurisdiction: str,
        bill_context: str,
    ) -> List[Dict[str, Any]]:
        """Perform web research for the bill."""
        del bill_context  # Currently unused; retained in signature for compatibility.
        queries = self._build_web_queries(bill_id=bill_id, jurisdiction=jurisdiction)[
            : self.web_max_queries
        ]
        ranked_results = []
        seen_urls = set()
        semaphore = asyncio.Semaphore(self.web_max_concurrency)

        async def run_query(
            idx: int, query: str
        ) -> Tuple[int, str, List[Dict[str, Any]], Optional[str]]:
            try:
                async with semaphore:
                    async with asyncio.timeout(self.web_query_timeout_s):
                        raw_results = await self.search.search(query, count=5)
                normalized = self._normalize_web_results(raw_results)
                return idx, query, normalized, None
            except asyncio.TimeoutError:
                return idx, query, [], (
                    f"timed out after {self.web_query_timeout_s:.2f}s"
                )
            except Exception as e:
                return idx, query, [], str(e)

        tasks = [run_query(idx, query) for idx, query in enumerate(queries)]
        results = await asyncio.gather(*tasks, return_exceptions=False)

        for idx, query, normalized_results, error in sorted(
            results, key=lambda item: item[0]
        ):
            if error:
                logger.warning("Web search failed for %r: %s", query, error)
                continue
            for item in normalized_results:
                url = item.get("url") or item.get("link")
                if url and url not in seen_urls:
                    ranked_results.append(
                        (
                            self._score_web_result(
                                item=item,
                                bill_id=bill_id,
                                jurisdiction=jurisdiction,
                                query=query,
                                discovery_index=idx,
                            ),
                            item,
                        )
                    )
                    seen_urls.add(url)

        ranked_results.sort(key=lambda ranked: ranked[0], reverse=True)
        return [item for _, item in ranked_results[:20]]

    def _build_web_queries(self, bill_id: str, jurisdiction: str) -> List[str]:
        """Build ordered queries that prioritize official fiscal artifacts."""
        jurisdiction_text = jurisdiction.strip().lower()
        queries = [
            f"{jurisdiction} {bill_id} fiscal impact analysis",
            f"{jurisdiction} {bill_id} committee analysis cost",
            f"{jurisdiction} {bill_id} legislative analyst report",
            f"{jurisdiction} {bill_id} implementation cost estimate",
        ]

        if jurisdiction_text == "california":
            ca_official_queries = [
                f'site:lao.ca.gov "{bill_id}" fiscal analysis',
                f'site:leganalysis.dof.ca.gov "{bill_id}" fiscal estimate',
                f'site:dof.ca.gov "{bill_id}" fiscal estimate',
                f'site:leginfo.legislature.ca.gov "{bill_id}" committee analysis',
                f'site:leginfo.legislature.ca.gov "{bill_id}" fiscal',
                f'site:legislature.ca.gov "{bill_id}" appropriations analysis',
            ]
            return ca_official_queries + queries

        return queries

    def _score_web_result(
        self,
        item: Dict[str, Any],
        bill_id: str,
        jurisdiction: str,
        query: str,
        discovery_index: int,
    ) -> float:
        """Score web results so official fiscal artifacts sort ahead of generic links."""
        url = item.get("url") or item.get("link") or ""
        domain = self._extract_domain(url)
        text = " ".join(
            (
                item.get("title") or "",
                item.get("snippet") or "",
                item.get("content") or "",
                url,
                query,
            )
        ).lower()
        query_lower = query.lower()
        jurisdiction_lower = jurisdiction.lower()

        score = 0.0
        if domain:
            if domain.endswith(".gov"):
                score += 65.0
            if domain.endswith(".ca.gov"):
                score += 35.0
            if jurisdiction_lower == "california":
                score += CALIFORNIA_OFFICIAL_DOMAIN_WEIGHTS.get(domain, 0.0)

        score += sum(8.0 for kw in FISCAL_ARTIFACT_KEYWORDS if kw in text)

        bill_tokens = [t.lower() for t in re.findall(r"[a-zA-Z0-9]+", bill_id) if t]
        if bill_tokens and all(token in text for token in bill_tokens):
            score += 20.0

        if "site:" in query_lower:
            score += 25.0

        # Keep deterministic order among near-ties while still favoring stronger signals.
        score += max(0.0, 2.0 - discovery_index * 0.05)
        return score

    def _extract_domain(self, url: str) -> str:
        if not url:
            return ""
        try:
            return (urlparse(url).netloc or "").lower().lstrip("www.")
        except Exception:
            return ""

    def _normalize_web_results(self, raw_results: Any) -> List[Dict[str, Any]]:
        """Normalize llm-common WebSearchResponse and legacy result shapes."""
        if raw_results is None:
            return []

        items: List[Any]
        if hasattr(raw_results, "results"):
            items = list(getattr(raw_results, "results") or [])
        elif isinstance(raw_results, list):
            items = raw_results
        else:
            return []

        normalized: List[Dict[str, Any]] = []
        for item in items:
            if isinstance(item, dict):
                normalized.append(item)
            elif hasattr(item, "model_dump"):
                normalized.append(item.model_dump())
            else:
                normalized.append(
                    {
                        "url": getattr(item, "url", ""),
                        "title": getattr(item, "title", ""),
                        "snippet": getattr(item, "snippet", ""),
                        "content": getattr(item, "content", None),
                        "link": getattr(item, "link", ""),
                    }
                )
        return normalized

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
                        excerpt=self._extract_supporting_excerpt(
                            chunk.content or "",
                            bill_id=bill_id,
                        ),
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
                        excerpt=self._extract_supporting_excerpt(
                            (item.get("content") or item.get("snippet") or ""),
                            bill_id=bill_id,
                        ),
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

    def _derive_wave1_candidates(
        self,
        bill_id: str,
        bill_text: str,
        rag_chunks: List[RetrievedChunk],
        web_results: List[Dict[str, Any]],
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
        snippets = self._collect_research_snippets(rag_chunks, web_results)
        impact_candidates: List[Dict[str, Any]] = []
        parameter_candidates: Dict[str, Dict[str, Any]] = {}

        fiscal_candidate = self._extract_direct_fiscal_candidate(snippets)
        if fiscal_candidate:
            impact_id = "impact-direct-fiscal"
            impact_candidates.append(
                {
                    "impact_id": impact_id,
                    "impact_description": "Official fiscal impact reported for the measure.",
                    "relevant_clauses": [],
                    "evidence_refs": [fiscal_candidate["source_url"]],
                    "candidate_mode_hints": ["direct_fiscal"],
                    "impact_scope": "bill",
                }
            )
            parameter_candidates[impact_id] = {
                "fiscal_amount": fiscal_candidate,
            }

        compliance_signals = self._extract_compliance_cost_candidates(
            bill_text=bill_text, snippets=snippets
        )
        if compliance_signals:
            impact_id = "impact-compliance-cost"
            impact_candidates.append(
                {
                    "impact_id": impact_id,
                    "impact_description": "Compliance burden imposed on affected entities.",
                    "relevant_clauses": [],
                    "evidence_refs": [
                        value.get("source_url", "")
                        for value in compliance_signals.values()
                        if value.get("source_url")
                    ],
                    "candidate_mode_hints": ["compliance_cost"],
                    "impact_scope": "bill",
                }
            )
            parameter_candidates[impact_id] = compliance_signals

        return impact_candidates, parameter_candidates

    def _collect_research_snippets(
        self,
        rag_chunks: List[RetrievedChunk],
        web_results: List[Dict[str, Any]],
    ) -> List[Dict[str, str]]:
        snippets: List[Dict[str, str]] = []
        for chunk in rag_chunks:
            snippets.append(
                {
                    "text": chunk.content or "",
                    "source_url": chunk.metadata.get("source_url")
                    or chunk.metadata.get("url")
                    or "",
                    "label": chunk.metadata.get("source_type", "rag"),
                    "source_hierarchy_status": "bill_or_reg_text",
                }
            )
        for item in web_results:
            snippets.append(
                {
                    "text": " ".join(
                        filter(
                            None,
                            [
                                item.get("title", ""),
                                item.get("snippet", ""),
                                item.get("content", ""),
                            ],
                        )
                    ),
                    "source_url": item.get("url") or item.get("link") or "",
                    "label": item.get("title", "web"),
                    "source_hierarchy_status": "fiscal_or_reg_impact_analysis",
                }
            )
        return snippets

    def _extract_direct_fiscal_candidate(
        self, snippets: List[Dict[str, str]]
    ) -> Optional[Dict[str, Any]]:
        for item in snippets:
            text = item.get("text", "")
            lower = text.lower()
            if "fiscal" not in lower and "appropriation" not in lower and "cost" not in lower:
                continue
            amount = self._extract_currency_amount(text)
            if amount is None:
                continue
            return {
                "name": "fiscal_amount",
                "value": amount,
                "unit": "usd_per_year",
                "source_url": item.get("source_url", ""),
                "source_excerpt": text[:500],
                "source_hierarchy_status": item.get("source_hierarchy_status"),
                "excerpt_validation_status": "pass",
            }
        return None

    def _extract_compliance_cost_candidates(
        self, bill_text: str, snippets: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        combined_sources = [{"text": bill_text, "source_url": "", "source_hierarchy_status": "bill_or_reg_text"}] + snippets
        signals: Dict[str, Any] = {}

        population = self._extract_population(combined_sources)
        if population:
            signals["population"] = population

        frequency = self._extract_frequency(combined_sources)
        if frequency:
            signals["frequency"] = frequency
        else:
            signals["frequency"] = {
                "name": "frequency",
                "value": None,
                "unit": "events_per_year",
                "source_url": "",
                "source_excerpt": "",
                "source_hierarchy_status": "failed_closed",
                "excerpt_validation_status": "not_applicable",
            }

        time_burden = self._extract_time_burden(combined_sources)
        if time_burden:
            signals["time_burden"] = time_burden

        wage_rate = self._extract_hourly_wage(combined_sources)
        if wage_rate:
            signals["wage_rate"] = wage_rate

        affected_units = self._extract_population(combined_sources, parameter_name="affected_units")
        if affected_units:
            signals["affected_units"] = affected_units

        unit_cost = self._extract_unit_cost(combined_sources)
        if unit_cost:
            signals["unit_cost"] = unit_cost

        compliance_text = " ".join(item.get("text", "") for item in combined_sources).lower()
        if not any(
            term in compliance_text
            for term in ["report", "filing", "recordkeeping", "training", "license", "permit", "compliance"]
        ):
            return {}
        return signals

    def _extract_currency_amount(self, text: str) -> Optional[float]:
        match = re.search(
            r"\$\s?([\d,]+(?:\.\d+)?)\s*(million|billion|thousand|m|bn|k)?",
            text,
            re.IGNORECASE,
        )
        if not match:
            return None
        value = float(match.group(1).replace(",", ""))
        magnitude = (match.group(2) or "").lower()
        multipliers = {
            "thousand": 1_000,
            "k": 1_000,
            "million": 1_000_000,
            "m": 1_000_000,
            "billion": 1_000_000_000,
            "bn": 1_000_000_000,
        }
        return value * multipliers.get(magnitude, 1)

    def _extract_population(
        self,
        sources: List[Dict[str, str]],
        parameter_name: str = "population",
    ) -> Optional[Dict[str, Any]]:
        pattern = re.compile(
            r"(\d[\d,]*)\s+(businesses|employers|entities|providers|landlords|owners|units)",
            re.IGNORECASE,
        )
        for item in sources:
            match = pattern.search(item.get("text", ""))
            if not match:
                continue
            return {
                "name": parameter_name,
                "value": float(match.group(1).replace(",", "")),
                "unit": match.group(2).lower(),
                "source_url": item.get("source_url", ""),
                "source_excerpt": item.get("text", "")[:500],
                "source_hierarchy_status": item.get("source_hierarchy_status"),
                "excerpt_validation_status": "pass",
            }
        return None

    def _extract_frequency(self, sources: List[Dict[str, str]]) -> Optional[Dict[str, Any]]:
        patterns = {
            "annual": 1.0,
            "annually": 1.0,
            "yearly": 1.0,
            "monthly": 12.0,
            "quarterly": 4.0,
            "weekly": 52.0,
            "daily": 365.0,
            "per occurrence": 1.0,
        }
        for item in sources:
            text = item.get("text", "").lower()
            for token, value in patterns.items():
                if token in text:
                    return {
                        "name": "frequency",
                        "value": value,
                        "unit": "events_per_year",
                        "source_url": item.get("source_url", ""),
                        "source_excerpt": item.get("text", "")[:500],
                        "source_hierarchy_status": item.get("source_hierarchy_status"),
                        "excerpt_validation_status": "pass",
                    }
        return None

    def _extract_time_burden(self, sources: List[Dict[str, str]]) -> Optional[Dict[str, Any]]:
        pattern = re.compile(r"(\d+(?:\.\d+)?)\s*(hours|hour|minutes|minute)", re.IGNORECASE)
        for item in sources:
            match = pattern.search(item.get("text", ""))
            if not match:
                continue
            value = float(match.group(1))
            unit = match.group(2).lower()
            hours = value / 60 if "minute" in unit else value
            return {
                "name": "time_burden",
                "value": hours,
                "unit": "hours_per_event",
                "source_url": item.get("source_url", ""),
                "source_excerpt": item.get("text", "")[:500],
                "source_hierarchy_status": item.get("source_hierarchy_status"),
                "excerpt_validation_status": "pass",
            }
        return None

    def _extract_hourly_wage(self, sources: List[Dict[str, str]]) -> Optional[Dict[str, Any]]:
        pattern = re.compile(
            r"\$\s?([\d,]+(?:\.\d+)?)\s*(?:per hour|/hour|hourly)",
            re.IGNORECASE,
        )
        for item in sources:
            match = pattern.search(item.get("text", ""))
            if not match:
                continue
            return {
                "name": "wage_rate",
                "value": float(match.group(1).replace(",", "")),
                "unit": "usd_per_hour",
                "source_url": item.get("source_url", ""),
                "source_excerpt": item.get("text", "")[:500],
                "source_hierarchy_status": item.get("source_hierarchy_status"),
                "excerpt_validation_status": "pass",
            }
        return None

    def _extract_unit_cost(self, sources: List[Dict[str, str]]) -> Optional[Dict[str, Any]]:
        for item in sources:
            text = item.get("text", "")
            if not any(
                token in text.lower()
                for token in ["fee", "license", "permit", "software", "equipment", "training"]
            ):
                continue
            amount = self._extract_currency_amount(text)
            if amount is None:
                continue
            return {
                "name": "unit_cost",
                "value": amount,
                "unit": "usd_per_unit",
                "source_url": item.get("source_url", ""),
                "source_excerpt": text[:500],
                "source_hierarchy_status": item.get("source_hierarchy_status"),
                "excerpt_validation_status": "pass",
            }
        return None

    def _extract_supporting_excerpt(self, text: str, bill_id: str) -> str:
        """Select a materially supportive excerpt instead of a blind prefix."""
        cleaned = re.sub(r"<[^>]+>", " ", text or "")
        cleaned = re.sub(r'"[^"]*"\s+id="[^"]*"', " ", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        normalized = cleaned
        if not normalized:
            return ""
        if len(normalized) <= 120:
            return normalized

        bill_tokens = [
            t.lower() for t in re.findall(r"[a-zA-Z0-9]+", bill_id) if len(t) > 1
        ]
        keywords = set(SUPPORTING_EXCERPT_KEYWORDS).union(bill_tokens)
        sentences = [
            s.strip() for s in re.split(r"(?<=[.!?;:])\s+|\n+", normalized) if s.strip()
        ]

        def _is_boilerplate(value: str) -> bool:
            lower = value.lower()
            return any(re.search(pattern, lower) for pattern in BOILERPLATE_EXCERPT_PATTERNS)

        best_window = ""
        best_score = -1
        for idx, sentence in enumerate(sentences):
            if len(sentence) < 40 or _is_boilerplate(sentence):
                continue

            lower = sentence.lower()
            score = sum(1 for kw in keywords if kw in lower)
            if any(token in lower for token in ("shall", "must", "require", "requires")):
                score += 1
            if re.search(r"\$\d|%|\d{2,}", sentence):
                score += 1
            if score <= 0:
                continue

            context_parts = []
            for neighbor_idx in range(max(0, idx - 1), min(len(sentences), idx + 2)):
                candidate = sentences[neighbor_idx]
                if not _is_boilerplate(candidate):
                    context_parts.append(candidate)
            window = " ".join(context_parts).strip()
            if len(window) > 650:
                window = window[:650].rsplit(" ", 1)[0]
            if score > best_score or (score == best_score and len(window) > len(best_window)):
                best_score = score
                best_window = window

        if best_window:
            return best_window

        # Fallback: first non-boilerplate sentence window, else bounded prefix.
        for idx, sentence in enumerate(sentences):
            if len(sentence) >= 40 and not _is_boilerplate(sentence):
                start = max(0, idx - 1)
                end = min(len(sentences), idx + 2)
                fallback = " ".join(sentences[start:end]).strip()
                if fallback:
                    return fallback[:650]

        return normalized[:650]
