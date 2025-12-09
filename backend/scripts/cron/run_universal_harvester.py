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
from datetime import datetime
from uuid import uuid4

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))

from db.supabase_client import SupabaseDB

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("harvester")

# Config
ZAI_API_KEY = os.environ.get("ZAI_API_KEY")
ZAI_BASE_URL = "https://api.z.ai/api/coding/paas/v4/chat/completions"
MODEL = "glm-4.6"

class UniversalHarvester:
    def __init__(self):
        self.db = SupabaseDB()
        if not ZAI_API_KEY:
            logger.warning("⚠️ ZAI_API_KEY not set. Harvester will fail.")

    async def run(self):
        task_id = str(uuid4())
        logger.info(f"🚀 Starting Universal Harvester (Task {task_id})")
        
        # 1. Log Start
        if self.db.client:
            self.db.client.table('admin_tasks').insert({
                'id': task_id,
                'task_type': 'universal_harvest',
                'status': 'running',
                'created_at': datetime.now().isoformat()
            }).execute()

        try:
            # 2. Fetch Sources to Harvest
            # Look for sources with type='web'
            sources = self.db.client.table('sources').select('*').eq('type', 'web').execute().data
            
            logger.info(f"found {len(sources)} web sources to harvest")
            
            results = {"processed": 0, "failed": 0, "chunks": 0}
            
            async with httpx.AsyncClient(timeout=120.0) as client:
                for source in sources:
                    try:
                        await self._process_source(client, source, task_id)
                        results["processed"] += 1
                    except Exception as e:
                        logger.error(f"Failed source {source.get('name')}: {e}")
                        results["failed"] += 1

            # 3. Log Completion
            logger.info(f"🏁 Complete. {results}")
            self.db.client.table('admin_tasks').update({
                'status': 'completed',
                'completed_at': datetime.now().isoformat(),
                'result': results
            }).eq('id', task_id).execute()

        except Exception as e:
            logger.error(f"❌ Critical Failure: {e}")
            self.db.client.table('admin_tasks').update({
                'status': 'failed',
                'completed_at': datetime.now().isoformat(),
                'error_message': str(e)
            }).eq('id', task_id).execute()
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
        import json
        
        content_hash = hashlib.sha256(markdown_content.encode("utf-8")).hexdigest()
        
        scrape_record = {
            "source_id": source['id'],
            "content_hash": content_hash,
            "content_type": "text/markdown",
            "data": {"content": markdown_content},
            "url": url,
            "metadata": {"harvester": "zai-glm-4.6", "task_id": task_id}
        }
        
        # Check duplicate hash to avoid re-ingesting identical content
        # (Optional optimization, skipping for now to ensure update)
        
        res = self.db.client.table("raw_scrapes").insert(scrape_record).execute()
        scrape_id = res.data[0]['id']
        
        # 3. Trigger Ingestion
        # Import here to avoid circular imports at top level if any
        from services.ingestion_service import IngestionService
        from llm_common.retrieval import SupabasePgVectorBackend
        from llm_common.embeddings.openai import OpenAIEmbeddingService
        from llm_common.embeddings.mock import MockEmbeddingService
        
        # Setup Services
        # Note: EmbeddingService needs API key. Assuming env var OPENAI_API_KEY is set or handled.
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
        
        chunks = await ingestion_service.process_raw_scrape(scrape_id)
        logger.info(f"✅ Ingested {url} -> {chunks} chunks")

if __name__ == "__main__":
    runner = UniversalHarvester()
    asyncio.run(runner.run())
