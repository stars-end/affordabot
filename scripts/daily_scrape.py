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
        
        # Lazy Import Ingestion Dependencies to avoid circular imports at top level if any
        from services.ingestion_service import IngestionService
        from llm_common.retrieval import SupabasePgVectorBackend
        from llm_common.embeddings.openai import OpenAIEmbeddingService
        from llm_common.embeddings.mock import MockEmbeddingService
        
        # Initialize Ingestion
        # Note: EmbeddingService relies on env vars (OPENAI_API_KEY or ZAI_API_KEY)
        if os.environ.get("OPENAI_API_KEY"):
            embedding_service = OpenAIEmbeddingService()
        else:
            embedding_service = MockEmbeddingService()
        vector_backend = SupabasePgVectorBackend(
            supabase_client=self.db.client,
            table="documents"
        )
        ingestion_service = IngestionService(
            supabase_client=self.db.client,
            vector_backend=vector_backend,
            embedding_service=embedding_service
        )
        
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
                
                # Ensure Source exists for this API scraper
                source_name = f"{slug} API"
                source_url = f"https://webapi.legistar.com/v1/{slug}/matters"
                source_id = await self.db.get_or_create_source(jur_id, source_name, "legislation_api", url=source_url)
                
                new_count = 0
                updated_count = 0
                ingested_count = 0
                
                for bill in bills:
                    # A. Store in SQL (Legislation Table)
                    if await self.db.store_legislation(jur_id, bill.dict()):
                        new_count += 1
                    
                    # B. Store in Vector DB (RAG Pipeline)
                    # Create raw_scrape record
                    import hashlib
                    import json
                    
                    bill_text = f"Title: {bill.title}\nStatus: {bill.status}\n\n{bill.text}"
                    content_hash = hashlib.sha256(bill_text.encode("utf-8")).hexdigest()
                    
                    # Check if we already ingested this exact text hash? 
                    # For now, simplistic insert. IngestionService can handle idempotency or we let it churn.
                    
                    scrape_record = {
                        "source_id": source_id,
                        "content_hash": content_hash,
                        "content_type": "text/plain",
                        "data": {"content": bill_text, "bill_number": bill.bill_number},
                        "url": f"api://{slug}/{bill.bill_number}",
                        "metadata": {"harvester": "daily_scrape_api", "bill_number": bill.bill_number}
                    }
                    
                    try:
                        res = self.db.client.table("raw_scrapes").insert(scrape_record).execute()
                        if res.data:
                            scrape_id = res.data[0]['id']
                            # Trigger Ingestion
                            chunks = await ingestion_service.process_raw_scrape(scrape_id)
                            if chunks > 0:
                                ingested_count += 1
                    except Exception as e:
                        logger.warning(f"Failed to ingest bill {bill.bill_number}: {e}")

                # 4. Log Success
                logger.info(f"[{slug}] Success: {len(bills)} bills ({new_count} new, {ingested_count} ingested)")
                
                if self.db.client:
                    self.db.client.table('admin_tasks').update({
                        'status': 'completed',
                        'completed_at': datetime.now().isoformat(),
                        'result': {'found': len(bills), 'new': new_count, 'ingested': ingested_count}
                    }).eq('id', task_id).execute()
                    
                    self.db.client.table('scrape_history').insert({
                        'jurisdiction': slug,
                        'bills_found': len(bills),
                        'bills_new': new_count,
                        'status': 'success',
                        'task_id': task_id,
                        'notes': f"Ingested {ingested_count} into RAG"
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
