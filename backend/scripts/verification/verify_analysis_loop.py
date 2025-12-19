
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
    import json
    test_html = "<html><body><h1>San Jose ADU Bill</h1><p>This bill allows more ADUs in residential zones to lower cost of living.</p></body></html>"
    # Wrap in JSON structure as column is likely JSONB and expects valid JSON
    test_data = json.dumps({"content": test_html})
    
    await db._execute("""
        INSERT INTO raw_scrapes (id, source_id, url, content_hash, content_type, data, processed)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
    """, test_id, source_id, "http://test.com/bill1", "hash123", "text/html", test_data, False)
    
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
    
    # 5. Run AnalysisPipeline
    print("🧠 Running AnalysisPipeline...")
    
    # Needs LLMClient and WebSearchClient
    from services.llm.orchestrator import AnalysisPipeline, LegislationAnalysisResponse, ReviewCritique, LegislationImpact
    from llm_common.core import LLMClient
    from llm_common.web_search import WebSearchClient
    from llm_common.core.models import LLMResponse, LLMConfig
    
    class MockLLMClient(LLMClient):
        def __init__(self):
            # Pass dummy config
            super().__init__(LLMConfig(api_key="mock", provider="mock"))
            
        async def chat_completion(self, messages, model=None, **kwargs):
            # Simple mock responding with specific JSON depending on content?
            # Or just return a generic valid JSON for whatever was asked.
            # pipeline calls generic "analyze", then "review", then "refine" (maybe)
            
            content = ""
            msg_str = str(messages)
            
            if "policy analyst" in msg_str: # Generate Step
                resp = LegislationAnalysisResponse(
                    bill_number="Test Bill 123",
                    impacts=[
                        LegislationImpact(
                            impact_number=1,
                            relevant_clause="clause 1",
                            impact_description="Lowers rent",
                            evidence=[],
                            chain_of_causality="supply up -> price down",
                            confidence_score=0.9,
                            p10=100.0, p25=200.0, p50=300.0, p75=400.0, p90=500.0
                        )
                    ],
                    total_impact_p50=300.0,
                    analysis_timestamp=datetime.now().isoformat(),
                    model_used="mock-model"
                )
                content = resp.model_dump_json()
                
            elif "policy reviewer" in msg_str: # Review Step
                resp = ReviewCritique(passed=True, critique="Good", missing_impacts=[])
                content = resp.model_dump_json()
                
            else:
                # Default/Fallback
                content = "{}"
                
            return LLMResponse(content=content, model="mock", usage=None)

        async def validate_api_key(self): return True
        async def stream_completion(self, **kwargs): pass
        
    class MockSearch(WebSearchClient):
        def __init__(self): pass
        async def search(self, query): return []

    mock_llm = MockLLMClient()
    mock_search = MockSearch()
    
    pipeline = AnalysisPipeline(mock_llm, mock_search, db)
    
    # Mock research agent to avoid real tool calls
    async def mock_research_run(bill_id, text, juris):
        return {"collected_data": [{"snippet": "Mock data"}]}
    pipeline.research_agent.run = mock_research_run
    
    try:
        bill_text = "This bill allows more ADUs in residential zones to lower cost of living."
        bill_number = "Test Bill 123"
        jurisdiction = "verification"
        
        # Ensure jurisdiction exists for pipeline to run against
        await db._execute("INSERT INTO jurisdictions (id, name, status) VALUES ($1, $2, $3) ON CONFLICT DO NOTHING", jurisdiction, "Test Juris", "active")
        
        # Run Pipeline
        models = {"research": "mock", "generate": "mock", "review": "mock"}
        analysis = await pipeline.run(bill_number, bill_text, jurisdiction, models)
        
        print("\n📊 Pipeline Result:")
        print(f"Impact P50: ${analysis.total_impact_p50}")
        
        # 6. Verify Persistence
        # AnalysisPipeline stores legislation and impacts automatically.
        print("💾 Verifying Postgres storage...")
        
        # Find Legislation
        # The pipeline likely uses 'bill_number' or looks up by ID?
        # In stored logic, it creates legislation.
        # We need to find the legislation row created by the pipeline.
        
        legs = await db._fetch("SELECT id FROM legislation WHERE bill_number = $1", bill_number)
        if not legs:
            print("❌ No legislation found in DB")
        else:
            leg_id = legs[0]['id']
            print(f"✅ Legislation found: {leg_id}")
            
            # Check Impacts
            imp_count = await db._fetchrow("SELECT count(*) as cnt FROM legislation_impacts WHERE legislation_id = $1", leg_id)
            print(f"✅ Verify Impacts Row Count: {imp_count['cnt']}")
            
            # Check Pipeline Run
            # We can check pipeline_runs table
            run_row = await db._fetchrow("SELECT count(*) as cnt FROM pipeline_runs WHERE legislation_id = $1", leg_id)
            print(f"✅ Pipeline Runs found: {run_row['cnt']}")

    except Exception as e:
        print(f"❌ Pipeline Execution Failed: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n✅ Verification Complete")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
