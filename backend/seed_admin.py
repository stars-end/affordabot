import os
import sys
from pathlib import Path
import asyncio

BACKEND_ROOT = Path(__file__).resolve().parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.append(str(BACKEND_ROOT))

from db.postgres_client import PostgresDB


async def seed_data() -> None:
    if not (os.getenv("DATABASE_URL_PUBLIC") or os.getenv("DATABASE_URL")):
        print("Error: DATABASE_URL or DATABASE_URL_PUBLIC not found.")
        raise SystemExit(1)

    db = PostgresDB()
    await db.connect()
    try:
        models = [
            {"provider": "zai", "model_name": "glm-4", "priority": 1, "enabled": True, "use_case": "generation"},
            {"provider": "openrouter", "model_name": "anthropic/claude-3-opus", "priority": 2, "enabled": True, "use_case": "generation"},
            {"provider": "openrouter", "model_name": "openai/gpt-4o", "priority": 3, "enabled": True, "use_case": "review"},
        ]

        print("Seeding models...")
        for model in models:
            await db.update_model_config(**model)
            print(f"Seeded model config: {model['provider']} / {model['model_name']} / {model['use_case']}")

        prompts = [
            {
                "prompt_type": "generation",
                "system_prompt": "You are an expert legislative analyst. Analyze the following bill text and identify potential impacts on the cost of living for families in the specified jurisdiction. Focus on housing, utilities, transportation, and taxes. Provide a confidence score for each impact.",
                "description": "Default generation prompt",
            },
            {
                "prompt_type": "review",
                "system_prompt": "You are a senior policy reviewer. Review the following impact analysis for accuracy, bias, and evidence. Flag any speculative claims that lack citation. Adjust confidence scores based on the strength of the evidence provided.",
                "description": "Default review prompt",
            },
        ]

        print("Seeding prompts...")
        for prompt in prompts:
            version = await db.update_system_prompt(
                prompt_type=prompt["prompt_type"],
                system_prompt=prompt["system_prompt"],
                description=prompt["description"],
                user_id="system",
            )
            print(f"Seeded prompt: {prompt['prompt_type']} v{version}")
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(seed_data())
