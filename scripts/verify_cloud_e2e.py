"""
Cloud End-to-End Verification Script for Railway.
Intended to be run via `railway run python scripts/verify_cloud_e2e.py` or as a post-deploy check.
"""

import asyncio
import sys
import os
import logging

# Ensure backend is in path
# Find the absolute path to the 'backend' directory
# Assuming script is in scripts/verify_cloud_e2e.py
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
backend_path = os.path.join(project_root, 'backend')
sys.path.append(backend_path)

print(f"DEBUG: Added {backend_path} to sys.path")
print(f"DEBUG: sys.path: {sys.path}")

from services.extractors.playwright_extractor import PlaywrightExtractor
from services.storage.supabase_storage import SupabaseBlobStorage
from supabase import create_client

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def verify_playwright():
    """Verify Playwright can launch a browser and fetch content."""
    logger.info("🧪 Testing Playwright Isolation...")
    extractor = PlaywrightExtractor()
    try:
        # Test 1: Simple headless fetch
        result = await extractor.fetch_raw_content("https://example.com")
        if "Example Domain" in result:
             logger.info("✅ Playwright Fetched Content (Length: %d)", len(result))
             return True
        else:
             logger.error("❌ Playwright fetched unexpected content")
             return False
    except Exception as e:
        logger.error(f"❌ Playwright Failed: {e}")
        return False

async def verify_storage():
    """Verify we can upload to Supabase Storage."""
    logger.info("🧪 Testing Storage Upload...")
    
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY")
    
    if not url or not key:
        logger.error("❌ Missing Supabase Credentials (SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY)")
        return False
        
    try:
        client = create_client(url, key)
        
        # Bootstrap: Ensure bucket exists
        try:
            buckets = client.storage.list_buckets()
            bucket_names = [b.name for b in buckets]
            if "raw_scrapes" not in bucket_names:
                logger.info("🔧 Creating 'raw_scrapes' bucket...")
                client.storage.create_bucket("raw_scrapes", options={"public": False})
        except Exception as e:
            logger.warning(f"⚠️ Bucket check/creation failed (might exist): {e}")

        storage = SupabaseBlobStorage(client)
        
        test_content = b"Cloud Verification Test Content"
        path = f"verification/cloud_test_{os.urandom(4).hex()}.txt"
        
        uri = await storage.upload(path, test_content)
        logger.info(f"✅ Uploaded to: {uri}")
        return True
    
    except Exception as e:
         logger.error(f"❌ Storage Upload Failed: {e}")
         return False

async def main():
    logger.info("🚀 Starting Railway Cloud Verification")
    
    playwright_ok = await verify_playwright()
    storage_ok = await verify_storage()
    
    if playwright_ok and storage_ok:
        logger.info("🎉 All Cloud Checks Passed")
        sys.exit(0)
    else:
        logger.error("🔥 Cloud Checks Failed")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
