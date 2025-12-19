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
        # Check jurisdictions table
        print("\n--- Checking Jurisdictions Table ---")
        rows = await db._fetch("SELECT id, name, type FROM jurisdictions WHERE name ILIKE '%jose%'")
        for r in rows:
            print(f"Found Jurisdiction: {dict(r)}")

        print("\n--- Checking Legislation Table ---")
        # Check by jurisdiction ID if found, or string match on name?
        # Legislation links via jurisdiction_id.
        
        # Check raw count with join
        query = """
            SELECT j.name, count(l.id) 
            FROM legislation l
            JOIN jurisdictions j ON l.jurisdiction_id = j.id
            WHERE j.name ILIKE '%jose%'
            GROUP BY j.name
        """
        rows = await db._fetch(query)
        for r in rows:
            print(f"Legislation Count for '{r['name']}': {r['count']}")
        
    finally:
        await db.close()

if __name__ == "__main__":
    asyncio.run(main())
