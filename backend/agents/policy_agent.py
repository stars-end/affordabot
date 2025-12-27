"""
PolicyAgent orchestrator for affordabot.

This agent coordinates research tools (Z.ai, Scraper, Retriever)
to analyze policy questions and generate evidence-backed responses.
"""

import logging
from dataclasses import dataclass
from typing import AsyncGenerator, List, Optional
import uuid

from llm_common.agents import (
    AgenticExecutor,
    StreamEvent,
    TaskPlanner,
    ToolContextManager,
    ToolRegistry,
)
from llm_common.agents.provenance import EvidenceEnvelope
from llm_common.core import LLMClient

logger = logging.getLogger(__name__)


@dataclass
class PolicyAnalysisResult:
    """Result of a policy analysis."""
    query: str
    answer: str
    sources: List[str]
    evidence: List[EvidenceEnvelope]
    success: bool
    error: Optional[str] = None


class PolicyAgent:
    """
    Orchestrates policy analysis using research tools.
    
    Coordinates:
    - ZaiSearchTool: Web search for current information
    - ScraperTool: Deep URL reading
    - RetrieverTool: Knowledge base search
    
    Flow:
    1. Plan research strategy
    2. Execute tools in parallel
    3. Synthesize answer from collected evidence
    """

    def __init__(
        self,
        llm_client: LLMClient,
        tool_registry: ToolRegistry,
        context_manager: ToolContextManager,
        planner: Optional[TaskPlanner] = None,
        executor: Optional[AgenticExecutor] = None,
    ):
        """
        Initialize PolicyAgent.
        
        Args:
            llm_client: LLM client for planning and synthesis
            tool_registry: Registry of available tools
            context_manager: Tool context persistence
            planner: Optional custom planner
            executor: Optional custom executor
        """
        self.client = llm_client
        self.registry = tool_registry
        self.context_manager = context_manager
        
        self.planner = planner or TaskPlanner(llm_client)
        self.executor = executor or AgenticExecutor(
            llm_client, tool_registry, context_manager
        )

    async def analyze(self, query: str, jurisdiction: str = "San Jose") -> PolicyAnalysisResult:
        """
        Analyze a policy question.
        
        Args:
            query: The policy question to analyze
            jurisdiction: Target jurisdiction for context
            
        Returns:
            PolicyAnalysisResult with answer and evidence
        """
        query_id = str(uuid.uuid4())[:8]
        logger.info(f"PolicyAgent: Analyzing '{query}' for {jurisdiction}")
        
        try:
            # Enrich query with jurisdiction context
            enriched_query = f"{query} (context: {jurisdiction})"
            
            # Plan the research strategy
            plan = await self.planner.create_plan(
                enriched_query,
                context=f"Research policy question for {jurisdiction} jurisdiction. "
                        f"Use available tools: {[t.name for t in self.registry.tools]}"
            )
            
            # Execute plan and collect results
            results = await self.executor.execute_plan(plan, query_id)
            
            # Collect evidence from results
            all_evidence: List[EvidenceEnvelope] = []
            all_sources: List[str] = []
            
            for result in results:
                if hasattr(result, 'result') and isinstance(result.result, list):
                    for tool_result in result.result:
                        if isinstance(tool_result, dict):
                            output = tool_result.get('output')
                            if hasattr(output, 'evidence'):
                                all_evidence.extend(output.evidence)
                            if hasattr(output, 'source_urls'):
                                all_sources.extend(output.source_urls)
            
            # Synthesize answer
            context_blob = await self._load_context_blob(query_id=query_id, query=query)
            answer = await self._synthesize_answer(query, context_blob)
            
            return PolicyAnalysisResult(
                query=query,
                answer=answer,
                sources=list(set(all_sources)),
                evidence=all_evidence,
                success=True,
            )
            
        except Exception as e:
            logger.error(f"PolicyAgent.analyze failed: {e}")
            return PolicyAnalysisResult(
                query=query,
                answer="",
                sources=[],
                evidence=[],
                success=False,
                error=str(e),
            )

    async def analyze_stream(
        self, 
        query: str, 
        jurisdiction: str = "San Jose"
    ) -> AsyncGenerator[StreamEvent, None]:
        """
        Analyze a policy question with streaming output.
        
        Yields StreamEvents for real-time UI updates.
        """
        query_id = str(uuid.uuid4())[:8]
        logger.info(f"PolicyAgent: Streaming analysis for '{query}'")
        
        # Yield initial thinking event
        yield StreamEvent(
            type="thinking",
            data={"message": f"Planning research strategy for: {query}"}
        )
        
        try:
            enriched_query = f"{query} (context: {jurisdiction})"
            plan = await self.planner.create_plan(enriched_query)
            
            yield StreamEvent(
                type="thinking",
                data={"message": f"Created plan with {len(plan.tasks)} tasks"}
            )
            
            # Stream execution
            async for event in self.executor.run_stream(plan, query_id):
                yield event
            
            # Final synthesis
            yield StreamEvent(
                type="thinking",
                data={"message": "Synthesizing answer from collected evidence..."}
            )
            
            context_blob = await self._load_context_blob(query_id=query_id, query=query)
            answer = await self._synthesize_answer(query, context_blob)
            
            yield StreamEvent(type="text", data={"content": answer})
            
        except Exception as e:
            yield StreamEvent(type="error", data={"error": str(e)})

    async def _load_context_blob(self, *, query_id: str, query: str) -> str:
        """
        Prefer pointer-based relevance selection when available; fall back to the legacy
        "dump all contexts" behavior to avoid regressions when selection is unavailable.
        """
        try:
            blob = await self.context_manager.select_relevant_contexts(
                query_id=query_id,
                query=query,
                client=self.client,
            )
            if blob.strip():
                return blob
        except Exception as e:
            logger.warning(f"Context relevance selection failed; falling back: {e}")
        return self.context_manager.load_relevant_contexts(query_id)

    async def _synthesize_answer(self, query: str, context: str) -> str:
        """
        Synthesize final answer from collected context.
        """
        from .prompts.policy import SYNTHESIS_PROMPT
        
        prompt = SYNTHESIS_PROMPT.format(query=query, context=context)
        
        from llm_common.core import LLMMessage
        response = await self.client.chat_completion(
            messages=[LLMMessage(role="user", content=prompt)],
            temperature=0.3,
        )
        
        return response.content
