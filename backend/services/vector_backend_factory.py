"""Factory for creating vector retrieval backends."""

from typing import Optional, Callable, Awaitable
from llm_common.retrieval import RetrievalBackend


def create_vector_backend(
    postgres_client=None, 
    embedding_fn: Optional[Callable[[str], Awaitable[list[float]]]] = None,
    **kwargs # Swallow legacy args
) -> RetrievalBackend:
    """
    Create vector retrieval backend (LocalPgVector for V3).
    
    Args:
        postgres_client: PostgresDB instance (required for LocalPgVector)
        embedding_fn: Async function to generate embeddings
        
    Returns:
        RetrievalBackend instance
    """
    # V3: Use LocalPgVectorBackend to fix JSONB encoding issues and control logic
    from services.retrieval.local_pgvector import LocalPgVectorBackend
    from db.postgres_client import PostgresDB
    
    if not postgres_client:
        # If not provided, assume Env var available and instantiate
        # But allow fallback if caller intends to set it later? 
        # LocalPgVectorBackend checks for db presence lazily in upsert usually,
        # but better to provide it.
        try:
             postgres_client = PostgresDB()
             # Note: connecting might be required later
        except Exception:
             pass

    return LocalPgVectorBackend(
        table_name="documents",
        postgres_client=postgres_client
    )
