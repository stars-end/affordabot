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

from db.supabase_client import SupabaseDB
from affordabot_scraper.affordabot_scraper.spiders.sanjose_meetings import SanJoseMeetingsSpider
from affordabot_scraper.affordabot_scraper.spiders.sanjose_municode import SanJoseMunicodeSpider

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("rag_cron")

class RAGSpiderRunner:
    def __init__(self):
        # Load Env
        from dotenv import load_dotenv
        load_dotenv(os.path.join(os.path.dirname(__file__), '../../.env'))
        
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
            os.environ.setdefault('SCRAPY_SETTINGS_MODULE', 'affordabot_scraper.affordabot_scraper.settings')
            settings = get_project_settings()
            settings.set('TELNETCONSOLE_ENABLED', False)
            settings.set('LOG_LEVEL', 'INFO')
            
            process = CrawlerProcess(settings)
            
            spiders = [SanJoseMeetingsSpider, SanJoseMunicodeSpider]
            
            for spider_cls in spiders:
                crawler = process.create_crawler(spider_cls)
                # Connect signals to track items
                crawler.signals.connect(self._item_scraped, signal=signals.item_scraped)
                process.crawl(crawler)

            # 3. Run (Blocks)
            logger.info("🏃 Running spiders...")
            process.start()
            
            # 4. Log Success
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

if __name__ == "__main__":
    runner = RAGSpiderRunner()
    runner.run()
