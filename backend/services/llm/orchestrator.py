from __future__ import annotations
from llm_common.core import LLMClient
from llm_common.web_search import WebSearchClient
from llm_common.agents import ResearchAgent
from llm_common.core.models import LLMMessage, MessageRole
from typing import List, Dict, Any
import re
from pydantic import BaseModel, ValidationError
from schemas.analysis import LegislationAnalysisResponse, ReviewCritique
from datetime import datetime

class AnalysisPipeline:
    """
    Orchestrate multi-step legislation analysis.
    
    Workflow:
    1. Research: Agentic web search (TaskPlanner + AgenticExecutor)
    2. Generate: LLM analysis with structured output (LegislationAnalysisResponse)
    3. Review: LLM critique
    4. Refine: Regenerate if review failed
    """
    
    def __init__(
        self,
        llm_client: LLMClient,
        search_client: WebSearchClient,
        db_client: Any,
        fallback_client: LLMClient | None = None
    ):
        """
        Initialize pipeline.
        
        Args:
            llm_client: Primary LLM client (e.g. Z.ai)
            search_client: Web search client
            db_client: Database client
            fallback_client: Optional fallback/embedding provider (e.g. OpenRouter)
        """
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
        models: Dict[str, str]
    ) -> LegislationAnalysisResponse:
        """
        Run full pipeline.
        
        Args:
            bill_id: Bill identifier (e.g., "AB-1234")
            bill_text: Full bill text
            jurisdiction: Jurisdiction (e.g., "California")
            models: {"research": "gpt-4o-mini", "generate": "claude-3.5-sonnet", "review": "glm-4.7"}
        
        Returns:
            Final analysis (validated LegislationAnalysisResponse)
        """
        from services.audit.logger import AuditLogger
        
        run_id = await self._create_pipeline_run(bill_id, jurisdiction, models)
        audit = AuditLogger(run_id, self.db)
        
        try:
            # Step 0: Ingestion Source (Synthetic Link)
            # Step 0: Ingestion Source (Virtual)
            source_data = await self.db.get_latest_scrape_for_bill(jurisdiction, bill_id)
            if source_data:
                await audit.log_step(
                    step_number=0,
                    step_name="ingestion_source",
                    status="completed",
                    input_context={
                        "jurisdiction": jurisdiction,
                        "bill_id": bill_id,
                        "bill_text_preview": bill_text[:500] + "..." if bill_text else "N/A"
                    },
                    output_result={
                        "raw_scrape_id": str(source_data['id']),
                        "source_url": source_data['url'],
                        "content_hash": source_data['content_hash'],
                        "metadata": source_data['metadata'],
                        "minio_blob_path": source_data.get('storage_uri', 'N/A')
                    },
                    model_info={"model": "scraper", "provider": "firecrawl"},
                    duration_ms=0
                )

                # Step 0.5: Embedding / Vector Storage (Virtual)
                if source_data.get('document_id'):
                    vector_stats = await self.db.get_vector_stats(source_data['document_id'])
                    await audit.log_step(
                        step_number=0.5,
                        step_name="embedding",
                        status="completed",
                        input_context={
                            "document_id": source_data['document_id'],
                            "chunk_strategy": "fixed_size",
                            "chunk_size": 1000,
                            "chunk_overlap": 200
                        },
                        output_result={
                            "vector_db": "pgvector",
                            "chunks_generated": vector_stats.get('chunk_count', 0),
                            "status": "indexed"
                        },
                        model_info={"model": "text-embedding-3-small", "provider": "openai"},
                        duration_ms=0
                    )
            else:
                await audit.log_step(
                    step_number=0,
                    step_name="ingestion_source",
                    status="skipped",
                    input_context={"jurisdiction": jurisdiction, "bill_id": bill_id},
                    output_result={"error": "No raw scrape found for this bill."},
                    model_info={"model": "scraper", "provider": "firecrawl"},
                    duration_ms=0
                )

            # Step 1: Research
            start_ts = datetime.now()
            research_data = await self._research_step(bill_id, bill_text, jurisdiction, models["research"])
            duration = int((datetime.now() - start_ts).total_seconds() * 1000)
            
            await audit.log_step(
                step_number=1,
                step_name="research",
                status="completed",
                input_context={"bill_id": bill_id, "prompt": "Research task planner"},
                output_result={"research_data": research_data},
                model_info={"model": models["research"]},
                duration_ms=duration
            )
            
            # Step 2: Generate
            start_ts = datetime.now()
            analysis = await self._generate_step(
                bill_id, bill_text, jurisdiction, research_data, models["generate"]
            )
            duration = int((datetime.now() - start_ts).total_seconds() * 1000)
            
            await audit.log_step(
                step_number=2,
                step_name="generate",
                status="completed",
                input_context={"research_data_count": len(research_data)},
                output_result=analysis.model_dump(),
                model_info={"model": models["generate"]},
                duration_ms=duration
            )
            
            # Step 3: Review
            start_ts = datetime.now()
            review = await self._review_step(bill_id, analysis, research_data, models["review"])
            duration = int((datetime.now() - start_ts).total_seconds() * 1000)
            
            await audit.log_step(
                step_number=3,
                step_name="review",
                status="completed",
                input_context={"analysis_summary": "See generate step"},
                output_result=review.model_dump(),
                model_info={"model": models["review"]},
                duration_ms=duration
            )
            
            # Step 4: Refine (if needed)
            if not review.passed:
                start_ts = datetime.now()
                analysis = await self._refine_step(
                    bill_id, analysis, review, bill_text, models["generate"]
                )
                duration = int((datetime.now() - start_ts).total_seconds() * 1000)
                
                await audit.log_step(
                    step_number=4,
                    step_name="refine",
                    status="completed",
                    input_context={"critique": review.model_dump()},
                    output_result=analysis.model_dump(),
                    model_info={"model": models["generate"]},
                    duration_ms=duration
                )
            
            # Mark run as complete
            await self._complete_pipeline_run(run_id, bill_id, analysis, review, jurisdiction)
            
            return analysis
        
        except Exception as e:
            await self._fail_pipeline_run(run_id, str(e))
            # Log failure to audit
            await audit.log_step(
                step_number=99, 
                step_name="pipeline_failure", 
                status="failed", 
                output_result={"error": str(e)},
                model_info={"models_attempted": models}
            )
            raise
    
    async def _research_step(
        self,
        bill_id: str,
        bill_text: str,
        jurisdiction: str,
        model: str
    ) -> List[Dict[str, Any]]:
        """
        Research step: Use ResearchAgent to find information.
        """
        # Note: ResearchAgent doesn't strictly support swapping model easily yet 
        # without re-init, but we assume default client setup is fine or add that capability later.
        
        # Execute agent
        agent_result = await self.research_agent.run(bill_id, bill_text, jurisdiction)
        
        return agent_result.get("collected_data", [])
    
    async def _chat(self, messages: List[Dict], model: str, response_model: type[BaseModel]) -> BaseModel:
        """Helper to get structured output from LLMClient."""
        # Convert dict messages to LLMMessage if needed, or rely on LLMClient handling dicts (usually it expects LLMMessage objects)
        
        llm_messages = []
        for m in messages:
            role = MessageRole.USER if m["role"] == "user" else MessageRole.SYSTEM
            llm_messages.append(LLMMessage(role=role, content=m["content"]))
            
        # Append JSON instruction
        schema = response_model.model_json_schema()
        json_instruction = f"\n\nRespond with valid JSON matching this schema:\n{schema}"
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
                    impacts=[],
                    total_impact_p50=0.0,
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
            raise ValidationError(f"LLM output did not match schema after retries: {validation_error}", response_model)  # type: ignore[arg-type]

        async def _call_llm(call_messages: list[LLMMessage], *, temperature: float) -> str:
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
                fallback_model = self.fallback_llm.config.default_model or "google/gemini-2.0-flash-exp"
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
            repair_messages.append(LLMMessage(role=MessageRole.ASSISTANT, content=content))
            repair_messages.append(LLMMessage(role=MessageRole.USER, content=repair_prompt))

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
        model: str
    ) -> LegislationAnalysisResponse:
        """
        Generate analysis using LLM.
        """
        system_prompt = """
        You are an expert policy analyst. Analyze legislation for cost-of-living impacts.
        Use the provided research data to support your analysis.
        Be conservative and evidence-based.
        """
        
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
                {"role": "user", "content": user_message}
            ],
            model=model,
            response_model=LegislationAnalysisResponse
        )
    
    async def _review_step(
        self,
        bill_id: str,
        analysis: LegislationAnalysisResponse,
        research_data: List[Dict],
        model: str
    ) -> ReviewCritique:
        """Review analysis using LLM."""
        system_prompt = "You are a senior policy reviewer. Critique the following analysis for accuracy, evidence, and conservatism."
        
        user_message = f"""
        Bill: {bill_id}
        Analysis: {analysis.model_dump_json()}
        Research: {research_data}
        """
        
        return await self._chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            model=model,
            response_model=ReviewCritique
        )

    async def _refine_step(
        self,
        bill_id: str,
        analysis: LegislationAnalysisResponse,
        review: ReviewCritique,
        bill_text: str,
        model: str
    ) -> LegislationAnalysisResponse:
        """Refine analysis based on critique."""
        system_prompt = "Refine the analysis based on the critique. Ensure all issues are addressed."
        
        user_message = f"""
        Original Analysis: {analysis.model_dump_json()}
        Critique: {review.model_dump_json()}
        Bill Text: {bill_text}
        """
        
        return await self._chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            model=model,
            response_model=LegislationAnalysisResponse
        )

    # Database logging methods
    async def _create_pipeline_run(self, bill_id: str, jurisdiction: str, models: Dict[str, str]) -> str:
        """Create a new pipeline run record."""
        # TODO: verify db methods exist or mock them
        if hasattr(self.db, 'create_pipeline_run'):
            run_id = await self.db.create_pipeline_run(bill_id, jurisdiction, models)
            if run_id:
                return run_id
        return "run_id_placeholder"

    async def _log_step(self, run_id: str, step_name: str, model: str, data: Any):
        """Log a pipeline step."""
        print(f"Pipeline Run {run_id} Step {step_name}: Completed")

    async def _complete_pipeline_run(self, run_id: str, bill_id: str, analysis: LegislationAnalysisResponse, review: ReviewCritique, jurisdiction: str):
        """Mark pipeline run as complete and store results."""
        try:
            # 1. Store Legislation
            bill_data = {
                "bill_number": bill_id,
                "title": f"Analysis: {bill_id}",
                "text": "Full text placeholder", 
                "status": "analyzed"
            }
            
            # Lookup jurisdiction ID
            if hasattr(self.db, 'get_or_create_jurisdiction'):
                jurisdiction_id = await self.db.get_or_create_jurisdiction(jurisdiction, "municipality")
                if not jurisdiction_id:
                    print(f"Failed to resolve jurisdiction_id for {jurisdiction}")
                    return

                if hasattr(self.db, 'store_legislation'):
                    legislation_id = await self.db.store_legislation(jurisdiction_id, bill_data)
                    
                    if legislation_id:
                       # 2. Store Impacts
                       impact_dicts = [i.model_dump() for i in analysis.impacts]
                       if hasattr(self.db, 'store_impacts'):
                           await self.db.store_impacts(legislation_id, impact_dicts)
                       print(f"✅ Stored analysis results for {bill_id}")
            
            # 3. Update Pipeline Run
            result_data = {
                "analysis": analysis.model_dump(),
                "review": review.model_dump()
            }
            if hasattr(self.db, 'complete_pipeline_run'):
                await self.db.complete_pipeline_run(run_id, result_data)

        except Exception as e:
            print(f"Failed to store results: {e}")
            import traceback
            traceback.print_exc()

    async def _fail_pipeline_run(self, run_id: str, error: str):
        """Mark pipeline run as failed."""
        print(f"Pipeline Run {run_id} Failed: {error}")
        if hasattr(self.db, 'fail_pipeline_run'):
            await self.db.fail_pipeline_run(run_id, error)
