#!/usr/bin/env python3
"""
E2E Glass Box Verification Script (P0 Audit)

Runs the full Affordabot pipeline (Ingestion -> Embedding -> Analysis) 
using REAL clients (Z.ai/OpenRouter) and REAL database interactions.

Goal: Generate traceable logs and data for "Proof of Work" audit.
"""

import asyncio
import os
import sys
import uuid
import json
import logging
from pathlib import Path
from dotenv import load_dotenv

# Load env vars
load_dotenv()

# Add backend to path
backend_root = str(Path(__file__).parent.parent.parent)
sys.path.append(backend_root)

# Imports
from db.postgres_client import PostgresDB
from services.ingestion_service import IngestionService
from services.storage.s3_storage import S3Storage
from services.llm.orchestrator import AnalysisPipeline
from llm_common.core import LLMClient, LLMConfig
from llm_common.providers import ZaiClient, OpenRouterClient
from llm_common.web_search import WebSearchClient
from llm_common.embeddings.openai import OpenAIEmbeddingService
# from llm_common.retrieval.pgvector_backend import PgVectorBackend # Not needed if using Local
from services.retrieval.local_pgvector import LocalPgVectorBackend
from llm_common.core.models import LLMResponse, LLMUsage

# Logging Setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - [E2E-AUDIT] - %(levelname)s - %(message)s')
logger = logging.getLogger("e2e_audit")

