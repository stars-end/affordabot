import asyncio
import os
import sys
# Add backend to path
sys.path.append(os.getcwd())
from db.postgres_client import PostgresDB

async def main():
    db = PostgresDB()
    await db.connect()
    try:
        rows = await db._fetch("SELECT id FROM pipeline_runs ORDER BY started_at DESC LIMIT 1")
        if rows:
            print(str(rows[0]['id']))
        else:
            print("No runs found")
    finally:
        await db.close()

if __name__ == "__main__":
    asyncio.run(main())
