import asyncio
import os
from openai import AsyncOpenAI

async def main():
    api_key = os.environ.get("ZAI_API_KEY")
    base_url = "https://api.z.ai/api/coding/paas/v4"
    
    print(f"Listing Models at {base_url}...")
    
    client = AsyncOpenAI(api_key=api_key, base_url=base_url)
    
    try:
        resp = await client.models.list()
        print(f"✅ Found {len(resp.data)} models:")
        for m in resp.data:
            print(f"  - {m.id} (Owner: {m.owned_by})")
    except Exception as e:
        print(f"❌ Failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
