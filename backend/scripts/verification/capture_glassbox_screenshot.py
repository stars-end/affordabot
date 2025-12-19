import sys
import asyncio
import os
from datetime import datetime
from playwright.async_api import async_playwright

# Configuration
BASE_URL = "http://localhost:5173"
ARTIFACT_DIR = f"{os.getcwd()}/scripts/verification/artifacts"

async def capture_granular_evidence(run_id: str):
    """
    Capture 10 granular screenshots from the Admin UI for audit purposes.
    Targeting specific steps (Research, Generate, Review) and their tabs.
    """
    os.makedirs(ARTIFACT_DIR, exist_ok=True)
    
    async with async_playwright() as p:
        print(f"🚀 Starting Playwright for run_id: {run_id}")
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1400, "height": 1200},
            device_scale_factor=2
        )
        page = await context.new_page()
        
        url = f"{BASE_URL}/admin/runs/{run_id}"
        print(f"📍 Navigating to {url}")
        
        try:
            # 1. Wait for page to load and ensure granular data is visible
            print("  ...waiting for navigation (30s)...")
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            
            # Wait for loading to finish (CircularProgress to detach)
            print("  ...waiting for loading to finish...")
            try:
                # Wait for CircularProgress to appear then disappear, or just wait for it to not be there
                # Since it might be gone already, we just wait for the accordion or alert
                # But safer to fast-fail if alert "No granular steps" appears
                await page.wait_for_selector(".MuiCircularProgress-root", state="detached", timeout=10000)
            except:
                pass # It might have been too fast

            print("  ...waiting for Step Timeline (.MuiAccordion-root)...")
            # Check if we have an error alert
            if await page.locator("text=No granular steps recorded").count() > 0:
                print("❌ Found 'No granular steps' message. Verify backend.")
                # Take error screenshot
                await page.screenshot(path=f"{ARTIFACT_DIR}/error_no_steps.png")
                await browser.close()
                return
                
            await page.wait_for_selector(".MuiAccordion-root", timeout=30000)
            
            # Initial overview screenshot
            await page.screenshot(path=f"{ARTIFACT_DIR}/0_run_overview_{run_id}.png")
            print(f"📸 Captured overview")

            # 2. Extract and capture each step
            accordions = await page.locator(".MuiAccordion-root").all()
            print(f"📋 Found {len(accordions)} granular steps.")

            for i, accordion in enumerate(accordions):
                # Scroll step into view
                await accordion.scroll_into_view_if_needed()
                
                # Expand accordion if not expanded
                is_expanded = await accordion.get_attribute("aria-expanded") == "true"
                if not is_expanded:
                    summary = accordion.locator(".MuiAccordionSummary-root")
                    await summary.click()
                    await asyncio.sleep(0.5)

                # Identify step name
                title_el = accordion.locator(".MuiTypography-root").first
                step_name = await title_el.inner_text()
                safe_name = step_name.lower().replace(" ", "_")
                print(f"  👉 Processing step {i+1}: {step_name}")

                # Capture tabs (Input Context, Output Result)
                tabs = accordion.locator("[role='tab']")
                tab_count = await tabs.count()
                
                for j in range(tab_count):
                    tab = tabs.nth(j)
                    tab_text = await tab.inner_text()
                    await tab.click()
                    await asyncio.sleep(2.0) # Increased wait for render safety
                    
                    filename = f"step_{i+1}_{safe_name}_tab_{tab_text.lower().replace(' ', '_')}.png"
                    await accordion.screenshot(path=f"{ARTIFACT_DIR}/{filename}")
                    print(f"    📸 Captured tab: {filename}")

            # 3. Final Full Page
            await page.screenshot(path=f"{ARTIFACT_DIR}/z_full_audit_{run_id}.png", full_page=True)
            print(f"✅ Comparison Audit Complete for {run_id}")

        except Exception as e:
            print(f"❌ Error during capture: {e}")
            # Take error screenshot
            await page.screenshot(path=f"{ARTIFACT_DIR}/error_state_{run_id}.png")
        finally:
            await browser.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python capture_glassbox_screenshot.py <run_id>")
        sys.exit(1)
        
    target_run_id = sys.argv[1]
    asyncio.run(capture_granular_evidence(target_run_id))
