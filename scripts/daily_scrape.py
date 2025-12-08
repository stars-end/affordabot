#!/usr/bin/env python3
"""
Daily Scrape Cron Job
Runs all configured scrapers with concurrency control, retries, and DB logging.
"""

import asyncio
import sys
import os
import logging
from datetime import datetime
from uuid import uuid4
from tenacity import retry, stop_after_attempt, wait_exponential

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../backend'))

from services.scraper.registry import SCRAPERS
from db.supabase_client import SupabaseDB

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("daily_scrape")

# Concurrency Limit
SEM = asyncio.Semaphore(3)

class ScrapeJob:
    def __init__(self, db: SupabaseDB):
        self.db = db

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def run_one(self, slug: str, scraper_class, jur_type: str):
        task_id = str(uuid4())
        
        async with SEM:
            try:
                logger.info(f"[{slug}] Starting scrape (Task {task_id})")
                
                # 1. Create Admin Task
                if self.db.client:
                    self.db.client.table('admin_tasks').insert({
                        'id': task_id,
                        'task_type': 'scrape',
                        'jurisdiction': slug,
                        'status': 'running',
                        'created_at': datetime.now().isoformat()
                    }).execute()

                # 2. Run Scraper
                scraper = scraper_class()
                bills = await scraper.scrape()
                
                # 3. Store
                # Get/Create Jurisdiction
                jur_id = await self.db.get_or_create_jurisdiction(scraper.jurisdiction_name, jur_type)
                
                new_count = 0
                updated_count = 0
                
                for bill in bills:
                    # Note: store_legislation usually returns ID if created/updated, None if error or ignored
                    # Simplified logic here
                    if await self.db.store_legislation(jur_id, bill.dict()):
                        new_count += 1
                
                # 4. Log Success
                logger.info(f"[{slug}] Success: {len(bills)} bills ({new_count} processed)")
                
                if self.db.client:
                    self.db.client.table('admin_tasks').update({
                        'status': 'completed',
                        'completed_at': datetime.now().isoformat(),
                        'result': {'found': len(bills), 'new': new_count}
                    }).eq('id', task_id).execute()
                    
                    self.db.client.table('scrape_history').insert({
                        'jurisdiction': slug,
                        'bills_found': len(bills),
                        'bills_new': new_count,
                        'status': 'success',
                        'task_id': task_id
                    }).execute()
                    
                return {"slug": slug, "status": "success", "count": len(bills)}

            except Exception as e:
                logger.error(f"[{slug}] Failed: {e}")
                # DB Log
                if self.db.client:
                    self.db.client.table('admin_tasks').update({
                        'status': 'failed',
                        'completed_at': datetime.now().isoformat(),
                        'error_message': str(e)
                    }).eq('id', task_id).execute()
                    
                    self.db.client.table('scrape_history').insert({
                        'jurisdiction': slug,
                        'bills_found': 0,
                        'status': 'failed',
                        'error_message': str(e),
                        'task_id': task_id
                    }).execute()
                raise # Re-raise for tenacity

async def main():
    logger.info("🚀 Starting Daily Scrape Cron")
    
    # Load Env (Required for SupabaseDB)
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), '../backend/.env'))
    
    db = SupabaseDB()
    job = ScrapeJob(db)
    
    tasks = []
    for slug, (cls, jtype) in SCRAPERS.items():
        tasks.append(job.run_one(slug, cls, jtype))
        
    # Run all
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Report
    success = 0
    failed = 0
    for r in results:
        if isinstance(r, Exception):
            failed += 1
            logger.error(f"Final Failure: {r}")
        else:
            success += 1
            
    logger.info(f"🏁 Done. Success: {success}, Failed: {failed}")
    
    if failed > 0:
        sys.exit(1) # Signal failure to Cron runner

if __name__ == "__main__":
    asyncio.run(main())
