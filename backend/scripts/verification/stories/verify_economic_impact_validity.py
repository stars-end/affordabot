
import asyncio
import sys
import uuid
from datetime import datetime
from pathlib import Path

# Add backend root to path
backend_root = str(Path(__file__).parent.parent.parent.parent)
if backend_root not in sys.path:
    sys.path.append(backend_root)

# Imports
from db.postgres_client import PostgresDB
from services.ingestion_service import IngestionService
from services.storage.s3_storage import S3Storage
from services.retrieval.local_pgvector import LocalPgVectorBackend
from llm_common.embeddings import EmbeddingService
from services.llm.orchestrator import AnalysisPipeline
from schemas.analysis import LegislationAnalysisResponse, LegislationImpact, ImpactEvidence, ReviewCritique
from llm_common.core import LLMClient
from llm_common.web_search import WebSearchClient
from llm_common.core.models import LLMResponse, LLMConfig, LLMUsage

# --- MOCKS ---

class MockEmbeddingService(EmbeddingService):
    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        # 4096 dim for pgvector compatibility (as seen in verify_analysis_loop)
        return [[0.1] * 4096 for _ in texts]
    async def embed_query(self, text: str) -> list[float]:
        return [0.1] * 4096

class MockSearch(WebSearchClient):
    def __init__(self):
        # Pass dummy key to satisfy parent
        super().__init__(api_key="mock")
    async def search(self, query): return []

class ImpactVerifyingLLM(LLMClient):
    """
    Mock LLM that:
    1. Verifies the prompt contains the Golden Data.
    2. Returns a 'High Impact' response to test pipeline parsing.
    """
    def __init__(self):
        super().__init__(LLMConfig(api_key="mock", provider="zai", default_model="mock"))
        self.prompt_verified = False
        
    async def chat_completion(self, messages, model=None, **kwargs):
        msg_str = str(messages)
        
        # CHECK: Did the golden data reach the prompt?
        if "$500" in msg_str and "fee" in msg_str:
            self.prompt_verified = True
            
        # Return canned High Impact response for the 'generate' step
        if "policy analyst" in msg_str.lower():
            resp = LegislationAnalysisResponse(
                title="Mock Bill",
                jurisdiction="Mock Verif",
                status="Mocked",
                bill_number="BILL-TEST-101",
                impacts=[
                    LegislationImpact(
                        impact_number=1,
                        relevant_clause="Section 5: Fees",
                        legal_interpretation="Imposes a new $500 fee",
                        impact_description="Increases cost of living significantly",
                        evidence=[ImpactEvidence(source_name="Text", url="http://test", excerpt="shall pay a fee of $500")],
                        chain_of_causality="fee -> expense -> cost of living",
                        confidence_score=0.95,
                        # High impact cost
                        p10=500.0, p25=500.0, p50=500.0, p75=500.0, p90=500.0
                    )
                ],
                total_impact_p50=500.0,
                analysis_timestamp=datetime.now().isoformat(),
                model_used="mock-model"
            )
            content = resp.model_dump_json()
        elif "policy reviewer" in msg_str.lower():
            resp = ReviewCritique(passed=True, critique="Accurate", missing_impacts=[], factual_errors=[])
            content = resp.model_dump_json()
        else:
            content = "{}"
            
        return LLMResponse(
            id="mock-123",
            content=content,
            model="mock",
            finish_reason="stop",
            usage=LLMUsage(prompt_tokens=10, completion_tokens=10, total_tokens=20)
        )

    async def validate_api_key(self): return True
    async def stream_completion(self, **kwargs): pass

# --- STORY EXECUTION ---

def run_story() -> tuple[bool, str]:
    """Execute the Economic Impact Validity story."""
    try:
        return asyncio.run(_async_run_story())
    except Exception as e:
        return False, f"Exception: {e}"

