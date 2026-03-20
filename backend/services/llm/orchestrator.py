"""
Legislation Analysis Pipeline (bd-tytc.4).

Orchestrates multi-step legislation analysis using the shared
LegislationResearchService for retrieval-backed research.

Workflow:
1. Research: Retrieval-backed + web research via LegislationResearchService
2. Generate: LLM analysis with structured output (LegislationAnalysisResponse)
3. Review: LLM critique
4. Refine: Regenerate if review failed
"""

from __future__ import annotations

from llm_common.core import LLMClient
from llm_common.web_search import WebSearchClient
from llm_common.core.models import LLMMessage, MessageRole
from typing import List, Dict, Any
import re
from pydantic import BaseModel, ValidationError
from schemas.analysis import (
    LegislationAnalysisResponse,
    LegislationImpact,
    ReviewCritique,
    SufficiencyState,
)
from datetime import datetime
import logging

from services.legislation_research import (
    LegislationResearchService,
    LegislationResearchResult,
)
from services.llm.evidence_adapter import envelope_to_impact_evidence
from services.llm.evidence_gates import assess_sufficiency, strip_quantification

logger = logging.getLogger(__name__)


class AnalysisPipeline:
    """
    Orchestrate multi-step legislation analysis.

    Uses LegislationResearchService for retrieval-backed research
    with structured EvidenceEnvelope provenance (bd-tytc.4).
    """

    def __init__(
        self,
        llm_client: LLMClient,
        search_client: WebSearchClient,
        db_client: Any,
        fallback_client: LLMClient | None = None,
        retrieval_backend: Any = None,
        embedding_fn: Any = None,
    ):
        """
        Initialize pipeline.

        Args:
            llm_client: Primary LLM client (e.g. Z.ai)
            search_client: Web search client
            db_client: Database client
            fallback_client: Optional fallback/embedding provider (e.g. OpenRouter)
            retrieval_backend: Vector retrieval backend for RAG
            embedding_fn: Async function to embed text queries
        """
        self.llm = llm_client
        self.search = search_client
        self.db = db_client
        self.fallback_llm = fallback_client
        self.retrieval_backend = retrieval_backend
        self.embedding_fn = embedding_fn

        self.research_service = LegislationResearchService(
            llm_client=llm_client,
            search_client=search_client,
            retrieval_backend=retrieval_backend,
            embedding_fn=embedding_fn,
            db_client=db_client,
        )

    async def run(
        self, bill_id: str, bill_text: str, jurisdiction: str, models: Dict[str, str]
    ) -> LegislationAnalysisResponse:
        """
        Run full pipeline.

        Args:
            bill_id: Bill identifier (e.g., "SB-277")
            bill_text: Full bill text
            jurisdiction: Jurisdiction (e.g., "California")
            models: {"research": "...", "generate": "...", "review": "..."}

        Returns:
            Final analysis (validated LegislationAnalysisResponse)
        """
        from services.audit.logger import AuditLogger

        run_id = await self._create_pipeline_run(bill_id, jurisdiction, models)
        audit = AuditLogger(run_id, self.db)

        try:
            source_data = await self.db.get_latest_scrape_for_bill(
                jurisdiction, bill_id
            )
            source_text_present = bool(bill_text and len(bill_text) > 100)
            if source_data:
                await audit.log_step(
                    step_number=0,
                    step_name="ingestion_source",
                    status="completed",
                    input_context={
                        "jurisdiction": jurisdiction,
                        "bill_id": bill_id,
                        "bill_text_preview": bill_text[:500] + "..."
                        if bill_text
                        else "N/A",
                    },
                    output_result={
                        "raw_scrape_id": str(source_data["id"]),
                        "source_url": source_data["url"],
                        "content_hash": source_data["content_hash"],
                        "metadata": source_data["metadata"],
                        "minio_blob_path": source_data.get("storage_uri", "N/A"),
                        "source_text_present": source_text_present,
                    },
                    model_info={"model": "scraper", "provider": "firecrawl"},
                    duration_ms=0,
                )
            else:
                await audit.log_step(
                    step_number=0,
                    step_name="ingestion_source",
                    status="skipped",
                    input_context={"jurisdiction": jurisdiction, "bill_id": bill_id},
                    output_result={
                        "error": "No raw scrape found for this bill.",
                        "source_text_present": source_text_present,
                    },
                    model_info={"model": "scraper", "provider": "firecrawl"},
                    duration_ms=0,
                )

            start_ts = datetime.now()
            research_result = await self._research_step(
                bill_id, bill_text, jurisdiction, models["research"]
            )
            duration = int((datetime.now() - start_ts).total_seconds() * 1000)

            await audit.log_step(
                step_number=2,
                step_name="research",
                status="completed" if research_result.is_sufficient else "degraded",
                input_context={"bill_id": bill_id, "jurisdiction": jurisdiction},
                output_result={
                    "rag_chunks": len(research_result.rag_chunks),
                    "web_sources": len(research_result.web_sources),
                    "evidence_envelopes": len(research_result.evidence_envelopes),
                    "sufficiency_breakdown": research_result.sufficiency_breakdown,
                    "is_sufficient": research_result.is_sufficient,
                    "insufficiency_reason": research_result.insufficiency_reason,
                },
                model_info={"model": models["research"]},
                duration_ms=duration,
            )

            evidence_items = []
            for envelope in research_result.evidence_envelopes:
                envelope_data = (
                    envelope.model_dump()
                    if hasattr(envelope, "model_dump")
                    else envelope
                )
                evidence_items.extend(envelope_to_impact_evidence(envelope_data))

            breakdown = assess_sufficiency(
                bill_text=bill_text,
                evidence_list=evidence_items,
                web_research_count=len(research_result.web_sources),
            )

            await audit.log_step(
                step_number=3,
                step_name="sufficiency_gate",
                status="completed",
                input_context={"bill_id": bill_id},
                output_result=breakdown.model_dump(),
                model_info={"model": "deterministic", "provider": "evidence_gates"},
                duration_ms=0,
            )

            if breakdown.sufficiency_state == SufficiencyState.RESEARCH_INCOMPLETE:
                analysis = LegislationAnalysisResponse(
                    bill_number=bill_id,
                    title="",
                    jurisdiction=jurisdiction,
                    status="",
                    sufficiency_state=breakdown.sufficiency_state,
                    insufficiency_reason="; ".join(breakdown.insufficiency_reasons),
                    quantification_eligible=False,
                    impacts=[],
                    total_impact_p50=None,
                    analysis_timestamp=datetime.now().isoformat(),
                    model_used=models.get("generate", "unknown"),
                )
                await self._complete_pipeline_run(
                    run_id,
                    bill_id,
                    bill_text,
                    analysis,
                    ReviewCritique(
                        passed=False,
                        critique="Skipped: research incomplete",
                        missing_impacts=[],
                        factual_errors=[],
                    ),
                    jurisdiction,
                    breakdown=breakdown,
                    rag_chunks_retrieved=len(research_result.rag_chunks),
                    retriever_invoked=research_result.retriever_invoked,
                )
                return analysis

            start_ts = datetime.now()
            analysis = await self._generate_step(
                bill_id,
                bill_text,
                jurisdiction,
                research_result,
                models["generate"],
                breakdown,
            )
            duration = int((datetime.now() - start_ts).total_seconds() * 1000)

            if not breakdown.quantification_eligible:
                analysis.impacts = [
                    LegislationImpact(**strip_quantification([imp.model_dump()])[0])
                    for imp in analysis.impacts
                ]
                analysis.sufficiency_state = breakdown.sufficiency_state
                analysis.insufficiency_reason = "; ".join(
                    breakdown.insufficiency_reasons
                )
                analysis.quantification_eligible = False
                analysis.total_impact_p50 = None

            await audit.log_step(
                step_number=4,
                step_name="generate",
                status="completed",
                input_context={
                    "evidence_envelope_count": len(research_result.evidence_envelopes),
                    "is_sufficient": research_result.is_sufficient,
                    "sufficiency_state": breakdown.sufficiency_state.value,
                },
                output_result=analysis.model_dump(),
                model_info={"model": models["generate"]},
                duration_ms=duration,
            )

            start_ts = datetime.now()
            review = await self._review_step(
                bill_id, analysis, research_result, models["review"]
            )
            duration = int((datetime.now() - start_ts).total_seconds() * 1000)

            await audit.log_step(
                step_number=5,
                step_name="review",
                status="completed",
                input_context={"analysis_summary": "See generate step"},
                output_result=review.model_dump(),
                model_info={"model": models["review"]},
                duration_ms=duration,
            )

            if not review.passed:
                start_ts = datetime.now()
                analysis = await self._refine_step(
                    bill_id,
                    analysis,
                    review,
                    bill_text,
                    models["generate"],
                    breakdown,
                )
                duration = int((datetime.now() - start_ts).total_seconds() * 1000)

                if not breakdown.quantification_eligible:
                    analysis.impacts = [
                        LegislationImpact(**strip_quantification([imp.model_dump()])[0])
                        for imp in analysis.impacts
                    ]
                    analysis.sufficiency_state = breakdown.sufficiency_state
                    analysis.insufficiency_reason = "; ".join(
                        breakdown.insufficiency_reasons
                    )
                    analysis.quantification_eligible = False
                    analysis.total_impact_p50 = None

                await audit.log_step(
                    step_number=6,
                    step_name="refine",
                    status="completed",
                    input_context={"critique": review.model_dump()},
                    output_result=analysis.model_dump(),
                    model_info={"model": models["generate"]},
                    duration_ms=duration,
                )

            await self._complete_pipeline_run(
                run_id,
                bill_id,
                bill_text,
                analysis,
                review,
                jurisdiction,
                breakdown=breakdown,
                rag_chunks_retrieved=len(research_result.rag_chunks),
                retriever_invoked=research_result.retriever_invoked,
            )

            return analysis

        except Exception as e:
            await self._fail_pipeline_run(run_id, str(e))
            await audit.log_step(
                step_number=99,
                step_name="pipeline_failure",
                status="failed",
                output_result={"error": str(e)},
                model_info={"models_attempted": models},
            )
            raise

    async def _research_step(
        self, bill_id: str, bill_text: str, jurisdiction: str, model: str
    ) -> LegislationResearchResult:
        """
        Research step using LegislationResearchService (bd-tytc.4).

        Replaces generic ResearchAgent with retrieval-backed research
        that returns structured EvidenceEnvelope provenance.
        """
        result = await self.research_service.research(
            bill_id=bill_id,
            bill_text=bill_text,
            jurisdiction=jurisdiction,
            top_k=10,
            min_score=0.5,
        )

        if not result.is_sufficient:
            logger.warning(
                f"Research insufficient for {bill_id}: {result.insufficiency_reason}"
            )

        return result

    async def _chat(
        self, messages: List[Dict], model: str, response_model: type[BaseModel]
    ) -> BaseModel:
        """Helper to get structured output from LLMClient."""
        llm_messages = []
        for m in messages:
            role = MessageRole.USER if m["role"] == "user" else MessageRole.SYSTEM
            llm_messages.append(LLMMessage(role=role, content=m["content"]))

        schema = response_model.model_json_schema()
        json_instruction = (
            f"\n\nRespond with valid JSON matching this schema:\n{schema}"
        )
        if llm_messages:
            llm_messages[-1].content += json_instruction

        def _normalize_json_text(text: str) -> str:
            content = text.strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1] if "\n" in content else content
                if content.endswith("```"):
                    content = content[:-3].strip()
                if content.startswith("json"):
                    content = content[4:].strip()
            return content

        def _extract_bill_number() -> str | None:
            combined = "\n".join(str(m.content) for m in llm_messages)
            match = re.search(r"(?m)^\\s*Bill:\\s*([^\\s\\(]+)", combined)
            return match.group(1) if match else None

        async def _call_llm(
            call_messages: list[LLMMessage], *, temperature: float
        ) -> str:
            try:
                response = await self.llm.chat_completion(
                    messages=call_messages,
                    model=model,
                    response_format={"type": "json_object"},
                    temperature=temperature,
                )
                return _normalize_json_text(response.content)
            except Exception as e:
                if not self.fallback_llm:
                    raise
                print(f"Primary LLM failed: {e}. Retrying with Fallback LLM...")
                fallback_model = (
                    self.fallback_llm.config.default_model
                    or "google/gemini-2.0-flash-exp"
                )
                response = await self.fallback_llm.chat_completion(
                    messages=call_messages,
                    model=fallback_model,
                    response_format={"type": "json_object"},
                    temperature=temperature,
                )
                return _normalize_json_text(response.content)

        content = await _call_llm(llm_messages, temperature=0.1)
        last_error = ""
        try:
            return response_model.model_validate_json(content)
        except Exception as e:
            last_error = str(e)

        for _attempt in range(2):
            repair_prompt = (
                "Your previous response did not validate against the required JSON schema.\n"
                "Return ONLY valid JSON that matches the schema exactly (all required fields present; correct types; no extra keys).\n\n"
                f"Schema:\n{schema}\n\n"
                f"Validation error:\n{last_error}\n\n"
                "Previous response:\n"
                f"{content}\n"
            )
            repair_messages = list(llm_messages)
            repair_messages.append(
                LLMMessage(role=MessageRole.ASSISTANT, content=content)
            )
            repair_messages.append(
                LLMMessage(role=MessageRole.USER, content=repair_prompt)
            )

            content = await _call_llm(repair_messages, temperature=0.0)
            try:
                return response_model.model_validate_json(content)
            except Exception as e:
                last_error = str(e)

        if response_model is LegislationAnalysisResponse:
            return LegislationAnalysisResponse(
                bill_number=_extract_bill_number() or "UNKNOWN",
                sufficiency_state=SufficiencyState.INSUFFICIENT_EVIDENCE,
                quantification_eligible=False,
                impacts=[],
                total_impact_p50=None,
                analysis_timestamp=datetime.now().isoformat(),
                model_used=model,
            )
        if response_model is ReviewCritique:
            return ReviewCritique(
                passed=False,
                critique=f"LLM output did not match schema after retries: {last_error}",
                missing_impacts=[],
                factual_errors=[last_error[:500]],
            )
        raise ValidationError(
            f"LLM output did not match schema after retries: {last_error}",
            response_model,
        )  # type: ignore[arg-type]

    async def _generate_step(
        self,
        bill_id: str,
        bill_text: str,
        jurisdiction: str,
        research_result: LegislationResearchResult,
        model: str,
        breakdown: Any = None,
    ) -> LegislationAnalysisResponse:
        """
        Generate analysis using LLM with structured evidence.
        """
        evidence_context = self._format_evidence_for_generation(research_result)

        sufficiency_note = ""
        if not research_result.is_sufficient:
            sufficiency_note = f"""
IMPORTANT: Research insufficiency detected: {research_result.insufficiency_reason}

Your analysis should acknowledge data gaps. If evidence is insufficient for 
quantification, provide qualitative analysis only.
"""
        if breakdown and not breakdown.quantification_eligible:
            sufficiency_note += (
                "\nIMPORTANT: Quantification is NOT permitted for this bill. "
                "Set all p10/p25/p50/p75/p90 fields to null. "
                f"Reason: {'; '.join(breakdown.insufficiency_reasons)}\n"
            )

        system_prompt = f"""
You are an expert policy analyst. Analyze legislation for cost-of-living impacts.

{sufficiency_note}

Use the provided research data to support your analysis.
Base your estimates only on the evidence provided.
Be conservative and evidence-based.
Cite sources when making claims.
"""

        user_message = f"""
Bill: {bill_id} ({jurisdiction})

Research Evidence:
{evidence_context}

Bill Text:
{bill_text[:5000]}
"""

        result = await self._chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            model=model,
            response_model=LegislationAnalysisResponse,
        )
        return result  # type: ignore[return-value]

    def _format_evidence_for_generation(
        self, research_result: LegislationResearchResult
    ) -> str:
        """Format research evidence for generation prompt."""
        parts = []

        parts.append(
            f"Research Sufficiency: {'Sufficient' if research_result.is_sufficient else 'Insufficient'}"
        )
        parts.append(f"RAG Chunks Retrieved: {len(research_result.rag_chunks)}")
        parts.append(f"Web Sources Found: {len(research_result.web_sources)}")
        parts.append("")

        if research_result.rag_chunks:
            parts.append("=== Internal Documents (RAG) ===")
            for i, chunk in enumerate(research_result.rag_chunks[:5], 1):
                source = (
                    chunk.metadata.get("source_url")
                    or chunk.metadata.get("source_id")
                    or "unknown"
                )
                parts.append(f"[{i}] (Source: {source}, Score: {chunk.score:.2f})")
                parts.append(chunk.content[:500])
                parts.append("")

        if research_result.web_sources:
            parts.append("=== Web Research ===")
            for i, source in enumerate(research_result.web_sources[:10], 1):
                title = source.get("title", "Untitled")
                url = source.get("url") or source.get("link", "")
                snippet = source.get("snippet", "")[:300]
                parts.append(f"[{i}] {title}")
                parts.append(f"URL: {url}")
                parts.append(f"Snippet: {snippet}")
                parts.append("")

        return "\n".join(parts)

    async def _review_step(
        self,
        bill_id: str,
        analysis: LegislationAnalysisResponse,
        research_result: LegislationResearchResult,
        model: str,
    ) -> ReviewCritique:
        """Review analysis using LLM."""
        system_prompt = "You are a senior policy reviewer. Critique the following analysis for accuracy, evidence, and conservatism."

        evidence_summary = f"RAG chunks: {len(research_result.rag_chunks)}, Web sources: {len(research_result.web_sources)}, Sufficient: {research_result.is_sufficient}"

        user_message = f"""
Bill: {bill_id}
Analysis: {analysis.model_dump_json()}
Evidence Summary: {evidence_summary}
"""

        result = await self._chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            model=model,
            response_model=ReviewCritique,
        )
        return result  # type: ignore[return-value]

    async def _refine_step(
        self,
        bill_id: str,
        analysis: LegislationAnalysisResponse,
        review: ReviewCritique,
        bill_text: str,
        model: str,
        breakdown: Any = None,
    ) -> LegislationAnalysisResponse:
        """Refine analysis based on critique."""
        quantification_note = ""
        if breakdown and not breakdown.quantification_eligible:
            quantification_note = (
                "\n\nIMPORTANT: Quantification is NOT permitted for this bill. "
                "Set all p10/p25/p50/p75/p90 fields to null."
            )
        system_prompt = (
            "Refine the analysis based on the critique. Ensure all issues are addressed."
            f"{quantification_note}"
        )

        user_message = f"""
Original Analysis: {analysis.model_dump_json()}
Critique: {review.model_dump_json()}
Bill Text: {bill_text[:5000]}
"""

        result = await self._chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            model=model,
            response_model=LegislationAnalysisResponse,
        )
        return result  # type: ignore[return-value]

    async def _create_pipeline_run(
        self, bill_id: str, jurisdiction: str, models: Dict[str, str]
    ) -> str:
        """Create a new pipeline run record."""
        if hasattr(self.db, "create_pipeline_run"):
            run_id = await self.db.create_pipeline_run(bill_id, jurisdiction, models)
            if run_id:
                return run_id
        return "run_id_placeholder"

    async def _complete_pipeline_run(
        self,
        run_id: str,
        bill_id: str,
        bill_text: str,
        analysis: LegislationAnalysisResponse,
        review: ReviewCritique,
        jurisdiction: str,
        breakdown: Any = None,
        rag_chunks_retrieved: int = 0,
        retriever_invoked: bool = False,
    ):
        """Mark pipeline run as complete and store results with truthful metadata."""
        try:
            bill_data = {
                "bill_number": bill_id,
                "title": analysis.title
                if analysis.title and analysis.title != ""
                else None,
                "text": bill_text if bill_text else None,
                "status": "analyzed",
                "sufficiency_state": analysis.sufficiency_state.value
                if analysis.sufficiency_state
                else None,
                "insufficiency_reason": analysis.insufficiency_reason,
                "quantification_eligible": analysis.quantification_eligible,
                "total_impact_p50": analysis.total_impact_p50,
            }

            if hasattr(self.db, "get_or_create_jurisdiction"):
                jurisdiction_id = await self.db.get_or_create_jurisdiction(
                    jurisdiction, "municipality"
                )
                if not jurisdiction_id:
                    logger.error(
                        f"Failed to resolve jurisdiction_id for {jurisdiction}"
                    )
                    return

                if hasattr(self.db, "store_legislation"):
                    legislation_id = await self.db.store_legislation(
                        jurisdiction_id, bill_data
                    )

                    if legislation_id:
                        impact_dicts = [i.model_dump() for i in analysis.impacts]
                        if hasattr(self.db, "store_impacts"):
                            await self.db.store_impacts(legislation_id, impact_dicts)
                        logger.info(f"Stored analysis results for {bill_id}")

            result_data = {
                "analysis": analysis.model_dump(),
                "review": review.model_dump(),
                "sufficiency_breakdown": breakdown.model_dump() if breakdown else None,
                "source_text_present": bool(bill_text and len(bill_text) > 100),
                "retriever_invoked": retriever_invoked,
                "rag_chunks_retrieved": rag_chunks_retrieved,
                "validated_evidence_count": len(analysis.impacts)
                if analysis.impacts
                else 0,
                "quantification_eligible": analysis.quantification_eligible,
                "insufficiency_reason": analysis.insufficiency_reason,
                "model_used": analysis.model_used,
            }
            if hasattr(self.db, "complete_pipeline_run"):
                await self.db.complete_pipeline_run(run_id, result_data)

        except Exception as e:
            logger.error(f"Failed to store results: {e}")
            import traceback

            traceback.print_exc()

    async def _fail_pipeline_run(self, run_id: str, error: str):
        """Mark pipeline run as failed."""
        print(f"Pipeline Run {run_id} Failed: {error}")
        if hasattr(self.db, "fail_pipeline_run"):
            await self.db.fail_pipeline_run(run_id, error)
