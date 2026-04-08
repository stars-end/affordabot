import os
import instructor
import logging
import re
from openai import AsyncOpenAI
# from typing import List, Optional (Unused)
from pydantic import BaseModel, Field
from urllib.parse import urlparse

logger = logging.getLogger(__name__)
ZAI_CODING_BASE_URL = "https://api.z.ai/api/coding/paas/v4"

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
                    base_url=ZAI_CODING_BASE_URL,
                )
            )
            self.model = "glm-4.7"
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
            if self._is_malformed_model_output_error(e):
                logger.warning(
                    "Discovery classifier returned malformed structured output; "
                    "using deterministic URL heuristic fallback for %s",
                    url,
                )
                return self._heuristic_discovery_fallback(url, page_text, str(e))

            logger.error(f"Discovery failed: {e}")
            return DiscoveryResponse(
                is_scrapable=False,
                jurisdiction_name="Error",
                source_type="error",
                recommended_spider="error",
                confidence=0.0,
                reasoning=str(e)
            )

    @staticmethod
    def _is_malformed_model_output_error(exc: Exception) -> bool:
        text = str(exc)
        malformed_signals = (
            "validation error for DiscoveryResponse",
            "validation errors for DiscoveryResponse",
            "Invalid JSON",
            "json_invalid",
            "<arg_key>",
            "</tool_call>",
        )
        lowered = text.lower()
        return any(signal.lower() in lowered for signal in malformed_signals)

    @staticmethod
    def _heuristic_discovery_fallback(
        url: str,
        page_text: str,
        error_text: str,
    ) -> DiscoveryResponse:
        parsed = urlparse(url)
        host = parsed.netloc.lower()
        blob = f"{url.lower()} {page_text.lower()}"

        if "minutes" in blob:
            source_type = "minutes"
            confidence = 0.78
            scrapable = True
        elif "agenda" in blob:
            source_type = "agenda"
            confidence = 0.78
            scrapable = True
        elif re.search(r"\bcity council\b", blob) and re.search(r"\bmeeting\b", blob):
            source_type = "agenda"
            confidence = 0.75
            scrapable = True
        else:
            source_type = "generic"
            confidence = 0.30
            scrapable = False

        jurisdiction_name = "Unknown"
        if "sanjoseca.gov" in host:
            jurisdiction_name = "San Jose, CA"
        elif "milpitas.gov" in host:
            jurisdiction_name = "Milpitas, CA"
        elif "acgov.org" in host or "alamedacountyca.gov" in host:
            jurisdiction_name = "Alameda County, CA"

        return DiscoveryResponse(
            is_scrapable=scrapable,
            jurisdiction_name=jurisdiction_name,
            source_type=source_type,
            recommended_spider="generic",
            confidence=confidence,
            reasoning=(
                "Fallback heuristic applied after malformed structured output. "
                f"Host={host or 'unknown'}, source_type={source_type}, "
                f"error_excerpt={error_text[:240]}"
            ),
        )
