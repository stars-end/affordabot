
import sys
import os

# Emulate run_rag_spiders.py path setup
sys.path.append(os.path.join(os.getcwd())) # backend

print(f"sys.path: {sys.path}")

try:
    print("Attempting import from affordabot_scraper.affordabot_scraper.spiders...")
    from affordabot_scraper.affordabot_scraper.spiders.sanjose_meetings import SanJoseMeetingsSpider
    print("✅ Success 1")
except ImportError as e:
    print(f"❌ Failed 1: {e}")

try:
    # Try adding outer to path
    sys.path.append(os.path.join(os.getcwd(), 'affordabot_scraper'))
    print("Attempting import from affordabot_scraper.spiders (shimmed path)...")
    from affordabot_scraper.spiders.sanjose_meetings import SanJoseMeetingsSpider
    print("✅ Success 2")
except ImportError as e:
    print(f"❌ Failed 2: {e}")
