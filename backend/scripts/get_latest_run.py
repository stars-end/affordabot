import asyncio
import sys
from pathlib import Path

# Add backend to sys.path
sys.path.append(str(Path(__file__).parent.parent))

from db.postgres_client import PostgresDB

async def main():
    db = PostgresDB()
    await db.connect()
    try:
        query = "SELECT id, bill_id, started_at FROM pipeline_runs ORDER BY started_at DESC LIMIT 1"
        row = await db._fetchrow(query)
        if row:
            print(f"Latest Run ID: {row['id']}")
            print(f"Bill: {row['bill_id']}")
        else:
            print("No pipeline runs found.")
    finally:
        await db.close()

if __name__ == "__main__":
    asyncio.run(main())
