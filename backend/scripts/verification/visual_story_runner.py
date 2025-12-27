#!/usr/bin/env python3
"""Visual Story Runner - Executes YAML-based visual verification stories using UISmokeAgent."""
import argparse
import asyncio
import os
import sys
import yaml
from pathlib import Path

from playwright.async_api import async_playwright

# Add backend root to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from scripts.verification.patch_zai import apply_patch
apply_patch()

from scripts.verification.browser_adapter import PlaywrightAdapter
from llm_common.agents import UISmokeAgent
from llm_common.core import LLMConfig
from llm_common.providers import ZaiClient
from llm_common.agents.schemas import AgentStory

from scripts.verification.clerk_auth import clerk_login

def _coerce_validation_criteria(raw_step: dict) -> list[str]:
    criteria = raw_step.get("validation_criteria")
    if isinstance(criteria, list):
        return [str(x) for x in criteria if str(x).strip()]

    expected = raw_step.get("expected")
    if expected is None:
        return []
    if isinstance(expected, list):
        return [str(x) for x in expected if str(x).strip()]
    expected_str = str(expected).strip()
    return [expected_str] if expected_str else []


def _build_step_description(raw_step: dict) -> str:
    if raw_step.get("description"):
        desc = str(raw_step["description"]).strip()
    else:
        action = str(raw_step.get("action", "")).strip()
        verification = str(raw_step.get("verification", "")).strip()
        desc = f"Goal: {action}. Verification required: {verification}.".strip()

    glm_prompt = raw_step.get("glm_prompt")
    if glm_prompt:
        desc = f"{desc}\n\nQuestion: {glm_prompt}".strip()
    return desc


async def run_story_file(story_path: Path, base_url: str, output_dir: Path, api_key: str) -> bool:
    """Run a single story file."""
    print(f"📖 Loading story from {story_path}")
    with open(story_path, "r") as f:
        data = yaml.safe_load(f)

    start_url = data.get("start_url", "/admin")
    raw_steps = data.get("steps", [])
    steps: list[dict] = []

    for idx, raw_step in enumerate(raw_steps):
        step_id = (
            raw_step.get("id")
            or raw_step.get("name")
            or raw_step.get("step_id")
            or f"step_{idx+1}"
        )
        step_id = str(step_id).replace(" ", "_").lower()

        desc = _build_step_description(raw_step)
        if idx == 0 and start_url:
            desc = f"Navigate to {start_url}.\n\n{desc}".strip()

        steps.append(
            {
                "id": step_id,
                "description": desc,
                "validation_criteria": _coerce_validation_criteria(raw_step),
            }
        )

    story = AgentStory(
        id=(data.get("id") or data.get("name") or story_path.stem).replace(" ", "_"),
        persona=data.get("persona", "User"),
        steps=steps,
        metadata=data,
    )
    
    # Run
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        
        # Authenticate (bypass header if available, else email/password)
        authed = await clerk_login(page, base_url, output_dir)
        if not authed:
            print("❌ Authentication failed. See artifacts in output dir.")
            return False

        # Ensure we actually start the story at its declared start_url.
        # Relying on the LLM to navigate is brittle (it may confuse similarly-shaped pages).
        try:
            if start_url:
                absolute_url = (
                    start_url
                    if str(start_url).startswith("http")
                    else f"{base_url.rstrip('/')}{start_url}"
                )
                await page.goto(absolute_url, wait_until="networkidle", timeout=60_000)
        except Exception as e:
            print(f"⚠️ Failed to navigate to start_url={start_url}: {e}")
        
        adapter = PlaywrightAdapter(page, base_url=base_url)
        adapter.start_tracing()
        
        llm = ZaiClient(LLMConfig(api_key=api_key, provider="zai", default_model="glm-4.6v"))
        
        agent = UISmokeAgent(
            glm_client=llm,
            browser=adapter,
            base_url=base_url,
            evidence_dir=str(output_dir)
        )
        
        print(f"▶️ Running Story: {story.id}")
        result = await agent.run_story(story)
        
        # Report
        print(f"🏁 Result: {result.status.upper()}")
        if result.status != "pass":
            print("❌ Story Failed. Check artifacts.")
            return False
        return True

async def main():
    parser = argparse.ArgumentParser(description="Run Visual Stories")
    parser.add_argument("--story", required=False, help="Path to specific YAML story")
    parser.add_argument("--all", action="store_true", help="Run all stories in docs/TESTING/STORIES")
    parser.add_argument(
        "--tags",
        required=False,
        help="Comma-separated tag filter (matches docs/TESTING/STORIES/*.yml metadata.tags)",
    )
    parser.add_argument("--url", default=os.environ.get("FRONTEND_URL", "http://localhost:3000"))
    parser.add_argument("--output", default="artifacts/verification/stories")
    args = parser.parse_args()

    api_key = os.environ.get("ZAI_API_KEY")
    if not api_key:
        print("❌ ZAI_API_KEY required")
        sys.exit(1)

    output_path = Path(args.output)
    output_path.mkdir(parents=True, exist_ok=True)

    stories_to_run: list[Path] = []
    if args.story:
        stories_to_run.append(Path(args.story))
    elif args.all:
        docs_root = Path(__file__).parent.parent.parent.parent / "docs" / "TESTING" / "STORIES"
        if docs_root.exists():
            stories_to_run.extend(sorted(docs_root.glob("*.yml")))

    if args.all and args.tags and stories_to_run:
        tag_filter = {t.strip() for t in str(args.tags).split(",") if t.strip()}
        if tag_filter:
            filtered: list[Path] = []
            for p in stories_to_run:
                try:
                    data = yaml.safe_load(p.read_text())
                    tags = data.get("metadata", {}).get("tags", [])
                    if isinstance(tags, list) and any(str(t) in tag_filter for t in tags):
                        filtered.append(p)
                except Exception:
                    continue
            stories_to_run = filtered
            print(f"🔎 Filtered stories by tags={sorted(tag_filter)} -> {len(stories_to_run)} stories")

    if not stories_to_run:
        print("No stories found.")
        sys.exit(0)

    success = True
    for story in stories_to_run:
        if not await run_story_file(story, args.url, output_path, api_key):
            success = False

    sys.exit(0 if success else 1)

if __name__ == "__main__":
    asyncio.run(main())
