import asyncio
import httpx
import sys
import os

# Ensure we can import backend modules
sys.path.append(os.getcwd())
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from backend.main import app
from backend.services.scraper.saratoga import SaratogaScraper
from backend.services.scraper.san_jose import SanJoseScraper
from backend.services.scraper.santa_clara_county import SantaClaraCountyScraper
from backend.services.scraper.california_state import CaliforniaStateScraper

async def run_tests():
    print("🚀 Starting E2E Tests...")
    
    # 1. Test Jurisdiction Loading
    print("\n1️⃣  Testing Jurisdiction Loading...")
    try:
        scrapers = {
            "saratoga": SaratogaScraper(),
            "san-jose": SanJoseScraper(),
            "santa-clara-county": SantaClaraCountyScraper(),
            "california": CaliforniaStateScraper()
        }
        print("✅ All scraper classes loaded successfully")
    except Exception as e:
        print(f"❌ Failed to load scrapers: {e}")
        return

    # 2. Test Health Checks (Connectivity)
    print("\n2️⃣  Testing Connectivity (Health Checks)...")
    for name, scraper in scrapers.items():
        try:
            is_healthy = await scraper.check_health()
            status = "✅ Online" if is_healthy else "⚠️ Offline (or Mocked)"
            print(f"   - {name}: {status}")
        except Exception as e:
            print(f"   - {name}: ❌ Error ({e})")

    # 3. Test Scraping (Dry Run)
    print("\n3️⃣  Testing Scraping (First item only)...")
    for name, scraper in scrapers.items():
        print(f"   Scraping {name}...", end="", flush=True)
        try:
            bills = await scraper.scrape()
            if bills:
                print(f" ✅ Found {len(bills)} bills. Sample: {bills[0].bill_number}")
            else:
                print(" ⚠️ No bills found")
        except Exception as e:
            print(f" ❌ Failed: {e}")

    # 4. Test LLM Connectivity & Pipeline Health
    print("\n4️⃣  Testing LLM Pipeline Health...")
    try:
        from backend.services.llm.pipeline import DualModelAnalyzer
        analyzer = DualModelAnalyzer()
        health = await analyzer.check_health()
        print(f"   - Generation Model: {health['generation']}")
        print(f"   - Review Model: {health['review']}")
    except Exception as e:
        print(f"   ❌ Health Check Failed: {e}")

    api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
    if api_key:
        print(f"   ✅ API Key present ({api_key[:5]}...)")
    else:
        print("   ❌ API Key MISSING")

    print("\n✅ E2E Tests Complete!")

if __name__ == "__main__":
    asyncio.run(run_tests())
