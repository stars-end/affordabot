import asyncio
import os
import logging
from backend.db.postgres_client import PostgresDB

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("db_inspector")

async def inspect():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("❌ DATABASE_URL missing")
        return

    db = PostgresDB()
    await db.connect()
    
    run_id = "6d591d8d-d879-46e7-bc4a-46101c41bd71"
    
    print(f"\n🔍 Inspecting Run ID: {run_id}")
    
    # 1. Check Pipeline Run
    runs = await db._fetch("SELECT * FROM pipeline_runs WHERE id::text = $1", run_id)
    if runs:
        print(f"✅ Pipeline Run Found: {runs[0]['id']}")
        print(f"   Bill ID: {runs[0]['bill_id']}")
    else:
        print("❌ Pipeline Run NOT FOUND")
        
    # 2. Check Pipeline Steps
    steps = await db._fetch("SELECT * FROM pipeline_steps WHERE run_id::text = $1 ORDER BY step_number", run_id)
    print(f"\n📊 Pipeline Steps Found: {len(steps)}")
    for s in steps:
        print(f"   Step {s['step_number']}: {s['step_name']} (Status: {s['status']})")
        # Check model_config column specifically
        if 'model_config' in s:
             print(f"   - model_config: {str(s['model_config'])[:50]}...")
        else:
             print("   - ❌ Column 'model_config' missing in row keys (Check Schema?)")

    # 3. Check Schema Columns for legislation and raw_scrapes
    print("\nRequested Schema Inspection:")
    for table in ['legislation', 'raw_scrapes']:
        print(f"\n📂 Table: {table}")
        schema_rows = await db._fetch("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = $1
            ORDER BY ordinal_position
        """, table)
        for row in schema_rows:
            print(f" - {row['column_name']} ({row['data_type']})")

    await db.close()

if __name__ == "__main__":
    asyncio.run(inspect())
