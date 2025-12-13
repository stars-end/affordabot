import asyncio
import os
import sys
from typing import List
from pydantic import BaseModel, Field

# Adjust path to find backend modules AND llm-common
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../llm-common')))

from backend.services.routers.extraction_router import ExtractionRouter
from backend.services.discovery.search_discovery import SearchDiscoveryService

# --- LLM Keyword Strategy (Mock for now, would be LLM driven) ---
class KeywordStrategy(BaseModel):
    topic: str
    queries: List[str]

SAN_JOSE_STRATEGY = KeywordStrategy(
    topic="Affordable Housing in San Jose",
    queries=[
        "Find affordable housing ordinances in San Jose from 2024",
        "Find San Jose inclusionary housing implementation guidelines on municode", 
        "Find the 2023-2031 San Jose Housing Element PDF"
    ]
)

# --- Schema for Extraction ---
class ExtractedDocument(BaseModel):
    title: str = Field(..., description="Title of the document")
    content: str = Field(..., description="Full text content of the document")
    url: str = Field(..., description="Source URL")
    summary: str = Field(default="", description="Brief summary")

async def main():
    print("🚀 Starting End-to-End Pipeline Validation")
    print("=" * 60)
    
    # 1. Environment Check
    zai_key = os.environ.get("ZAI_API_KEY")
    if not zai_key:
        print("❌ Error: ZAI_API_KEY not found. Please add it to Railway Variables.")
        print("Required Env Var: ZAI_API_KEY")
        return

    # 2. Initialize Services
    discovery = SearchDiscoveryService(api_key=zai_key)
    router = ExtractionRouter(zai_api_key=zai_key)
    
    # 3. Execute Strategy
    all_urls = []
    print(f"📋 executing Strategy: {SAN_JOSE_STRATEGY.topic}")
    
    for query in SAN_JOSE_STRATEGY.queries:
        print(f"\nrunning query: {query}")
        results = await discovery.find_urls(query, count=2) # Limit to 2 per query for speed
        for res in results:
            print(f"  found: {res.title[:50]}... ({res.url[:40]}...)")
            all_urls.append(res.url)
            
    print("-" * 60)
    print(f"🔗 Total URLs Discovered: {len(all_urls)}")
    
    # --- DEMO FALLBACK: Inject URLs if Discovery failed (likely due to Env/Quota) ---
    if len(all_urls) == 0:
        print("\n⚠️ [DEMO MODE] 0 URLs found using Z.ai/DDG. Injecting TEST URLs to validate Router/Extraction logic:")
        all_urls = [
            "https://library.municode.com/ca/san_jose/codes/code_of_ordinances?nodeId=TIT1GEPR_CH1.01COAD_1.01.010TIRE", # SPA -> Playwright
            "https://www.sanjoseca.gov/your-government", # CMS -> Z.ai
            "https://iterm2.com/" # Simple -> Z.ai
        ]
        print(f"🔗 Total URLs After Injection: {len(all_urls)}")

    print("-" * 60)
    
    # 4. Ingestion & Routing
    results_data = []
    
    for url in all_urls:
        print(f"\nProcessing: {url}")
        try:
            # The Router decides which tool to use
            data = await router.extract(url, ExtractedDocument)
            
            # Simple summarization (mock) if extractor didn't do it
            snippet = data.content[:200].replace("\n", " ")
            print(f"✅ Success! Length: {len(data.content)} chars")
            print(f"   Snippet: {snippet}...")
            results_data.append(data)
            
        except Exception as e:
            print(f"❌ Failed: {e}")
            
    # 5. Summary Report
    print("\n" + "=" * 60)
    print("📊 PIPELINE SUMMARY")
    print("=" * 60)
    print(f"Processed: {len(results_data)} / {len(all_urls)} URLs")
    
    for doc in results_data:
        print(f"- [{len(doc.content)} chars] {doc.title} ({doc.url})")


    # 6. VECTOR STORAGE VALIDATION (Phase 4)
    print("\n" + "=" * 60)
    print("🧠 VECTOR STORAGE & EMBEDDINGS (Phase 4)")
    print("=" * 60)
    print("Configuring OpenRouter Embeddings (qwen/qwen3-embedding-8b)...")
    
    # Imports for Phase 4
    try:
        from llm_common.embeddings.openai import OpenAIEmbeddingService
        from llm_common.retrieval.base import RetrievalBackend, RetrievedChunk
        
        # Mock Backend to verify Ingestion logic without DB dependencies
        class MockPgVectorBackend(RetrievalBackend):
            async def upsert(self, chunks: List[RetrievedChunk]):
                print(f"   💾 [MOCK DB] Upserting {len(chunks)} chunks...")
                if chunks:
                    print(f"      Sample Embedding Dim: {len(chunks[0].embedding)}")
                    print(f"      Sample Chunk: {chunks[0].content[:50]}...")
                return len(chunks)
            
            async def query(self, embedding: List[float], limit: int = 5):
                return []

        # Setup Services
        embedding_service = OpenAIEmbeddingService(
            api_key=os.environ.get("OPENROUTER_API_KEY") or os.environ.get("ZAI_API_KEY"),
            base_url="https://openrouter.ai/api/v1",
            model="qwen/qwen3-embedding-8b"
        )
        
        # We manually chunk and embed one document to prove the pipeline
        if results_data:
            doc_to_ingest = results_data[0]
            print(f"Processing Document: {doc_to_ingest.title}")
            
            # 1. Chunking (Simple mock logic)
            chunks_text = [doc_to_ingest.content[i:i+500] for i in range(0, len(doc_to_ingest.content), 500)]
            chunks_text = [c for c in chunks_text if c.strip()][:3] # Take top 3 chunks
            print(f"   Generated {len(chunks_text)} chunks.")
            
            # 2. Embedding
            print("   Generating Embeddings via OpenRouter...")
            embeddings = await embedding_service.embed_documents(chunks_text)
            print(f"   ✅ Embeddings Generated! Count: {len(embeddings)}")
            
            # 3. Storage
            backend = MockPgVectorBackend()
            
            # Construct Chunks
            stored_chunks = []
            for i, (txt, emb) in enumerate(zip(chunks_text, embeddings)):
                stored_chunks.append(RetrievedChunk(
                    id=f"chunk_{i}",
                    content=txt,
                    embedding=emb,
                    document_id="doc_1",
                    chunk_id=f"chunk_{i}",
                    source=doc_to_ingest.url,
                    metadata={"title": doc_to_ingest.title}
                ))
                
            await backend.upsert(stored_chunks)
            print("✅ Phase 4 Validation: SUCCESS")
            
        else:
            print("⚠️ No documents to ingest. Skipping Phase 4 validation.")

    except Exception as e:
        import traceback
        print(f"❌ Phase 4 Validation Failed: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
