import asyncio
import os
from llm_common.core import LLMConfig, LLMMessage
from llm_common.providers import ZaiClient
from pydantic import BaseModel

# Simplified schema for testing
class TestSchema(BaseModel):
    summary: str
    impact_score: int

async def test_zai_json():
    print("🧪 Testing Z.ai GLM-4.6 JSON Generation...")
    
    api_key = os.getenv("ZAI_API_KEY")
    if not api_key:
        print("❌ ZAI_API_KEY missing")
        return

    # 1. Config
    config = LLMConfig(api_key=api_key, provider="zai", default_model="glm-4.6")
    client = ZaiClient(config)
    
    # 2. Test Case A: Standard OpenAI JSON Mode
    print("\n[A] Testing `response_format={'type': 'json_object'}`...")
    try:
        response = await client.chat_completion(
            messages=[
                LLMMessage(role="system", content="You are a helper. Output JSON."),
                LLMMessage(role="user", content="Summarize 'Hello World' and give it a score.")
            ],
            response_format={"type": "json_object"},
            temperature=0.1
        )
        print(f"Result A Raw: {response.content}")
    except Exception as e:
        print(f"Result A Failed: {e}")

    # 3. Test Case B: Explicit System Prompt (Robustness)
    print("\n[B] Testing Explicit Prompt only...")
    try:
        response = await client.chat_completion(
            messages=[
                LLMMessage(
                    role="system", 
                    content=f"You are a helper. You MUST return valid JSON matching this schema: {TestSchema.model_json_schema()}"
                ),
                LLMMessage(role="user", content="Summarize 'Hello World' and give it a score.")
            ],
            # Removing response_format to see if raw text is better
            temperature=0.1
        )
        print(f"Result B Raw: {response.content}")
    except Exception as e:
        print(f"Result B Failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_zai_json())
