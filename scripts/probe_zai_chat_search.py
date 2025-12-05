import asyncio
import os
import json
import httpx
import traceback

async def main():
    api_key = os.environ.get("ZAI_API_KEY")
    if not api_key:
        print("❌ Error: ZAI_API_KEY not found in environment")
        return

    url = "https://api.z.ai/api/coding/paas/v4/chat/completions"
    
    print(f"Probing Raw HTTP at {url}...")
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "glm-4.5",
        "messages": [{"role": "user", "content": "What is the latest news from San Jose City Council?"}],
        # Matching User's exact config from Step 789
        "tools": [{
            "type": "web_search",
            "web_search": {
                 "enable": "True", # User used String "True"
                 "search_engine": "search-prime", # User used this
                 "search_result": "True", # User used String "True"
                 "search_query": "news about San Jose city council"
            }
        }],
        "stream": False
    }
    
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(url, json=payload, headers=headers, timeout=60.0)
            print(f"Status: {resp.status_code}")
            
            if resp.status_code == 200:
                data = resp.json()
                print("Keys in Response:", list(data.keys()))
                
                if "web_search" in data:
                    print("✅ FOUND 'web_search' in JSON root!")
                    print(f"Count: {len(data['web_search'])}")
                else:
                    print("❌ 'web_search' NOT FOUND in JSON root.")
                    
                # Save full raw JSON for review
                with open("raw_probe_response.json", "w") as f:
                    json.dump(data, f, indent=2)
            else:
                print(f"Error: {resp.text}")
                
        except Exception as e:
            print(f"Exception: {repr(e)}")
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
