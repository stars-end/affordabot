"""Factory for creating vector retrieval backends with feature flag support."""

import os
from typing import Optional, Callable, Awaitable
from llm_common.retrieval import RetrievalBackend


def create_vector_backend(
    supabase_client=None,
    embedding_fn: Optional[Callable[[str], Awaitable[list[float]]]] = None
) -> RetrievalBackend:
    """
    Create vector retrieval backend based on feature flag.
    
    Args:
        supabase_client: Supabase client (for legacy backend)
        embedding_fn: Async function to generate embeddings
        
    Returns:
        RetrievalBackend instance
        
    Environment Variables:
        USE_PGVECTOR_RAG: "true" to use PgVectorBackend, "false" for SupabasePgVectorBackend
        DATABASE_URL: PostgreSQL connection string (for PgVectorBackend)
    """
    use_pgvector = os.getenv("USE_PGVECTOR_RAG", "false").lower() == "true"
    
    if use_pgvector:
        # New: Generic PgVectorBackend (llm-common 0.4.0+)
        from llm_common.retrieval.backends import create_pg_backend
        
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise ValueError("DATABASE_URL required for PgVectorBackend")
        
        # Ensure asyncpg driver is used
        if database_url.startswith("postgresql://"):
            database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        elif database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql+asyncpg://", 1)
        
        return create_pg_backend(
            database_url=database_url,
            table="documents",  # Keep existing table
            vector_dimensions=4096,  # Qwen embedding dimensions
            embed_fn=embedding_fn
        )
    else:
        # Legacy: Supabase-specific backend (llm-common 0.3.0)
        from llm_common.retrieval.backends import SupabasePgVectorBackend
        
        if not supabase_client:
            raise ValueError("supabase_client required for SupabasePgVectorBackend")
        
        return SupabasePgVectorBackend(
            supabase_client=supabase_client,
            table="documents",
            embed_fn=embedding_fn
        )
