import asyncio
import logging
import os
import sys
from pathlib import Path

# Add llm-common to path if needed (though it should be installed)
# sys.path.append(str(Path(__file__).parent.parent.parent.parent / "llm-common"))

from llm_common.agents import (
    GLMConfig, 
    GLMVisionClient, 
    UISmokeAgent, 
    load_stories_from_directory
)
from browser_adapter import create_browser_context

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

async def main():
    api_key = os.environ.get("ZAI_API_KEY")
    base_url = os.environ.get("VISUAL_AUDIT_BASE_URL", "http://127.0.0.1:5173")
    
    if not api_key:
        logger.error("ZAI_API_KEY not set")
        sys.exit(1)
        
    logger.info(f"Starting visual audit against {base_url}")
    
    # 1. Setup Client
    glm_config = GLMConfig(api_key=api_key, model="glm-4.6v")
    glm_client = GLMVisionClient(glm_config)
    
    # 2. Load Story
    # backend/scripts/verification/capture_visual_proof.py -> backend/docs/TESTING/STORIES
    stories_dir = Path(__file__).parent.parent.parent / "docs" / "TESTING" / "STORIES"
    stories = load_stories_from_directory(stories_dir)
    audit_story = next((s for s in stories if s.id == "story-vis-audit-detailed"), None)
    
    if not audit_story:
        logger.error("Audit story not found")
        sys.exit(1)
        
    # 3. Launch Browser
    playwright, browser, adapter = await create_browser_context(base_url, headless=True)
    
    # 4. Run Agent with Evidence Capture
    # Artifacts dir: /home/fengning/.gemini/antigravity/brain/9112de99-6087-4677-88e8-ddcb9dc376f2
    evidence_dir = Path("/home/fengning/.gemini/antigravity/brain/9112de99-6087-4677-88e8-ddcb9dc376f2/evidence")
    
    agent = UISmokeAgent(
        glm_client=glm_client,
        browser=adapter,
        base_url=base_url,
        evidence_dir=str(evidence_dir)
    )
    
    try:
        result = await agent.run_story(audit_story)
        logger.info(f"Visual audit status: {result.status}")
        logger.info(f"Evidence saved to: {evidence_dir}")
        
    except Exception as e:
        logger.exception(f"Visual audit failed: {e}")
    finally:
        await adapter.close()
        await browser.close()
        await playwright.stop()

if __name__ == "__main__":
    asyncio.run(main())
