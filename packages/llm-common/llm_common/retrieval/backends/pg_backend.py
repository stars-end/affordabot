"""Generic pgvector backend for Railway Postgres retrieval.

This backend uses SQLAlchemy with asyncpg to connect to Railway Postgres
with the pgvector extension. It replaces the Supabase-specific implementation
with a more portable solution that works with any pgvector-enabled Postgres.

Recommended for: Prime Radiant and Affordabot production deployments on Railway.
"""

from typing import Any, Callable, Optional

try:
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
    from pgvector.sqlalchemy import Vector  # type: ignore
except ImportError as e:
    raise ImportError(
        "PgVectorBackend requires optional dependencies. "
        "Install with: pip install llm-common[pgvector] "
        "or: poetry install -E pgvector"
    ) from e

from llm_common.retrieval.base import RetrievalBackend
from llm_common.retrieval.models import RetrievedChunk


class PgVectorBackend(RetrievalBackend):
    """Generic pgvector backend using SQLAlchemy + asyncpg.

    This backend connects directly to Railway Postgres using DATABASE_URL
    and uses native pgvector operators for similarity search.

    Example:
        ```python
        from llm_common.retrieval.backends import PgVectorBackend

        async def embed_query(text: str) -> list[float]:
            # Your embedding logic (OpenAI, local model, etc.)
            return embedding_vector

        backend = PgVectorBackend(
            database_url="postgresql+asyncpg://user:pass@host/db",
            table="document_chunks",
            embed_fn=embed_query,
            vector_dimensions=1536  # For OpenAI embeddings
        )

        # Search
        results = await backend.retrieve("What is RAG?", top_k=5)

        # Ingest
        await backend.upsert([
            {
                "content": "RAG stands for Retrieval-Augmented Generation",
                "source": "docs/rag.md",
                "metadata": {"section": "intro"}
            }
        ])

        await backend.close()
        ```

    Args:
        database_url: PostgreSQL connection URL (postgresql+asyncpg://...)
        table: Name of the table containing embeddings
        embed_fn: Async function to generate embeddings from text
        vector_dimensions: Dimensionality of embedding vectors (e.g., 1536)
        vector_col: Name of the vector column (default: "embedding")
        text_col: Name of the text content column (default: "content")
        source_col: Name of the source identifier column (default: "source")
        id_col: Name of the ID column (default: "id")
        metadata_col: Name of the JSONB metadata column (default: "metadata")
        pool_size: SQLAlchemy connection pool size (default: 5)
        max_overflow: Maximum overflow connections (default: 10)
    """

    def __init__(
        self,
        database_url: str,
        table: str,
        embed_fn: Callable[[str], Any],
        vector_dimensions: int,
        vector_col: str = "embedding",
        text_col: str = "content",
        source_col: str = "source",
        id_col: str = "id",
        metadata_col: str = "metadata",
        pool_size: int = 5,
        max_overflow: int = 10,
    ) -> None:
        """Initialize the pgvector backend."""
        self.database_url = database_url
        self.table = table
        self.embed_fn = embed_fn
        self.vector_dimensions = vector_dimensions
        self.vector_col = vector_col
        self.text_col = text_col
        self.source_col = source_col
        self.id_col = id_col
        self.metadata_col = metadata_col

        # Create async engine with connection pooling
        self.engine: AsyncEngine = create_async_engine(
            database_url,
            pool_size=pool_size,
            max_overflow=max_overflow,
            echo=False,  # Set to True for SQL debugging
        )

    async def retrieve(
        self,
        query: str,
        top_k: int = 5,
        min_score: Optional[float] = None,
        filters: Optional[dict[str, Any]] = None,
    ) -> list[RetrievedChunk]:
        """Retrieve relevant chunks using pgvector similarity search.

        Uses cosine distance (<-> operator) for similarity. Scores are
        converted to similarity (1 - distance) for consistency with
        other backends.

        Args:
            query: Query text to search for
            top_k: Number of results to return
            min_score: Minimum similarity score threshold (0.0-1.0)
            filters: Dictionary of metadata filters (key: value)

        Returns:
            List of RetrievedChunk objects ordered by relevance

        Raises:
            ValueError: If embed_fn not provided or query cannot be embedded
            RuntimeError: If database query fails
        """
        # Generate query embedding
        query_embedding = await self.embed_fn(query)

        # Ensure query_embedding is a list
        if not isinstance(query_embedding, list):
            query_embedding = list(query_embedding)

        # Build SQL query with pgvector operators
        # Note: <-> is cosine distance, we convert to similarity (1 - distance)
        sql_query = f"""
            SELECT
                {self.id_col},
                {self.text_col},
                {self.source_col},
                {self.metadata_col},
                1 - ({self.vector_col} <-> :query_embedding) as similarity
            FROM {self.table}
        """

        # Add metadata filters if provided
        where_clauses = []
        params = {"query_embedding": str(query_embedding)}

        if filters:
            for key, value in filters.items():
                # JSONB filter: metadata->>'key' = 'value'
                where_clauses.append(f"{self.metadata_col}->>:filter_key_{key} = :filter_val_{key}")
                params[f"filter_key_{key}"] = key
                params[f"filter_val_{key}"] = str(value)

        if where_clauses:
            sql_query += " WHERE " + " AND ".join(where_clauses)

        # Order by similarity and limit
        sql_query += f" ORDER BY similarity DESC LIMIT {top_k}"

        # Execute query
        try:
            async with self.engine.begin() as conn:
                result = await conn.execute(text(sql_query), params)
                rows = result.fetchall()
        except Exception as e:
            raise RuntimeError(f"Failed to execute similarity search: {e}") from e

        # Convert to RetrievedChunk objects
        chunks = []
        for row in rows:
            # Apply min_score filter
            score = float(row.similarity)
            if min_score is not None and score < min_score:
                continue

            # Extract metadata (stored as JSONB)
            metadata_dict = row.metadata if row.metadata else {}

            chunks.append(
                RetrievedChunk(
                    content=row[self.text_col],
                    score=score,
                    source=row[self.source_col],
                    metadata=metadata_dict,
                    chunk_id=str(row[self.id_col]),
                    embedding=None,  # Don't return embeddings to save bandwidth
                )
            )

        return chunks

    async def upsert(
        self,
        chunks: list[dict[str, Any]],
    ) -> None:
        """Upsert chunks into the database.

        Each chunk dict should contain:
        - content: Text content (required)
        - source: Source identifier (required)
        - metadata: Dictionary of metadata (optional)
        - chunk_id: Unique ID (optional, will be generated if not provided)

        The embedding will be generated automatically using embed_fn.

        Args:
            chunks: List of chunk dictionaries to upsert

        Raises:
            ValueError: If required fields are missing
            RuntimeError: If database operation fails
        """
        if not chunks:
            return

        # Prepare chunks with embeddings
        prepared_chunks = []
        for chunk in chunks:
            if "content" not in chunk or "source" not in chunk:
                raise ValueError("Each chunk must have 'content' and 'source' fields")

            # Generate embedding
            embedding = await self.embed_fn(chunk["content"])
            if not isinstance(embedding, list):
                embedding = list(embedding)

            prepared_chunks.append(
                {
                    "id": chunk.get("chunk_id") or chunk.get("id"),
                    "content": chunk["content"],
                    "source": chunk["source"],
                    "metadata": chunk.get("metadata", {}),
                    "embedding": embedding,
                }
            )

        # Build upsert SQL (PostgreSQL INSERT ... ON CONFLICT DO UPDATE)
        upsert_sql = f"""
            INSERT INTO {self.table}
                ({self.id_col}, {self.text_col}, {self.source_col},
                 {self.metadata_col}, {self.vector_col})
            VALUES
                (:id, :content, :source, :metadata, :embedding)
            ON CONFLICT ({self.id_col})
            DO UPDATE SET
                {self.text_col} = EXCLUDED.{self.text_col},
                {self.source_col} = EXCLUDED.{self.source_col},
                {self.metadata_col} = EXCLUDED.{self.metadata_col},
                {self.vector_col} = EXCLUDED.{self.vector_col}
        """

        try:
            async with self.engine.begin() as conn:
                for chunk in prepared_chunks:
                    await conn.execute(text(upsert_sql), chunk)
        except Exception as e:
            raise RuntimeError(f"Failed to upsert chunks: {e}") from e

    async def get_by_id(self, chunk_id: str) -> Optional[RetrievedChunk]:
        """Retrieve a specific chunk by ID.

        Args:
            chunk_id: The unique identifier for the chunk

        Returns:
            RetrievedChunk if found, None otherwise
        """
        sql_query = f"""
            SELECT
                {self.id_col},
                {self.text_col},
                {self.source_col},
                {self.metadata_col}
            FROM {self.table}
            WHERE {self.id_col} = :chunk_id
        """

        try:
            async with self.engine.begin() as conn:
                result = await conn.execute(text(sql_query), {"chunk_id": chunk_id})
                row = result.fetchone()

            if not row:
                return None

            metadata_dict = row.metadata if row.metadata else {}

            return RetrievedChunk(
                content=row[self.text_col],
                score=1.0,  # Direct retrieval has perfect match score
                source=row[self.source_col],
                metadata=metadata_dict,
                chunk_id=str(row[self.id_col]),
            )
        except Exception:
            return None

    async def health_check(self) -> bool:
        """Check if the backend is healthy and can connect to database.

        Returns:
            True if backend can connect and pgvector extension is available
        """
        try:
            async with self.engine.begin() as conn:
                # Check connection and pgvector extension
                result = await conn.execute(
                    text("SELECT COUNT(*) FROM pg_extension WHERE extname = 'vector'")
                )
                row = result.fetchone()
                return row[0] > 0 if row else False
        except Exception:
            return False

    async def close(self) -> None:
        """Close database connections and clean up resources."""
        await self.engine.dispose()

    async def __aenter__(self) -> "PgVectorBackend":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()


def create_pg_backend(
    database_url: str,
    table: str,
    embed_fn: Callable[[str], Any],
    vector_dimensions: int = 1536,
    **kwargs: Any,
) -> PgVectorBackend:
    """Factory function to create a PgVectorBackend instance.

    This is a convenience function for easy construction from environment
    variables or configuration.

    Args:
        database_url: PostgreSQL connection URL (from Railway env)
        table: Table name for vector storage
        embed_fn: Embedding function
        vector_dimensions: Embedding vector dimensions (default: 1536 for OpenAI)
        **kwargs: Additional arguments passed to PgVectorBackend

    Returns:
        Configured PgVectorBackend instance

    Example:
        ```python
        import os
        from llm_common.retrieval.backends.pg_backend import create_pg_backend

        backend = create_pg_backend(
            database_url=os.getenv("DATABASE_URL"),
            table="document_chunks",
            embed_fn=my_embed_function,
        )
        ```
    """
    return PgVectorBackend(
        database_url=database_url,
        table=table,
        embed_fn=embed_fn,
        vector_dimensions=vector_dimensions,
        **kwargs,
    )
