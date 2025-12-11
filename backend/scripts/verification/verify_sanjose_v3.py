#!/usr/bin/env python3
import asyncio
import os
import sys
import logging

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))

from db.postgres_client import PostgresDB

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify_v3")

async def main():
    logger.info("🚀 Starting San Jose Pipeline Verification V3 (Postgres Native)")
    
    # 1. DB Connection
    db = PostgresDB()
    try:
        await db.connect()
        logger.info("✅ PostgresDB Connected")
    except Exception as e:
        logger.error(f"❌ DB Connection Failed: {e}")
        return

    # 2. Verify Tables
    tables = ["sources", "raw_scrapes", "documents", "admin_tasks"]
    for t in tables:
        try:
            res = await db._fetch(f"SELECT count(*) FROM {t}")
            logger.info(f"✅ Table '{t}' exists (count: {res[0]['count']})")
        except Exception as e:
            logger.error(f"❌ Table '{t}' check failed: {e}")

    # 3. Test Universal Harvester (Universal/Z.ai)
    logger.info("\n🧪 Testing Universal Harvester...")
    # Create a dummy source for test
    try:
        source_id = await db.get_or_create_source("web", "https://iterm2.com/", "web")
        # Ensure it has scrape_url in metadata or column if schema changed?
        # In `run_universal_harvester`, it looks for `scrape_url` OR `url`.
        # Just ensure type='web'.
        await db._execute("UPDATE sources SET type = 'web' WHERE id = $1", source_id)
        logger.info(f"   Created Source: {source_id}")
    except Exception as e:
        logger.error(f"   Failed to create test source: {e}")

    # Run script
    import subprocess
    script_path = os.path.join(os.path.dirname(__file__), '../cron/run_universal_harvester.py')
    
    # Run with timeout
    try:
        proc = subprocess.run([sys.executable, script_path], capture_output=True, text=True, timeout=120)
        if proc.returncode == 0:
            logger.info("✅ run_universal_harvester.py executed successfully")
        else:
            logger.error(f"❌ run_universal_harvester.py Failed:\n{proc.stderr}")
    except subprocess.TimeoutExpired:
        logger.error("❌ run_universal_harvester.py Timed Out")

    # 4. Test Municode Spider (Backbone)
    logger.info("\n🧪 Testing San Jose Municode Spider...")
    # Create source for Municode
    municode_source_id = await db.get_or_create_source("sanjose", "Municode Title 24", "code")
    
    spider_cmd = [
        "scrapy", "crawl", "sanjose_municode",
        "-a", f"source_id={municode_source_id}"
    ]
    cwd = os.path.join(os.path.dirname(__file__), '../../affordabot_scraper')
    
    try:
        # Need config for DATABASE_URL for pipeline
        env = os.environ.copy()
        if not env.get("DATABASE_URL"):
            env["DATABASE_URL"] = db.database_url
            
        proc = subprocess.run(spider_cmd, cwd=cwd, env=env, capture_output=True, text=True, timeout=120)
        
        if "Saved item to raw_scrapes" in proc.stderr:
            logger.info("✅ Spider signaled success in logs")
        elif proc.returncode == 0:
            logger.warning("⚠️ Spider exited 0 but confirmation log not found. Checking DB...")
        else:
            logger.error(f"❌ Spider Failed:\n{proc.stderr}")
            
    except Exception as e:
        logger.error(f"❌ Spider Execution Error: {e}")

    # 5. Verify Data Landing
    logger.info("\n🧪 Verifying Ingestion...")
    # Check raw_scrapes for municode
    rows = await db._fetch(
        "SELECT id, processed, document_id FROM raw_scrapes WHERE source_id = $1 ORDER BY created_at DESC LIMIT 1",
        municode_source_id
    )
    if rows:
        row = rows[0]
        logger.info(f"✅ Found Raw Scrape: {row['id']}")
        if row['processed']:
            logger.info(f"✅ Scrape Processed! Document ID: {row['document_id']}")
        else:
            logger.warning("⚠️ Scrape exists but NOT PROCESSED (Ingestion failure?)")
    else:
        logger.error("❌ No raw scrape found for Municode source.")

    await db.close()

if __name__ == "__main__":
    asyncio.run(main())
