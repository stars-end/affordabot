"""Factory for creating vector retrieval backends."""

import os
from typing import Optional, Callable, Awaitable
from llm_common.retrieval import RetrievalBackend


def create_vector_backend(
    postgres_client=None, # Not used directly by create_pg_backend but kept for signature compat if needed, or better, remove it?
    # Actually, create_pg_backend takes database_url.
    # Caller can pass DSN if they have it, or we read Env.
    # postgres_client argument was added by me in run_rag_spiders.py.
    # Let's support it or just rely on Env.
    # Best to rely on Env for create_pg_backend as it handles connection pool itself.
    embedding_fn: Optional[Callable[[str], Awaitable[list[float]]]] = None
) -> RetrievalBackend:
    """
    Create vector retrieval backend (PgVector only).
    
    Args:
        postgres_client: Ignored (legacy compat)
        embedding_fn: Async function to generate embeddings
        
    Returns:
        RetrievalBackend instance
        
    Environment Variables:
        DATABASE_URL: PostgreSQL connection string
    """
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
