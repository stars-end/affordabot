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

# Imports moved to inner scope to support testing
# from db.supabase_client import SupabaseDB
# from affordabot_scraper.spiders.sanjose_meetings import SanJoseMeetingsSpider
# from affordabot_scraper.spiders.sanjose_municode import SanJoseMunicodeSpider

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("rag_cron")

class RAGSpiderRunner:
    def __init__(self):
        # Load Env
        from dotenv import load_dotenv
        load_dotenv(os.path.join(os.path.dirname(__file__), '../../.env'))
        
        # Import DB client here
        from db.supabase_client import SupabaseDB
        self.db = SupabaseDB()
        self.results = {}

    def _item_scraped(self, item, response, spider):
        if spider.name not in self.results:
            self.results[spider.name] = 0
        self.results[spider.name] += 1

    def run(self):
        task_id = str(uuid4())
        logger.info(f"🚀 Starting RAG Spiders (Task {task_id})")

        # 1. Log Start
        if self.db.client:
            self.db.client.table('admin_tasks').insert({
                'id': task_id,
                'task_type': 'rag_scrape',
                'jurisdiction': 'multiple', # TODO: Split per spider if needed
                'status': 'running',
                'created_at': datetime.now().isoformat()
            }).execute()

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
            # If not, create it
            # Note: The async method run_rag_spiders call is synchronous, so we need to run async DB calls
            
            # Helper to run async in sync context
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            jur_id = loop.run_until_complete(self.db.get_or_create_jurisdiction("City of San Jose", "city"))
            
            if not jur_id:
                raise Exception("Failed to get Jurisdiction ID")
                
            source_ids = []
            
            for spider_cls, source_name, source_type in spider_configs:
                # Use first start_url as canonical url
                source_url = spider_cls.start_urls[0] if spider_cls.start_urls else None
                source_id = loop.run_until_complete(self.db.get_or_create_source(jur_id, source_name, source_type, url=source_url))
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
            # Note: EmbeddingService might need provider config. 
            # Assuming defaults or env vars (OPENAI_API_KEY)
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
            
            # Create vector backend (feature flag controlled)
            vector_backend = create_vector_backend(
                supabase_client=self.db.client,
                embedding_fn=embed_fn
            )
            
            # Create embedding function for vector backend
            async def embed_fn(text: str) -> list[float]:
                return await embedding_service.embed_query(text)
            
            # Create vector backend (feature flag controlled)
            vector_backend = create_vector_backend(
                supabase_client=self.db.client,
                embedding_fn=embed_fn
            )
            storage_backend = S3Storage()  # Uses MINIO_* env vars
            ingestion_service = IngestionService(
                supabase_client=self.db.client,
                vector_backend=vector_backend,
                embedding_service=embedding_service,
                storage_backend=storage_backend
            )
            
            # Fetch unprocessed scrapes for these sources
            total_ingested = 0
            
            if self.db.client:
                # We can't query "IN" easily with simple supabase-py syntax sometimes, loop for now
                for sid in source_ids:
                    # Fetch unprocessed
                    # Note: We should probably limit batch size
                    unprocessed = self.db.client.table('raw_scrapes').select('id')\
                        .eq('source_id', sid)\
                        .is_('processed', 'null')\
                        .execute()
                    
                    for row in unprocessed.data:
                        try:
                            # Run async ingestion
                            chunks = loop.run_until_complete(ingestion_service.process_raw_scrape(row['id']))
                            total_ingested += chunks
                        except Exception as e:
                            logger.error(f"Failed to ingest scrape {row['id']}: {e}")
                            
            logger.info(f"🍽️  Ingestion Complete. Created {total_ingested} chunks.")
            
            # 5. Log Success
            total_items = sum(self.results.values())
            logger.info(f"🏁 Complete. Scraped {total_items} items: {self.results}")
            
            if self.db.client:
                # Update Task
                self.db.client.table('admin_tasks').update({
                    'status': 'completed',
                    'completed_at': datetime.now().isoformat(),
                    'result': self.results
                }).eq('id', task_id).execute()
                
                # Log History per Spider
                for spider_name, count in self.results.items():
                    self.db.client.table('scrape_history').insert({
                        'jurisdiction': spider_name, # Use spider name as proxy for jurisdiction/source
                        'bills_found': count,
                        'status': 'success',
                        'task_id': task_id,
                        'notes': 'RAG Scrape'
                    }).execute()

        except Exception as e:
            logger.error(f"❌ Critical Failure: {e}")
            if self.db.client:
                self.db.client.table('admin_tasks').update({
                    'status': 'failed',
                    'completed_at': datetime.now().isoformat(),
                    'error_message': str(e)
                }).eq('id', task_id).execute()
            sys.exit(1)

def main():
    runner = RAGSpiderRunner()
    runner.run()

if __name__ == "__main__":
    main()
