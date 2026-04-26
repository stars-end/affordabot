import os
import html
import httpx
import logging
import re
from typing import List, Optional
from urllib.parse import parse_qs, unquote, urlparse

from playwright.async_api import async_playwright
# Use LLM Common's WebSearchResult if available
from llm_common.core.models import WebSearchResult

logger = logging.getLogger(__name__)


class SearchDiscoveryService:
    """
    Discovery service that uses Z.ai Chat (with Web Search tool) to find content URLs.
    
    Implementation: Uses direct HTTP requests to Z.ai Chat API to extract 
    native structured `web_search` data ("Z.ai Structured Search").
    This provides reliable Title, URL, and Snippets directly from the search index, 
    bypassing LLM markdown generation.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("ZAI_API_KEY")
        # Use Coding Endpoint for Chat as validated
        self.endpoint = "https://api.z.ai/api/coding/paas/v4/chat/completions"
        self.model = "glm-4.7"
        self.enable_playwright_fallback = os.environ.get(
            "DISCOVERY_ENABLE_PLAYWRIGHT_FALLBACK",
            "true",
        ).strip().lower() not in {"0", "false", "no"}
        self._playwright_available: Optional[bool] = None
        self._playwright_disable_reason: Optional[str] = None
    
    async def find_urls(self, query: str, count: int = 5) -> List[WebSearchResult]:
        """
        Search for content using Z.ai Structured Search.
        Falls back to Playwright if that fails.
        
        Sanitization: The underlying search engine often returns 0 results
        for queries with `site:` operators. This method attempts to convert strict 
        boolean logic into natural language or keyword constraints to ensure results.
        """
        # Sanitize Query for Reliability
        optimized_query = self._optimize_query(query)
        if optimized_query != query:
            logger.info("Optimized query for structured search: %r -> %r", query, optimized_query)
            
        try:
            results = await self._search_zai_structured(optimized_query, count)
            if results:
                logger.info("Z.ai structured search succeeded with %d URL(s).", len(results))
                return results
            logger.warning("Z.ai structured search returned no URLs; trying HTTP fallback.")
        except Exception as e:
            logger.warning("Z.ai structured search failed: %s. Trying HTTP fallback.", e)

        html_fallback_results = await self._fallback_search_duckduckgo_html(query, count)
        if html_fallback_results:
            logger.info("DuckDuckGo HTML fallback produced %d URL(s).", len(html_fallback_results))
            return html_fallback_results

        logger.warning("DuckDuckGo HTML fallback returned no URLs.")
        if not self.enable_playwright_fallback:
            logger.warning("Playwright fallback disabled by DISCOVERY_ENABLE_PLAYWRIGHT_FALLBACK.")
            return []
        if self._playwright_available is False:
            logger.warning(
                "Skipping Playwright fallback: browser runtime unavailable (%s).",
                self._playwright_disable_reason or "unknown",
            )
            return []
        
        # Fallback to Playwright (pass original query as DDG supports site:)
        return await self._fallback_search_duckduckgo(query, count)

    def _optimize_query(self, query: str) -> str:
        """
        Transform query to maximize compatibility.
        - Converts `site:domain.com query` -> `query from domain.com`
        """
        # Simple regex for site: operator
        import re
        site_match = re.search(r'site:([\w\.-]+)', query)
        if site_match:
            domain = site_match.group(1)
            # Remove site:domain and extra spaces
            clean_q = re.sub(r'site:[\w\.-]+', '', query).strip()
            return f"{clean_q} from {domain}"
        return query

    async def _search_zai_structured(self, query: str, count: int) -> List[WebSearchResult]:
        """Execute search via Z.ai API to get structured 'web_search' field."""

        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # Exact config validated to return 'web_search' root field
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": f"Search for: {query}"}],
            "tools": [{
                "type": "web_search",
                "web_search": {
                     "enable": "True", # String True required for strict mode?
                     "search_engine": "search-prime", 
                     "search_result": "True",
                     "search_query": query
                }
            }],
            "stream": False
        }
        
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                self.endpoint, 
                json=payload, 
                headers=headers, 
                timeout=60.0
            )
            
            if resp.status_code != 200:
                print(f"⚠️ Z.ai API Error {resp.status_code}: {resp.text}")
                return []
                
            data = resp.json()
            
            # Extract structured data from root 'web_search' field
            # Structure: [{"refer": "ref_1", "title": "...", "link": "...", "content": "..."}]
            web_search_data = data.get("web_search", [])
            
            results = []
            seen_urls = set()
            
            for item in web_search_data:
                url = item.get("link")
                if not url or url in seen_urls:
                    continue
                
                seen_urls.add(url)
                
                from urllib.parse import urlparse
                domain = urlparse(url).netloc
                
                pub_date = None # item.get("publish_date") - Disable due to formatting issues (e.g. '2025年')
                    
                results.append(WebSearchResult(
                    title=item.get("title", "No Title"),
                    url=url,
                    snippet=item.get("content", ""), # Map 'content' from API to 'snippet'
                    content=None, # Full content not provided by search
                    published_date=pub_date,
                    domain=domain
                ))
                
            return results[:count]

    async def _fallback_search_duckduckgo(self, query: str, count: int) -> List[WebSearchResult]:
        """Fallback: Scrape DuckDuckGo using Playwright."""
        if self._playwright_available is False:
            logger.warning(
                "Playwright fallback skipped for %r due to prior runtime failure (%s).",
                query,
                self._playwright_disable_reason or "unknown",
            )
            return []

        logger.info("Falling back to DuckDuckGo Playwright search for query: %r", query)
        results = []
        async with async_playwright() as p:
            try:
                browser = await p.chromium.launch(headless=True)
            except Exception as e:
                self._playwright_available = False
                self._playwright_disable_reason = str(e)
                logger.warning(
                    "Playwright fallback unavailable; disabling for remaining queries: %s",
                    e,
                )
                return []
                
            try:
                self._playwright_available = True
                page = await browser.new_page()
                await page.goto(f"https://html.duckduckgo.com/html/?q={query}", timeout=15000)
                await page.wait_for_selector(".result__body", timeout=5000)
                
                elements = await page.query_selector_all(".result__body")
                
                for el in elements[:count]:
                    try:
                        title_el = await el.query_selector(".result__a")
                        snippet_el = await el.query_selector(".result__snippet")
                        
                        if title_el and snippet_el:
                            title = await title_el.inner_text()
                            url = await title_el.get_attribute("href")
                            snippet = await snippet_el.inner_text()
                            
                            if url and not url.startswith("//") and url not in [r.url for r in results]:
                                results.append(WebSearchResult(
                                    title=title,
                                    url=url,
                                    content=snippet,
                                    score=0.8,
                                    source="duckduckgo_fallback"
                                ))
                    except Exception:
                        continue
            except Exception as e:
                logger.warning("Playwright fallback failed for query %r: %s", query, e)
            finally:
                await browser.close()
                
        return results

    async def _fallback_search_duckduckgo_html(
        self,
        query: str,
        count: int,
    ) -> List[WebSearchResult]:
        """DuckDuckGo HTML fallback without browser dependencies."""
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(
                    "https://html.duckduckgo.com/html/",
                    params={"q": query},
                    headers={"User-Agent": "Mozilla/5.0"},
                )
                response.raise_for_status()
        except Exception as exc:
            logger.warning("DuckDuckGo HTML fallback request failed for %r: %s", query, exc)
            return []

        return self._parse_duckduckgo_html_results(response.text, count)

    @staticmethod
    def _parse_duckduckgo_html_results(html_body: str, count: int) -> List[WebSearchResult]:
        anchor_pattern = re.compile(
            r'(?s)<a[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>'
        )
        snippet_pattern = re.compile(
            r'(?s)<a[^>]*class="result__snippet"[^>]*>(.*?)</a>|<div[^>]*class="result__snippet"[^>]*>(.*?)</div>'
        )

        results: List[WebSearchResult] = []
        seen_urls: set[str] = set()

        for match in anchor_pattern.finditer(html_body):
            href, raw_title = match.groups()
            url = SearchDiscoveryService._unwrap_duckduckgo_redirect(href)
            if not url or url in seen_urls:
                continue

            seen_urls.add(url)
            remainder = html_body[match.end() : match.end() + 1500]
            snippet_match = snippet_pattern.search(remainder)
            raw_snippet = ""
            if snippet_match:
                raw_snippet = snippet_match.group(1) or snippet_match.group(2) or ""

            parsed = urlparse(url)
            results.append(
                WebSearchResult(
                    title=SearchDiscoveryService._clean_html_text(raw_title) or "No Title",
                    url=url,
                    snippet=SearchDiscoveryService._clean_html_text(raw_snippet),
                    content=None,
                    published_date=None,
                    domain=parsed.netloc,
                )
            )
            if len(results) >= count:
                break

        return results

    @staticmethod
    def _unwrap_duckduckgo_redirect(url: str) -> str:
        if not url:
            return ""
        if url.startswith("//"):
            url = f"https:{url}"

        parsed = urlparse(url)
        if "duckduckgo.com" not in parsed.netloc:
            return url

        uddg = parse_qs(parsed.query).get("uddg", [])
        if not uddg:
            return ""
        return unquote(uddg[0])

    @staticmethod
    def _clean_html_text(value: str) -> str:
        stripped = re.sub(r"<[^>]+>", " ", value or "")
        return re.sub(r"\s+", " ", html.unescape(stripped)).strip()

    async def close(self):
        # httpx client is context managed in method, nothing to close permanently
        pass
