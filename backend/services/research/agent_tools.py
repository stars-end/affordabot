import httpx
from bs4 import BeautifulSoup
from typing import List, Dict, Any, Optional
from llm_common.agents import BaseTool, ToolMetadata, ToolParameter, ToolResult
from services.research.zai import ZaiResearchService

class WebSearchTool(BaseTool):
    """Tool for web search using Z.ai."""
    
    def __init__(self):
        self.service = ZaiResearchService()
        
    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="web_search",
            description="Search the web for information about bills, laws, and impacts.",
            parameters=[
                ToolParameter(name="query", type="string", description="The search query")
            ]
        )
        
    async def execute(self, query: str) -> ToolResult:
        try:
            results = await self.service.execute_search(query)
            data = [r.dict() for r in results]
            return ToolResult(success=True, data=data)
        except Exception as e:
            return ToolResult(success=False, error=str(e))

class UrlFetchTool(BaseTool):
    """Tool to fetch and parse URL content."""
    
    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="fetch_url",
            description="Fetch content from a URL (e.g. news article, bill text).",
            parameters=[
                ToolParameter(name="url", type="string", description="The URL to fetch")
            ]
        )
        
    async def execute(self, url: str) -> ToolResult:
        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                response = await client.get(url)
                response.raise_for_status()
                
                # Simple parsing
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Remove scripts and styles
                for script in soup(["script", "style"]):
                    script.decompose()
                    
                text = soup.get_text(separator="\n")
                # Clean up whitespace
                lines = (line.strip() for line in text.splitlines())
                chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
                text = '\n'.join(chunk for chunk in chunks if chunk)
                
                return ToolResult(
                    success=True, 
                    data={
                        "url": url,
                        "title": soup.title.string if soup.title else "",
                        "content": text[:10000] # Truncate for safety
                    }
                )
        except Exception as e:
            return ToolResult(success=False, error=str(e))
