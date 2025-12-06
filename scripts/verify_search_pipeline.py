
import asyncio
import os
import sys
import logging

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), "../backend"))
# Add llm-common to path
sys.path.append(os.path.join(os.path.dirname(__file__), "../packages/llm-common"))

from supabase import create_client

from services.discovery.search_discovery import SearchDiscoveryService
from services.ingestion_service import IngestionService
from services.search_pipeline_service import SearchPipelineService
from services.storage.supabase_storage import SupabaseBlobStorage
from services.retrieval.custom_pgvector_backend import CustomPgVectorBackend

from llm_common import (
    SupabasePgVectorBackend, # Keep for type check if needed, but we use Custom
    WebSearchResult,
    OpenRouterClient,
    LLMConfig,
    OpenAIEmbeddingService
)

# Configure Logging
logging.basicConfig(level=logging.INFO)

async def main():
    # 1. Setup Clients
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY")
    zai_key = os.getenv("ZAI_API_KEY")
    
    keys = {
        "SUPABASE_URL": supabase_url,
        "SUPABASE_KEY": supabase_key,
        "ZAI_API_KEY": zai_key
    }
    
    # Try OpenAI or OpenRouter
    llm_key = os.getenv("OPENAI_API_KEY") or os.getenv("OPENROUTER_API_KEY")
    if not llm_key:
         keys["LLM_API_KEY"] = None
    
    missing = [k for k, v in keys.items() if not v]
    
    if missing:
        print(f"❌ Missing Environment Variables: {', '.join(missing)}")
        return

    supabase = create_client(supabase_url, supabase_key)
    
    # Common Services
    # Explicitly use OpenRouter if key is found (and provider arg if needed)
    # LLMClient might need config object or kwargs.
    # checking LLMClient.__init__ in code view earlier: takes `config: LLMConfig`.
    # But wait, LLMClient is ABSTRACT.
    # I need to instantiate `OpenRouterClient` or `ZaiClient` directly!
    # OR Use a factory if available.
    # `llm_common.__init__` exports `OpenRouterClient`.
    
    from llm_common import OpenRouterClient, LLMConfig
    
    llm_config = LLMConfig(
        api_key=llm_key,
        provider="openrouter", 
        default_model="openai/gpt-4o-mini" # Low cost for verification
    )
    llm_client = OpenRouterClient(llm_config)
    
    # If using OpenRouter for embeddings, we need OpenAIEmbeddingService with base_url?
    # Or just OpenAI key?
    # Phase 4 said "Unblocked via OpenRouter (qwen/qwen3-embedding-8b)".
    # So we should use OpenAI client pointing to OpenRouter.
    # Note: Using OpenAIEmbeddingService (Concrete) not EmbeddingService (Abstract)
    from llm_common import OpenAIEmbeddingService
    
    embedding_service = OpenAIEmbeddingService(
        api_key=llm_key,
        base_url="https://openrouter.ai/api/v1",
        model="text-embedding-3-small" # Start with standard, assuming OpenRouter routes it or use specific if known
        # Actually standard OpenAI embedding is usually separate. 
        # But if user says "Unblocked via OpenRouter", then OpenRouter provides an embedding endpoint compatible with OpenAI.
        # model="qwen/qwen3-embedding-8b" was noted.
    )

    # 2. Setup Vector Backend (Custom for Affordabot)
    vector_backend = CustomPgVectorBackend(
        supabase_client=supabase,
        table="documents",
        source_col=None, 
        metadata_cols=["document_id", "metadata"],
        embed_fn=embedding_service.embed_query
    )
    storage_backend = SupabaseBlobStorage(supabase)
    
    # Domain Services
    discovery = SearchDiscoveryService(api_key=zai_key)
    ingestion = IngestionService(
        supabase_client=supabase,
        vector_backend=vector_backend,
        embedding_service=embedding_service,
        storage_backend=storage_backend
    )
    
    # Pipeline
    pipeline = SearchPipelineService(
        discovery=discovery,
        ingestion=ingestion,
        retrieval=vector_backend,
        llm=llm_client
    )
    
    # 2. Run Query
    query = "What are the requirements for building an ADU in San Jose?"
    print(f"\n❓ Query: {query}")
    
    response = await pipeline.search(query, limit_sources=3)
    
    print("\n✅ Verification Result:")
    print(f"Answer: {response.answer[:200]}...") # Truncate
    print(f"Citations: {len(response.citations)}")
    print(f"Context Chunks Used: {len(response.context_used)}")
    
    if not response.context_used:
        print("❌ Failure: No context retrieved.")
        sys.exit(1)
        
    print("\n🎉 Pipeline Success!")

if __name__ == "__main__":
    asyncio.run(main())
