"""
WebReaderTool - Deep content extraction from JavaScript-heavy pages.

Uses Playwright for JS rendering and trafilatura for content extraction.
Returns EvidenceEnvelope with structured content and metadata.

Feature-Key: affordabot-dmzy.6
"""

import asyncio
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Optional imports - gracefully handle missing dependencies
try:
    from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logger.warning("Playwright not available - WebReaderTool will use fallback")

try:
    import trafilatura
    TRAFILATURA_AVAILABLE = True
except ImportError:
    TRAFILATURA_AVAILABLE = False
    logger.warning("Trafilatura not available - using simple extraction")

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False


class WebReaderTool:
    """
    Deep content extraction tool for JavaScript-heavy pages.
    
    Uses Playwright for rendering and trafilatura for extraction.
    Falls back to simple HTTP if dependencies unavailable.
    """
    
    name = "web_reader"
    description = "Extract content from JavaScript-heavy web pages"
    
    def __init__(self, timeout_ms: int = 30000, headless: bool = True):
        self.timeout_ms = timeout_ms
        self.headless = headless
        self._browser = None
    
    async def _ensure_browser(self):
        """Lazy initialization of Playwright browser."""
        if not PLAYWRIGHT_AVAILABLE:
            return None
        
        if self._browser is None:
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(headless=self.headless)
        return self._browser
    
    async def _extract_with_playwright(self, url: str) -> tuple[str, dict]:
        """Extract content using Playwright for JS rendering."""
        browser = await self._ensure_browser()
        if not browser:
            raise RuntimeError("Playwright not available")
        
        page = await browser.new_page()
        metadata = {"method": "playwright", "url": url}
        
        try:
            await page.goto(url, timeout=self.timeout_ms, wait_until="networkidle")
            
            # Wait for content to load
            await page.wait_for_load_state("domcontentloaded")
            
            # Get page content
            html = await page.content()
            title = await page.title()
            metadata["title"] = title
            
            # Extract text content
            if TRAFILATURA_AVAILABLE:
                content = trafilatura.extract(html, include_links=True, include_tables=True)
            else:
                # Fallback: get innerText
                content = await page.evaluate("() => document.body.innerText")
            
            return content or "", metadata
            
        except PlaywrightTimeout:
            logger.warning(f"Timeout loading {url}")
            metadata["error"] = "timeout"
            return "", metadata
        except Exception as e:
            logger.error(f"Error extracting from {url}: {e}")
            metadata["error"] = str(e)
            return "", metadata
        finally:
            await page.close()
    
    async def _extract_with_httpx(self, url: str) -> tuple[str, dict]:
        """Fallback extraction using httpx."""
        if not HTTPX_AVAILABLE:
            return "", {"error": "No HTTP client available", "url": url}
        
        metadata = {"method": "httpx", "url": url}
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, follow_redirects=True)
                response.raise_for_status()
                html = response.text
                metadata["status_code"] = response.status_code
                
                if TRAFILATURA_AVAILABLE:
                    content = trafilatura.extract(html, include_links=True)
                else:
                    # Very basic extraction
                    import re
                    content = re.sub(r'<[^>]+>', ' ', html)
                    content = ' '.join(content.split())
                
                return content or "", metadata
                
        except Exception as e:
            logger.error(f"HTTP error for {url}: {e}")
            metadata["error"] = str(e)
            return "", metadata
    
    async def execute(self, url: str, use_js: bool = True) -> dict[str, Any]:
        """
        Extract content from a URL.
        
        Args:
            url: The URL to extract content from
            use_js: Whether to use Playwright for JS rendering (default True)
            
        Returns:
            Dictionary with content, metadata, and evidence envelope
        """
        from llm_common.agents.provenance import Evidence, EvidenceEnvelope
        
        if use_js and PLAYWRIGHT_AVAILABLE:
            content, metadata = await self._extract_with_playwright(url)
        else:
            content, metadata = await self._extract_with_httpx(url)
        
        # Create evidence envelope
        evidence = Evidence(
            kind="url",
            label=metadata.get("title", "Web Page"),
            url=url,
            content=content[:5000] if content else "",  # Truncate for storage
            excerpt=content[:500] if content else "",
            metadata=metadata,
        )
        
        envelope = EvidenceEnvelope(
            source_tool=self.name,
        )
        envelope.add(evidence)
        
        return {
            "url": url,
            "content": content,
            "title": metadata.get("title", ""),
            "metadata": metadata,
            "evidence_envelope": envelope,
            "success": bool(content) and "error" not in metadata,
        }
    
    async def close(self):
        """Clean up browser resources."""
        if self._browser:
            await self._browser.close()
            await self._playwright.stop()
            self._browser = None
    
    def get_schema(self) -> dict:
        """Return tool schema for LLM function calling."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "URL to extract content from",
                    },
                    "use_js": {
                        "type": "boolean",
                        "description": "Use JavaScript rendering (slower but more complete)",
                        "default": True,
                    },
                },
                "required": ["url"],
            },
        }
