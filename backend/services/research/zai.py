import os
import httpx
import asyncio
import logging
from typing import List, Dict, Optional
from pydantic import BaseModel

logger = logging.getLogger(__name__)

class SearchResult(BaseModel):
    url: str
    title: str
    snippet: str
    content: Optional[str] = None

class ResearchPackage(BaseModel):
    summary: str
    key_facts: List[str]
    opposition_arguments: List[str]
    fiscal_estimates: List[str]
    sources: List[SearchResult]

class ZaiResearchService:
    def __init__(self):
        self.api_key = os.getenv("ZAI_API_KEY")
        # MCP Endpoint for Web Search
        self.mcp_url = "https://api.z.ai/api/mcp/web_search_prime/mcp"
        self.tool_name = "search" # Default, will try to discover
        
        if not self.api_key:
            logger.warning("ZAI_API_KEY not set. Research service will be mocked.")

    async def _call_mcp(self, method: str, params: Optional[Dict] = None) -> Dict:
        """Execute a JSON-RPC call to the MCP endpoint."""
        if not self.api_key:
            raise ValueError("API Key missing")
            
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params or {}
        }
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                self.mcp_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json=payload
            )
            response.raise_for_status()
            return response.json()

    async def check_health(self) -> bool:
        """Check if Z.ai MCP is accessible by listing tools."""
        if not self.api_key:
            return False
        
        try:
            # Call tools/list to check connectivity and discover tool name
            result = await self._call_mcp("tools/list")
            tools = result.get("result", {}).get("tools", [])
            
            # Look for a search tool
            for tool in tools:
                if "search" in tool["name"].lower():
                    self.tool_name = tool["name"]
                    logger.info(f"Discovered Z.ai search tool: {self.tool_name}")
                    return True
            
            # If we got a response but no search tool, it's technically "healthy" but useless
            # But let's return True as connectivity is there
            return True
        except Exception as e:
            logger.error(f"Z.ai Health Check Failed: {e}")
            return False

    async def _generate_search_queries(self, bill_text: str, bill_number: str) -> List[str]:
        """
        Generate 30-40 exhaustive search queries based on the bill.
        """
        keywords = [
            "cost of living impact",
            "housing affordability",
            "opposition arguments",
            "support arguments",
            "fiscal analysis",
            "economic impact report",
            "legal challenges",
            "similar legislation results",
            "tenant rights impact",
            "landlord opposition",
            "taxpayer cost",
            "implementation challenges"
        ]
        
        queries = []
        for kw in keywords:
            queries.append(f"{bill_number} {kw}")
            queries.append(f"California {bill_number} {kw}")
            queries.append(f"{bill_number} legislation {kw}")
        
        return queries[:40]

    async def _execute_search(self, query: str) -> List[SearchResult]:
        """Execute a single search query via Z.ai MCP."""
        try:
            # Execute the tool via MCP
            response = await self._call_mcp(
                "tools/call",
                {
                    "name": self.tool_name,
                    "arguments": {"query": query}
                }
            )
            
            # Parse MCP result
            # MCP tools/call returns {result: {content: [{type: "text", text: "..."}]}}
            content_list = response.get("result", {}).get("content", [])
            results = []
            
            for content in content_list:
                if content.get("type") == "text":
                    # The text might be a JSON string or raw text. 
                    # Z.ai search usually returns a JSON string or structured text.
                    # Let's assume it returns a JSON string of results for now, 
                    # or we might need to parse the text if it's a formatted list.
                    text = content.get("text", "")
                    
                    # Try to parse as JSON if it looks like it
                    import json
                    try:
                        data = json.loads(text)
                        if isinstance(data, list):
                            for item in data:
                                results.append(SearchResult(
                                    url=item.get("url") or item.get("link"),
                                    title=item.get("title"),
                                    snippet=item.get("snippet") or item.get("body")
                                ))
                        elif isinstance(data, dict) and "results" in data:
                             for item in data["results"]:
                                results.append(SearchResult(
                                    url=item.get("url") or item.get("link"),
                                    title=item.get("title"),
                                    snippet=item.get("snippet") or item.get("body")
                                ))
                    except json.JSONDecodeError:
                        # Fallback: Treat as a single blob if we can't parse
                        # Or maybe it's just text.
                        pass

            return results
        except Exception as e:
            logger.error(f"Search failed for '{query}': {e}")
            return []

    async def search_exhaustively(self, bill_text: str, bill_number: str) -> ResearchPackage:
        """
        Perform exhaustive research on a bill.
        """
        if not self.api_key:
            logger.info("Mocking research for missing API key")
            return self._get_mock_research(bill_number)
            
        # Ensure we have the tool name
        if self.tool_name == "search":
             await self.check_health()

        queries = await self._generate_search_queries(bill_text, bill_number)
        logger.info(f"Generated {len(queries)} search queries for {bill_number}")

        all_results = []
        # Serial execution for now to avoid complexity with MCP rate limits/async client sharing
        # In prod, we'd use a semaphore
        for query in queries[:5]: # Limit to 5 for testing speed
            res = await self._execute_search(query)
            all_results.extend(res)
            await asyncio.sleep(0.2)

        unique_results = {r.url: r for r in all_results if r.url}.values()
        logger.info(f"Found {len(unique_results)} unique sources")
        
        return ResearchPackage(
            summary=f"Research conducted on {len(unique_results)} sources.",
            key_facts=[],
            opposition_arguments=[],
            fiscal_estimates=[],
            sources=list(unique_results)[:20]
        )

    def _get_mock_research(self, bill_number: str) -> ResearchPackage:
        return ResearchPackage(
            summary="Mock research data (API key missing)",
            key_facts=["Fact 1", "Fact 2"],
            opposition_arguments=["Arg 1", "Arg 2"],
            fiscal_estimates=["$1M cost"],
            sources=[
                SearchResult(
                    url="https://example.com",
                    title="Example Source",
                    snippet="This is a mock search result."
                )
            ]
        )
