import asyncio
import httpx
import sys
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

BASE_URL = "http://localhost:8000"

async def verify_cron_scrape():
    logger.info("🧪 Verifying Cron Scrape Endpoint...")
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Trigger daily scrape (background task)
        resp = await client.post(f"{BASE_URL}/cron/daily-scrape")
        if resp.status_code != 200:
            logger.error(f"❌ Cron scrape failed: {resp.text}")
            return False
        
        data = resp.json()
        if data["status"] != "success":
             logger.error(f"❌ Cron scrape status not success: {data}")
             return False
        
        logger.info("✅ Cron scrape triggered successfully.")
        return True

async def verify_nyc_scrape():
    logger.info("🧪 Verifying NYC Scraper (Jules Dispatch)...")
    async with httpx.AsyncClient(timeout=60.0) as client:
        # Trigger specific scrape
        resp = await client.post(f"{BASE_URL}/scrape/nyc")
        if resp.status_code != 200:
             logger.error(f"❌ NYC scrape failed: {resp.text}")
             return False
        
        data = resp.json()
        if "processed" not in data or data["processed"] == 0:
             logger.error(f"❌ NYC scrape processed 0 bills: {data}")
             return False
        
        logger.info(f"✅ NYC Scraper processed {data['processed']} bills.")
        return True

async def verify_glass_box():
    logger.info("🧪 Verifying Glass Box (Admin Traces)...")
    async with httpx.AsyncClient(timeout=10.0) as client:
        # List sessions
        resp = await client.get(f"{BASE_URL}/admin/traces")
        if resp.status_code != 200:
             logger.error(f"❌ Admin traces list failed: {resp.text}")
             return False
             
        sessions = resp.json()
        logger.info(f"✅ Found {len(sessions)} agent sessions.")
        
        # If sessions exist, verify we can fetch details
        if sessions:
            query_id = sessions[0]
            resp_trace = await client.get(f"{BASE_URL}/admin/traces/{query_id}")
            if resp_trace.status_code != 200:
                 logger.error(f"❌ Fetch trace details failed for {query_id}")
                 return False
            logger.info(f"✅ Fetched trace details for {query_id}")
            
        return True

async def main():
    logger.info("🚀 Starting MVP V2 Release Verification")
    
    # 1. Verify Cron
    if not await verify_cron_scrape():
        sys.exit(1)
        
    # 2. Verify New Scraper (NYC)
    if not await verify_nyc_scrape():
        sys.exit(1)
        
    # 3. Verify Glass Box
    if not await verify_glass_box():
        sys.exit(1)
        
    logger.info("✨ ALL SYSTEMS GREEN (Release Verified)")

if __name__ == "__main__":
    asyncio.run(main())
