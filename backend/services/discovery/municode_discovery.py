from typing import List
import logging

from llm_common.core.models import WebSearchResult
from services.extractors.playwright_extractor import PlaywrightExtractor

logger = logging.getLogger(__name__)

class MunicodeDiscoveryService:
    """
    Discovery service for Municode (CivicPlus) hosted municipal codes.
    Uses Playwright to crawl the SPA (library.municode.com) because the API is restricted.
    """
    
    # Valid San Jose SPA Link
    BASE_URL = "https://library.municode.com/ca/san_jose/codes/code_of_ordinances"
    
    def __init__(self):
        self.extractor = PlaywrightExtractor()

    async def find_laws(self, query: str = None) -> List[WebSearchResult]:
        """
        Fetch the main page and extract top-level Nodes (Titles).
        """
        url = self.BASE_URL
        logger.info(f"Crawling Municode SPA: {url}")
        
        try:
            # 1. Fetch rendered HTML
            html = await self.extractor.fetch_raw_content(url)
            
            # 2. Parse HTML (Simple regex/soup for now for speed/reliability)
            # In a real pipeline, we might use an LLM or specific selector.
            # Using regex to find the Sidebar nodes which usually link to nodes.
            # Pattern: <a ... href="...nodeId=12345...">Title</a>
            
            results = []
            
            # Simple approach: Identify links with nodeId=
            # We use BeautifulSoup (lxml) which is robust
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")
            
            # Municode sidebar structure is complex, often nested lists.
            # Look for anchors with nodeId in href
            links = soup.find_all("a", href=True)
            
            seen_urls = set()
            
            for link in links:
                href = link["href"]
                text = link.get_text(strip=True)
                
                if "nodeId=" in href and len(text) > 3:
                     # Validate it's a substantive node
                     if href not in seen_urls:
                         # Normalize URL
                         full_url = href
                         if href.startswith("/"):
                             full_url = f"https://library.municode.com{href}"
                             
                         results.append(WebSearchResult(
                             title=text,
                             url=full_url,
                             snippet=f"Section: {text}",
                             content=f"Substantive Code Section: {text}",
                             domain="library.municode.com",
                             source="municode/playwright"
                         ))
                         seen_urls.add(href)
            
            # Deduplicate by Title if needed, but URL is safer
            logger.info(f"Found {len(results)} nodes")
            return results[:20] # Return top 20 for discovery

        except Exception as e:
            logger.error(f"Error crawling Municode: {e}")
            return []

