import asyncio
import os
import logging
from db.postgres_client import PostgresDB

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("schema_fix")

async def apply_schema():
    print("🔧 Applying Schema Fix...")
    db = PostgresDB()
    if not os.getenv("DATABASE_URL"):
        print("❌ DATABASE_URL missing")
        return

    await db.connect()
    
    # Create pipeline_runs table
    print("Creating pipeline_runs table...")
    await db._execute("""
    CREATE TABLE IF NOT EXISTS pipeline_runs (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        bill_id TEXT NOT NULL,
        jurisdiction TEXT NOT NULL,
        models JSONB,
        status TEXT DEFAULT 'running',
        result JSONB,
        error TEXT,
        started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        completed_at TIMESTAMP WITH TIME ZONE
    );
    """)

    # Create analysis_history table just in case
    print("Creating analysis_history table...")
    await db._execute("""
    CREATE TABLE IF NOT EXISTS analysis_history (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        bill_id TEXT NOT NULL,
        jurisdiction TEXT NOT NULL,
        step TEXT NOT NULL,
        model TEXT,
        data JSONB,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );
    """)

    print("✅ Schema applied.")
    await db.close()

if __name__ == "__main__":
    asyncio.run(apply_schema())
