import base64
import logging
import asyncio
from typing import Any, List, Dict
from urllib.parse import urljoin
from playwright.async_api import Page, TimeoutError as PlaywrightTimeout, async_playwright

logger = logging.getLogger(__name__)

class PlaywrightAdapter:
    """Simplified Playwright implementation of BrowserAdapter protocol."""

    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url.rstrip("/")
        self._console_errors: List[str] = []
        self._network_errors: List[Dict[str, Any]] = []
        self._setup_listeners()

    def _setup_listeners(self) -> None:
        def on_console(msg):
            if msg.type in ("error", "warning"):
                self._console_errors.append(f"[{msg.type}] {msg.text}")

        def on_request_failed(request):
            failure = request.failure
            if failure:
                self._network_errors.append({
                    "url": request.url,
                    "method": request.method,
                    "message": failure,
                    "status": None  # Failure before response
                })

        self.page.on("console", on_console)
        self.page.on("requestfailed", on_request_failed)

    async def navigate(self, path: str) -> None:
        url = urljoin(self.base_url, path)
        logger.info(f"Navigating to {url}")
        # Wait for networkidle AND domcontentloaded
        await self.page.goto(url, wait_until="networkidle", timeout=30000)
        # Explicit sleep to ensure React hydration/rendering completes
        import asyncio
        await asyncio.sleep(2)

    async def click(self, target: str) -> None:
        logger.info(f"Clicking: {target}")
        selector = target if target.startswith(("text=", "/", "#", ".")) else f"text={target}"
        # Wait for element to be visible and stable
        try:
            await self.page.wait_for_selector(selector, state="visible", timeout=10000)
            await self.page.click(selector, timeout=5000)
            # Wait for potential navigation or UI update
            await self.page.wait_for_load_state("networkidle")
            await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"Click failed for {selector}: {e}")
            raise
    async def type_text(self, selector: str, text: str) -> None:
        logger.info(f"Typing into {selector}")
        await self.page.fill(selector, text, timeout=5000)

    async def screenshot(self) -> str:
        screenshot_bytes = await self.page.screenshot(type="png")
        return base64.b64encode(screenshot_bytes).decode("utf-8")

    async def get_console_errors(self) -> List[str]:
        errors = self._console_errors.copy()
        self._console_errors.clear()
        return errors

    async def get_network_errors(self) -> List[Dict[str, Any]]:
        errors = self._network_errors.copy()
        self._network_errors.clear()
        return errors

    async def wait_for_selector(self, selector: str, timeout_ms: int = 5000) -> None:
        await self.page.wait_for_selector(selector, timeout=timeout_ms)

    async def get_current_url(self) -> str:
        return self.page.url

    async def get_content(self) -> str:
        return await self.page.content()

    async def close(self) -> None:
        await self.page.close()

async def create_browser_context(base_url: str, headless: bool = True):
    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(headless=headless)
    context = await browser.new_context(viewport={"width": 1280, "height": 720})
    page = await context.new_page()
    adapter = PlaywrightAdapter(page, base_url)
    return playwright, browser, adapter
