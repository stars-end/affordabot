import os
import logging
import asyncio
from typing import List, Optional
from pathlib import Path

from llm_common.core.models import LLMConfig
from llm_common.providers.openrouter_client import OpenRouterClient
from llm_common.agents import (
    TaskPlanner, 
    AgenticExecutor, 
    ToolRegistry, 
    ToolContextManager
)
from services.research.agent_tools import WebSearchTool, UrlFetchTool
from schemas.analysis import LegislationAnalysisResponse
import instructor
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

class AgentService:
    def __init__(self):
        # 1. Setup LLM Client for Agent (using llm-common)
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            logger.warning("OPENROUTER_API_KEY not set. Agent service will fail.")
            
        config = LLMConfig(
            api_key=api_key or "mock",
            provider="openrouter",
            default_model="x-ai/grok-4.1-fast:free", # Efficient model for planning/exec
            temperature=0.0
        )
        self.client = OpenRouterClient(config)
        
        # 2. Setup Tools
        self.registry = ToolRegistry()
        self.registry.register(WebSearchTool())
        self.registry.register(UrlFetchTool())
        
        # 3. Setup Context Manager
        # Use a temporary cache dir or a persistent one
        cache_dir = Path("/tmp/affordabot/agent_cache")
        self.context_manager = ToolContextManager(cache_dir, self.client)
        
        # 4. Setup Components
        self.planner = TaskPlanner(self.client)
        self.executor = AgenticExecutor(self.client, self.registry, self.context_manager)
        
        # 5. Setup Instructor Client for Final Synthesis (Typed)
        self.instructor_client = instructor.from_openai(
            AsyncOpenAI(
                api_key=api_key,
                base_url="https://openrouter.ai/api/v1",
            )
        )

    async def analyze_bill_agentic(self, bill_text: str, bill_number: str, jurisdiction: str) -> LegislationAnalysisResponse:
        """
        Analyze a bill using the agentic workflow.
        """
        logger.info(f"Starting agentic analysis for {bill_number}")
        start_time = asyncio.get_event_loop().time()
        query_id = f"{bill_number}_{int(start_time)}"
        
        # 1. Plan
        query = f"Analyze bill {bill_number} in {jurisdiction}. Focus on cost of living impact, housing, and taxes."
        context_data = {"bill_text_snippet": bill_text[:2000]} # Initial context
        
        try:
            plan = await self.planner.plan(query, context=context_data, available_tools=self.registry.list_tools())
            logger.info(f"Generated plan with {len(plan.tasks)} tasks")
            
            # 2. Execute
            task_results = []
            for task in plan.tasks:
                res = await self.executor.execute_task(task, query_id)
                task_results.append(res)
                
            # 3. Synthesize
            # Load full context from tool outputs
            research_context = await self.context_manager.load_relevant_contexts(query_id, max_tokens=20000)
            
            response = await self._synthesize_legislation_response(
                bill_number, 
                bill_text, 
                research_context, 
                task_results
            )
            
            elapsed_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            logger.info(
                f"Agentic analysis complete for {bill_number}",
                extra={
                    "event": "analysis_pipeline_complete",
                    "bill_number": bill_number, 
                    "jurisdiction": jurisdiction,
                    "latency_ms": elapsed_ms,
                    "model_generated": True,
                    "agentic": True,
                    "tasks_count": len(plan.tasks)
                }
            )
            return response
            
        except Exception as e:
            logger.error(f"Agentic analysis failed: {e}", extra={"bill_number": bill_number})
            raise

    async def _synthesize_legislation_response(
        self, 
        bill_number: str, 
        bill_text: str, 
        research_context: str,
        task_results: List[Any]
    ) -> LegislationAnalysisResponse:
        """Synthesize final typed response."""
        
        system_prompt = """
        You are an expert policy analyst. Based on the conducted research, provide a detailed analysis of the legislation.
        Focus on Cost of Living impacts.
        """
        
        user_message = f"""
        BILL: {bill_number}
        
        RESEARCH FINDINGS:
        {research_context}
        
        BILL TEXT SNIPPET:
        {bill_text[:5000]}
        
        Provide the analysis in the requested schema.
        """
        
        return await self.instructor_client.chat.completions.create(
            model="x-ai/grok-4.1-fast:free", # Capable model
            response_model=LegislationAnalysisResponse,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ]
        )
