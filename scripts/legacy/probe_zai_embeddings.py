import asyncio
import os
import httpx
import json

async def main():
    api_key = os.environ.get("ZAI_API_KEY")
    # The endpoint we are successfully using for Chat/Search/Reader
    base_url = "https://api.z.ai/api/coding/paas/v4" 
    url = f"{base_url}/embeddings"
    
    print(f"🔎 Probing Embeddings at: {url}")
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    # Try standard OpenAI embedding payload
    payload = {
        "model": "text-embedding-3-small", # Standard allowed model usually
        "input": "The food in San Jose is great."
    }
    
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(url, json=payload, headers=headers, timeout=10.0)
            print(f"Status: {resp.status_code}")
            print(f"Response: {resp.text}")
            
            if resp.status_code == 200:
                print("✅ Embeddings WORK on this endpoint!")
            elif resp.status_code == 404:
                print("❌ Endpoint NOT FOUND (Coding API likely doesn't support embeddings)")
            elif resp.status_code == 429:
                print("❌ Quota Exceeded (429) - Credits required")
            else:
                print(f"❌ Other Error: {resp.status_code}")
                
        except Exception as e:
            print(f"Exception: {e}")

if __name__ == "__main__":
    asyncio.run(main())
