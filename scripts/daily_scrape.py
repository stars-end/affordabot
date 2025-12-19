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
from db.postgres_client import PostgresDB

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("daily_scrape")

# Concurrency Limit
SEM = asyncio.Semaphore(3)

class ScrapeJob:
    def __init__(self, db: PostgresDB):
        self.db = db

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def run_one(self, slug: str, scraper_class, jur_type: str):
        task_id = str(uuid4())
        
        # Lazy Import Ingestion Dependencies to avoid circular imports at top level if any
        from services.ingestion_service import IngestionService
        from services.vector_backend_factory import create_vector_backend
        from llm_common.embeddings.openai import OpenAIEmbeddingService
        from services.storage.s3_storage import S3Storage
        # from llm_common.embeddings.mock import MockEmbeddingService # Removed broken import
        
        # Initialize Storage
        s3_storage = S3Storage()

        # Initialize Ingestion
        # Note: EmbeddingService relies on env vars (OPENAI_API_KEY or OPENROUTER_API_KEY)
        if os.environ.get("OPENAI_API_KEY") or os.environ.get("OPENROUTER_API_KEY"):
            embedding_service = OpenAIEmbeddingService(
                base_url="https://openrouter.ai/api/v1",
                api_key=os.environ.get("OPENROUTER_API_KEY"),
                model="qwen/qwen3-embedding-8b",
                dimensions=1536 # Was 4096. Assuming local DB is 1536. Qwen supports truncation or we risk mismatch.
                # If verified mismatch with Qwen, we must update DB schema or model choice.
            )
        else:
            # Inline Mock if llm-common missing it
            class MockEmbeddingService:
                async def embed_query(self, text: str) -> list[float]:
                    return [0.1] * 1536
                async def embed_documents(self, texts: list[str]) -> list[list[float]]:
                    return [[0.1] * 1536 for _ in texts]
            embedding_service = MockEmbeddingService()
        
        # Create embedding function for vector backend
        async def embed_fn(text: str) -> list[float]:
            return await embedding_service.embed_query(text)
        
        # Create vector backend (feature flag controlled)
        vector_backend = create_vector_backend(
            postgres_client=self.db,
            embedding_fn=embed_fn
        )
        ingestion_service = IngestionService(
            postgres_client=self.db,
            vector_backend=vector_backend,
            embedding_service=embedding_service,
            storage_backend=s3_storage
        )
        
        async with SEM:
            try:
                logger.info(f"[{slug}] Starting scrape (Task {task_id})")
                
                # 1. Create Admin Task
                await self.db.create_admin_task(
                    task_id=task_id,
                    task_type='scrape',
                    jurisdiction=slug,
                    status='running'
                )

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
                        # RAG: Store Raw Scrape and Trigger Ingestion (v2.1)
                        scrape_id = await self.db.create_raw_scrape(scrape_record)
                        if scrape_id and ingestion_service:
                             await ingestion_service.process_raw_scrape(scrape_id)
                             ingested_count += 1
                    except Exception as e:
                        logger.warning(f"Failed to record raw scrape for {bill.bill_number}: {e}")

                # 4. Log Success
                logger.info(f"[{slug}] Success: {len(bills)} bills ({new_count} new, {ingested_count} ingested)")
                
                await self.db.update_admin_task(
                    task_id=task_id,
                    status='completed',
                    result={'found': len(bills), 'new': new_count, 'ingested': ingested_count}
                )
                    
                await self.db.log_scrape_history({
                    'jurisdiction': slug,
                    'bills_found': len(bills),
                    'bills_new': new_count,
                    'status': 'success',
                    'task_id': task_id,
                    'notes': f"Ingested {ingested_count} into RAG (Disabled)"
                })
                    
                return {"slug": slug, "status": "success", "count": len(bills)}

            except Exception as e:
                logger.error(f"[{slug}] Failed: {e}")
                # DB Log
                await self.db.update_admin_task(task_id, 'failed', error=str(e))
                
                await self.db.log_scrape_history({
                    'jurisdiction': slug,
                    'status': 'failed',
                    'error_message': str(e),
                    'task_id': task_id
                })
                raise # Re-raise for tenacity

async def main():
    logger.info("🚀 Starting Daily Scrape Cron")
    
    # Load Env (Required for DB connection)
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), '../backend/.env'))
    
    db = PostgresDB()
    await db.connect() # Ensure pool creation
    job = ScrapeJob(db)
    
    tasks = []
    # v2.1 Pilot: Hardcode San Jose for E2E Verification
    # Original: for slug, (cls, jtype) in SCRAPERS.items():
    sanjose_pilot = {k: v for k, v in SCRAPERS.items() if k == "san-jose"}
    
    if not sanjose_pilot:
        logger.error("San Jose scraper not found in registry!")
        sys.exit(1)

    for slug, (cls, jtype) in sanjose_pilot.items():
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
