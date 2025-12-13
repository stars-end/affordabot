import asyncio
import os
from openai import AsyncOpenAI

async def main():
    api_key = os.environ.get("ZAI_API_KEY")
    bases = [
        "https://open.bigmodel.cn/api/paas/v4",
        "https://api.z.ai/api/coding/paas/v4",
        "https://api.z.ai/api/paas/v4"
    ]
    
    # Try models
    models = ["embedding-2", "embedding-3", "text-embedding", "glm-embedding"]
    
    client = AsyncOpenAI(api_key=api_key) # base_url will be set per loop if possible, or new client

    for base in bases:
        print(f"--- Testing Base: {base} ---")
        client = AsyncOpenAI(api_key=api_key, base_url=base)
        for model in models:
            print(f"Testing model: {model}")
            try:
                resp = await client.embeddings.create(
                    model=model,
                    input="hello world"
                )
                print(f"  ✅ Success! Dim: {len(resp.data[0].embedding)}")
                return # Found it
            except Exception as e:
                print(f"  ❌ Failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
