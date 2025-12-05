from typing import Type, TypeVar
from pydantic import BaseModel
from playwright.async_api import async_playwright
# Using the protocol from contracts
from backend.contracts.extraction import ExtractorClient

T = TypeVar("T", bound=BaseModel)

class PlaywrightExtractor(ExtractorClient):
    """
    Extractor that uses Playwright to render SPA content (e.g. Municode).
    """

    async def extract(self, url: str, schema: Type[T]) -> T:
        """
        Extract structured data from a URL using Playwright.
        
        Note: For now, this returns a schema with raw content. 
        In a full implementation, we would feed this HTML to an LLM to parse into 'schema'.
        For this verification, we prioritize getting the content.
        """
        content = await self._fetch_html(url)
        
        # In a real pipeline, we would pass 'content' to an LLM here to extract 'schema'.
        # For compatibility with the interface, we assume the schema has a 'content' field
        # or we mock the extraction.
        # This is a simplification for the pipeline spike.
        
        # If the schema allows arbitrary fields or has a body/content field:
        if hasattr(schema, "model_fields") and "content" in schema.model_fields:
             return schema(content=content, title="Extracted by Playwright", url=url, **{}) # type: ignore
        
        # Fallback: parsing logic would go here. 
        # For now, raise if we can't fit data into schema
        raise NotImplementedError("LLM parsing of Playwright HTML not yet implemented in this step.")

    async def fetch_raw_content(self, url: str) -> str:
        """
        Fetch raw rendered HTML content.
        """
        return await self._fetch_html(url)

    async def _fetch_html(self, url: str) -> str:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                # Use a realistic User-Agent to avoid basic blocking
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )
                page = await context.new_page()
                
                # Navigate with wait strategy proven in spike
                try:
                    await page.goto(url, wait_until="networkidle", timeout=30000)
                except Exception as e:
                    print(f"⚠️ Playwright navigation fetch warning (continuing): {e}")

                # Get the full content
                content = await page.content()
                
                # Basic validation
                body_text = await page.inner_text("body")
                if len(body_text) < 500 and ("Loading" in body_text or "Initializing" in body_text):
                    raise ValueError(f"Playwright failed to render SPA: Found shell content only ({len(body_text)} chars)")
                    
                return content
            finally:
                await browser.close()
