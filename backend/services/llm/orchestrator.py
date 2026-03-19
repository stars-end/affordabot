from __future__ import annotations
from llm_common.core import LLMClient
from llm_common.web_search import WebSearchClient
from llm_common.agents import ResearchAgent
from llm_common.core.models import LLMMessage, MessageRole
from typing import List, Dict, Any, Optional
import re
from pydantic import BaseModel, ValidationError
from schemas.analysis import (
    LegislationAnalysisResponse,
    ReviewCritique,
    SufficiencyState,
    LegislationImpact,
)
from services.llm.evidence_gates import assess_sufficiency, strip_quantification
from services.llm.evidence_adapter import research_data_to_evidence_items
from datetime import datetime


class AnalysisPipeline:
    """
    Orchestrate multi-step legislation analysis.

    Workflow:
    1. Research: Agentic web search (TaskPlanner + AgenticExecutor)
    1.5. Evidence Sufficiency Gate: deterministic check before generation
    2. Generate: LLM analysis with structured output (LegislationAnalysisResponse)
    3. Review: LLM critique
    4. Refine: Regenerate if review failed
    """

    def __init__(
        self,
        llm_client: LLMClient,
        search_client: WebSearchClient,
        db_client: Any,
        fallback_client: LLMClient | None = None,
    ):
        self.llm = llm_client
        self.search = search_client
        self.db = db_client
        self.fallback_llm = fallback_client
        self.research_agent = ResearchAgent(llm_client, search_client)

    async def run(
        self,
        bill_id: str,
        bill_text: str,
        jurisdiction: str,
        models: Dict[str, str],
    ) -> LegislationAnalysisResponse:
        from services.audit.logger import AuditLogger

        run_id = await self._create_pipeline_run(bill_id, jurisdiction, models)
        audit = AuditLogger(run_id, self.db)

        try:
            source_data = await self.db.get_latest_scrape_for_bill(
                jurisdiction, bill_id
            )
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
                    output_result={"error": "No raw scrape found for this bill."},
                    model_info={"model": "scraper", "provider": "firecrawl"},
                    duration_ms=0,
                )

            start_ts = datetime.now()
            research_data = await self._research_step(
                bill_id, bill_text, jurisdiction, models["research"]
            )
            duration = int((datetime.now() - start_ts).total_seconds() * 1000)

            evidence_items = research_data_to_evidence_items(research_data)

            await audit.log_step(
                step_number=1,
                step_name="research",
                status="completed",
                input_context={"bill_id": bill_id, "prompt": "Research task planner"},
                output_result={
                    "research_data_count": len(research_data),
                    "evidence_items_count": len(evidence_items),
                },
                model_info={"model": models["research"]},
                duration_ms=duration,
            )

            breakdown = assess_sufficiency(
                bill_text=bill_text,
                evidence_list=evidence_items,
                web_research_count=len(research_data),
            )

            await audit.log_step(
                step_number=1,
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
                    analysis,
                    ReviewCritique(
                        passed=False,
                        critique="Skipped: research incomplete",
                        missing_impacts=[],
                        factual_errors=[],
                    ),
                    jurisdiction,
                )
                return analysis

            start_ts = datetime.now()
            analysis = await self._generate_step(
                bill_id,
                bill_text,
                jurisdiction,
                research_data,
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
                step_number=2,
                step_name="generate",
                status="completed",
                input_context={
                    "research_data_count": len(research_data),
                    "sufficiency_state": breakdown.sufficiency_state.value,
                },
                output_result=analysis.model_dump(),
                model_info={"model": models["generate"]},
                duration_ms=duration,
            )

            start_ts = datetime.now()
            review = await self._review_step(
                bill_id, analysis, research_data, models["review"]
            )
            duration = int((datetime.now() - start_ts).total_seconds() * 1000)

            await audit.log_step(
                step_number=3,
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
                    bill_id, analysis, review, bill_text, models["generate"], breakdown
                )
                duration = int((datetime.now() - start_ts).total_seconds() * 1000)

                if not breakdown.quantification_eligible:
                    analysis.impacts = [
                        LegislationImpact(**strip_quantification([imp.model_dump()])[0])
                        for imp in analysis.impacts
                    ]
                    analysis.sufficiency_state = breakdown.sufficiency_state
                    analysis.quantification_eligible = False
                    analysis.total_impact_p50 = None

                await audit.log_step(
                    step_number=4,
                    step_name="refine",
                    status="completed",
                    input_context={"critique": review.model_dump()},
                    output_result=analysis.model_dump(),
                    model_info={"model": models["generate"]},
                    duration_ms=duration,
                )

            await self._complete_pipeline_run(
                run_id, bill_id, analysis, review, jurisdiction
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
        self,
        bill_id: str,
        bill_text: str,
        jurisdiction: str,
        model: str,
    ) -> List[Dict[str, Any]]:
        agent_result = await self.research_agent.run(bill_id, bill_text, jurisdiction)
        return agent_result.get("collected_data", [])

    async def _chat(
        self, messages: List[Dict], model: str, response_model: type[BaseModel]
    ) -> BaseModel:
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

        def _fallback_model(validation_error: str) -> BaseModel:
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
                    critique=f"LLM output did not match schema after retries: {validation_error}",
                    missing_impacts=[],
                    factual_errors=[validation_error[:500]],
                )
            raise ValidationError(
                f"LLM output did not match schema after retries: {validation_error}",
                response_model,
            )  # type: ignore[arg-type]

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
                fallback_model_name = (
                    self.fallback_llm.config.default_model
                    or "google/gemini-2.0-flash-exp"
                )
                response = await self.fallback_llm.chat_completion(
                    messages=call_messages,
                    model=fallback_model_name,
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

        return _fallback_model(last_error)

    async def _generate_step(
        self,
        bill_id: str,
        bill_text: str,
        jurisdiction: str,
        research_data: List[Dict],
        model: str,
        breakdown: Any = None,
    ) -> LegislationAnalysisResponse:
        quantification_note = ""
        if breakdown and not breakdown.quantification_eligible:
            quantification_note = (
                "\n\nIMPORTANT: Quantification is NOT permitted for this bill. "
                "Set all p10/p25/p50/p75/p90 fields to null. "
                f"Reason: {'; '.join(breakdown.insufficiency_reasons)}"
            )

        system_prompt = (
            "You are an expert policy analyst. Analyze legislation for cost-of-living impacts.\n"
            "Use the provided research data to support your analysis.\n"
            "Be conservative and evidence-based.\n"
            "If evidence is insufficient, provide qualitative analysis only "
            "and set percentile fields to null."
            f"{quantification_note}"
        )

        user_message = f"""
        Bill: {bill_id} ({jurisdiction})

        Research Data:
        {research_data}

        Bill Text:
        {bill_text}
        """

        return await self._chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            model=model,
            response_model=LegislationAnalysisResponse,
        )

    async def _review_step(
        self,
        bill_id: str,
        analysis: LegislationAnalysisResponse,
        research_data: List[Dict],
        model: str,
    ) -> ReviewCritique:
        system_prompt = "You are a senior policy reviewer. Critique the following analysis for accuracy, evidence, and conservatism."

        user_message = f"""
        Bill: {bill_id}
        Analysis: {analysis.model_dump_json()}
        Research: {research_data}
        """

        return await self._chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            model=model,
            response_model=ReviewCritique,
        )

    async def _refine_step(
        self,
        bill_id: str,
        analysis: LegislationAnalysisResponse,
        review: ReviewCritique,
        bill_text: str,
        model: str,
        breakdown: Any = None,
    ) -> LegislationAnalysisResponse:
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
        Bill Text: {bill_text}
        """

        return await self._chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            model=model,
            response_model=LegislationAnalysisResponse,
        )

    async def _create_pipeline_run(
        self, bill_id: str, jurisdiction: str, models: Dict[str, str]
    ) -> str:
        if hasattr(self.db, "create_pipeline_run"):
            run_id = await self.db.create_pipeline_run(bill_id, jurisdiction, models)
            if run_id:
                return run_id
        return "run_id_placeholder"

    async def _log_step(self, run_id: str, step_name: str, model: str, data: Any):
        print(f"Pipeline Run {run_id} Step {step_name}: Completed")

    async def _complete_pipeline_run(
        self,
        run_id: str,
        bill_id: str,
        analysis: LegislationAnalysisResponse,
        review: ReviewCritique,
        jurisdiction: str,
    ):
        try:
            bill_data = {
                "bill_number": bill_id,
                "title": analysis.title or bill_id,
                "text": bill_text
                if (bill_text := getattr(analysis, "_bill_text", None))
                else "",
                "status": "analyzed",
            }

            if hasattr(self.db, "get_or_create_jurisdiction"):
                jurisdiction_id = await self.db.get_or_create_jurisdiction(
                    jurisdiction, "municipality"
                )
                if not jurisdiction_id:
                    print(f"Failed to resolve jurisdiction_id for {jurisdiction}")
                    return

                if hasattr(self.db, "store_legislation"):
                    legislation_id = await self.db.store_legislation(
                        jurisdiction_id, bill_data
                    )

                    if legislation_id:
                        impact_dicts = [i.model_dump() for i in analysis.impacts]
                        if hasattr(self.db, "store_impacts"):
                            await self.db.store_impacts(legislation_id, impact_dicts)
                        print(f"Stored analysis results for {bill_id}")

            result_data = {
                "analysis": analysis.model_dump(),
                "review": review.model_dump(),
            }
            if hasattr(self.db, "complete_pipeline_run"):
                await self.db.complete_pipeline_run(run_id, result_data)

        except Exception as e:
            print(f"Failed to store results: {e}")
            import traceback

            traceback.print_exc()

    async def _fail_pipeline_run(self, run_id: str, error: str):
        print(f"Pipeline Run {run_id} Failed: {error}")
        if hasattr(self.db, "fail_pipeline_run"):
            await self.db.fail_pipeline_run(run_id, error)
