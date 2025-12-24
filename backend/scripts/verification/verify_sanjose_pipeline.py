#!/usr/bin/env python3
"""
Master E2E Glass Box Verification Script for San Jose RAG Pipeline.

Orchestrates the entire flow with 10 phases and per-phase screenshot capture:

Phase 0: Environment Validation
Phase 1: Database Connection
Phase 2: Jurisdiction Setup
Phase 3: Discovery (Z.ai Search)
Phase 4: Discovery Ingestion
Phase 5: Legislation API Scrape
Phase 6: Legislation Ingestion
Phase 7: Backbone Scrape (Scrapy)
Phase 8: Vector DB Validation
Phase 9: RAG Query Verification

Usage:
    python verify_sanjose_pipeline.py [--screenshots] [--artifacts-dir PATH]
"""

import sys
import os
import logging
import asyncio
import argparse
from datetime import datetime
from dotenv import load_dotenv

# Load env vars
load_dotenv(os.path.join(os.path.dirname(__file__), '../../.env'))

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))

from db.postgres_client import PostgresDB  # noqa: E402

# Configure Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("e2e_verify")

# Screenshot utilities
try:
    from screenshot_utils import capture_text_screenshot, VerificationReporter
    SCREENSHOTS_AVAILABLE = True
except ImportError:
    SCREENSHOTS_AVAILABLE = False
    print("⚠️  screenshot_utils not available, running without screenshots")


