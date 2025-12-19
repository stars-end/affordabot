import asyncio
import os
from llm_common.providers import ZaiClient
from llm_common.core import LLMConfig, LLMMessage, MessageRole

async def test_zai():
    print("🧪 Testing Z.ai GLM-4.6 Isolation...")
    api_key = os.getenv("ZAI_API_KEY")
    if not api_key:
        print("❌ ZAI_API_KEY not set")
        return

    config = LLMConfig(
        api_key=api_key,
        provider="zai",
        default_model="glm-4.6" 
    )
    client = ZaiClient(config)

    # 1. Simple User Message
    print("\n[1] Simple User Message (User only)")
    messages = [
        LLMMessage(role=MessageRole.USER, content="Hello")
    ]
    try:
        response = await client.chat_completion(messages=messages)
        print(f"✅ Success: {response.content[:50]}...")
    except Exception as e:
        print(f"❌ Failed: {e}")

    # 2. System + User
    print("\n[2] System + User")
    messages = [
        LLMMessage(role=MessageRole.SYSTEM, content="You are helpful."),
        LLMMessage(role=MessageRole.USER, content="Hi")
    ]
    try:
        response = await client.chat_completion(messages=messages)
        print(f"✅ Success: {response.content[:50]}...")
    except Exception as e:
        print(f"❌ Failed: {e}")

    # 3. User First (No System)
    print("\n[3] User First (No System)")
    messages = [
        LLMMessage(role=MessageRole.USER, content="Hi"),
        LLMMessage(role=MessageRole.ASSISTANT, content="Hello"),
        LLMMessage(role=MessageRole.USER, content="How are you?")
    ]
    try:
        response = await client.chat_completion(messages=messages)
        print(f"✅ Success: {response.content[:50]}...")
    except Exception as e:
        print(f"❌ Failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_zai())
