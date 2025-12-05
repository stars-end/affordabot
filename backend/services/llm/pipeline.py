import os
import instructor
from openai import AsyncOpenAI
from typing import List, Dict
from pydantic import BaseModel
from schemas.analysis import LegislationAnalysisResponse
from services.research.zai import ZaiResearchService, ResearchPackage
import logging

logger = logging.getLogger(__name__)

class ReviewCritique(BaseModel):
    passed: bool
    critique: str
    missing_impacts: List[str]
    factual_errors: List[str]
    citation_issues: List[str]

class DualModelAnalyzer:
    def __init__(self):
        # Initialize clients for different providers
        self.openrouter_client = instructor.from_openai(
            AsyncOpenAI(
                api_key=os.getenv("OPENROUTER_API_KEY"),
                base_url="https://openrouter.ai/api/v1",
            )
        )
        
        # Initialize Z.ai client if key is present
        self.zai_client = None
        if os.getenv("ZAI_API_KEY"):
            self.zai_client = instructor.from_openai(
                AsyncOpenAI(
                    api_key=os.getenv("ZAI_API_KEY"),
                    base_url="https://api.z.ai/api/paas/v4",
                )
            )
        
        # Generation Models Priority: Grok -> Kimi -> GLM
        self.gen_models = [
            ("x-ai/grok-4.1-fast:free", "openrouter"),
            ("moonshotai/kimi-k2:free", "openrouter"),
            ("glm-4.6", "zai")
        ]
        
        # Review Models Priority: GLM -> Grok -> Kimi
        self.review_models = [
            ("glm-4.6", "zai"),
            ("x-ai/grok-4.1-fast:free", "openrouter"),
            ("moonshotai/kimi-k2:free", "openrouter")
        ]
        
        self.researcher = ZaiResearchService()

    async def check_health(self) -> Dict[str, str]:
        """
        Check health of Generation and Review models.
        Returns a dict with status for each role.
        """
        status = {"generation": "unknown", "review": "unknown"}
        
        # Simple model for health check
        class HealthCheck(BaseModel):
            status: str

        # Test Generation Model (Try chain)
        try:
            await self._call_with_fallback(
                self.gen_models,
                "system",
                "ping",
                HealthCheck
            )
            status["generation"] = "healthy"
        except Exception as e:
            logger.error(f"Generation model health check failed: {e}")
            status["generation"] = f"unhealthy: {str(e)}"

        # Test Review Model (Try chain)
        try:
            await self._call_with_fallback(
                self.review_models,
                "system",
                "ping",
                HealthCheck
            )
            status["review"] = "healthy"
        except Exception as e:
            logger.error(f"Review model health check failed: {e}")
            status["review"] = f"unhealthy: {str(e)}"
            
        return status

    async def _call_with_fallback(
        self, 
        models: List[tuple], 
        system_prompt: str, 
        user_message: str, 
        response_model: type
    ):
        """Try models in sequence until one succeeds."""
        last_exception = None
        
        for model_name, provider in models:
            # Select appropriate client
            client = self.zai_client if provider == "zai" else self.openrouter_client
            
            if not client:
                logger.warning(f"Skipping {model_name} ({provider}): Client not initialized (missing API key?)")
                continue
                
            try:
                logger.info(f"Attempting call with {model_name} via {provider}")
                return await client.chat.completions.create(
                    model=model_name,
                    response_model=response_model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message}
                    ]
                )
            except Exception as e:
                logger.warning(f"Failed call with {model_name}: {e}")
                last_exception = e
                continue
        
        logger.error("All models failed in fallback chain")
        raise last_exception or Exception("All models failed")

    async def analyze(self, bill_text: str, bill_number: str, jurisdiction: str) -> LegislationAnalysisResponse:
        """
        Full analysis pipeline:
        1. Exhaustive Research (Z.ai)
        2. Initial Generation (Grok/Kimi/GLM)
        3. Review & Critique (GLM/Grok/Kimi)
        4. Refinement (Grok/Kimi/GLM)
        """
        logger.info(f"Starting dual-model analysis for {bill_number}")
        
        # 1. Research Phase
        research_package = await self.researcher.search_exhaustively(bill_text, bill_number)
        
        # 2. Generation Phase
        draft_analysis = await self._generate_draft(bill_text, bill_number, jurisdiction, research_package)
        
        # 3. Review Phase
        critique = await self._review_draft(bill_text, draft_analysis, research_package)
        
        if critique.passed:
            logger.info(f"Draft passed review for {bill_number}")
            return draft_analysis
        
        # 4. Refinement Phase
        logger.info(f"Refining draft based on critique for {bill_number}")
        final_analysis = await self._refine_draft(draft_analysis, critique, bill_text)
        
        return final_analysis

    async def _generate_draft(
        self, 
        bill_text: str, 
        bill_number: str, 
        jurisdiction: str,
        research: ResearchPackage
    ) -> LegislationAnalysisResponse:
        """Generate initial draft using fallback models."""
        system_prompt = """
        You are an expert policy analyst. Analyze the legislation for cost-of-living impacts.
        Use the provided RESEARCH DATA to support your analysis with real evidence.
        """
        
        user_message = f"""
        BILL: {bill_number} ({jurisdiction})
        
        RESEARCH SUMMARY:
        {research.summary}
        
        SOURCES:
        {[s.url for s in research.sources]}
        
        TEXT:
        {bill_text[:10000]}... (truncated)
        """
        
        return await self._call_with_fallback(
            self.gen_models,
            system_prompt,
            user_message,
            LegislationAnalysisResponse
        )

    async def _review_draft(
        self,
        bill_text: str,
        analysis: LegislationAnalysisResponse,
        research: ResearchPackage
    ) -> ReviewCritique:
        """Review the draft using fallback models."""
        system_prompt = """
        You are a strict auditor. Review the provided analysis against the bill text and research.
        Verify every claim. Check for hallucinations. Ensure all impacts are supported by evidence.
        """
        
        user_message = f"""
        ANALYSIS TO REVIEW:
        {analysis.model_dump_json()}
        
        RESEARCH DATA:
        {research.model_dump_json()}
        
        BILL TEXT:
        {bill_text[:5000]}...
        """
        
        return await self._call_with_fallback(
            self.review_models,
            system_prompt,
            user_message,
            ReviewCritique
        )

    async def _refine_draft(
        self,
        draft: LegislationAnalysisResponse,
        critique: ReviewCritique,
        bill_text: str
    ) -> LegislationAnalysisResponse:
        """Refine the draft based on critique using fallback models."""
        system_prompt = """
        You are an expert policy analyst. Update your previous analysis based on the auditor's critique.
        Fix factual errors, add missing impacts, and correct citations.
        """
        
        user_message = f"""
        PREVIOUS DRAFT:
        {draft.model_dump_json()}
        
        CRITIQUE:
        {critique.model_dump_json()}
        
        Please provide the FINAL corrected analysis.
        """
        
        return await self._call_with_fallback(
            self.gen_models,
            system_prompt,
            user_message,
            LegislationAnalysisResponse
        )
