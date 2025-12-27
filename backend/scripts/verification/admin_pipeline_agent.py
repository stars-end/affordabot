#!/usr/bin/env python3
"""
Admin Pipeline Agent - UISmokeAgent-based verification for Affordabot.

Refactored to use llm-common's UISmokeAgent and PlaywrightAdapter.
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

from playwright.async_api import async_playwright

# Add backend root to path to find scripts modules if needed
sys.path.append(str(Path(__file__).parent.parent.parent))

from scripts.verification.patch_zai import apply_patch
apply_patch()

# Import Adapter
from scripts.verification.browser_adapter import PlaywrightAdapter
from scripts.verification.clerk_auth import clerk_login

# Import llm-common
from llm_common.agents import UISmokeAgent
from llm_common.core import LLMConfig
from llm_common.providers import ZaiClient
from llm_common.agents.schemas import AgentStory

@dataclass
class PipelineStep:
    """Definition of a pipeline verification step."""
    id: str
    name: str
    path: str
    wait_selector: Optional[str] = None
    description: str = ""
    glm_prompt: str = "Describe the main UI elements visible in this screenshot."


# Define admin pipeline steps for ACTUAL routes that exist
ADMIN_PIPELINE_STEPS = [
    PipelineStep(
        id="01_dashboard",
        name="Admin Dashboard",
        path="/admin",
        wait_selector="body",
        description="Main admin dashboard with overview, metrics, and navigation",
        glm_prompt="Is this an admin dashboard? List the main navigation items and metrics visible.",
    ),
    PipelineStep(
        id="02_discovery",
        name="Discovery",
        path="/admin/discovery",
        wait_selector="body",
        description="URL discovery interface",
        glm_prompt="Is this a discovery/search interface?",
    ),
    PipelineStep(
        id="03_sources",
        name="Sources",
        path="/admin/sources",
        wait_selector="body",
        description="Source management",
        glm_prompt="Is this a sources/data management page?",
    ),
    PipelineStep(
        id="04_jurisdiction_california",
        name="Jurisdiction - California",
        path="/admin/jurisdiction/california",
        wait_selector="body",
        description="California jurisdiction detail",
        glm_prompt="Is this a jurisdiction detail page?",
    ),
    # PipelineStep(
    #     id="05_jurisdiction_sanjose",
    #     name="Jurisdiction - San Jose",
    #     path="/admin/jurisdiction/san-jose",
    #     wait_selector="body",
    #     description="San Jose jurisdiction detail with local policies",
    #     glm_prompt="Is this a jurisdiction detail page for a city?",
    # ),
    PipelineStep(
        id="06_prompts",
        name="Prompts",
        path="/admin/prompts",
        wait_selector="body",
        description="LLM prompt management",
        glm_prompt="Is this a prompt management interface?",
    ),
    PipelineStep(
        id="07_reviews",
        name="Reviews",
        path="/admin/reviews",
        wait_selector="body",
        description="Review queue",
        glm_prompt="Is this a review queue?",
    ),
]

async def main():
    parser = argparse.ArgumentParser(description="Admin Pipeline Visual Verification (Refactored)")
    parser.add_argument("--url", default=os.environ.get("FRONTEND_URL", "http://localhost:3000"))
    parser.add_argument("--output", default="artifacts/verification/admin_pipeline")
    args = parser.parse_args()
    
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    api_key = os.environ.get("ZAI_API_KEY")
    if not api_key:
        print("❌ ZAI_API_KEY required for UISmokeAgent")
        sys.exit(1)
        
    print(f"🚀 Starting Admin Pipeline Verification against {args.url}")

    # Initialize LLM Client
    config = LLMConfig(api_key=api_key, provider="zai", default_model="glm-4.6v")
    llm_client = ZaiClient(config)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        # Create context to allow header injection if needed
        context = await browser.new_context()
        page = await context.new_page()
        
        # Authenticate (bypass header if available, else email/password via env vars)
        authed = await clerk_login(page, args.url, output_dir)
        if not authed:
            print("❌ Authentication failed. See artifacts in output dir.")
            sys.exit(1)
        
        # Initialize Adapter and Agent
        adapter = PlaywrightAdapter(page, base_url=args.url)
        adapter.start_tracing()
        
        agent = UISmokeAgent(
            glm_client=llm_client,
            browser=adapter,
            base_url=args.url,
            evidence_dir=str(output_dir)
        )
        
        # Convert PipelineSteps to AgentStory
        story_steps = []
        for step in ADMIN_PIPELINE_STEPS:
            story_steps.append({
                "id": step.id,
                "description": f"Navigate to {step.path}. Goal: {step.description}. Verification: {step.glm_prompt}",
                "validation_criteria": ["Dashboard", "Admin"] if step.id == "01_dashboard" else [] # Simple text checks
            })
            
        story = AgentStory(
            id="admin_pipeline_e2e",
            persona="Admin User",
            steps=story_steps
        )
        
        # Run Story
        print("📋 Running Story via UISmokeAgent...")
        result = await agent.run_story(story)
        
        print("\n" + "="*60)
        print(f"🏁 Story Result: {result.status.upper()}")
        for res in result.step_results:
            icon = "✅" if res.status == "pass" else "❌"
            print(f"{icon} {res.step_id}: {res.status}")
            if res.errors:
                for e in res.errors:
                    print(f"   Err: {e.message}")
        print("="*60)
        
        # Cleanup
        await browser.close()
        
        if result.status != "pass":
            sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
