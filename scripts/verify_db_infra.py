import asyncio
import os
import sys
import logging

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../backend'))

from db.postgres_client import PostgresDB
from dotenv import load_dotenv

# Load env (though usually provided by Railway)
load_dotenv(os.path.join(os.path.dirname(__file__), '../backend/.env'))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify_db")

async def main():
    logger.info("Testing connection to Shared Railway Postgres DB...")
    
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        logger.error("DATABASE_URL not found!")
        sys.exit(1)
        
    logger.info(f"Target URL: {db_url.split('@')[-1]}") # Log host only for safety

    db = PostgresDB()
    # Update PostgresDB logic manually here for testing or assume it handles options
    # Wait, PostgresDB uses asyncpg.create_pool(url).
    # We can pass kwargs to it?
    # backend/db/postgres_client.py doesn't currently accept kwargs in connect().
    # Let's verify via direct asyncpg call first to isolate.
    import asyncpg
    try:
        logger.info("Attempting direct asyncpg connection with ssl='require'...")
        conn = await asyncpg.connect(db_url, ssl='require', timeout=10)
        logger.info("✅ Direct Connection Established.")
        version = await conn.fetchval("SELECT version()")
        logger.info(f"DB Version: {version}")
        await conn.close()
        return

    except Exception as e:
        logger.error(f"❌ Direct Connection Failed: {e}")
        # Continue to try PostgresDB class if needed, or just exit
        sys.exit(1)

    # db = PostgresDB() # Skipped class usage to test raw connectivity first

if __name__ == "__main__":
    asyncio.run(main())
