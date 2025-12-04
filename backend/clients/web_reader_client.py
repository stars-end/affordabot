"""Client for z.ai Web Reader API."""

import aiohttp
import os
from typing import Optional, Dict, Any

class WebReaderClient:
    """
    Client for z.ai Web Reader API (POST /paas/v4/reader).
    Fetches clean markdown/text from URLs.
    """
    
    def __init__(self, api_key: Optional[str] = None, base_url: str = "https://api.z.ai"):
        self.api_key = api_key or os.environ.get("Z_AI_API_KEY")
        self.base_url = base_url.rstrip("/")
        
    async def fetch_content(self, url: str) -> Dict[str, Any]:
        """
        Fetch content from a URL using Web Reader.
        
        Args:
            url: URL to fetch
            
        Returns:
            Dict containing 'content' (markdown), 'title', etc.
        """
        if not self.api_key:
            # Mock behavior for dev/test without API key
            print(f"⚠️ No Z_AI_API_KEY found. Mocking Web Reader fetch for {url}")
            return {
                "content": f"# Mock Content for {url}\n\nThis is mocked content because no API key was provided.",
                "title": f"Mock Title for {url}",
                "url": url
            }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/paas/v4/reader",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"url": url}
            ) as response:
                if response.status != 200:
                    text = await response.text()
                    raise Exception(f"Web Reader failed: {response.status} - {text}")
                
                return await response.json()
