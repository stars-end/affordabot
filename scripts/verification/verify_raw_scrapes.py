#!/usr/bin/env python3
import asyncio
import os
import sys
from dotenv import load_dotenv

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../backend'))

from db.postgres_client import PostgresDB

async def main():
    load_dotenv(os.path.join(os.path.dirname(__file__), '../../backend/.env'))
    
    db = PostgresDB()
    try:
        await db.connect()
        # Query raw_scrapes table directly via the db client if possible, or use a custom query
        # For verification, we just want to see if we can read records.
        async with db.pool.acquire() as conn:
            rows = await conn.fetch("SELECT id, source_id, content_hash FROM raw_scrapes LIMIT 5")
            print(f"Found {len(rows)} raw scrapes in Postgres.")
            for row in rows:
                print(f"ID: {row['id']}, Source: {row['source_id']}, Hash: {row[2][:8]}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if db.pool:
            await db.pool.close()

if __name__ == "__main__":
    asyncio.run(main())
