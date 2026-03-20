"""Factory for creating vector retrieval backends."""

from typing import Optional, Callable, Awaitable
from llm_common.retrieval import RetrievalBackend


def create_vector_backend(
    postgres_client=None,
    embedding_fn: Optional[Callable[[str], Awaitable[list[float]]]] = None,
    **kwargs,  # Swallow legacy args
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
        try:
            postgres_client = PostgresDB()
        except Exception:
            pass

    return LocalPgVectorBackend(
        table_name="document_chunks",
        postgres_client=postgres_client,
        embedding_fn=embedding_fn,
    )
