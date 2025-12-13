import asyncio
import os
import httpx
from openai import AsyncOpenAI

async def main():
    api_key = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("ZAI_API_KEY") # Sometimes people share keys? Unlikely.
    # Check if user mentioned OpenAI key but meant OpenRouter?
    # Let's check explicit OPENROUTER_API_KEY first as standard.
    
    if not api_key:
        print("❌ OPENROUTER_API_KEY not found in environment")
        # Try checking other common names just in case
        print(f"Env Keys: {[k for k in os.environ.keys() if 'API_KEY' in k]}")
        return

    base_url = "https://openrouter.ai/api/v1"
    model = "qwen/qwen3-embedding-8b"
    
    print(f"🔎 Probing OpenRouter Embeddings at: {base_url}")
    print(f"   Model: {model}")
    
    client = AsyncOpenAI(api_key=api_key, base_url=base_url)
    
    try:
        resp = await client.embeddings.create(
            model=model,
            input="San Jose is a great city."
        )
        print("✅ Embeddings WORK!")
        print(f"   Dimensions: {len(resp.data[0].embedding)}")
        print(f"   Usage: {resp.usage}")
        
    except Exception as e:
        print(f"❌ Failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
