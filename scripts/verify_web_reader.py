"""Verification script for Web Reader integration."""

import asyncio
import os
import sys
from unittest.mock import MagicMock

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

# Mock dependencies
sys.modules['aiohttp'] = MagicMock()

async def verify_web_reader():
    print("🧪 Starting Web Reader Verification...")
    
    from clients.web_reader_client import WebReaderClient
    
    # Test without API key (should mock)
    client = WebReaderClient()
    result = await client.fetch_content("https://example.gov/permits")
    
    print(f"✅ Fetched content: {result['title']}")
    print(f"✅ Content preview: {result['content'][:100]}...")
    
    print("\n✅ Web Reader Verification Complete!")

if __name__ == "__main__":
    asyncio.run(verify_web_reader())
