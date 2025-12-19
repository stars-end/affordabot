import asyncio
import os
import json
import uuid
from datetime import datetime
from db.postgres_client import PostgresDB

async def seed_data():
    db = PostgresDB()
    # Mock URL - assumed to work with local postgres instance
    # If connection fails, we might need to adjust user/pass
    # For CI environments often user=postgres pass=postgres or empty
    os.environ["DATABASE_URL"] = "postgresql://postgres:password@localhost:5432/railway"
    
    try:
        await db.connect()
        print("Connected to DB.")
        
        # 1. Create Jurisdiction
        print("Creating Jurisdiction: San Jose")
        jur_id = await db.get_or_create_jurisdiction("San Jose", "city")
        print(f"Jurisdiction ID: {jur_id}")
        
        # 2. Store Legislation
        print("Storing Legislation...")
        bill_data = {
            "bill_number": "25-1234",
            "title": "Ordinance Amending Municipal Code to Increase Affordable Housing Requirements",
            "text": "The City Council hereby ordains that all new developments of 10 or more units must designate 20% as affordable...",
            "status": "Active",
            "introduced_date": datetime.now(),
            "raw_html": "<html>...</html>"
        }
        leg_id = await db.store_legislation(jur_id, bill_data)
        print(f"Legislation ID: {leg_id}")
        
        # 3. Store Impacts (Analysis Result)
        print("Storing Impacts...")
        impacts = [
            {
                "relevant_clause": "Section 4.2: 20% Requirement",
                "impact_description": "Increases development costs for market-rate units by approximately 5%.",
                "confidence_score": 0.9,
                "p50": 1500000,
                "evidence": [{"source": "Housing Study 2024", "url": "http://example.com"}]
            },
            {
                "relevant_clause": "Section 5: In-Lieu Fees",
                "impact_description": "Generates $2M annually for the city housing fund.",
                "confidence_score": 0.85,
                "p50": 2000000,
                "evidence": []
            }
        ]
        await db.store_impacts(leg_id, impacts)
        
        # 4. Store Traces (GlassBox) - Mocking simple steps
        # GlassBoxService reads from disk usually? Or DB?
        # backend/routers/admin.py uses GlassBoxService(trace_dir=".traces")
        # So I need to write to .traces directory!
        
        trace_id = str(uuid.uuid4())
        trace_data = [
            {
                "tool": "TaskPlanner",
                "task_id": "task_1",
                "query_id": trace_id,
                "args": {"query": "Analyze bill 25-1234"},
                "result": {"plan": ["Research", "Analyze"]},
                "timestamp": datetime.now().timestamp()
            },
            {
                "tool": "WebSearch",
                "task_id": "task_2",
                "query_id": trace_id,
                "args": {"query": "San Jose housing costs"},
                "result": {"results": ["..."]},
                "timestamp": datetime.now().timestamp() + 1
            }
        ]
        
        os.makedirs(".traces", exist_ok=True)
        with open(f".traces/{trace_id}.json", "w") as f:
            for step in trace_data:
                f.write(json.dumps(step) + "\n")
                
        print(f"Stored Trace: {trace_id}")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await db.close()

if __name__ == "__main__":
    asyncio.run(seed_data())
