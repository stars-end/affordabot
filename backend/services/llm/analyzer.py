import os
import instructor
from openai import AsyncOpenAI
from schemas.analysis import LegislationAnalysisResponse
from typing import Optional

class LegislationAnalyzer:
    def __init__(self):
        # Use OpenRouter or OpenAI based on env vars
        base_url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
        api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
        
        if not api_key:
            # Fallback for local testing without env vars if needed, but per user instructions we assume they exist
            print("WARNING: No API key found for LLM. Analysis will fail.")

        self.client = instructor.from_openai(
            AsyncOpenAI(
                api_key=api_key,
                base_url=base_url,
            )
        )
        # Default to a cheap/free model for MVP, can be overridden
        self.model = os.getenv("LLM_MODEL", "x-ai/grok-beta") 

    async def analyze(self, bill_text: str, bill_number: str, jurisdiction: str) -> LegislationAnalysisResponse:
        """
        Analyze legislation text using LLM to extract cost of living impacts.
        """
        system_prompt = """
        You are an expert policy analyst for AffordaBot, specializing in cost of living impacts for California families.
        Analyze the following legislation and identify ALL impacts on cost of living.
        
        REQUIREMENTS:
        1. For EACH impact, you MUST provide:
           - relevant_clause: Exact text from legislation
           - impact_description: How this affects cost of living
           - evidence: List of quantitative sources with URLs (academic, gov, industry)
           - chain_of_causality: Step-by-step reasoning
           - confidence_factor: 0.0-1.0 (your confidence in this analysis)
           - Cost distribution: p10, p25, p50, p75, p90 in 2025 dollars

        2. Evidence MUST include:
           - URLs must be real and accessible if possible, or cite specific known studies.
           - Cite specific numbers/data points.

        3. If you cannot find sufficient evidence for an impact, DO NOT include it.
        """

        user_message = f"""
        JURISDICTION: {jurisdiction}
        BILL NUMBER: {bill_number}
        
        LEGISLATION TEXT:
        {bill_text}
        """

        return await self.client.chat.completions.create(
            model=self.model,
            response_model=LegislationAnalysisResponse,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            temperature=0.1, # Low temperature for factual extraction
            max_retries=3
        )
