import asyncio
import os
import sys

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from db.postgres_client import PostgresDB

async def seed_prompts():
    print("Connecting to DB...")
    db = PostgresDB()
    await db.connect()

    prompts = [
        {
            "prompt_type": "legislation_analysis",
            "system_prompt": """
You are an expert policy analyst. Analyze the legislation for cost-of-living impacts.
Use the provided RESEARCH DATA to support your analysis with real evidence.
Focus on housing costs, utility bills, taxes, and consumer goods prices.
""",
            "description": "Initial seed for legislation analysis generation."
        },
        {
            "prompt_type": "analysis_review",
            "system_prompt": """
You are a strict auditor. Review the provided analysis against the bill text and research.
Verify every claim. Check for hallucinations. Ensure all impacts are supported by evidence.
Reject any analysis that cites hallucinated clauses or fails to link evidence to impacts.
""",
            "description": "Initial seed for analysis review."
        },
        {
            "prompt_type": "analysis_refinement",
            "system_prompt": """
You are an expert policy analyst. Update your previous analysis based on the auditor's critique.
Fix factual errors, add missing impacts, and correct citations.
Ensure the final output is polished and evidence-backed.
""",
            "description": "Initial seed for analysis refinement."
        }
    ]

    for p in prompts:
        print(f"Seeding {p['prompt_type']}...")
        # Check if exists
        existing = await db.get_system_prompt(p['prompt_type'])
        if not existing:
            await db.update_system_prompt(
                prompt_type=p['prompt_type'],
                system_prompt=p['system_prompt'],
                description=p['description'],
                user_id="seed_script"
            )
            print("  Created.")
        else:
            print("  Already exists, skipping.")

    await db.close()
    print("Done.")

if __name__ == "__main__":
    asyncio.run(seed_prompts())
