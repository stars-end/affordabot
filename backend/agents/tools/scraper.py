"""
ScraperTool for web page content extraction.

This tool wraps the WebReader client for deep URL reading
using Playwright and trafilatura for content extraction.
"""

import logging
from typing import Any, Dict

from llm_common.agents.tools import (
    BaseTool,
    ToolMetadata,
    ToolParameter,
    ToolResult,
)
from llm_common.agents.provenance import Evidence, EvidenceEnvelope

logger = logging.getLogger(__name__)


class ScraperTool(BaseTool):
    """
    A tool for scraping web pages using the WebReader client.
    
    Integrates with Playwright/trafilatura for robust content extraction
    and returns evidence envelope for provenance tracking.
    """

    def __init__(self, web_reader_client: Any = None):
        """
        Initialize ScraperTool.
        
        Args:
            web_reader_client: Optional WebReaderClient instance.
                              If None, uses mock mode.
        """
        self._web_reader = web_reader_client

    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="scraper",
            description=(
                "Scrapes a web page and extracts the main content. "
                "Returns structured content with source URL for citation."
            ),
            parameters=[
                ToolParameter(
                    name="url",
                    type="string",
                    description="The URL of the web page to scrape.",
                    required=True,
                ),
                ToolParameter(
                    name="extract_links",
                    type="boolean",
                    description="Whether to extract links from the page.",
                    required=False,
                ),
            ],
        )

    async def execute(self, url: str, extract_links: bool = False) -> ToolResult:
        """
        Scrapes a web page and returns the content with provenance.

        Args:
            url: The URL of the web page to scrape.
            extract_links: Whether to extract links from the page.

        Returns:
            A ToolResult containing the scraped content and evidence envelope.
        """
        logger.info(f"ScraperTool: Scraping {url}")
        
        try:
            if self._web_reader:
                # Use real WebReader client
                result = await self._web_reader.read_url(url)
                content = result.get("content", "")
                title = result.get("title", "")
                links = result.get("links", []) if extract_links else []
            else:
                # Mock mode for testing
                content = f"[Mock] Content extracted from {url}"
                title = f"Page at {url}"
                links = []
                logger.warning("ScraperTool: Using mock mode (no web_reader_client)")
            
            # Create evidence envelope
            evidence = EvidenceEnvelope(
                source_tool="scraper",
                source_query=url,
                evidence=[
                    Evidence(
                        kind="url",
                        label=title or url,
                        url=url,
                        content=content[:500] if content else "",  # First 500 chars
                        excerpt=content[:200] if content else "",
                    )
                ],
            )
            
            return ToolResult(
                success=True,
                data={
                    "url": url,
                    "title": title,
                    "content": content,
                    "links": links,
                    "content_length": len(content),
                },
                source_urls=[url],
                evidence=[evidence],
            )
            
        except Exception as e:
            logger.error(f"ScraperTool failed for {url}: {e}")
            return ToolResult(
                success=False,
                error=str(e),
                source_urls=[url],
            )

