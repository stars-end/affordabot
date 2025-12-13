import asyncio
import os
import aiohttp

async def probe_url(session, base_url, path):
    url = f"{base_url}{path}"
    print(f"Testing {url}...")
    try:
        async with session.post(
            url, 
            headers={"Authorization": f"Bearer {os.environ.get('ZAI_API_KEY')}"},
            json={"query": "test", "count": 1}
        ) as resp:
            print(f"  Status: {resp.status}")
            text = await resp.text()
            if resp.status == 200 and '"success":true' in text.lower():
                print("  ✅ STRICT SUCCESS!")
                print(f"  Response: {text[:200]}")
                return True
            elif resp.status == 200:
                 print(f"  ⚠️ 200 but Failed Body: {text[:100]}")
            else:
                 print(f"  ❌ Fail status: {text[:100]}")
    except Exception as e:
        print(f"  ⚠️ Error: {e}")
    return False

async def main():
    api_key = os.environ.get("ZAI_API_KEY")
    if not api_key:
        print("Set ZAI_API_KEY")
        return

    # User specified endpoints to check
    targets = [
        # 1. Z.AI Coding Endpoint (Previous)
        {
            "name": "Z.AI Coding Endpoint",
            "url": "https://api.z.ai/api/coding/paas/v4/web_search"
        },
        # 2. BIGMODEL Coding Endpoint (New Candidate)
        {
            "name": "BIGMODEL Coding Endpoint",
            "url": "https://open.bigmodel.cn/api/coding/paas/v4/web_search"
        },
        # 3. BIGMODEL General Endpoint
        {
            "name": "BIGMODEL General Endpoint",
            "url": "https://open.bigmodel.cn/api/paas/v4/web_search"
        }
    ]

    # Correct Payload
    payload = {
        "search_engine": "search-prime",
        "search_query": "test query", 
        "count": 1
    }

    async with aiohttp.ClientSession() as session:
        for t in targets:
            print(f"Testing {t['name']}: {t['url']}")
            try:
                # BigModel might need different tokens or headers, but usually keys share validty if same provider.
                async with session.post(
                    t['url'], 
                    headers={
                        "Authorization": f"Bearer {os.environ.get('ZAI_API_KEY')}",
                        "Content-Type": "application/json"
                    },
                    json=payload
                ) as resp:
                    text = await resp.text()
                    print(f"  Status: {resp.status}")
                    print(f"  Body: {text[:200]}")
                    
                    if resp.status == 200:
                        print(f"  🎯 SUCCESS with {t['name']}!")
                    elif resp.status == 429:
                        print("  ⚠️ 429 Insufficient Balance")
                    else:
                         print(f"  ❌ Error {resp.status}")
                         
            except Exception as e:
                print(f"  Error: {e}")
            print("-" * 40)

if __name__ == "__main__":
    asyncio.run(main())
