#!/usr/bin/env python3
"""
Daily Scrape Cron Job
Runs the current pilot scrape workflow from the backend service scope.

Updated (bd-tytc.3):
- California bills use official legislature-linked text
- Jurisdiction/source identity is injected into raw-scrape and chunk metadata
- No silent truncation (removed bills[:3])
"""

import asyncio
import logging
import os
import sys
from pathlib import Path
from uuid import uuid4
import hashlib

from tenacity import retry, stop_after_attempt, wait_exponential

BACKEND_ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(BACKEND_ROOT))

from db.postgres_client import PostgresDB
from services.scraper.registry import SCRAPERS


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("daily_scrape")
SEM = asyncio.Semaphore(3)

PILOT_JURISDICTIONS = ["san-jose", "california"]
EMBEDDING_DIMENSIONS = 4096


class ScrapeJob:
    def __init__(self, db: PostgresDB):
        self.db = db

    @retry(
        stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def run_one(self, slug: str, scraper_class, jur_type: str):
        task_id = str(uuid4())

        from llm_common.embeddings.openai import OpenAIEmbeddingService
        from services.ingestion_service import IngestionService
        from services.storage.s3_storage import S3Storage
        from services.vector_backend_factory import create_vector_backend

        s3_storage = S3Storage()

        if os.environ.get("OPENROUTER_API_KEY"):
            embedding_service = OpenAIEmbeddingService(
                base_url="https://openrouter.ai/api/v1",
                api_key=os.environ.get("OPENROUTER_API_KEY"),
                model="qwen/qwen3-embedding-8b",
                dimensions=EMBEDDING_DIMENSIONS,
            )
        else:

            class MockEmbeddingService:
                async def embed_query(self, text: str) -> list[float]:
                    return [0.1] * EMBEDDING_DIMENSIONS

                async def embed_documents(self, texts: list[str]) -> list[list[float]]:
                    return [[0.1] * EMBEDDING_DIMENSIONS for _ in texts]

            embedding_service = MockEmbeddingService()

        async def embed_fn(text: str) -> list[float]:
            return await embedding_service.embed_query(text)

        vector_backend = create_vector_backend(
            postgres_client=self.db,
            embedding_fn=embed_fn,
        )
        ingestion_service = IngestionService(
            postgres_client=self.db,
            vector_backend=vector_backend,
            embedding_service=embedding_service,
            storage_backend=s3_storage,
        )

        async with SEM:
            try:
                logger.info(f"[{slug}] Starting scrape (Task {task_id})")
                await self.db.create_admin_task(
                    task_id=task_id,
                    task_type="scrape",
                    jurisdiction=slug,
                    status="running",
                )

                scraper = scraper_class()
                bills = await scraper.scrape()

                jur_id = await self.db.get_or_create_jurisdiction(
                    scraper.jurisdiction_name, jur_type
                )

                if slug == "california":
                    source_name = "California Legislature (OpenStates + leginfo)"
                    source_url = "https://leginfo.legislature.ca.gov"
                else:
                    source_name = f"{slug} API"
                    source_url = f"https://webapi.legistar.com/v1/{slug}/matters"

                source_id = await self.db.get_or_create_source(
                    jur_id,
                    source_name,
                    "legislation_api",
                    url=source_url,
                )

                new_count = 0
                ingested_count = 0
                skipped_placeholder = 0

                for bill in bills:
                    if await self.db.store_legislation(jur_id, bill.dict()):
                        new_count += 1

                    if slug == "california":
                        scrape_record = self._build_california_scrape_record(
                            bill, source_id, scraper
                        )
                        if not bill.text or len(bill.text) < 100:
                            skipped_placeholder += 1
                            logger.warning(
                                f"[{slug}] Skipping ingestion for {bill.bill_number}: "
                                f"insufficient bill text ({len(bill.text or '')} chars)"
                            )
                            continue
                    else:
                        scrape_record = self._build_generic_scrape_record(
                            bill, source_id, slug
                        )

                    try:
                        scrape_id = await self.db.create_raw_scrape(scrape_record)
                        if scrape_id:
                            await ingestion_service.process_raw_scrape(scrape_id)
                            ingested_count += 1
                    except Exception as exc:
                        logger.warning(
                            f"Failed to record raw scrape for {bill.bill_number}: {exc}"
                        )

                logger.info(
                    f"[{slug}] Success: {len(bills)} bills "
                    f"({new_count} new, {ingested_count} ingested, {skipped_placeholder} skipped)"
                )
                await self.db.update_admin_task(
                    task_id=task_id,
                    status="completed",
                    result={
                        "found": len(bills),
                        "new": new_count,
                        "ingested": ingested_count,
                        "skipped_placeholder": skipped_placeholder,
                    },
                )
                await self.db.log_scrape_history(
                    {
                        "jurisdiction": slug,
                        "bills_found": len(bills),
                        "bills_new": new_count,
                        "status": "success",
                        "task_id": task_id,
                        "notes": f"Ingested {ingested_count} into RAG",
                    }
                )
                return {"slug": slug, "status": "success", "count": len(bills)}
            except Exception as exc:
                logger.error(f"[{slug}] Failed: {exc}")
                await self.db.update_admin_task(task_id, "failed", error=str(exc))
                await self.db.log_scrape_history(
                    {
                        "jurisdiction": slug,
                        "status": "failed",
                        "error_message": str(exc),
                        "task_id": task_id,
                    }
                )
                raise

    def _build_california_scrape_record(self, bill, source_id: str, scraper) -> dict:
        """Build raw_scrape record for California bills with full provenance."""
        if hasattr(scraper, "to_raw_scrape_record"):
            return scraper.to_raw_scrape_record(bill, source_id)

        bill_text = bill.text or ""
        content_hash = hashlib.sha256(bill_text.encode("utf-8")).hexdigest()

        metadata = {
            "bill_number": bill.bill_number,
            "title": bill.title,
            "status": bill.status,
            "jurisdiction": "california",
            "source_system": "openstates+leginfo",
            "harvester": "daily_scrape_california",
        }

        if hasattr(bill, "provenance") and bill.provenance:
            metadata["source_url"] = bill.provenance.source_url
            metadata["source_type"] = bill.provenance.source_type
            metadata["extraction_status"] = bill.provenance.extraction_status

        return {
            "source_id": source_id,
            "url": getattr(bill.provenance, "source_url", None)
            if hasattr(bill, "provenance")
            else f"california://{bill.bill_number}",
            "content_hash": content_hash,
            "content_type": "text/html",
            "data": {
                "content": bill_text,
                "bill_number": bill.bill_number,
                "title": bill.title,
                "status": bill.status,
            },
            "metadata": metadata,
        }

    def _build_generic_scrape_record(self, bill, source_id: str, slug: str) -> dict:
        """Build raw_scrape record for generic jurisdictions."""
        bill_text = f"Title: {bill.title}\nStatus: {bill.status}\n\n{bill.text}"
        content_hash = hashlib.sha256(bill_text.encode("utf-8")).hexdigest()

        return {
            "source_id": source_id,
            "content_hash": content_hash,
            "content_type": "text/plain",
            "data": {"content": bill_text, "bill_number": bill.bill_number},
            "url": f"api://{slug}/{bill.bill_number}",
            "metadata": {
                "harvester": "daily_scrape_api",
                "bill_number": bill.bill_number,
                "jurisdiction": slug,
            },
        }


async def main():
    logger.info("Starting Daily Scrape Cron")
    db = PostgresDB()
    await db.connect()
    job = ScrapeJob(db)

    pilot_scrapers = {k: v for k, v in SCRAPERS.items() if k in PILOT_JURISDICTIONS}
    if not pilot_scrapers:
        logger.error(f"No pilot scrapers found. Available: {list(SCRAPERS.keys())}")
        sys.exit(1)

    logger.info(f"Running pilot scrapers: {list(pilot_scrapers.keys())}")

    results = await asyncio.gather(
        *(
            job.run_one(slug, cls, jtype)
            for slug, (cls, jtype) in pilot_scrapers.items()
        ),
        return_exceptions=True,
    )

    failed = sum(1 for result in results if isinstance(result, Exception))
    success = len(results) - failed
    logger.info(f"Done. Success: {success}, Failed: {failed}")
    await db.close()

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
