from prefect import flow, task, get_run_logger
from services.ingestion_service import IngestionService
from services.llm.pipeline import DualModelAnalyzer
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings
import os
import asyncio

@task
def run_spider(spider_name: str):
    logger = get_run_logger()
    logger.info(f"Starting spider: {spider_name}")
    # Note: Scrapy inside Prefect requires careful process management (usually strictly separate processes)
    # For MVP V2, we might just shell out or assume single-process execution for now
    os.system(f"cd backend && poetry run bash -c 'cd affordabot_scraper && scrapy crawl {spider_name}'")
    logger.info(f"Finished spider: {spider_name}")
    return "s3://bucket/path"  # Mock return of artifact path

@task
async def run_pipeline(source_path: str):
    logger = get_run_logger()
    logger.info(f"Running ingestion pipeline for {source_path}")
    # pipeline = IngestionService(...) # Requires DB, etc. Mocking for flow verify.
    # await pipeline.process_jurisdiction(source_path) 
    # Mock pipeline process for now to avoid actual DB/LLM calls during flow verify
    # await pipeline.process(source_path)
    logger.info("Ingestion complete (Mocked)")

@flow(name="Daily Scrape Orchestration")
async def run_daily_sync():
    logger = get_run_logger()
    logger.info("Starting Daily Scrape Flow")
    
    # 1. Coordinate Spiders
    spiders = ["sanjose_minutes", "santa_clara_legislation", "sunnyvale_agendas"]
    for spider in spiders:
        artifact = run_spider(spider) # Synchronous task
        await run_pipeline(artifact)  # Async pipeline

if __name__ == "__main__":
    asyncio.run(run_daily_sync())
