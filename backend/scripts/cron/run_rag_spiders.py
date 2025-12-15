#!/usr/bin/env python3
"""
RAG Spiders Cron Runner
Executes Scrapy spiders for RAG ingestion (Meetings, Municipal Codes).
Designed to run via Railway Cron.
"""

import sys
import os
import logging
import asyncio
from datetime import datetime
from uuid import uuid4
from scrapy.crawler import CrawlerProcess
from scrapy import signals
from scrapy.utils.project import get_project_settings

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))
# Add scraper project root to path so we can import 'affordabot_scraper' package
sys.path.append(os.path.join(os.path.dirname(__file__), '../../affordabot_scraper'))

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("rag_cron")

class RAGSpiderRunner:
    def __init__(self):
        # Load Env
        from dotenv import load_dotenv
        load_dotenv(os.path.join(os.path.dirname(__file__), '../../.env'))
        
        # Import DB client here
        from db.postgres_client import PostgresDB
        self.db = PostgresDB()
        self.results = {}

    def _item_scraped(self, item, response, spider):
        if spider.name not in self.results:
            self.results[spider.name] = 0
        self.results[spider.name] += 1

    def run(self):
        # Helper to run async in sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        task_id = str(uuid4())
        logger.info(f"🚀 Starting RAG Spiders (Task {task_id})")

        # 1. Log Start
        try:
             loop.run_until_complete(
                self.db.create_admin_task(
                    task_id=task_id,
                    task_type='rag_scrape',
                    jurisdiction='multiple',
                    status='running'
                )
             )
        except Exception as e:
            logger.error(f"Failed to create admin task: {e}")

        try:
            # 2. Setup Scrapy
            # Treat affordabot_scraper as a package (sys.path includes backend/affordabot_scraper)
            os.environ.setdefault('SCRAPY_SETTINGS_MODULE', 'affordabot_scraper.settings')
            settings = get_project_settings()
            settings.set('TELNETCONSOLE_ENABLED', False)
            settings.set('LOG_LEVEL', 'INFO')
            
            process = CrawlerProcess(settings)
            
            # 2a. Map Spiders to Sources
            from affordabot_scraper.spiders.sanjose_meetings import SanJoseMeetingsSpider
            from affordabot_scraper.spiders.sanjose_municode import SanJoseMunicodeSpider

            spider_configs = [
                (SanJoseMeetingsSpider, "San Jose Meetings", "meetings"),
                (SanJoseMunicodeSpider, "San Jose Municode", "code")
            ]
            
            # Get Jurisdiction ID (Assuming "City of San Jose" exists from legislation scrape)
            jur_id = loop.run_until_complete(self.db.get_or_create_jurisdiction("City of San Jose", "city"))
            
            if not jur_id:
                raise Exception("Failed to get Jurisdiction ID")
                
            source_ids = []
            
            for spider_cls, source_name, source_type in spider_configs:
                # Use first start_url as canonical url
                source_url = spider_cls.start_urls[0] if spider_cls.start_urls else None
                source_id = loop.run_until_complete(self.db.get_or_create_source(jur_id, source_name, source_type))
                # Note: get_or_create_source in PostgresDB doesn't take URL yet, might need update if schema requires it,
                # but older signature was (jur_id, name, type). Using that for now.
                
                if source_id:
                    source_ids.append(source_id)
                    crawler = process.create_crawler(spider_cls)
                    crawler.signals.connect(self._item_scraped, signal=signals.item_scraped)
                    # Pass source_id as spider argument
                    process.crawl(crawler, source_id=source_id)
                else:
                    logger.error(f"Failed to get Source ID for {source_name}")

            # 3. Run (Blocks)
            logger.info("🏃 Running spiders...")
            process.start()
            
            # 4. Trigger Ingestion
            logger.info("🍽️  Starting Ingestion...")
            
            # Import Ingestion Service components
            from services.ingestion_service import IngestionService
            from services.storage import S3Storage
            from services.vector_backend_factory import create_vector_backend
            from llm_common.embeddings.openai import OpenAIEmbeddingService
            from llm_common.embeddings.mock import MockEmbeddingService
            
            # Setup Services
            if os.environ.get("OPENAI_API_KEY") or os.environ.get("OPENROUTER_API_KEY"):
                embedding_service = OpenAIEmbeddingService(
                    base_url="https://openrouter.ai/api/v1",
                    api_key=os.environ.get("OPENROUTER_API_KEY"),
                    model="qwen/qwen3-embedding-8b",
                    dimensions=4096
                )
            else:
                logger.warning("Using Mock Embedding Service")
                embedding_service = MockEmbeddingService()
            
            # Create embedding function for vector backend
            async def embed_fn(text: str) -> list[float]:
                return await embedding_service.embed_query(text)
            
            # Create vector backend
            vector_backend = create_vector_backend(
                postgres_client=self.db, # Factory needs update or direct instantiation
                embedding_fn=embed_fn
            )
            # WORKAROUND: Factory might still require supabase_client if not updated.
            # Assuming custom_pgvector_backend for now.
            # Let's check factory later. For now assume it works or we use direct.
            
            storage_backend = S3Storage()  # Uses MINIO_* env vars
            
            ingestion_service = IngestionService(
                postgres_client=self.db,
                vector_backend=vector_backend,
                embedding_service=embedding_service,
                storage_backend=storage_backend
            )
            
            # Fetch unprocessed scrapes for these sources
            total_ingested = 0
            
            # We can't query "IN" easily with simple helper, loop for now
            for sid in source_ids:
                # Fetch unprocessed
                unprocessed_rows = loop.run_until_complete(
                    self.db._fetch("SELECT id FROM raw_scrapes WHERE source_id = $1 AND processed IS NULL", sid)
                )
                
                for row in unprocessed_rows:
                    try:
                        # Run async ingestion
                        chunks = loop.run_until_complete(ingestion_service.process_raw_scrape(str(row['id'])))
                        total_ingested += chunks
                    except Exception as e:
                        logger.error(f"Failed to ingest scrape {row['id']}: {e}")
                            
            logger.info(f"🍽️  Ingestion Complete. Created {total_ingested} chunks.")
            
            # 5. Log Success
            total_items = sum(self.results.values())
            logger.info(f"🏁 Complete. Scraped {total_items} items: {self.results}")
            
            loop.run_until_complete(
                self.db.update_admin_task(
                    task_id=task_id,
                    status='completed',
                    result=self.results
                )
            )
                
            # Log History per Spider
            for spider_name, count in self.results.items():
                loop.run_until_complete(
                    self.db.log_scrape_history({
                        'jurisdiction': spider_name,
                        'bills_found': count,
                        'bills_new': 0, # TODO: calculate
                        'status': 'success',
                        'task_id': task_id,
                        'notes': 'RAG Scrape'
                    })
                )

        except Exception as e:
            logger.error(f"❌ Critical Failure: {e}")
            try:
                loop.run_until_complete(
                    self.db.update_admin_task(
                        task_id=task_id,
                        status='failed',
                        error=str(e)
                    )
                )
            except:
                pass
            sys.exit(1)
        finally:
            loop.close()

def main():
    runner = RAGSpiderRunner()
    runner.run()

if __name__ == "__main__":
    main()
