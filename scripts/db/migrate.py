#!/usr/bin/env python3
"""
Migration Runner
Applies SQL files from backend/migrations to the database.
Run this in Railway to restore the schema.
"""
import os
import sys
import asyncio
import logging

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../backend'))

from db.postgres_client import PostgresDB

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("migrator")

async def run_migrations():
    logger.info("🔌 Connecting to Database...")
    try:
        db = PostgresDB()
        # Initialize connection
        await db.connect()
    except Exception as e:
        logger.error(f"❌ Failed to connect: {e}")
        return

    migration_file = os.path.join(os.path.dirname(__file__), '../../backend/migrations/002_schema_recovery_v2.sql')
    
    if not os.path.exists(migration_file):
        logger.error(f"❌ Migration file not found: {migration_file}")
        return

    logger.info(f"📜 Reading migration: {migration_file}")
    with open(migration_file, 'r') as f:
        sql_content = f.read()

    # Split by statements if necessary, or execute as block?
    # asyncpg execute supports multiple statements usually.
    
    try:
        logger.info("🚀 Applying migration...")
        await db._execute(sql_content)
        logger.info("✅ Migration applied successfully!")
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
    finally:
        await db.close()

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(run_migrations())
