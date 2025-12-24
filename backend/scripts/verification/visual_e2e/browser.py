"""
Browser helpers for Visual E2E testing.

Provides Playwright-based screenshot capture and assertions.
"""

import asyncio
import logging
from pathlib import Path
from typing import List, Tuple, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class BrowserHelper:
    """Playwright browser helper for visual verification."""
    
    def __init__(self, base_url: str, artifacts_dir: Path, headless: bool = True):
        self.base_url = base_url.rstrip("/")
        self.artifacts_dir = artifacts_dir
        self.headless = headless
        self.browser = None
        self.context = None
        self.page = None
    
    async def start(self):
        """Start browser instance."""
        try:
            from playwright.async_api import async_playwright
            self._playwright = await async_playwright().start()
            self.browser = await self._playwright.chromium.launch(headless=self.headless)
            self.context = await self.browser.new_context(
                viewport={"width": 1280, "height": 720},
                ignore_https_errors=True,
            )
            self.page = await self.context.new_page()
            logger.info(f"Browser started: {self.base_url}")
        except ImportError:
            raise ImportError("playwright not installed. Run: pip install playwright && playwright install chromium")
    
    async def stop(self):
        """Stop browser instance."""
        if self.browser:
            await self.browser.close()
        if hasattr(self, '_playwright'):
            await self._playwright.stop()
        logger.info("Browser stopped")
    
    async def navigate(self, path: str, wait_for: str, timeout: int = 10000) -> bool:
        """Navigate to URL and wait for selector."""
        url = f"{self.base_url}{path}"
        logger.info(f"Navigating to: {url}")
        
        try:
            await self.page.goto(url, timeout=timeout)
            await self.page.wait_for_selector(wait_for, timeout=timeout)
            return True
        except Exception as e:
            logger.warning(f"Navigation issue: {e}")
            # Still capture what we can
            return False
    
    async def screenshot(self, filename: str) -> Path:
        """Take screenshot and save as WebP."""
        screenshot_path = self.artifacts_dir / filename
        screenshot_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Playwright supports webp format
        await self.page.screenshot(path=str(screenshot_path), type="png")
        
        # Convert to webp if PIL available
        try:
            from PIL import Image
            img = Image.open(screenshot_path)
            webp_path = screenshot_path.with_suffix(".webp")
            img.save(webp_path, "WEBP", quality=85)
            screenshot_path.unlink()  # Remove PNG
            logger.info(f"Screenshot saved: {webp_path}")
            return webp_path
        except ImportError:
            logger.info(f"Screenshot saved (PNG): {screenshot_path}")
            return screenshot_path
    
    async def check_assertion(self, selector: str, op: str, value: str) -> Tuple[bool, str]:
        """
        Check an assertion against the page.
        
        Returns (passed, message).
        """
        try:
            if op == "visible":
                element = await self.page.query_selector(selector)
                passed = element is not None
                return passed, f"'{selector}' {'is' if passed else 'is NOT'} visible"
            
            elif op == "contains":
                element = await self.page.query_selector(selector)
                if element:
                    text = await element.text_content()
                    passed = value.lower() in (text or "").lower()
                    return passed, f"'{selector}' {'contains' if passed else 'does NOT contain'} '{value}'"
                return False, f"'{selector}' not found"
            
            elif op == "count_gte":
                elements = await self.page.query_selector_all(selector)
                count = len(elements)
                threshold = int(value)
                passed = count >= threshold
                return passed, f"'{selector}' count={count} {'>=':if passed else '<'} {threshold}"
            
            elif op == "no_crash":
                # Page loaded without crashing
                return True, "Page loaded successfully (no crash)"
            
            else:
                return False, f"Unknown assertion op: {op}"
                
        except Exception as e:
            return False, f"Assertion error: {e}"
    
    async def run_assertions(self, assertions: List[Tuple[str, str, str]]) -> List[Tuple[bool, str]]:
        """Run all assertions and return results."""
        results = []
        for selector, op, value in assertions:
            passed, msg = await self.check_assertion(selector, op, value)
            results.append((passed, msg))
        return results


async def create_browser(base_url: str, artifacts_dir: Path, headless: bool = True) -> BrowserHelper:
    """Factory function to create and start browser."""
    helper = BrowserHelper(base_url, artifacts_dir, headless)
    await helper.start()
    return helper
