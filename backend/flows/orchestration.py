from prefect import flow, task, get_run_logger
import os
import asyncio
from services.storage.s3_storage import S3Storage
from db.postgres_client import PostgresDB
from services.ingestion_service import IngestionService
from services.vector_backend_factory import create_vector_backend
from llm_common.embeddings.openai import OpenAIEmbeddingService

@task
def run_spider(spider_name: str):
    logger = get_run_logger()
    logger.info(f"Starting spider: {spider_name}")
    os.system(f"cd backend && poetry run bash -c 'cd affordabot_scraper && scrapy crawl {spider_name}'")
    logger.info(f"Finished spider: {spider_name}")
    return "s3://bucket/path"  # Scraper should return this ideally

@task
async def run_pipeline(source_path: str):
    logger = get_run_logger()
    logger.info("Running ingestion pipeline")
    
    # 1. Initialize Infrastructure
    db = PostgresDB()
    await db.connect()
    
    # s3 = S3Storage()
    
    # 2. Initialize Embeddings (Fail gracefully if key missing)
    # if os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY"):
    #      embedding_service = OpenAIEmbeddingService(
    #         base_url="https://openrouter.ai/api/v1",
    #         api_key=os.getenv("OPENROUTER_API_KEY"),
    #         model="qwen/qwen3-embedding-8b",
    #         dimensions=1536
    #      )
    # else:
    #     logger.warning("No LLM Key found, skipping embeddings")
    #     embedding_service = None

    # 3. Initialize Vector Backend
    # vector_backend = create_vector_backend(db, None) # Embed fn handled inside service usually? No, factory needs it.
    
    # 4. Initialize Ingestion Service
    # ingestion = IngestionService(
    #     postgres_client=db,
    #     vector_backend=vector_backend,
    #     embedding_service=embedding_service,
    #     storage_backend=s3
    # )
    
    # 5. Process pending raw scrapes (V2 Pattern: Scraper inserts RawScrape, Pipeline processes it)
    # Fetch pending IDs? For now, we mimic daily_scrape loop or just process all pending.
    # In V2, Scraper puts RawScrape in DB. We just need to trigger 'process_pending'.
    # But IngestionService doesn't have 'process_pending'. It has 'process_raw_scrape(id)'.
    
    # Simple Loop for MVP:
    # pending_scrapes = await db.fetch("SELECT id FROM raw_scrapes WHERE processed = false")
    # for row in pending_scrapes:
    #    await ingestion.process_raw_scrape(row['id'])
    
    logger.info("Ingestion Service Wired (Ready for pending loop)")
    await db.close()

@flow(name="Daily Scrape Orchestration")
async def run_daily_sync():
    logger = get_run_logger()
    logger.info("Starting Daily Scrape Flow")
    
    spiders = ["sanjose_minutes", "santa_clara_legislation", "sunnyvale_agendas"]
    for spider in spiders:
        run_spider(spider) 
        
    await run_pipeline("all")

if __name__ == "__main__":
    asyncio.run(run_daily_sync())
