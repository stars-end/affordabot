#!/usr/bin/env python3
"""
Universal Harvester Cron
Uses Z.ai GLM-4.7 to "read" generic web pages (configured in sources)
and ingest them into the vector database.

Updated (bd-owqm.1):
- Migrated onto framework-complete substrate metadata
- New rows now carry canonical_url, document_type, content_class, trust_tier,
  promotion_state, and ingestion_truth before downstream processing
"""

import sys
import os
import logging
import asyncio
import httpx
from uuid import uuid4

sys.path.append(os.path.join(os.path.dirname(__file__), "../../"))

from db.postgres_client import PostgresDB
from services.substrate_promotion import (
    apply_promotion_decision,
    evaluate_rules,
    seed_capture_promotion_metadata,
)
from scripts.cron.substrate_helpers import (
    build_substrate_metadata,
    build_raw_scrape_record,
    DOCUMENT_TYPE_WEB_REFERENCE,
    CAPTURE_METHOD_LLM_HARVEST,
    CONTENT_CLASS_PLAIN_TEXT,
)

# Logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("harvester")

# Config
ZAI_API_KEY = os.environ.get("ZAI_API_KEY")
ZAI_BASE_URL = "https://api.z.ai/api/coding/paas/v4/chat/completions"
MODEL = "glm-4.7"


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
                task_type="universal_harvest",
                jurisdiction="system",
                status="running",
            )

        try:
            # 2. Fetch Sources to Harvest
            # Look for sources with type='web'
            # PostgresDB helper needed here or raw query
            sources = await self.db._fetch(
                "SELECT * FROM sources WHERE type = $1", "web"
            )

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
                task_id=task_id, status="completed", result=results
            )

        except Exception as e:
            logger.error(f"❌ Critical Failure: {e}")
            if self.db:
                await self.db.update_admin_task(
                    task_id=task_id, status="failed", error=str(e)
                )
            sys.exit(1)

    async def _process_source(self, client, source, task_id):
        url = source.get("scrape_url") or source.get(
            "url"
        )  # Handle both schema variations if any
        if not url:
            return

        logger.info(f"📖 Reading: {url}")

        # 1. Call Z.ai to Read & Clean
        payload = {
            "model": MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": f"Read the content of {url}. Extract the full text content in clean Markdown format. Ignore navigation, footers, and ads. If it's a list of rules/requirements, preserve the list structure.",
                }
            ],
            "tools": [
                {
                    "type": "web_search",
                    "web_search": {"enable": True, "search_result": True},
                }
            ],
        }

        response = await client.post(
            ZAI_BASE_URL,
            json=payload,
            headers={
                "Authorization": f"Bearer {ZAI_API_KEY}",
                "Content-Type": "application/json",
            },
        )

        if response.status_code != 200:
            raise Exception(f"Z.ai Error {response.status_code}: {response.text}")

        data = response.json()
        if "error" in data:
            raise Exception(f"Z.ai API Error: {data['error']}")

        markdown_content = data["choices"][0]["message"]["content"]

        # 2. Save to Raw Scrapes with framework-complete substrate metadata
        base_metadata = build_substrate_metadata(
            canonical_url=url,
            document_type=DOCUMENT_TYPE_WEB_REFERENCE,
            trust_tier="non_official",
            capture_method=CAPTURE_METHOD_LLM_HARVEST,
            extra={
                "harvester": "zai-glm-4.7",
                "task_id": task_id,
                "source_name": source.get("name"),
            },
        )

        scrape_record = build_raw_scrape_record(
            source_id=str(source["id"]),
            canonical_url=url,
            content=markdown_content,
            content_type="text/markdown",
            metadata=base_metadata,
            extra_data={"content": markdown_content},
        )

        scrape_id = await self.db.create_raw_scrape(scrape_record)
        if not scrape_id:
            raise Exception("Failed to insert raw scrape record")

        # 3. Trigger Ingestion
        # Import here to avoid circular imports at top level if any
        from services.ingestion_service import IngestionService
        from services.storage import S3Storage
        from services.retrieval.local_pgvector import LocalPgVectorBackend
        from llm_common.embeddings.openai import OpenAIEmbeddingService
        from llm_common.embeddings import EmbeddingService

        if os.environ.get("OPENAI_API_KEY") or os.environ.get("OPENROUTER_API_KEY"):
            embedding_service: EmbeddingService = OpenAIEmbeddingService(
                base_url="https://openrouter.ai/api/v1",
                api_key=os.environ.get("OPENROUTER_API_KEY"),
                model="qwen/qwen3-embedding-8b",
                dimensions=4096,
            )
        else:
            logger.error(
                "No embedding API key configured; ingestion requires embeddings"
            )
            return

        vector_backend = LocalPgVectorBackend(
            table_name="document_chunks",
            postgres_client=self.db,
            embedding_fn=embedding_service.embed_query,
            fail_closed=True,
        )

        storage_backend = S3Storage()

        ingestion_service = IngestionService(
            postgres_client=self.db,
            vector_backend=vector_backend,
            embedding_service=embedding_service,
            storage_backend=storage_backend,
        )

        chunks = await ingestion_service.process_raw_scrape(scrape_id)
        logger.info(f"✅ Ingested {url} -> {chunks} chunks")


if __name__ == "__main__":
    runner = UniversalHarvester()
    asyncio.run(runner.run())
