import os
import httpx
from typing import List, Optional
from playwright.async_api import async_playwright
# Use LLM Common's WebSearchResult if available
from llm_common.core.models import WebSearchResult

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
        self.model = "glm-4.5"
    
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
            print(f"🔄 Optimized Query: '{query}' -> '{optimized_query}'")
            
        try:
            results = await self._search_zai_structured(optimized_query, count)
            if results:
                print(f"✅ Z.ai Structured Search Success: {len(results)} URLs found.")
                return results
            else:
                print("⚠️ Z.ai Structured Search returned no URLs. Falling back to Playwright...")
        except Exception as e:
            print(f"⚠️ Z.ai Structured Search Failed: {e}. Falling back to Playwright...")
        
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
                
                results.append(WebSearchResult(
                    title=item.get("title", "No Title"),
                    url=url,
                    content=item.get("content", ""), # This is the snippet
                    published_date=item.get("publish_date"),
                    source=item.get("media", "z.ai")
                ))
                
            return results[:count]

    async def _fallback_search_duckduckgo(self, query: str, count: int) -> List[WebSearchResult]:
        """Fallback: Scrape DuckDuckGo using Playwright."""
        print(f"🦆 Falling back to DuckDuckGo/Playwright for: {query}")
        results = []
        async with async_playwright() as p:
            try:
                browser = await p.chromium.launch(headless=True)
            except Exception as e:
                print(f"❌ Failed to launch browser: {e}")
                return []
                
            try:
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
                print(f"❌ Playwright Fallback Failed: {e}")
            finally:
                await browser.close()
                
        return results

    async def close(self):
        # httpx client is context managed in method, nothing to close permanently
        pass
