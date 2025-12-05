import asyncio
import os
import sys
from typing import List
from pydantic import BaseModel, Field

# Adjust path to find backend modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

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

if __name__ == "__main__":
    asyncio.run(main())
