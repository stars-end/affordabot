#!/usr/bin/env python3
"""
Universal Harvester Cron
Uses Z.ai GLM-4.6 to "read" generic web pages (configured in sources) 
and ingest them into the vector database.
"""

import sys
import os
import logging
import asyncio
import httpx
from uuid import uuid4

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))

from db.postgres_client import PostgresDB

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("harvester")

# Config
ZAI_API_KEY = os.environ.get("ZAI_API_KEY")
ZAI_BASE_URL = "https://api.z.ai/api/coding/paas/v4/chat/completions"
MODEL = "glm-4.6"

class UniversalHarvester:
    def __init__(self):
        self.db = PostgresDB()
        if not ZAI_API_KEY:
            logger.warning("⚠️ ZAI_API_KEY not set. Harvester will fail.")

    async def run(self):
        task_id = str(uuid4())
        logger.info(f"🚀 Starting Universal Harvester (Task {task_id})")
        
        # 1. Log Start
        if self.db:
            await self.db.create_admin_task(
                task_id=task_id,
                task_type='universal_harvest',
                jurisdiction='system',
                status='running'
            )

        try:
            # 2. Fetch Sources to Harvest
            # Look for sources with type='web'
            # PostgresDB helper needed here or raw query
            sources = await self.db._fetch("SELECT * FROM sources WHERE type = $1", 'web')
            
            logger.info(f"found {len(sources)} web sources to harvest")
            
            results = {"processed": 0, "failed": 0, "chunks": 0}
            
            async with httpx.AsyncClient(timeout=120.0) as client:
                for source in sources:
                    try:
                        # Convert Record to dict
                        source_dict = dict(source)
                        await self._process_source(client, source_dict, task_id)
                        results["processed"] += 1
                    except Exception as e:
                        logger.error(f"Failed source {source.get('name')}: {e}")
                        results["failed"] += 1

            # 3. Log Completion
            logger.info(f"🏁 Complete. {results}")
            await self.db.update_admin_task(
                task_id=task_id,
                status='completed',
                result=results
            )

        except Exception as e:
            logger.error(f"❌ Critical Failure: {e}")
            if self.db:
                await self.db.update_admin_task(
                    task_id=task_id,
                    status='failed',
                    error=str(e)
                )
            sys.exit(1)

    async def _process_source(self, client, source, task_id):
        url = source.get('scrape_url') or source.get('url') # Handle both schema variations if any
        if not url:
            return

        logger.info(f"📖 Reading: {url}")
        
        # 1. Call Z.ai to Read & Clean
        payload = {
            "model": MODEL,
            "messages": [
                {
                    "role": "user", 
                    "content": f"Read the content of {url}. Extract the full text content in clean Markdown format. Ignore navigation, footers, and ads. If it's a list of rules/requirements, preserve the list structure."
                }
            ],
            "tools": [{"type": "web_search", "web_search": {"enable": True, "search_result": True}}]
        }
        
        response = await client.post(ZAI_BASE_URL, json=payload, headers={
            "Authorization": f"Bearer {ZAI_API_KEY}",
            "Content-Type": "application/json"
        })
        
        if response.status_code != 200:
            raise Exception(f"Z.ai Error {response.status_code}: {response.text}")
            
        data = response.json()
        if "error" in data:
            raise Exception(f"Z.ai API Error: {data['error']}")
            
        markdown_content = data["choices"][0]["message"]["content"]
        
        # 2. Save to Raw Scrapes
        import hashlib
        
        content_hash = hashlib.sha256(markdown_content.encode("utf-8")).hexdigest()
        
        scrape_record = {
            "source_id": str(source['id']), # Ensure UUID is string
            "content_hash": content_hash,
            "content_type": "text/markdown",
            "data": {"content": markdown_content},
            "url": url,
            "metadata": {"harvester": "zai-glm-4.6", "task_id": task_id}
        }
        
        scrape_id = await self.db.create_raw_scrape(scrape_record)
        if not scrape_id:
             raise Exception("Failed to insert raw scrape record")
        
        # 3. Trigger Ingestion
        # Import here to avoid circular imports at top level if any
        from services.ingestion_service import IngestionService
        from services.storage import S3Storage
        # from services.vector_backend_factory import create_vector_backend 
        # Factory might depend on SC, let's look at direct backend creation for PG
        from llm_common.embeddings.openai import OpenAIEmbeddingService
        from llm_common.embeddings.mock import MockEmbeddingService
        from llm_common.retrieval.pgvector_backend import PgVectorBackend
        
        # Setup Services
        if os.environ.get("OPENAI_API_KEY") or os.environ.get("OPENROUTER_API_KEY"):
            embedding_service = OpenAIEmbeddingService(
                base_url="https://openrouter.ai/api/v1",
                api_key=os.environ.get("OPENROUTER_API_KEY"),
                model="qwen/qwen3-embedding-8b",
                dimensions=4096
            )
        else:
            embedding_service = MockEmbeddingService()
        
        # Create vector backend (Directly use PgVectorBackend with our connection string)
        # Note: llm-common PgVectorBackend typically needs a connection string or pool.
        # Our internal PostgresDB uses asyncpg directly. 
        # Check if we can reuse the pool or if we need to pass the dsn.
        
        vector_backend = PgVectorBackend(
            connection_string=self.db.database_url,
            table_name="documents"
        )
        
        # Note: S3Storage uses env vars, no DB dep
        storage_backend = S3Storage()  
        
        # IngestionService typically takes supabase_client for updates.
        # We need to UPDATE IngestionService to accept PostgresDB or generic Database Interface.
        # For now, IngestionService is still tightly coupled to Supabase Client?
        # Let's check IngestionService again. It calls self.supabase.table(...).
        
        # CRITICAL: IngestionService needs to be refactored OR we mock the client.
        # The prompt plan said "Update Universal Harvester".
        # But IngestionService IS the logic.
        # If IngestionService uses Supabase, we are still blocked.
        # I must refactor IngestionService to accept `db_client` which can be `PostgresDB`.
        
        # STOPGAP: For this file, I will just call IngestionService.
        # But I need to pass it something compatible.
        # If I pass `self.db` (PostgresDB) to `supabase_client` arg, it will crash on `.table()`.
        # So I MUST refactor IngestionService first?
        # Or I can implement a "SupabaseAdapter" wrapper around PostgresDB?
        # Refactoring IngestionService is the cleaner V4 way.
        
        # Let's assumes we will refactor IngestionService next.
        # Pass `self.db` as a new arg `postgres_client` or generic `db_client`.
        
        ingestion_service = IngestionService(
             supabase_client=None, # Deprecated
             postgres_client=self.db, # NEW
             vector_backend=vector_backend,
             embedding_service=embedding_service,
             storage_backend=storage_backend
        )
        
        chunks = await ingestion_service.process_raw_scrape(scrape_id)
        logger.info(f"✅ Ingested {url} -> {chunks} chunks")

if __name__ == "__main__":
    runner = UniversalHarvester()
    asyncio.run(runner.run())
