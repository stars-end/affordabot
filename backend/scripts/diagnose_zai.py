import os
import json
import httpx
import asyncio

# Config
API_KEY = os.environ.get("ZAI_API_KEY")
BASE_URL = "https://api.z.ai/api/coding/paas/v4/chat/completions"
MODEL = "glm-4.6"

TEST_CASES = [
    {
        "name": "Specific Page (ADU)",
        "prompt": "Read the content of https://www.sanjoseca.gov/your-government/departments-offices/planning-building-code-enforcement/building-division/single-family-residential/accessory-dwelling-units-adus and extract the 'Three categories of ADUs' mentioned in the text.",
        "expected_keywords": ["Detached", "Attached", "Junior"]
    },
    {
        "name": "General Search (News)",
        "prompt": "Search for the latest press releases from the City of San Jose about housing from the last month.",
        "expected_keywords": ["Housing", "2024", "2025"]
    },
    {
        "name": "Technical/Code (Municode)",
        "prompt": "Search for San Jose Municipal Code regarding 'Tree Removal' permits. What is the relevant section number?",
        "expected_keywords": ["13.32", "Tree"] 
    }
]

async def run_test(client, test):
    print(f"\n--- Running Test: {test['name']} ---")
    print(f"Prompt: {test['prompt']}")
    
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": test["prompt"]}],
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

    try:
        response = await client.post(BASE_URL, json=payload, headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        }, timeout=90.0)
        
        if response.status_code != 200:
            print(f"❌ Error {response.status_code}: {response.text}")
            return

        data = response.json()
        
        # Check for errors in body
        if "error" in data:
            print(f"❌ API Error: {data['error']}")
            return

        content = data["choices"][0]["message"]["content"]
        print(f"✅ Response:\n{content[:500]}...\n(truncated)")
        
        # Simple verification
        missing = [k for k in test.get("expected_keywords", []) if k.lower() not in content.lower()]
        if missing:
            print(f"⚠️  Missing keywords: {missing}")
        else:
            print("🌟 passed keyword check")

    except httpx.ReadTimeout:
        print("❌ Exception: ReadTimeout (Model took too long)")
    except Exception as e:
        print(f"❌ Exception: {type(e).__name__}: {e}")

async def main():
    if not API_KEY:
        print("❌ ZAI_API_KEY not set")
        return

    async with httpx.AsyncClient() as client:
        for test in TEST_CASES:
            await run_test(client, test)

if __name__ == "__main__":
    asyncio.run(main())
