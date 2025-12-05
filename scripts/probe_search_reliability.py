import asyncio
import os
import httpx
import json

async def test_query(api_key: str, query: str):
    url = "https://api.z.ai/api/coding/paas/v4/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "glm-4.5",
        "messages": [{"role": "user", "content": f"Search for: {query}"}],
        "tools": [{
            "type": "web_search",
            "web_search": {
                 "enable": "True",
                 "search_engine": "search-prime",
                 "search_result": "True",
                 "search_query": query
            }
        }],
        "stream": False
    }
    
    print(f"Testing Query: '{query}'")
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(url, json=payload, headers=headers, timeout=30.0)
            if resp.status_code == 200:
                data = resp.json()
                results = data.get("web_search", [])
                count = len(results)
                print(f"   -> Count: {count}")
                if count > 0:
                    print(f"      Top Result: {results[0].get('title')} ({results[0].get('link')})")
            else:
                print(f"   -> Error {resp.status_code}: {resp.text[:100]}")
        except Exception as e:
            print(f"   -> Exception: {e}")

async def main():
    api_key = os.environ.get("ZAI_API_KEY")
    if not api_key:
        print("Missing ZAI_API_KEY")
        return

    queries = [
        # Boolean / Dork
        "site:sanjoseca.gov affordable housing",
        "site:sanjoseca.gov housing element 2023 filetype:pdf",
        
        # Keyword
        "San Jose affordable housing ordinances 2024",
        "San Jose inclusionary housing requirements",
        
        # Natural Language
        "What are the affordable housing ordinances in San Jose from 2024?",
        "Find the 2023-2031 Housing Element for San Jose"
    ]
    
    print("🔎 Starting Reliability Probe...\n")
    for q in queries:
        await test_query(api_key, q)
        await asyncio.sleep(1) # Rate limit niceness

if __name__ == "__main__":
    asyncio.run(main())