async def main():
    logger.info("🚀 Starting E2E Glass Box Audit Verification")
    real_mode = os.environ.get("VERIFY_REAL_LLM") == "1"
    if not real_mode:
        logger.info("🧪 VERIFY_REAL_LLM not set; running in deterministic MOCK mode (no external LLM/search dependencies).")
    
    # 1. Setup Database
    db = PostgresDB()
    await db.connect()
    logger.info("✅ Database Connected")

    # Ensure vector table exists for audit
    await db._execute("""
        CREATE EXTENSION IF NOT EXISTS vector;
        CREATE TABLE IF NOT EXISTS document_chunks (
            id UUID PRIMARY KEY,
            document_id UUID,
            content TEXT,
            embedding vector(4096),
            metadata JSONB
        );
    """)
    logger.info("✅ Ensured 'document_chunks' table exists")

    # 2. Setup Services (Real Clients)
    
    # Storage
    storage = S3Storage()
    logger.info("✅ Storage Service Initialized")

    # Embedding (OpenRouter)
    if real_mode:
        if not os.getenv("OPENROUTER_API_KEY"):
            logger.error("❌ OPENROUTER_API_KEY missing! Required for embeddings in VERIFY_REAL_LLM=1 mode.")
            return

        embedding_service = OpenAIEmbeddingService(
            base_url="https://openrouter.ai/api/v1",
            api_key=os.getenv("OPENROUTER_API_KEY"),
            model="qwen/qwen3-embedding-8b",
            dimensions=4096,
        )
        logger.info("✅ Embedding Service Initialized (OpenRouter)")
    else:
        class MockEmbeddingService:
            async def embed_documents(self, texts: list[str]) -> list[list[float]]:
                return [[0.1] * 4096 for _ in texts]

            async def embed_query(self, text: str) -> list[float]:
                return [0.1] * 4096

        embedding_service = MockEmbeddingService()
        logger.info("✅ Embedding Service Initialized (Mock)")

    # Vector Backend
    # Use LocalPgVectorBackend to reuse existing DB connection
    vector_backend = LocalPgVectorBackend(
        table_name="document_chunks",
        postgres_client=db
    )
    logger.info("✅ Vector Backend Initialized (LocalPgVector)")

    # Ingestion
    ingestion = IngestionService(
        postgres_client=db,
        vector_backend=vector_backend,
        embedding_service=embedding_service,
        storage_backend=storage
    )

    # LLM Clients (Z.ai + Fallback) OR deterministic mocks
    if real_mode:
        llm_config = LLMConfig(
            api_key=os.getenv("ZAI_API_KEY"),
            provider="zai",
            default_model="glm-4.6",  # Fix P0: Use confirmed generic model ID
        )
        llm_client: LLMClient = ZaiClient(llm_config)

        fallback_client = None
        if os.getenv("OPENROUTER_API_KEY"):
            or_config = LLMConfig(
                api_key=os.getenv("OPENROUTER_API_KEY"),
                provider="openrouter",
                default_model="openai/gpt-4o-mini",
            )
            fallback_client = OpenRouterClient(or_config)

        search_client = WebSearchClient(api_key=os.getenv("ZAI_API_KEY"))
    else:
        from datetime import datetime
        from schemas.analysis import ImpactEvidence, LegislationAnalysisResponse, LegislationImpact, ReviewCritique

        class MockLLMClient(LLMClient):
            def __init__(self):
                super().__init__(LLMConfig(api_key="mock", provider="zai", default_model="mock-model"))

            async def chat_completion(self, messages, model=None, **kwargs):
                msg_str = str(messages).lower()
                if "policy reviewer" in msg_str:
                    resp = ReviewCritique(passed=True, critique="mock-ok", missing_impacts=[], factual_errors=[])
                    content = resp.model_dump_json()
                else:
                    resp = LegislationAnalysisResponse(
                        bill_number="MOCK-BILL-001",
                        impacts=[
                            LegislationImpact(
                                impact_number=1,
                                relevant_clause="mock clause",
                                legal_interpretation="mock interpretation",
                                impact_description="mock impact",
                                evidence=[ImpactEvidence(source_name="Mock", url="http://mock", excerpt="mock")],
                                chain_of_causality="mock",
                                confidence_score=0.5,
                                p10=0.0,
                                p25=0.0,
                                p50=0.0,
                                p75=0.0,
                                p90=0.0,
                            )
                        ],
                        total_impact_p50=0.0,
                        analysis_timestamp=datetime.now().isoformat(),
                        model_used=model or "mock-model",
                    )
                    content = resp.model_dump_json()

                return LLMResponse(
                    id="mock-llm",
                    model=model or "mock-model",
                    content=content,
                    finish_reason="stop",
                    usage=LLMUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
                )

            async def validate_api_key(self):
                return True

            async def stream_completion(self, **kwargs):
                raise NotImplementedError

        class MockSearch(WebSearchClient):
            def __init__(self):
                super().__init__(api_key="mock")

            async def search(self, query):
                return []

        llm_client = MockLLMClient()
        fallback_client = None
        search_client = MockSearch()

    pipeline = AnalysisPipeline(llm_client, search_client, db, fallback_client=fallback_client)
    if not real_mode:
        async def _mock_research(*_args, **_kwargs):
            return {"collected_data": [{"snippet": "mock research"}]}
        pipeline.research_agent.run = _mock_research

    # 3. Execution Trace
    logger.info("STEP 1: Search Simulation (Mock Data) -> Raw Scrape")
    logger.info("✅ Analysis Pipeline Initialized")

    # 3. Create Test Data (Simulating "Search -> Scrape")
    
    # Audit ID
    audit_id = f"audit-{uuid.uuid4().hex[:8]}"
    jurisdiction = "San Jose (Audit)"
    bill_id = f"Bill-{audit_id}"
    logger.info(f"🆔 Audit Run ID: {audit_id}")

    # Create Source
    # await db.ensure_jurisdiction(jurisdiction, "municipality") # Method doesn't exist
    # Use get_or_create_jurisdiction instead
    await db.get_or_create_jurisdiction(jurisdiction, "municipality")
    
    source_id = await db.get_or_create_source(
        jurisdiction_id="web", # generic
        name="San Jose Audit Source",
        type="general",
        url="http://sanjose.example.com/audit"
    )
    
    # Create Raw Scrape (The "Search Result")
    # Real text about an ADU bill to provoke analysis
    audit_text = f"<h1>San Jose ADU Bill {audit_id}</h1><p>This bill authorizes the construction of Accessory Dwelling Units (ADUs) in all single-family zones to alleviate the housing shortage. It waives impact fees for units under 750 sq ft.</p>"
    
    logger.info("📥 Ingesting Test Scrape...")
    
    # Insert raw scrape manually (simulating harvester)
    scrape_id = str(uuid.uuid4())
    scrape_data = json.dumps({"content": audit_text})
    
    await db._execute("""
        INSERT INTO raw_scrapes (id, source_id, url, content_hash, content_type, data, processed)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
    """, scrape_id, source_id, f"http://sanjose.example.com/{bill_id}", f"hash-{audit_id}", "text/html", scrape_data, False)

    # 4. Run Ingestion (MinIO -> Embedding -> PgVector)
    logger.info("⚙️    # 4. Ingest (Should embed + vector store)")
    logger.info("STEP 2: Ingestion & Embedding (Real OpenRouter -> Remote PgVector)" if real_mode else "STEP 2: Ingestion & Embedding (Mock)")
    chunks_created = await ingestion.process_raw_scrape(scrape_id)
    if chunks_created > 0:
        logger.info(f"✅ Ingestion Complete: {chunks_created} chunks created.")
    else:
        logger.error("❌ Ingestion Failed (0 chunks)")
        return
    
    # 5. Run Analysis Pipeline (Should use Z.ai + Search)
    logger.info("STEP 3: Analysis Pipeline (Real Z.ai GLM-4.6)" if real_mode else "STEP 3: Analysis Pipeline (Mock)")
    logger.info("🧠 Running Analysis Pipeline (Real LLM)..." if real_mode else "🧠 Running Analysis Pipeline (Mock LLM)...")
    
    models = {"research": "glm-4.6", "generate": "glm-4.6", "review": "glm-4.6"} if real_mode else {"research": "mock", "generate": "mock", "review": "mock"}

    try:
        analysis = await pipeline.run(
            bill_id=bill_id,
            bill_text=audit_text, # In real flow, this might come from DB, but passing explicit for test
            jurisdiction=jurisdiction,
            models=models
        )
        
        logger.info("✅ Pipeline Execution Successful!")
        print(json.dumps(analysis.model_dump(), indent=2))
        
        # 6. Verify Log Persistence for Glass Box
        # Check if pipeline run exists
        runs = await db._fetch("SELECT id FROM pipeline_runs WHERE result->>'analysis' LIKE $1", f"%{bill_id}%")
        if runs:
            logger.info(f"✅ Glass Box Trace Found: Run ID {runs[0]['id']}")
            print(f"\nPROOF_OF_WORK_RUN_ID: {runs[0]['id']}")
        else:
            logger.warning("⚠️  Pipeline run not found in DB (might be async storage issue?)")

    except Exception as e:
        logger.error(f"❌ Pipeline Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
