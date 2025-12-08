"""Service for auto-discovering sources using Z.ai GLM-4.6."""

from __future__ import annotations
from typing import List, Dict, Any
import os
import httpx
import logging

logger = logging.getLogger(__name__)

# Config
ZAI_API_KEY = os.environ.get("ZAI_API_KEY")
ZAI_BASE_URL = "https://api.z.ai/api/coding/paas/v4/chat/completions"
MODEL = "glm-4.6"

QUERY_TEMPLATES = {
    "city": {
        "permits": [
            "{name} building permit requirements adu guide",
            "{name} planning application process flowchart",
            "{name} affordable housing impact fee faq"
        ],
        "zoning": [
            "{name} zoning map interactive",
            "{name} zoning code density bonus"
        ],
        "housing_element": [
            "{name} housing element 2023-2031 pdf",
            "{name} rhna allocation progress"
        ]
    },
    "county": {
        "health": ["{name} environmental health permits restaurant"],
        "taxes": ["{name} property tax assessment appeal"]
    }
}

class AutoDiscoveryService:
    def __init__(self):
        if not ZAI_API_KEY:
            logger.warning("ZAI_API_KEY not set. Discovery will fail.")

    async def discover_sources(self, jurisdiction_name: str, jurisdiction_type: str = "city") -> List[Dict[str, Any]]:
        """
        Run discovery for a jurisdiction using Z.ai Web Search.
        """
        templates = QUERY_TEMPLATES.get(jurisdiction_type, {})
        results = []

        async with httpx.AsyncClient(timeout=60.0) as client:
            for category, queries in templates.items():
                for query_template in queries:
                    query = query_template.format(name=jurisdiction_name)
                    
                    try:
                        search_results = await self._zai_search(client, query)
                        
                        for res in search_results:
                            if self._is_relevant(res['url']):
                                results.append({
                                    "jurisdiction_name": jurisdiction_name,
                                    "category": category,
                                    "query": query,
                                    "title": res['title'],
                                    "url": res['url'],
                                    "snippet": res.get('content', '')
                                })
                    except Exception as e:
                        logger.error(f"Search failed for '{query}': {e}")
        
        return results

    async def _zai_search(self, client: httpx.AsyncClient, query: str) -> List[Dict[str, Any]]:
        """
        Perform web search via Z.ai Chat Completion tools.
        """
        payload = {
            "model": MODEL,
            "messages": [
                {"role": "user", "content": query}
            ],
            "tools": [
                {
                    "type": "web_search",
                    "web_search": {
                        "enable": True,
                        "search_result": True
                    }
                }
            ]
        }
        
        response = await client.post(ZAI_BASE_URL, json=payload, headers={
            "Authorization": f"Bearer {ZAI_API_KEY}",
            "Content-Type": "application/json"
        })
        
        if response.status_code != 200:
            raise Exception(f"Z.ai API Error {response.status_code}: {response.text}")
            
        data = response.json()
        
        # Z.ai/GLM-4 usually puts search results in the 'web_search' tool result 
        # OR embeds them in the choices if search_result=True.
        # Based on documentation/experience, the 'search_result=True' flag often appends results to the response 
        # or provides them in a specific field. 
        # However, looking at the raw response structure is key.
        # Often the choice content contains citations.
        # But we want structured URLs.
        # Let's check if 'web_search' field exists in choices or tool_calls.
        
        # NOTE: Since we can't easily parse the internal tool calls of GLM-4 without a schema,
        # we will rely on the fact that we can ASK the model to format the output.
        
        # ALTERNATIVE STRATEGY:
        # Instead of raw tool usage, ask the model to return JSON.
        
        return await self._zai_search_json(client, query)

    async def _zai_search_json(self, client: httpx.AsyncClient, query: str) -> List[Dict[str, Any]]:
        """
        Ask GLM-4 to search and return JSON list of results.
        """
        prompt = f"""
        Search for: "{query}"
        Return the top 3 most relevant official government or legal URLs.
        Format the output strictly as a JSON list of objects with keys: "title", "url", "content" (brief snippet).
        Do not include markdown formatting like ```json.
        """
        
        payload = {
            "model": MODEL,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "tools": [{"type": "web_search", "web_search": {"enable": True, "search_result": True}}]
        }
        
        response = await client.post(ZAI_BASE_URL, json=payload, headers={
            "Authorization": f"Bearer {ZAI_API_KEY}",
            "Content-Type": "application/json"
        })
        
        if response.status_code != 200:
             raise Exception(f"Z.ai API Error {response.status_code}")
             
        content = response.json()["choices"][0]["message"]["content"]
        
        # Clean cleanup
        content = content.replace("```json", "").replace("```", "").strip()
        
        import json
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse JSON from GLM-4: {content[:100]}...")
            return []

    def _is_relevant(self, url: str) -> bool:
        """Filter out obviously irrelevant URLs."""
        allowed = ['.gov', '.us', 'legistar.com', 'municode.com', 'granicus.com', 'codepublishing.com', 'amlegal.com']
        ignored = ['youtube.com', 'facebook.com', 'twitter.com', 'instagram.com']
        
        url_lower = url.lower()
        if any(bad in url_lower for bad in ignored):
            return False
            
        # Weak check: prefer allowed, but don't strictly enforce if it looks official?
        # For safety, let's enforce allowed list OR exact jurisdiction match if we had it.
        # But for "universal" we might want to be broader.
        # Let's keep the allowed list but add 'ca.gov' etc.
        
        return any(good in url_lower for good in allowed) or '.org' in url_lower
