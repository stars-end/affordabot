import asyncio
import os
import sys
import time
from typing import Dict, Any, List
from playwright.async_api import async_playwright

# Adjust path to find backend modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from backend.services.extractors.zai import ZaiExtractor
from backend.clients.web_reader_client import WebReaderClient

TEST_URLS = [
    # 1. User provided: Municode Main (SPA)
    "https://library.municode.com/ca/san_jose/codes/code_of_ordinances",
    
    # 2. User provided: Main Gov Page (GovCMS)
    "https://www.sanjoseca.gov/your-government",
    
    # 3. User provided: Legistar Calendar (ASP.NET WebForms)
    "https://sanjose.legistar.com/Calendar.aspx",
    
    # 4. User provided: Legistar Attachment (PDF/File Download)
    "https://sanjose.legistar.com/View.ashx?M=A&ID=1364408&GUID=C224711B-2111-4DC4-BB2B-615C76A09833",
    
    # 5. News Listing (GovCMS List)
    "https://www.sanjoseca.gov/news-stories",
    
    # 6. Housing Department (Dept Page)
    "https://www.sanjoseca.gov/your-government/departments-offices/housing",
    
    # 7. Police Department (Dept Page)
    "https://www.sanjoseca.gov/your-government/departments-offices/police-department",
    
    # 8. City Clerk (Appointee Page)
    "https://www.sanjoseca.gov/your-government/appointees/city-clerk",
    
    # 9. Utility Bill (Service Page)
    "https://www.sanjoseca.gov/i-want-to/pay-my",
    
    # 10. 311 Service (Likely SPA/CRM)
    "https://311.sanjoseca.gov/"
]

async def test_zai(url: str, client: WebReaderClient) -> str:
    start_time = time.time()
    try:
        # Use verified kwargs from spike
        result = await client.fetch_content(url, timeout=60)
        
        # Check if actual content or error content
        content = result.get("content", "") or result.get("reader_result", {}).get("content", "")
        
        elapsed = time.time() - start_time
        
        if not content:
            return f"❌ FAILED (Empty, {elapsed:.1f}s)"
            
        if "Content Not Found" in content or "Initializing application" in content:
             return f"⚠️ SHELL ONLY ({len(content)} chars, {elapsed:.1f}s)"
             
        if "Attention Required" in content or "Cloudflare" in content:
            return f"🚫 BLOCKED ({elapsed:.1f}s)"
            
        return f"✅ SUCCESS ({len(content)} chars, {elapsed:.1f}s)"
        
    except Exception as e:
        elapsed = time.time() - start_time
        return f"❌ ERROR ({str(e)[:20]}..., {elapsed:.1f}s)"

async def test_playwright(url: str) -> str:
    start_time = time.time()
    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                 user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = await context.new_page()
            
            # Use verified verified strategy
            try:
                await page.goto(url, wait_until="networkidle", timeout=20000)
            except Exception:
                # Fallback if networkidle times out (common on heavy sites)
                pass
                
            content = await page.content()
            body_text = await page.inner_text("body")
            
            elapsed = time.time() - start_time
            
            if not body_text.strip():
                 return f"❌ FAILED (Empty, {elapsed:.1f}s)"
            
            # Check for generic SPA loading messages
            if len(body_text) < 500 and ("Loading" in body_text or "Initializing" in body_text):
                 return f"⚠️ SHELL ONLY ({len(body_text)} chars, {elapsed:.1f}s)"

            return f"✅ SUCCESS ({len(body_text)} chars, {elapsed:.1f}s)"
            
        except Exception as e:
            elapsed = time.time() - start_time
            return f"❌ ERROR ({str(e)[:20]}..., {elapsed:.1f}s)"
        finally:
            if 'browser' in locals():
                await browser.close()

async def main():
    print(f"🚀 Starting Bulk Validation on {len(TEST_URLS)} URLs")
    print("-" * 80)
    print(f"{'URL':<50} | {'Z.ai':<25} | {'Playwright':<25}")
    print("-" * 80)
    
    api_key = os.environ.get("ZAI_API_KEY")
    zai_client = WebReaderClient(api_key=api_key, base_url="https://api.z.ai/api/coding")
    
    for url in TEST_URLS:
        # Truncate URL for display
        display_url = (url[:47] + '..') if len(url) > 47 else url
        
        # Test Z.ai
        zai_res = await test_zai(url, zai_client)
        
        # Test Playwright
        pw_res = await test_playwright(url)
        
        print(f"{display_url:<50} | {zai_res:<25} | {pw_res:<25}")
        
    print("-" * 80)

if __name__ == "__main__":
    asyncio.run(main())
