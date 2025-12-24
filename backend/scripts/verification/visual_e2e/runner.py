"""
Visual E2E Runner for Affordabot.

Orchestrates story-driven browser testing with screenshots.
"""

import argparse
import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import List

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from scripts.verification.visual_e2e.stories import get_all_stories, Story
from scripts.verification.visual_e2e.browser import create_browser, BrowserHelper

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class VisualE2ERunner:
    """Orchestrates visual E2E testing with browser screenshots."""
    
    def __init__(
        self,
        stage: str,
        base_url: str,
        api_url: str = None,
        artifacts_dir: Path = None,
        headless: bool = True,
    ):
        self.stage = stage
        self.base_url = base_url
        self.api_url = api_url or base_url
        self.headless = headless
        
        # Setup artifacts directory
        timestamp = datetime.now().strftime("%Y-%m-%d-%H%M")
        if artifacts_dir:
            self.artifacts_dir = Path(artifacts_dir) / stage / timestamp
        else:
            self.artifacts_dir = Path(__file__).parent.parent.parent.parent.parent / "artifacts" / "verification" / stage / timestamp
        
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        self.results: List[dict] = []
    
    async def run_story(self, browser: BrowserHelper, story: Story) -> dict:
        """Run a single story and return results."""
        logger.info(f"\n{'='*60}")
        logger.info(f"Story {story.id}: {story.name}")
        logger.info(f"{'='*60}")
        
        result = {
            "id": story.id,
            "name": story.name,
            "url": story.url,
            "passed": True,
            "screenshot": None,
            "assertions": [],
            "error": None,
        }
        
        try:
            # Navigate to URL
            nav_ok = await browser.navigate(story.url, story.wait_for)
            if not nav_ok:
                logger.warning(f"Navigation may have issues, continuing...")
            
            # Small delay for page to settle
            await asyncio.sleep(0.5)
            
            # Take screenshot
            screenshot_path = await browser.screenshot(story.screenshot_name)
            result["screenshot"] = screenshot_path.name
            
            # Run assertions
            for selector, op, value in story.assertions:
                passed, msg = await browser.check_assertion(selector, op, value)
                result["assertions"].append({"passed": passed, "message": msg})
                if not passed:
                    result["passed"] = False
                logger.info(f"  {'✅' if passed else '❌'} {msg}")
            
            # If no assertions, consider passed if screenshot taken
            if not story.assertions:
                logger.info("  ✅ Screenshot captured (no specific assertions)")
            
        except Exception as e:
            result["passed"] = False
            result["error"] = str(e)
            logger.error(f"  ❌ Error: {e}")
        
        return result
    
    async def run_all(self) -> bool:
        """Run all stories and generate report."""
        stories = get_all_stories()
        
        print(f"\n🎬 Visual E2E Runner - {self.stage.upper()}")
        print(f"📍 Base URL: {self.base_url}")
        print(f"📁 Artifacts: {self.artifacts_dir}")
        print(f"📋 Stories: {len(stories)}")
        print("="*60)
        
        browser = await create_browser(self.base_url, self.artifacts_dir, self.headless)
        
        try:
            for story in stories:
                result = await self.run_story(browser, story)
                self.results.append(result)
        finally:
            await browser.stop()
        
        # Generate report
        report_path = self.generate_report()
        
        # Summary
        passed = sum(1 for r in self.results if r["passed"])
        total = len(self.results)
        
        print("\n" + "="*60)
        print(f"🏁 Visual E2E Complete: {passed}/{total} PASSED")
        print(f"📋 Report: {report_path}")
        print("="*60)
        
        return passed == total
    
    def generate_report(self) -> Path:
        """Generate markdown report with embedded screenshots."""
        report_path = self.artifacts_dir / "report.md"
        
        passed = sum(1 for r in self.results if r["passed"])
        total = len(self.results)
        status = "✅ PASSED" if passed == total else f"⚠️ {passed}/{total} PASSED"
        
        lines = [
            f"# Visual E2E Report - Affordabot",
            f"",
            f"**Stage**: {self.stage.upper()}",
            f"**Environment**: {self.base_url}",
            f"**Timestamp**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"**Result**: {status}",
            f"",
            f"---",
            f"",
        ]
        
        for result in self.results:
            status_icon = "✅" if result["passed"] else "❌"
            lines.append(f"## Story {result['id']}: {result['name']}")
            lines.append(f"")
            lines.append(f"**Status**: {status_icon} {'PASSED' if result['passed'] else 'FAILED'}")
            lines.append(f"**URL**: `{result['url']}`")
            lines.append(f"")
            
            if result["screenshot"]:
                lines.append(f"![{result['name']}](./{result['screenshot']})")
                lines.append(f"")
            
            if result["assertions"]:
                lines.append("**Assertions**:")
                for a in result["assertions"]:
                    icon = "✅" if a["passed"] else "❌"
                    lines.append(f"- {icon} {a['message']}")
                lines.append("")
            
            if result["error"]:
                lines.append(f"**Error**: {result['error']}")
                lines.append("")
            
            lines.append("---")
            lines.append("")
        
        report_path.write_text("\n".join(lines))
        return report_path


async def main():
    parser = argparse.ArgumentParser(description="Visual E2E Runner for Affordabot")
    parser.add_argument("--stage", choices=["local", "pr"], default="local", help="Test stage")
    parser.add_argument("--base-url", default="http://localhost:3000", help="Frontend base URL")
    parser.add_argument("--api-url", default="http://localhost:8000", help="Backend API URL")
    parser.add_argument("--artifacts-dir", help="Artifacts directory")
    parser.add_argument("--headed", action="store_true", help="Run with visible browser")
    
    args = parser.parse_args()
    
    runner = VisualE2ERunner(
        stage=args.stage,
        base_url=args.base_url,
        api_url=args.api_url,
        artifacts_dir=Path(args.artifacts_dir) if args.artifacts_dir else None,
        headless=not args.headed,
    )
    
    success = await runner.run_all()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
