import os
import subprocess
from prefect import flow, task, get_run_logger
from supabase import create_client, Client

@task
def fetch_active_sources():
    logger = get_run_logger()
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise ValueError("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY")
    
    supabase: Client = create_client(url, key)
    response = supabase.table("sources").select("*").eq("status", "active").execute()
    logger.info(f"Found {len(response.data)} active sources")
    return response.data

@task
async def fetch_with_web_reader(source):
    """Fetch content using Web Reader for non-meeting sources."""
    logger = get_run_logger()
    source_id = source["id"]
    url = source["url"]
    
    logger.info(f"Fetching {url} with Web Reader for source {source_id}")
    
    # Import here to avoid top-level async issues
    import sys
    sys.path.append(os.path.join(os.getcwd(), "backend"))
    from clients.web_reader_client import WebReaderClient
    from supabase import create_client
    import hashlib
    
    client = WebReaderClient()
    result = await client.fetch_content(url)
    
    # Store in raw_scrapes
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    supabase = create_client(supabase_url, supabase_key)
    
    content_hash = hashlib.sha256(result["content"].encode()).hexdigest()
    
    raw_scrape = {
        "source_id": source_id,
        "content_hash": content_hash,
        "content_type": "text/markdown",
        "data": result,
        "metadata": {"fetcher": "web_reader"}
    }
    
    supabase.table("raw_scrapes").insert(raw_scrape).execute()
    logger.info(f"Stored raw scrape for source {source_id}")

@task
def run_spider(source):
    logger = get_run_logger()
    source_id = source["id"]
    handler = source.get("handler")
    source_method = source.get("source_method", "scrape")

    if not handler:
        logger.error(f"No handler specified for source {source_id}")
        return
    
    if source_method != "scrape":
        logger.warning(f"Source {source_id} has method '{source_method}', skipping spider execution")
        return

    logger.info(f"Starting spider {handler} for source {source_id}")
    
    # Run scrapy as a subprocess
    # We assume we are in the project root, so we need to point to backend/affordabot_scraper
    cwd = os.path.join(os.getcwd(), "backend", "affordabot_scraper")
    scrapy_bin = os.path.join(os.getcwd(), "backend", "venv", "bin", "scrapy")
    
    try:
        result = subprocess.run(
            [scrapy_bin, "crawl", handler, "-a", f"source_id={source_id}"],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True
        )
        logger.info(f"Spider finished successfully: {result.stdout}")
    except subprocess.CalledProcessError as e:
        logger.error(f"Spider failed: {e.stderr}")
        raise

@flow(name="Scrape All Sources")
async def scrape_all_flow():
    """Route sources to appropriate fetcher based on source_method."""
    sources = fetch_active_sources()
    for source in sources:
        source_method = source.get("source_method", "scrape")
        
        if source_method == "web_reader":
            await fetch_with_web_reader(source)
        elif source_method == "scrape":
            run_spider.submit(source)
        else:
            logger = get_run_logger()
            logger.warning(f"Unknown source_method '{source_method}' for source {source['id']}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(scrape_all_flow())
