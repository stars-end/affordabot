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
from llm_common.core import LLMConfig
from llm_common.providers import ZaiClient, OpenRouterClient
from llm_common.web_search import WebSearchClient
from llm_common.embeddings.openai import OpenAIEmbeddingService
# from llm_common.retrieval.pgvector_backend import PgVectorBackend # Not needed if using Local
from services.retrieval.local_pgvector import LocalPgVectorBackend

# Logging Setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - [E2E-AUDIT] - %(levelname)s - %(message)s')
logger = logging.getLogger("e2e_audit")

async def main():
    logger.info("🚀 Starting E2E Glass Box Audit Verification")
    
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
    if not os.getenv("OPENROUTER_API_KEY"):
        logger.error("❌ OPENROUTER_API_KEY missing! Required for embeddings.")
        return

    embedding_service = OpenAIEmbeddingService(
        base_url="https://openrouter.ai/api/v1",
        api_key=os.getenv("OPENROUTER_API_KEY"),
        # Using a reliable embedding model on OR, or fallback to Qwen
        # model="qwen/qwen-turbo", 
        # Actually Qwen Turbo is chat. We ideally need an embedding model.
        # If standard OpenAI client, use text-embedding-ada-002?
        # Let's try to stick to what UniversalHarvester uses or a known working one.
        # UniversalHarvester used "qwen/qwen3-embedding-8b" (mocked in mind or real?)
        # Let's use a standard one: 'amazon/titan-embed-text-v1' or check docs.
        # For now, let's use a placeholder and see if OR supports it, or use Z.ai if they have one?
        # Z.ai has embedding-2. Let's use Z.ai for embedding if OR is tricky?
        # User asked for "OpenRouter embedding workflow".
        # Let's assume "qwen/qwen-2-7b-instruct" acts as embedding? No.
        # I will use "text-embedding-ada-002" mapping if using OpenAI client directed at OR?
        # No, OR hosts specific models.
        # Let's use "amazon/titan-embed-text-v1" if available, or just mocking for the *audit* if real embedding is blocking?
        # User said "provide logs... embedding". I must try real.
        # Let's try standard 'text-embedding-3-small' if OR proxies it.
        # Safe bet: Z.ai embedding-3 (actually Z.ai supports standard OpenAI compat).
        # But Requirement: "OpenRouter... for embedding workflow".
        # I will use 'qwen/qwen-2.5-72b-instruct'? No.
        # Let's check if the client supports it.
        # Revert: UniversalHarvester config had model="qwen/qwen3-embedding-8b"
        # I will use that.
        model="qwen/qwen3-embedding-8b", 
        dimensions=4096
    )
    logger.info("✅ Embedding Service Initialized (OpenRouter)")

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

    # LLM Clients (Z.ai + Fallback)
    llm_config = LLMConfig(
        api_key=os.getenv("ZAI_API_KEY"), 
        provider="zai",
        default_model="glm-4.6" # Fix P0: Use confirmed generic model ID
    )
    llm_client = ZaiClient(llm_config)
    
    fallback_client = None
    if os.getenv("OPENROUTER_API_KEY"):
        or_config = LLMConfig(
            api_key=os.getenv("OPENROUTER_API_KEY"),
            provider="openrouter",
            default_model="openai/gpt-4o-mini"
        )
        fallback_client = OpenRouterClient(or_config)
    
    search_client = WebSearchClient(api_key=os.getenv("ZAI_API_KEY"))

    pipeline = AnalysisPipeline(llm_client, search_client, db, fallback_client=fallback_client)

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
    logger.info("STEP 2: Ingestion & Embedding (Real OpenRouter -> Remote PgVector)")
    chunks_created = await ingestion.process_raw_scrape(scrape_id)
    if chunks_created > 0:
        logger.info(f"✅ Ingestion Complete: {chunks_created} chunks created.")
    else:
        logger.error("❌ Ingestion Failed (0 chunks)")
        return
    
    # 5. Run Analysis Pipeline (Should use Z.ai + Search)
    logger.info("STEP 3: Analysis Pipeline (Real Z.ai GLM-4.6)")
    logger.info("🧠 Running Analysis Pipeline (Real LLM)...")
    
    models = {
        "research": "glm-4.6",
        "generate": "glm-4.6",
        "review": "glm-4.6"
    }

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
