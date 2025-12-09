"""Retrieval backend implementations."""

from llm_common.retrieval.backends.pgvector_backend import SupabasePgVectorBackend

# Import pgvector backend if dependencies are available
try:
    from llm_common.retrieval.backends.pg_backend import (
        PgVectorBackend,
        create_pg_backend,
    )

    __all__ = [
        "PgVectorBackend",  # Recommended: Generic pgvector for Railway Postgres
        "create_pg_backend",  # Factory function for easy instantiation
        "SupabasePgVectorBackend",  # Legacy: Supabase-specific (deprecated)
    ]
except ImportError:
    # pgvector dependencies not installed
    __all__ = [
        "SupabasePgVectorBackend",  # Legacy: Supabase-specific (deprecated)
    ]
