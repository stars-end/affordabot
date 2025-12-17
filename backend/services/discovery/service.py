import os
import instructor
import logging
from openai import AsyncOpenAI
from typing import List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

class DiscoveryResponse(BaseModel):
    is_scrapable: bool = Field(..., description="Whether the URL looks like a valid source for scraping")
    jurisdiction_name: str = Field(..., description="Predicted name of the jurisdiction (e.g., 'San Jose, CA')")
    source_type: str = Field(..., description="Type of source: 'agenda', 'minutes', 'legislation', 'generic'")
    recommended_spider: str = Field(..., description="Recommended spider template (e.g., 'sanjose_prime', 'generic_minutes')")
    confidence: float = Field(..., description="Confidence score 0.0-1.0")
    reasoning: str = Field(..., description="Brief explanation of the classification")

class AutoDiscoveryService:
    def __init__(self):
        self.client = None
        
        # Prefer Z.ai (GLM) for reasoning, fall back to OpenRouter (Fast)
        if os.getenv("ZAI_API_KEY"):
            self.client = instructor.from_openai(
                AsyncOpenAI(
                    api_key=os.getenv("ZAI_API_KEY"),
                    base_url="https://api.z.ai/api/paas/v4",
                )
            )
            self.model = "glm-4.6"
        elif os.getenv("OPENROUTER_API_KEY"):
            self.client = instructor.from_openai(
                AsyncOpenAI(
                    api_key=os.getenv("OPENROUTER_API_KEY"),
                    base_url="https://openrouter.ai/api/v1",
                )
            )
            self.model = "x-ai/grok-4.1-fast:free" # Default fast model
        else:
            logger.warning("AutoDiscoveryService: No LLM API keys found. Discovery will fail.")

    async def discover_url(self, url: str, page_text: str = "") -> DiscoveryResponse:
        """
        Analyze a URL (and optional page text) to classify it.
        """
        if not self.client:
            return DiscoveryResponse(
                is_scrapable=False,
                jurisdiction_name="Unknown",
                source_type="unknown",
                recommended_spider="none",
                confidence=0.0,
                reasoning="LLM Client not initialized"
            )

        system_prompt = """
        You are a web scraping expert. specificially for local government data.
        Analyze the provided URL and content snippet to determine:
        1. If this is a valid legacy meeting/legislation site.
        2. Which standard scraping template would work best.
        """

        user_message = f"""
        URL: {url}
        CONTENT SNIPPET: {page_text[:1000]}...
        
        Please classify this source.
        """

        try:
            return await self.client.chat.completions.create(
                model=self.model,
                response_model=DiscoveryResponse,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ]
            )
        except Exception as e:
            logger.error(f"Discovery failed: {e}")
            return DiscoveryResponse(
                is_scrapable=False,
                jurisdiction_name="Error",
                source_type="error",
                recommended_spider="error",
                confidence=0.0,
                reasoning=str(e)
            )
