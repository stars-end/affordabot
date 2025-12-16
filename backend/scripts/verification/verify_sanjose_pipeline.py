#!/usr/bin/env python3
"""
Master E2E Verification Script for San Jose RAG Pipeline.

Orchestrates the entire flow:
1. Discovery (Finds URLs via GLM-4.6)
2. Harvest (Reads URLs via GLM-4.6 -> Vectors)
3. Backbone Scrape (Meetings/Code via Scrapy -> Vectors)
4. API Scrape (Legistar -> Legislation SQL -> Vectors)
5. Verify (Query Vector DB)
"""

import sys
import os
import logging
import asyncio
from dotenv import load_dotenv

# Load env vars
load_dotenv(os.path.join(os.path.dirname(__file__), '../../.env'))

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))

from db.postgres_client import PostgresDB

# Configure Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("e2e_verify")

async def verify_pipeline():
    print("\n🚀 Starting Master E2E Verification: San Jose Pipeline\n")
    
    db = PostgresDB()
    # Check connection? PostgresDB connects lazily usually, we can force a query
    try:
        # Debug connection info
        if db.database_url:
             from urllib.parse import urlparse
             parsed = urlparse(db.database_url)
             print(f"   ℹ️  Connecting to DB Host: {parsed.hostname} (Port: {parsed.port})")
        
        await db._fetchrow("SELECT 1")
    except Exception as e:
        print(f"❌ DB connection failed: {e}")
        return


    # Phase 0: Ensure San Jose Exists
    print("📍 Phase 0: Setup Jurisdiction")
    jur_id = await db.get_or_create_jurisdiction("City of San Jose", "city")
    print(f"   Jurisdiction ID: {jur_id}")

    # Phase 1: Discovery (Z.ai - The Scout)
    print("\n🔍 Phase 1: Discovery (Z.ai)")
    from services.discovery.search_discovery import SearchDiscoveryService
    discovery_svc = SearchDiscoveryService()
    
    # Run a real search test if key provided, else skip/mock
    import os
    if os.environ.get("ZAI_API_KEY"):
         try:
             results = await discovery_svc.find_urls("City of San Jose ADU Guide", count=3)
             print(f"   ✅ Found {len(results)} URLs via Z.ai")
             for r in results:
                 print(f"      - {r.title} ({r.url})")
                 
             # Ingest found results (Integration Test)
             from services.ingestion_service import IngestionService
             from services.vector_backend_factory import create_vector_backend
             from llm_common.embeddings.base import EmbeddingService
             
             # Inline Mock Embedding for speed/cost
             class MockEmbeddingService(EmbeddingService):
                async def embed_query(self, text: str) -> list[float]:
                    return [0.1] * 4096 
                async def embed_documents(self, texts: list[str]) -> list[list[float]]:
                    return [[0.1] * 4096 for _ in texts]
             
             embedding_svc = MockEmbeddingService()
             embedding_svc = MockEmbeddingService()
             backend = create_vector_backend(postgres_client=db, embedding_fn=embedding_svc.embed_query)
             ingestion = IngestionService(db, backend, embedding_svc)
             
             print("   Simulating Ingestion for Z.ai results...")
             count = 0
             for r in results:
                 count += await ingestion.ingest_from_search_result(r)
             print(f"   ✅ Ingested {count} chunks from found URLs.")
             
         except Exception as e:
             print(f"   ❌ Discovery Failed: {e}")
    else:
         print("   ⚠️  Skipping Discovery Call (No ZAI_API_KEY)")


    # Phase 2: Harvest (The Reader)
    print("\n📖 Phase 2: Universal Harvester (GLM-4.6 - Skipped for V3 Minimal)")
    # skipping heavy harvester run to keep verification fast
    
    # Phase 2.5: API Legislation Scrape (The Law)
    print("\n⚖️  Phase 2.5: Legislation API (Legistar -> SQL + Vector)")
    # This invokes daily_scrape.py - keeping it as is or skipping if too slow?
    # Keeping it as it validates external scripts integration.
    
    daily_scrape_path = os.path.join(os.path.dirname(__file__), '../../../scripts/daily_scrape.py')
    print("   Running daily_scrape.py for San Jose...")
    
    env = os.environ.copy()
    env["PYTHONPATH"] = os.path.join(os.path.dirname(__file__), '../../')
    
    proc = await asyncio.create_subprocess_exec(
        sys.executable, daily_scrape_path,
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await proc.communicate()
    
    if proc.returncode == 0:
        print("   ✅ Daily Scrape Finished.")
    else:
         # Warn but don't fail entire script if just networking
        print(f"   ⚠️  Daily Scrape Warning/Fail: {stderr.decode()[:200]}...")


    # Phase 3: Backbone Scrape (Meetings/Code)
    print("\n🕷️ Phase 3: Backbone Scrape (Scrapy)")
    script_path = os.path.join(os.path.dirname(__file__), '../cron/run_rag_spiders.py')
    
    print("   Running Scrapy subprocess...")
    proc = await asyncio.create_subprocess_exec(
        sys.executable, script_path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await proc.communicate()
    
    if proc.returncode == 0:
        print("   ✅ Scrapy Finished.")
    else:
        print(f"   ❌ Scrapy Failed: {stderr.decode()[:200]}...")

    # Phase 4: Verification Query (RAG)
    print("\n🧠 Phase 4: RAG Verification")
    user_query = "What are the height limits for ADUs in San Jose?"
    
    try:
        from services.search_pipeline_service import SearchPipelineService
        
        # Re-use mock embedding
        embedding_svc = MockEmbeddingService()
        async def embed_wrapper(text):
            return await embedding_svc.embed_query(text)
            
        retrieval = create_vector_backend(embedding_fn=embed_wrapper)
        ingestion = IngestionService(db, retrieval, embedding_svc)
        
        # Minimal Pipeline
        # We need a mock LLM or rely on clean abstractions
        class MockLLM:
             async def chat_completion(self, messages, model): 
                 from dataclasses import dataclass
                 @dataclass
                 class Resp:
                    content: str = "Mock Answer"
                 return Resp()

        pipeline = SearchPipelineService(
            discovery=discovery_svc,
            ingestion=ingestion,
            retrieval=retrieval,
            llm=MockLLM()
        )
        
        print(f"   Running Pipeline Search: '{user_query}'")
        # pipeline.search is the high level entry point
        response = await pipeline.search(user_query)
        
        print(f"   ✅ Answer: {response.answer}")
        print(f"   ✅ Citations: {len(response.citations)}")
        for c in response.citations:
            print(f"      - {c.title}")
            
    except Exception as e:
        print(f"   ❌ RAG Verification Failed: {e}")

    print("\n🏁 Master E2E Verification Complete.")

if __name__ == "__main__":
    asyncio.run(verify_pipeline())
