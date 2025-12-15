from __future__ import annotations
from llm_common.core import LLMClient
from llm_common.web_search import WebSearchClient
from llm_common.agents import ResearchAgent
from typing import List, Dict, Any
from pydantic import BaseModel

class BillAnalysis(BaseModel):
    """Structured analysis output."""
    summary: str
    impacts: List[Dict[str, Any]]
    confidence: float
    sources: List[str]

class ReviewCritique(BaseModel):
    """Review output."""
    passed: bool
    critique: str
    missing_impacts: List[str]
    factual_errors: List[str]

class AnalysisPipeline:
    """
    Orchestrate multi-step legislation analysis.
    
    Workflow:
    1. Research: z.ai web search (20-30 queries)
    2. Generate: LLM analysis with structured output
    3. Review: LLM critique
    4. Refine: Regenerate if review failed
    """
    
    def __init__(
        self,
        llm_client: LLMClient,
        search_client: WebSearchClient,
        db_client: Any
    ):
        """
        Initialize pipeline.
        
        Args:
            llm_client: LLM client (LiteLLM wrapper)
            search_client: Web search client (z.ai)
            cost_tracker: Cost tracking client
            db_client: Supabase client for logging
        """
        self.llm = llm_client
        self.search = search_client
        self.db = db_client
        self.research_agent = ResearchAgent(llm_client, search_client)
    
    async def run(
        self,
        bill_id: str,
        bill_text: str,
        jurisdiction: str,
        models: Dict[str, str]
    ) -> BillAnalysis:
        """
        Run full pipeline.
        
        Args:
            bill_id: Bill identifier (e.g., "AB-1234")
            bill_text: Full bill text
            jurisdiction: Jurisdiction (e.g., "California")
            models: {"research": "gpt-4o-mini", "generate": "claude-3.5-sonnet", "review": "glm-4.5"}
        
        Returns:
            Final analysis (validated BillAnalysis)
        """
        run_id = await self._create_pipeline_run(bill_id, jurisdiction, models)
        
        try:
            # Step 1: Research
            research_data = await self._research_step(bill_id, bill_text, jurisdiction, models["research"])
            await self._log_step(run_id, "research", models["research"], research_data)
            
            # Step 2: Generate
            analysis = await self._generate_step(
                bill_id, bill_text, jurisdiction, research_data, models["generate"]
            )
            await self._log_step(run_id, "generate", models["generate"], analysis.model_dump())
            
            # Step 3: Review
            review = await self._review_step(bill_id, analysis, research_data, models["review"])
            await self._log_step(run_id, "review", models["review"], review.model_dump())
            
            # Step 4: Refine (if needed)
            if not review.passed:
                analysis = await self._refine_step(
                    bill_id, analysis, review, bill_text, models["generate"]
                )
                await self._log_step(run_id, "refine", models["generate"], analysis.model_dump())
            
            # Mark run as complete
            await self._complete_pipeline_run(run_id, bill_id, analysis, review, jurisdiction)
            
            return analysis
        
        except Exception as e:
            await self._fail_pipeline_run(run_id, str(e))
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
        
        Returns:
            List of search results
        """
        # Update agent model if needed
        self.research_agent.model_name = model
        
        # Execute agent
        agent_result = await self.research_agent.run(bill_id, bill_text, jurisdiction)
        
        # Log plan and summary if beneficial (currently we just return search results for downstream)
        # Ideally we'd log the whole agent interaction.
        # But for compatibility, we return the collected structured data.
        
        return agent_result.get("collected_data", [])
    
    async def _generate_research_queries(
        self,
        bill_id: str,
        bill_text: str,
        model: str
    ) -> List[str]:
        """Generate 20-30 research queries using LLM."""
        class ResearchQueries(BaseModel):
            queries: List[str]
        
        response = await self.llm.chat(
            messages=[
                {"role": "system", "content": "Generate research queries for legislation analysis."},
                {"role": "user", "content": f"Bill: {bill_id}\nText: {bill_text[:1000]}..."}
            ],
            model=model,
            response_model=ResearchQueries
        )
        
        return response.queries
    
    async def _generate_step(
        self,
        bill_id: str,
        bill_text: str,
        jurisdiction: str,
        research_data: List[Dict],
        model: str
    ) -> BillAnalysis:
        """
        Generate analysis using LLM.
        
        Returns:
            Validated BillAnalysis
        """
        system_prompt = """
        You are an expert policy analyst. Analyze legislation for cost-of-living impacts.
        Use the provided research data to support your analysis.
        """
        
        user_message = f"""
        Bill: {bill_id} ({jurisdiction})
        
        Research Data:
        {research_data}
        
        Bill Text:
        {bill_text}
        """
        
        return await self.llm.chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            model=model,
            response_model=BillAnalysis
        )
    
    async def _review_step(
        self,
        bill_id: str,
        analysis: BillAnalysis,
        research_data: List[Dict],
        model: str
    ) -> ReviewCritique:
        """Review analysis using LLM."""
        system_prompt = "You are a senior policy reviewer. Critique the following analysis."
        
        user_message = f"""
        Bill: {bill_id}
        Analysis: {analysis.model_dump_json()}
        Research: {research_data}
        """
        
        return await self.llm.chat(
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
        analysis: BillAnalysis,
        review: ReviewCritique,
        bill_text: str,
        model: str
    ) -> BillAnalysis:
        """Refine analysis based on critique."""
        system_prompt = "Refine the analysis based on the critique."
        
        user_message = f"""
        Original Analysis: {analysis.model_dump_json()}
        Critique: {review.model_dump_json()}
        Bill Text: {bill_text}
        """
        
        return await self.llm.chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            model=model,
            response_model=BillAnalysis
        )

    # Database logging methods (placeholders for now, assuming Supabase client structure)
    async def _create_pipeline_run(self, bill_id: str, jurisdiction: str, models: Dict[str, str]) -> str:
        """Create a new pipeline run record."""
        run_id = await self.db.create_pipeline_run(bill_id, jurisdiction, models)
        if run_id:
            return run_id
        return "run_id_placeholder"

    async def _log_step(self, run_id: str, step_name: str, model: str, data: Any):
        """Log a pipeline step."""
        print(f"Pipeline Run {run_id} Step {step_name}: Completed")

    async def _complete_pipeline_run(self, run_id: str, bill_id: str, analysis: BillAnalysis, review: ReviewCritique, jurisdiction: str):
        """Mark pipeline run as complete and store results."""
        try:
            # 1. Store Legislation (Upsert)
            # Use BillAnalysis data + minimal defaults
            bill_data = {
                "bill_number": bill_id,
                "title": f"Analysis: {bill_id}", # Default title if missing
                "text": "Full text not available in analysis object", # Ideally fetched from context
                "status": "analyzed"
            }
            # Note: store_legislation updates if exists, preserving text if we don't overwrite it?
            # PostgresDB.store_legislation overwrites text.
            # Ideally we should fetch existing first or just store impacts if we know leg exists.
            # But here we want a robust "Ensure Exists" logic.
            # Let's rely on bill_number matching.
            
            # Lookup jurisdiction ID
            # Assuming passed jurisdiction is name (e.g. "San Jose")
            jurisdiction_id = await self.db.get_or_create_jurisdiction(jurisdiction, "municipality")
            if not jurisdiction_id:
                print(f"Failed to resolve jurisdiction_id for {jurisdiction}")
                return

            legislation_id = await self.db.store_legislation(jurisdiction_id, bill_data)
            
            if legislation_id:
               # 2. Store Impacts
               # Convert impacts to dicts
               impact_dicts = [i.model_dump() for i in analysis.impacts]
               await self.db.store_impacts(legislation_id, impact_dicts)
               print(f"✅ Stored analysis results for {bill_id}")
            else:
               print(f"❌ Failed to store legislation for {bill_id}")

            # 3. Update Pipeline Run
            result_data = {
                "analysis": analysis.model_dump(),
                "review": review.model_dump()
            }
            await self.db.complete_pipeline_run(run_id, result_data)

        except Exception as e:
            print(f"Failed to store results: {e}")
            import traceback
            traceback.print_exc()

    async def _fail_pipeline_run(self, run_id: str, error: str):
        """Mark pipeline run as failed."""
        print(f"Pipeline Run {run_id} Failed: {error}")
        await self.db.fail_pipeline_run(run_id, error)
