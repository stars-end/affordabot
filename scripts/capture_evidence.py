
import asyncio
from playwright.async_api import async_playwright

async def capture_screenshot():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        try:
            url = "https://frontend-dev-f8a3.up.railway.app/admin"
            print(f"Navigating to {url}...")
            await page.goto(url, timeout=60000)
            await page.screenshot(path="/home/fengning/.gemini/antigravity/brain/8162ce81-b56f-4708-b2bd-eb4c91b6af0f/verification_artifacts/affordabot_screenshot_raw.png")
            print("Screenshot saved.")
        except Exception as e:
            print(f"Error: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(capture_screenshot())
