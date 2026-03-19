"""
Local PgVector Backend with embedder-backed retrieval.

Implements the canonical llm-common retrieval interface:
- retrieve(query, top_k, min_score, filters)

Supports jurisdiction/source filtering using metadata from bd-tytc.3.
"""

from typing import List, Dict, Any, Optional, Callable, Awaitable
import json
import logging
import os

from llm_common.retrieval import RetrievalBackend, RetrievedChunk

logger = logging.getLogger(__name__)


class LocalPgVectorBackend(RetrievalBackend):
    """
    Local implementation of PgVectorBackend using PostgresDB client.

    Implements the canonical llm-common retrieval interface with:
    - Embedder-backed text-to-vector query
    - Jurisdiction/source metadata filtering
    - Production-ready error handling (fail closed)
    """

    def __init__(
        self,
        table_name: str = "document_chunks",
        postgres_client: Any = None,
        embedding_fn: Optional[Callable[[str], Awaitable[List[float]]]] = None,
        fail_closed: bool = True,
    ):
        """
        Initialize LocalPgVectorBackend.

        Args:
            table_name: PostgreSQL table name for vector storage
            postgres_client: PostgresDB client instance
            embedding_fn: Async function to embed query text into vector
            fail_closed: If True, raise errors instead of returning empty results
        """
        self.table_name = table_name
        self.db = postgres_client
        self._embedding_fn = embedding_fn
        self._fail_closed = fail_closed

        if not self._embedding_fn:
            env_fail_closed = os.environ.get(
                "VECTOR_BACKEND_FAIL_CLOSED", "true"
            ).lower()
            if (
                env_fail_closed == "true"
                and os.environ.get("ENVIRONMENT", "development") == "production"
            ):
                logger.warning(
                    "LocalPgVectorBackend initialized without embedding_fn in production. "
                    "Text-based retrieval will fail."
                )

    async def upsert(self, chunks: List[Dict[str, Any]]) -> bool:
        """
        Upsert chunks into Postgres using pgvector.

        Args:
            chunks: List of chunk dictionaries with id, content, embedding, metadata, document_id

        Returns:
            True if successful, False otherwise
        """
        if not chunks:
            return True

        if not self.db:
            logger.error("LocalPgVectorBackend.upsert: No DB client provided")
            return False

        try:
            for chunk in chunks:
                query = f"""
                INSERT INTO {self.table_name} 
                (id, content, embedding, metadata, document_id)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (id) DO UPDATE SET
                    content = EXCLUDED.content,
                    embedding = EXCLUDED.embedding,
                    metadata = EXCLUDED.metadata;
                """

                embedding_val = str(chunk["embedding"])

                from uuid import UUID

                def json_serial(obj):
                    if isinstance(obj, UUID):
                        return str(obj)
                    raise TypeError(f"Type {type(obj)} not serializable")

                await self.db._execute(
                    query,
                    chunk["id"],
                    chunk["content"],
                    embedding_val,
                    json.dumps(chunk["metadata"], default=json_serial),
                    chunk.get("document_id"),
                )

            return True

        except Exception as e:
            logger.error(f"LocalPgVectorBackend.upsert failed: {e}")
            return False

    async def query(
        self,
        embedding: List[float],
        top_k: int = 5,
        min_score: float | None = None,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[RetrievedChunk]:
        """
        Query by embedding vector with optional filters.

        Args:
            embedding: Query embedding vector
            top_k: Maximum number of results
            min_score: Minimum similarity score threshold
            filters: Optional metadata filters (jurisdiction, source_system, etc.)

        Returns:
            List of RetrievedChunk objects
        """
        if not self.db:
            if self._fail_closed:
                raise RuntimeError(
                    "LocalPgVectorBackend: No DB client configured (fail_closed=True)"
                )
            return []

        try:
            embedding_val = str(embedding)

            where_clauses = []
            params = [embedding_val]
            param_idx = 2

            if filters:
                for key, value in filters.items():
                    if value is None:
                        continue
                    if key in ("jurisdiction", "source_system", "bill_number"):
                        where_clauses.append(f"metadata->>'{key}' = ${param_idx}")
                        params.append(str(value))
                        param_idx += 1
                    elif key == "source_id":
                        where_clauses.append(f"metadata->>'source_id' = ${param_idx}")
                        params.append(str(value))
                        param_idx += 1

            params.append(str(top_k))

            where_sql = ""
            if where_clauses:
                where_sql = "WHERE " + " AND ".join(where_clauses)

            query_sql = f"""
            SELECT id, content, metadata, embedding, document_id, 
                   1 - (embedding <=> $1) as similarity
            FROM {self.table_name}
            {where_sql}
            ORDER BY embedding <=> $1
            LIMIT ${param_idx}
            """

            rows = await self.db._fetch(query_sql, *params)

            results = []
            for row in rows:
                similarity = (
                    float(row.get("similarity", 0)) if row.get("similarity") else 0.0
                )

                if min_score is not None and similarity < min_score:
                    continue

                meta = row.get("metadata")
                if isinstance(meta, str):
                    meta = json.loads(meta)

                chunk = RetrievedChunk(
                    chunk_id=str(row["id"]) if row.get("id") else None,
                    content=row["content"],
                    embedding=None,
                    metadata=meta or {},
                    score=similarity,
                    source=meta.get("source_url")
                    or meta.get("url")
                    or meta.get("source_id")
                    or "unknown",
                )
                results.append(chunk)

            return results

        except Exception as e:
            logger.error(f"LocalPgVectorBackend.query failed: {e}")
            if self._fail_closed:
                raise
            return []

    async def retrieve(
        self,
        query: str,
        top_k: int = 5,
        min_score: float | None = None,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[RetrievedChunk]:
        """
        Retrieve documents by text query using embedding.

        This is the canonical llm-common retrieval interface.

        Args:
            query: Text query to embed and search
            top_k: Maximum number of results (default 5)
            min_score: Minimum similarity score threshold (default 0.0)
            filters: Optional metadata filters

        Returns:
            List of RetrievedChunk objects

        Raises:
            RuntimeError: If embedding_fn is not configured and fail_closed=True
        """
        if not self._embedding_fn:
            msg = "LocalPgVectorBackend.retrieve: No embedding_fn configured"
            if self._fail_closed:
                raise RuntimeError(f"{msg} (fail_closed=True)")
            logger.warning(f"{msg}. Returning empty results.")
            return []

        try:
            embedding = await self._embedding_fn(query)
            effective_min_score = min_score if min_score is not None else 0.0
            return await self.query(embedding, top_k, effective_min_score, filters)
        except Exception as e:
            logger.error(f"LocalPgVectorBackend.retrieve failed: {e}")
            if self._fail_closed:
                raise
            return []
