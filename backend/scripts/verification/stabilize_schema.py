import asyncio
import os
import sys
import logging

# Add parent directory to sys.path
sys.path.append(os.getcwd())

from db.postgres_client import PostgresDB

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def stabilize_schema():
    db = PostgresDB()
    await db.connect()
    
    logger.info("🚀 Stabilizing Database Schema...")
    
    # 1. Pipeline Runs Table
    logger.info("Checking 'pipeline_runs'...")
    await db._execute("""
        CREATE TABLE IF NOT EXISTS pipeline_runs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            bill_id TEXT,
            jurisdiction TEXT,
            models JSONB,
            started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP WITH TIME ZONE,
            status TEXT DEFAULT 'running',
            result JSONB,
            error TEXT
        )
    """)
    
    # Ensure columns exist (if table already existed)
    columns = {
        "result": "JSONB",
        "models": "JSONB",
        "started_at": "TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP",
        "jurisdiction": "TEXT",
        "error": "TEXT"
    }
    
    for col, col_type in columns.items():
        try:
            await db._execute(f"ALTER TABLE pipeline_runs ADD COLUMN IF NOT EXISTS {col} {col_type}")
        except Exception as e:
            logger.warning(f"Could not add column {col}: {e}")

    # 2. Legislation Table
    logger.info("Checking 'legislation'...")
    # Map text_content -> text if missing
    try:
        await db._execute("ALTER TABLE legislation ADD COLUMN IF NOT EXISTS text TEXT")
        await db._execute("ALTER TABLE legislation ADD COLUMN IF NOT EXISTS bill_number TEXT")
    except Exception as e:
        logger.warning(f"Legislation update warning: {e}")

    # 3. Impacts Table
    logger.info("Checking 'impacts'...")
    try:
        await db._execute("ALTER TABLE impacts ADD COLUMN IF NOT EXISTS confidence_score FLOAT")
    except Exception as e:
        logger.warning(f"Impacts update warning: {e}")

    logger.info("✅ Schema Stabilization Complete.")
    await db.close()

if __name__ == "__main__":
    asyncio.run(stabilize_schema())