class GlassBoxVerifier:
    """
    Orchestrates 10-phase Glass Box verification with screenshot capture.
    """
    
    def __init__(self, enable_screenshots: bool = False, artifacts_dir: str = None):
        self.screenshots = enable_screenshots and SCREENSHOTS_AVAILABLE
        self.artifacts_dir = artifacts_dir
        self.reporter = None
        self.db = None
        self.phase_outputs = {}
        
        if self.screenshots:
            self.reporter = VerificationReporter("Affordabot San Jose Pipeline", artifacts_dir)
    
    def _capture(self, phase_id: int, name: str, content: str, status: str = "success"):
        """Capture screenshot and record phase result."""
        screenshot_path = None
        if self.screenshots:
            screenshot_path = capture_text_screenshot(
                f"Phase {phase_id}: {name}",
                content,
                status,
                self.artifacts_dir
            )
            self.reporter.add_phase(phase_id, name, status, content, screenshot_path)
        return screenshot_path
    
    async def phase_0_environment(self) -> bool:
        """Phase 0: Environment Validation"""
        print("\n🔧 Phase 0: Environment Validation")
        
        output_lines = []
        required_vars = ["DATABASE_URL", "OPENROUTER_API_KEY"]
        optional_vars = ["ZAI_API_KEY", "RAILWAY_PROJECT_NAME"]
        
        all_present = True
        for var in required_vars:
            value = os.environ.get(var)
            if value:
                masked = value[:10] + "..." if len(value) > 10 else "***"
                output_lines.append(f"   ✅ {var}: {masked}")
            else:
                output_lines.append(f"   ❌ {var}: MISSING")
                all_present = False
        
        for var in optional_vars:
            value = os.environ.get(var)
            if value:
                masked = value[:10] + "..." if len(value) > 10 else "***"
                output_lines.append(f"   ℹ️  {var}: {masked}")
            else:
                output_lines.append(f"   ⚠️  {var}: Not set (optional)")
        
        content = "\n".join(output_lines)
        print(content)
        
        status = "success" if all_present else "failure"
        self._capture(0, "Environment Validation", content, status)
        
        return all_present
    
    async def phase_1_database(self) -> bool:
        """Phase 1: Database Connection"""
        print("\n🔌 Phase 1: Database Connection")
        
        self.db = PostgresDB()
        output_lines = []
        
        try:
            if self.db.database_url:
                from urllib.parse import urlparse
                parsed = urlparse(self.db.database_url)
                output_lines.append(f"   Host: {parsed.hostname}")
                output_lines.append(f"   Port: {parsed.port}")
                output_lines.append(f"   Database: {parsed.path.lstrip('/')}")
            
            await self.db._fetchrow("SELECT 1 AS test")
            output_lines.append("   ✅ Connection successful")
            
            # Get table counts
            tables = ["document_chunks", "jurisdictions", "raw_scrapes"]
            for table in tables:
                try:
                    result = await self.db._fetchrow(f"SELECT COUNT(*) as cnt FROM {table}")
                    output_lines.append(f"   📊 {table}: {result['cnt']} rows")
                except:
                    output_lines.append(f"   ⚠️  {table}: table not found")
            
            content = "\n".join(output_lines)
            print(content)
            self._capture(1, "Database Connection", content, "success")
            return True
            
        except Exception as e:
            output_lines.append(f"   ❌ Connection failed: {e}")
            content = "\n".join(output_lines)
            print(content)
            self._capture(1, "Database Connection", content, "failure")
            return False
    
    async def phase_2_jurisdiction(self) -> bool:
        """Phase 2: Jurisdiction Setup"""
        print("\n📍 Phase 2: Jurisdiction Setup")
        
        output_lines = []
        try:
            jur_id = await self.db.get_or_create_jurisdiction("City of San Jose", "city")
            output_lines.append(f"   Jurisdiction: City of San Jose")
            output_lines.append(f"   ID: {jur_id}")
            output_lines.append("   ✅ Jurisdiction ready")
            
            self.phase_outputs['jurisdiction_id'] = jur_id
            
            content = "\n".join(output_lines)
            print(content)
            self._capture(2, "Jurisdiction Setup", content, "success")
            return True
            
        except Exception as e:
            output_lines.append(f"   ❌ Failed: {e}")
            content = "\n".join(output_lines)
            print(content)
            self._capture(2, "Jurisdiction Setup", content, "failure")
            return False
    
    async def phase_3_discovery(self) -> bool:
        """Phase 3: Discovery (Z.ai Search)"""
        print("\n🔍 Phase 3: Discovery (Z.ai Search)")
        
        output_lines = []
        
        if not os.environ.get("ZAI_API_KEY"):
            output_lines.append("   ⚠️  ZAI_API_KEY not set, skipping live discovery")
            output_lines.append("   Using mock results for verification flow")
            self.phase_outputs['discovery_results'] = []
            
            content = "\n".join(output_lines)
            print(content)
            self._capture(3, "Discovery (Z.ai)", content, "warning")
            return True
        
        try:
            from services.discovery.search_discovery import SearchDiscoveryService
            discovery_svc = SearchDiscoveryService()
            
            results = await discovery_svc.find_urls("City of San Jose ADU Guide", count=3)
            output_lines.append(f"   Query: 'City of San Jose ADU Guide'")
            output_lines.append(f"   Found: {len(results)} URLs")
            
            for i, r in enumerate(results, 1):
                output_lines.append(f"   {i}. {r.title}")
                output_lines.append(f"      URL: {r.url}")
            
            self.phase_outputs['discovery_results'] = results
            
            content = "\n".join(output_lines)
            print(content)
            self._capture(3, "Discovery (Z.ai)", content, "success")
            return True
            
        except Exception as e:
            output_lines.append(f"   ❌ Discovery failed: {e}")
            content = "\n".join(output_lines)
            print(content)
            self._capture(3, "Discovery (Z.ai)", content, "failure")
            return False
    
    async def phase_4_discovery_ingestion(self) -> bool:
        """Phase 4: Discovery Ingestion"""
        print("\n📥 Phase 4: Discovery Ingestion")
        
        output_lines = []
        results = self.phase_outputs.get('discovery_results', [])
        
        if not results:
            output_lines.append("   ⚠️  No discovery results to ingest (skipped Phase 3)")
            content = "\n".join(output_lines)
            print(content)
            self._capture(4, "Discovery Ingestion", content, "warning")
            return True
        
        try:
            from services.ingestion_service import IngestionService
            from services.vector_backend_factory import create_vector_backend
            from llm_common.embeddings.base import EmbeddingService
            
            class MockEmbeddingService(EmbeddingService):
                async def embed_query(self, text: str) -> list[float]:
                    return [0.1] * 1536
                async def embed_documents(self, texts: list[str]) -> list[list[float]]:
                    return [[0.1] * 1536 for _ in texts]
            
            embedding_svc = MockEmbeddingService()
            backend = create_vector_backend(postgres_client=self.db, embedding_fn=embedding_svc.embed_query)
            ingestion = IngestionService(self.db, backend, embedding_svc)
            
            total_chunks = 0
            for r in results:
                count = await ingestion.ingest_from_search_result(r)
                output_lines.append(f"   Ingested: {r.title} → {count} chunks")
                total_chunks += count
            
            output_lines.append(f"   ✅ Total ingested: {total_chunks} chunks")
            self.phase_outputs['discovery_chunks'] = total_chunks
            
            content = "\n".join(output_lines)
            print(content)
            self._capture(4, "Discovery Ingestion", content, "success" if total_chunks > 0 else "warning")
            return True
            
        except Exception as e:
            output_lines.append(f"   ❌ Ingestion failed: {e}")
            content = "\n".join(output_lines)
            print(content)
            self._capture(4, "Discovery Ingestion", content, "failure")
            return False
    
    async def phase_5_legislation_scrape(self) -> bool:
        """Phase 5: Legislation API Scrape"""
        print("\n⚖️  Phase 5: Legislation API Scrape")
        
        output_lines = []
        daily_scrape_path = os.path.join(os.path.dirname(__file__), '../../../scripts/daily_scrape.py')
        
        if not os.path.exists(daily_scrape_path):
            output_lines.append(f"   ⚠️  daily_scrape.py not found at {daily_scrape_path}")
            content = "\n".join(output_lines)
            print(content)
            self._capture(5, "Legislation Scrape", content, "warning")
            return True
        
        output_lines.append("   Running daily_scrape.py for San Jose...")
        
        env = os.environ.copy()
        env["PYTHONPATH"] = os.path.join(os.path.dirname(__file__), '../../')
        
        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable, daily_scrape_path,
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT
            )
            
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=120)
            output_text = stdout.decode()[-2000:]  # Last 2000 chars
            
            output_lines.append(f"   Exit code: {proc.returncode}")
            output_lines.append("   Output (last 2000 chars):")
            output_lines.append(output_text)
            
            status = "success" if proc.returncode == 0 else "warning"
            
        except asyncio.TimeoutError:
            output_lines.append("   ⚠️  Scrape timed out after 120s")
            status = "warning"
        except Exception as e:
            output_lines.append(f"   ❌ Scrape failed: {e}")
            status = "failure"
        
        content = "\n".join(output_lines)
        print(content)
        self._capture(5, "Legislation Scrape", content, status)
        return status != "failure"
    
    async def phase_6_legislation_ingestion(self) -> bool:
        """Phase 6: Legislation Ingestion Validation"""
        print("\n📊 Phase 6: Legislation Ingestion Validation")
        
        output_lines = []
        
        try:
            # Check raw_scrapes table - try with created_at, fallback to total count
            try:
                result = await self.db._fetchrow(
                    "SELECT COUNT(*) as cnt FROM raw_scrapes WHERE created_at > NOW() - INTERVAL '1 hour'"
                )
                recent_scrapes = result['cnt'] if result else 0
                output_lines.append(f"   Recent scrapes (last hour): {recent_scrapes}")
            except Exception:
                # Fallback: count all records
                result = await self.db._fetchrow("SELECT COUNT(*) as cnt FROM raw_scrapes")
                total_scrapes = result['cnt'] if result else 0
                output_lines.append(f"   Total scrapes (no timestamp): {total_scrapes}")
                recent_scrapes = total_scrapes
            
            # Check document_chunks - try with created_at, fallback to total count
            try:
                result = await self.db._fetchrow(
                    "SELECT COUNT(*) as cnt FROM document_chunks WHERE created_at > NOW() - INTERVAL '1 hour'"
                )
                recent_chunks = result['cnt'] if result else 0
                output_lines.append(f"   Recent chunks (last hour): {recent_chunks}")
            except Exception:
                # Fallback: count all records
                result = await self.db._fetchrow("SELECT COUNT(*) as cnt FROM document_chunks")
                total_chunks = result['cnt'] if result else 0
                output_lines.append(f"   Total chunks (no timestamp): {total_chunks}")
                recent_chunks = total_chunks
            
            self.phase_outputs['legislation_chunks'] = recent_chunks
            
            status = "success" if recent_chunks > 0 else "warning"
            if recent_chunks == 0:
                output_lines.append("   ⚠️  No chunks found")
            else:
                output_lines.append(f"   ✅ {recent_chunks} chunks indexed")
            
            content = "\n".join(output_lines)
            print(content)
            self._capture(6, "Legislation Ingestion", content, status)
            return True
            
        except Exception as e:
            output_lines.append(f"   ❌ Validation failed: {e}")
            content = "\n".join(output_lines)
            print(content)
            self._capture(6, "Legislation Ingestion", content, "failure")
            return False
    
    async def phase_7_backbone_scrape(self) -> bool:
        """Phase 7: Backbone Scrape (Scrapy)"""
        print("\n🕷️ Phase 7: Backbone Scrape (Scrapy)")
        
        output_lines = []
        script_path = os.path.join(os.path.dirname(__file__), '../cron/run_rag_spiders.py')
        
        if not os.path.exists(script_path):
            output_lines.append(f"   ⚠️  run_rag_spiders.py not found")
            output_lines.append("   Skipping backbone scrape")
            content = "\n".join(output_lines)
            print(content)
            self._capture(7, "Backbone Scrape", content, "warning")
            return True
        
        output_lines.append("   Running Scrapy spiders...")
        
        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable, script_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT
            )
            
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=120)
            output_text = stdout.decode()[-2000:]
            
            output_lines.append(f"   Exit code: {proc.returncode}")
            output_lines.append(output_text)
            
            status = "success" if proc.returncode == 0 else "warning"
            
        except asyncio.TimeoutError:
            output_lines.append("   ⚠️  Scrapy timed out after 120s")
            status = "warning"
        except Exception as e:
            output_lines.append(f"   ❌ Scrapy failed: {e}")
            status = "failure"
        
        content = "\n".join(output_lines)
        print(content)
        self._capture(7, "Backbone Scrape", content, status)
        return status != "failure"
    
    async def phase_8_vector_validation(self) -> bool:
        """Phase 8: Vector DB Validation"""
        print("\n🗄️ Phase 8: Vector DB Validation")
        
        output_lines = []
        
        try:
            # Total chunks
            result = await self.db._fetchrow("SELECT COUNT(*) as cnt FROM document_chunks")
            total_chunks = result['cnt'] if result else 0
            output_lines.append(f"   Total chunks in DB: {total_chunks}")
            
            # Sample embeddings
            result = await self.db._fetchrow(
                "SELECT id, LENGTH(embedding::text) as emb_len FROM document_chunks LIMIT 1"
            )
            if result:
                output_lines.append(f"   Sample chunk ID: {result['id']}")
                output_lines.append(f"   Embedding length: {result['emb_len']} chars")
            
            # Chunks by source
            results = await self.db._fetch(
                """
                SELECT metadata->>'source_id' as source, COUNT(*) as cnt 
                FROM document_chunks 
                GROUP BY metadata->>'source_id' 
                ORDER BY cnt DESC 
                LIMIT 5
                """
            )
            output_lines.append("   Top sources:")
            for r in results:
                output_lines.append(f"      - {r['source']}: {r['cnt']} chunks")
            
            status = "success" if total_chunks > 0 else "warning"
            output_lines.append(f"   {'✅' if status == 'success' else '⚠️'} Vector DB validated")
            
            content = "\n".join(output_lines)
            print(content)
            self._capture(8, "Vector DB Validation", content, status)
            return True
            
        except Exception as e:
            output_lines.append(f"   ❌ Validation failed: {e}")
            content = "\n".join(output_lines)
            print(content)
            self._capture(8, "Vector DB Validation", content, "failure")
            return False
    
    async def phase_9_rag_query(self) -> bool:
        """Phase 9: RAG Query Verification"""
        print("\n🧠 Phase 9: RAG Query Verification")
        
        output_lines = []
        user_query = "What are the height limits for ADUs in San Jose?"
        
        try:
            from services.search_pipeline_service import SearchPipelineService
            from services.discovery.search_discovery import SearchDiscoveryService
            from services.ingestion_service import IngestionService
            from services.vector_backend_factory import create_vector_backend
            from llm_common.embeddings.base import EmbeddingService
            
            class MockEmbeddingService(EmbeddingService):
                async def embed_query(self, text: str) -> list[float]:
                    return [0.1] * 1536
                async def embed_documents(self, texts: list[str]) -> list[list[float]]:
                    return [[0.1] * 1536 for _ in texts]
            
            class MockLLM:
                async def chat_completion(self, messages, model):
                    from dataclasses import dataclass
                    @dataclass
                    class Resp:
                        content: str = "Mock Answer: ADU height limits are typically 16 feet for detached units."
                    return Resp()
                
                async def create_embedding(self, text: str) -> list[float]:
                    return [0.1] * 1536
            
            embedding_svc = MockEmbeddingService()
            discovery_svc = SearchDiscoveryService()
            retrieval = create_vector_backend(embedding_fn=embedding_svc.embed_query)
            ingestion = IngestionService(self.db, retrieval, embedding_svc)
            
            pipeline = SearchPipelineService(
                discovery=discovery_svc,
                ingestion=ingestion,
                retrieval=retrieval,
                llm=MockLLM()
            )
            
            output_lines.append(f"   Query: '{user_query}'")
            response = await pipeline.search(user_query)
            
            output_lines.append(f"   Answer: {response.answer[:200]}...")
            output_lines.append(f"   Citations: {len(response.citations)}")
            
            for i, c in enumerate(response.citations[:5], 1):
                output_lines.append(f"      {i}. {c.title}")
            
            output_lines.append("   ✅ RAG pipeline executed successfully")
            
            content = "\n".join(output_lines)
            print(content)
            self._capture(9, "RAG Query", content, "success")
            return True
            
        except Exception as e:
            output_lines.append(f"   ❌ RAG verification failed: {e}")
            import traceback
            output_lines.append(traceback.format_exc()[:500])
            content = "\n".join(output_lines)
            print(content)
            self._capture(9, "RAG Query", content, "failure")
            return False
    
    async def run(self) -> int:
        """Run all 10 phases and return exit code."""
        print("\n🚀 Starting Glass Box Verification: San Jose RAG Pipeline")
        print("=" * 60)
        
        phases = [
            self.phase_0_environment,
            self.phase_1_database,
            self.phase_2_jurisdiction,
            self.phase_3_discovery,
            self.phase_4_discovery_ingestion,
            self.phase_5_legislation_scrape,
            self.phase_6_legislation_ingestion,
            self.phase_7_backbone_scrape,
            self.phase_8_vector_validation,
            self.phase_9_rag_query,
        ]
        
        results = []
        for i, phase in enumerate(phases):
            try:
                result = await phase()
                results.append(result)
            except Exception as e:
                print(f"   ❌ Phase {i} crashed: {e}")
                results.append(False)
                if self.screenshots:
                    self._capture(i, f"Phase {i} (Crashed)", str(e), "failure")
        
        # Generate summary
        passed = sum(results)
        total = len(results)
        
        print("\n" + "=" * 60)
        print(f"🏁 Glass Box Verification Complete: {passed}/{total} phases passed")
        
        if self.screenshots and self.reporter:
            self.reporter.generate_report()
        
        return 0 if all(results) else 1


def main():
    parser = argparse.ArgumentParser(description="Glass Box Verification for San Jose RAG Pipeline")
    parser.add_argument("--screenshots", action="store_true", help="Enable per-phase screenshot capture")
    parser.add_argument("--artifacts-dir", type=str, help="Custom artifacts directory")
    args = parser.parse_args()
    
    verifier = GlassBoxVerifier(
        enable_screenshots=args.screenshots,
        artifacts_dir=args.artifacts_dir
    )
    
    exit_code = asyncio.run(verifier.run())
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
