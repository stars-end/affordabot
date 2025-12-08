#!/usr/bin/env python3
"""
RAG Spiders Cron Runner
Executes Scrapy spiders for RAG ingestion (Meetings, Municipal Codes).
Designed to run via Railway Cron.
"""

import sys
import os
import logging
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))

from affordabot_scraper.affordabot_scraper.spiders.sanjose_meetings import SanJoseMeetingsSpider
from affordabot_scraper.affordabot_scraper.spiders.sanjose_municode import SanJoseMunicodeSpider

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("rag_cron")

def main():
    logger.info("🚀 Starting RAG Spiders Cron")
    
    # Load Scrapy settings
    # We need to point to the scrapy.cfg or manually set settings
    # For now, we'll try to load standard settings and override
    os.environ.setdefault('SCRAPY_SETTINGS_MODULE', 'affordabot_scraper.affordabot_scraper.settings')
    
    try:
        settings = get_project_settings()
        
        # Override for Cron execution (headless, no telemetry)
        settings.set('TELNETCONSOLE_ENABLED', False)
        settings.set('LOG_LEVEL', 'INFO')
        
        process = CrawlerProcess(settings)
        
        # Add Spiders
        # 1. San Jose Meetings
        logger.info("🕷️ Scheduling: SanJoseMeetingsSpider")
        process.crawl(SanJoseMeetingsSpider)
        
        # 2. San Jose Municode
        logger.info("🕷️ Scheduling: SanJoseMunicodeSpider")
        process.crawl(SanJoseMunicodeSpider)
        
        # Run! (Blocks until all spiders finish)
        logger.info("🏃 Running spiders...")
        process.start()
        
        logger.info("🏁 RAG Spiders Complete")
        
    except Exception as e:
        logger.error(f"❌ Critical Failure: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
