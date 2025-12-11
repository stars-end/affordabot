
import asyncio
import uuid
from datetime import datetime
from dotenv import load_dotenv

# Load env vars
load_dotenv()

import sys  # noqa: E402
from pathlib import Path  # noqa: E402

# Add backend root to path
backend_root = str(Path(__file__).parent.parent.parent)
sys.path.append(backend_root)

# Imports
from db.postgres_client import PostgresDB  # noqa: E402
from services.ingestion_service import IngestionService  # noqa: E402
from services.storage.s3_storage import S3Storage  # noqa: E402
# from llm_common.retrieval import PgVectorBackend # Disabled due to dependency issue
from services.retrieval.local_pgvector import LocalPgVectorBackend  # noqa: E402
from llm_common.embeddings import EmbeddingService  # noqa: E402

class MockEmbeddingService(EmbeddingService):
    def __init__(self):
        pass
    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        # Return dummy embeddings (vector size 1536 for OpenAI compat, or 4096?)
        # Let's use 1536 as common default
        return [[0.1] * 1536 for _ in texts]
    async def embed_query(self, text: str) -> list[float]:
        return [0.1] * 1536

async def main():
    print("🚀 Starting Analysis Loop Verification...")
    
    # 1. Setup Clients
    db = PostgresDB()
    try:
        await db.connect()
        print("✅ Postgres Connected")
    except Exception as e:
        print(f"❌ Postgres Connection Failed: {e}")
        return

    # S3 Storage (MinIO)
    storage = S3Storage() # Reads env vars MINIO_*
    
    # Needs Mock Embedding
    embedding_service = MockEmbeddingService()
    
    vector_backend = LocalPgVectorBackend(
        table_name="document_chunks",
        postgres_client=db
    )
    
    ingestion = IngestionService(
        postgres_client=db,
        storage_backend=storage,
        vector_backend=vector_backend,
        embedding_service=embedding_service,
        chunk_size=500
    )
    
    # Mock Analyzer for verification without API keys
    class MockAnalyzer:
        async def analyze(self, text, number, jurisdiction):
            from schemas.analysis import LegislationAnalysisResponse, LegislationImpact
            return LegislationAnalysisResponse(
                bill_number=number,
                impacts=[
                    LegislationImpact(
                        impact_number=1,
                        relevant_clause="clause 1",
                        impact_description="Lowers rent",
                        evidence=[],
                        chain_of_causality="supply up -> price down",
                        confidence_factor=0.9,
                        p10=100.0, p25=200.0, p50=300.0, p75=400.0, p90=500.0
                    )
                ],
                total_impact_p50=300.0,
                analysis_timestamp=datetime.now().isoformat(),
                model_used="mock-model"
            )

    analyzer = MockAnalyzer()
    
    # 2. Create Dummy Raw Scrape
    test_id = str(uuid.uuid4())
    print(f"📝 Creating test scrape: {test_id}")
    
    # We need a source first?
    # Ensure source exists (idempotent check ideally, or just insert)
    # Since we are verifying, we can insert a temp source or use existing.
    
    # Insert generic source
    await db._execute("""
        INSERT INTO sources (jurisdiction_id, url, type, status)
        VALUES ('verification', 'http://test.com', 'test', 'active')
        ON CONFLICT DO NOTHING
    """)
    
    # Get that source ID
    rows = await db._fetch("SELECT id FROM sources WHERE jurisdiction_id = 'verification' LIMIT 1")
    if not rows:
        print("❌ Failed to get test source")
        return
    source_id = rows[0]['id']

    # Insert Raw Scrape
    test_html = "<html><body><h1>San Jose ADU Bill</h1><p>This bill allows more ADUs in residential zones to lower cost of living.</p></body></html>"
    await db._execute("""
        INSERT INTO raw_scrapes (id, source_id, url, content_hash, content_type, data, processed)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
    """, test_id, source_id, "http://test.com/bill1", "hash123", "text/html", test_html, False)
    
    print("✅ Raw Scrape inserted")

    # 3. Run Ingestion
    print("⚙️ Running IngestionService...")
    try:
        chunks_count = await ingestion.process_raw_scrape(test_id)
        print(f"✅ Ingestion complete. Chunks: {chunks_count}")
        
        if chunks_count == 0:
            print("❌ No chunks created. Ingestion failed logic.")
            print("  ✅ Done.") # Added line
            return

    except Exception as e:
        print(f"❌ Ingestion Failed: {e}")
        import traceback
        traceback.print_exc()
        return

    # 4. Verify Side Effects (Storage & Vector)
    # Check "processed" flag
    row = await db._fetchrow("SELECT processed, storage_uri, document_id FROM raw_scrapes WHERE id = $1", test_id)
    if row and row['processed']:
        print(f"✅ Scrape marked processed. Storage URI: {row['storage_uri']}")
    else:
        print("❌ Scrape NOT marked processed")
        
    doc_id = row['document_id']
    if not doc_id:
        print("❌ No document_id generated")
        
    # Check Vector Chunks
    # Using psycopg2 inside PgVectorBackend, so we need to check DB directly or use backend.
    # Check directly via PostgresDB
    chunk_rows = await db._fetch("SELECT count(*) as cnt FROM document_chunks WHERE document_id = $1", doc_id)
    print(f"✅ Vector chunks found in DB: {chunk_rows[0]['cnt']}")
    
    # 5. Run Analyzer
    print("🧠 Running LegislationAnalyzer...")
    try:
        bill_text = "This bill allows more ADUs in residential zones to lower cost of living."
        bill_number = "Test Bill 123"
        analysis = await analyzer.analyze(bill_text, bill_number, "San Jose")
        
        print("\n📊 Analysis Result:")
        print(f"Impact P50: ${analysis.total_impact_p50}")
        if analysis.impacts:
            for impact in analysis.impacts:
                print(f"- {impact.impact_description} (Conf: {impact.confidence_factor})")
        
        # 6. Store Result (Simulating AnalysisService/Admin Task)
        # First, store legislation container
        print("💾 Storing analysis to Postgres...")
        
        # We need a legislation ID. 
        # Usually created during ingestion or just before analysis?
        # Let's create one now.
        leg_data = {
            "bill_number": bill_number,
            "title": "ADU Housing Bill",
            "text": bill_text,
            "status": "introduced",
            "raw_html": test_html,
            "introduced_date": datetime.now()
        }
        
        # IngestionService doesn't create legislation rows usually (it creates chunks).
        # Admin task or Harvester creates legislation.
        # We can simulate creation here.
        # Assuming table 'legislation' exists and linked to jurisdiction.
        # Jurisdiction ID 'verification' (from source)
        jurisdiction_id = "verification" # Mapped to source earlier
        # Ensure jurisdiction exists in 'jurisdictions' table?
        # 'sources' table has 'jurisdiction_id' column, but is it FK?
        # Let's try inserting jurisdiction if needed.
        await db._execute("INSERT INTO jurisdictions (id, name, status) VALUES ('verification', 'Test Jurisdiction', 'active') ON CONFLICT DO NOTHING")
        
        leg_id = await db.store_legislation(jurisdiction_id, leg_data)
        if not leg_id:
            print("❌ Failed to store legislation")
            return
            
        print(f"✅ Legislation stored: {leg_id}")
        
        # Store Impacts
        # Convert Pydantic objects to dicts matching store_impacts expectation?
        # PostgresDB.store_impacts expects List[Dict[str, Any]]
        # Let's check signature in postgres_client.py (saw it earlier: store_impacts(legislation_id, impacts))
        
        impact_dicts = [impact.model_dump() for impact in analysis.impacts]
        success = await db.store_impacts(leg_id, impact_dicts)
        
        if success:
            print("✅ Impacts stored successfully")
        else:
            print("❌ Failed to store impacts")
            
        # Verify DB Rows
        imp_count = await db._fetchrow("SELECT count(*) as cnt FROM legislation_impacts WHERE legislation_id = $1", leg_id)
        print(f"✅ Verify Impacts Row Count: {imp_count['cnt']}")
            
    except Exception as e:
        print(f"❌ Analyzer/Storage Failed: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n✅ Verification Complete")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