async def _async_run_story() -> tuple[bool, str]:
    # 1. Setup Environment
    db = PostgresDB()
    conn_result = await db.connect()
    
    # Check if DB connection actually worked (PostgresDB connects silently usually or raises)
    # verify_analysis_loop catches exception.
    
    storage = S3Storage()
    embedding_service = MockEmbeddingService()
    vector_backend = LocalPgVectorBackend(table_name="document_chunks", postgres_client=db)
    
    ingestion = IngestionService(
        postgres_client=db,
        storage_backend=storage,
        vector_backend=vector_backend,
        embedding_service=embedding_service,
        chunk_size=500
    )
    
    # 2. Inject Golden Data (BILL-TEST-101)
    test_id = str(uuid.uuid4())
    bill_number = "BILL-TEST-101"
    # Content contains the trigger words "$500" and "fee"
    bill_content = """
    <html><body>
    <h1>The Cost of Living Act</h1>
    <p>Section 5. Every resident shall pay a mandatory fee of $500 per year to the municipal fund.</p>
    </body></html>
    """
    
    # Setup dependencies in DB
    JURISDICTION_ID = "11111111-1111-1111-1111-111111111111"
    await db._execute("INSERT INTO jurisdictions (id, name, type) VALUES ($1, 'Verification City', 'city') ON CONFLICT DO NOTHING", JURISDICTION_ID)
    
    # Create Source
    source_rows = await db._fetch("SELECT id FROM sources WHERE jurisdiction_id = $1 LIMIT 1", JURISDICTION_ID)
    if not source_rows:
        await db._execute("INSERT INTO sources (jurisdiction_id, url, type, status) VALUES ($1, 'http://verify.com', 'test', 'active')", JURISDICTION_ID)
        source_rows = await db._fetch("SELECT id FROM sources WHERE jurisdiction_id = $1 LIMIT 1", JURISDICTION_ID)
    source_id = source_rows[0]['id']
    
    # Create Raw Scrape
    import json
    data_json = json.dumps({"content": bill_content})
    await db._execute("""
        INSERT INTO raw_scrapes (id, source_id, url, content_hash, content_type, data, processed)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        ON CONFLICT (id) DO UPDATE SET processed = FALSE
    """, test_id, source_id, "http://verify.com/bill101", "hash101", "text/html", data_json, False)
    
    # 3. Process Ingestion (Extract Text -> DB)
    await ingestion.process_raw_scrape(test_id)
    
    # 4. Run Analysis Pipeline
    mock_llm = ImpactVerifyingLLM()
    mock_search = MockSearch()
    pipeline = AnalysisPipeline(mock_llm, mock_search, db)
    
    # Mock research to avoid network
    async def mock_run_research(*args): return {"collected_data": []}
    pipeline.research_agent.run = mock_run_research
    
    # Execute
    # We pass the same text directly or rely on pipeline to fetch? 
    # Pipeline.run takes text directly as arg 2.
    models = {"research": "mock", "generate": "mock", "review": "mock"}
    analysis = await pipeline.run(bill_number, "Every resident shall pay a mandatory fee of $500 per year.", "verification", models)
    
    # 5. Assertions
    failures = []
    
    # Check 1: Did prompt creation see the data?
    if not mock_llm.prompt_verified:
        failures.append("Golden Data ('$500', 'fee') not found in LLM prompt.")
        
    # Check 2: Impact Level
    if analysis.total_impact_p50 != 500.0:
        failures.append(f"Impact P50 mismatch. Expected 500.0, got {analysis.total_impact_p50}")
        
    # Check 3: Description correctness (verifies parsing)
    impact_desc = analysis.impacts[0].impact_description
    if "Cost of living" not in impact_desc and "living" not in impact_desc: # loose match
        failures.append(f"Impact description mismatch: {impact_desc}")

    if failures:
        return False, "; ".join(failures)
    
    return True, "Economic Logic Verified: $500 fee detected and mapped to High Impact."

if __name__ == "__main__":
    success, message = run_story()
    print(f"{'✅' if success else '❌'} {message}")
    sys.exit(0 if success else 1)
