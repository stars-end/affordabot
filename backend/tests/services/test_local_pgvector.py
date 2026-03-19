"""
Tests for LocalPgVectorBackend retrieval contract (bd-tytc.4).

Validates:
- Canonical retrieve(query, top_k, min_score, filters) interface
- Embedder-backed text queries
- Jurisdiction/source filtering
- Fail-closed production behavior
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from services.retrieval.local_pgvector import LocalPgVectorBackend


class TestLocalPgVectorBackendContract:
    """Test that LocalPgVectorBackend conforms to llm-common contract."""

    def test_init_with_defaults(self):
        """Backend should initialize with default parameters."""
        backend = LocalPgVectorBackend()
        assert backend.table_name == "document_chunks"
        assert backend.db is None
        assert backend._embedding_fn is None

    def test_init_with_custom_params(self):
        """Backend should accept custom parameters."""
        mock_db = MagicMock()

        async def embed_fn(text):
            return [0.1] * 1536

        backend = LocalPgVectorBackend(
            table_name="custom_chunks",
            postgres_client=mock_db,
            embedding_fn=embed_fn,
            fail_closed=True,
        )

        assert backend.table_name == "custom_chunks"
        assert backend.db == mock_db
        assert backend._embedding_fn == embed_fn
        assert backend._fail_closed is True


class TestRetrieveContract:
    """Test the canonical retrieve() interface."""

    @pytest.mark.asyncio
    async def test_retrieve_without_embedding_fn_returns_empty(self):
        """Without embedding_fn and fail_closed=False, should return empty list."""
        backend = LocalPgVectorBackend(fail_closed=False)

        results = await backend.retrieve("test query", top_k=5)

        assert results == []

    @pytest.mark.asyncio
    async def test_retrieve_without_embedding_fn_fails_closed(self):
        """Without embedding_fn and fail_closed=True, should raise."""
        backend = LocalPgVectorBackend(fail_closed=True)

        with pytest.raises(RuntimeError) as exc_info:
            await backend.retrieve("test query", top_k=5)

        assert "embedding_fn" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_retrieve_calls_embedding_fn(self):
        """retrieve() should call embedding_fn with query text."""
        mock_db = MagicMock()
        embed_calls = []

        async def embed_fn(text):
            embed_calls.append(text)
            return [0.1] * 1536

        backend = LocalPgVectorBackend(
            postgres_client=mock_db,
            embedding_fn=embed_fn,
            fail_closed=True,
        )

        with patch.object(backend, "query", new_callable=AsyncMock) as mock_query:
            mock_query.return_value = []

            await backend.retrieve("test legislation query", top_k=5)

            assert len(embed_calls) == 1
            assert embed_calls[0] == "test legislation query"

    @pytest.mark.asyncio
    async def test_retrieve_passes_filters_to_query(self):
        """retrieve() should pass filters to query()."""
        mock_db = MagicMock()

        async def embed_fn(text):
            return [0.1] * 1536

        backend = LocalPgVectorBackend(
            postgres_client=mock_db,
            embedding_fn=embed_fn,
            fail_closed=True,
        )

        with patch.object(backend, "query", new_callable=AsyncMock) as mock_query:
            mock_query.return_value = []

            filters = {"jurisdiction": "california", "bill_number": "SB 277"}
            await backend.retrieve(
                "test query", top_k=10, min_score=0.5, filters=filters
            )

            mock_query.assert_called_once()
            call_kwargs = mock_query.call_args
            assert call_kwargs[0][0] == [0.1] * 1536  # embedding
            assert call_kwargs[1]["top_k"] == 10
            assert call_kwargs[1]["filters"] == filters


class TestQueryWithFilters:
    """Test that query() applies jurisdiction/source filters."""

    @pytest.mark.asyncio
    async def test_query_without_filters(self):
        """Query without filters should not add WHERE clause."""
        mock_db = MagicMock()
        mock_db._fetch = AsyncMock(return_value=[])

        backend = LocalPgVectorBackend(postgres_client=mock_db)

        embedding = [0.1] * 1536
        await backend.query(embedding, top_k=5)

        mock_db._fetch.assert_called_once()
        call_args = mock_db._fetch.call_args
        sql = call_args[0][0]

        assert "WHERE" not in sql

    @pytest.mark.asyncio
    async def test_query_with_jurisdiction_filter(self):
        """Query with jurisdiction filter should add WHERE clause."""
        mock_db = MagicMock()
        mock_db._fetch = AsyncMock(return_value=[])

        backend = LocalPgVectorBackend(postgres_client=mock_db)

        embedding = [0.1] * 1536
        await backend.query(embedding, top_k=5, filters={"jurisdiction": "california"})

        mock_db._fetch.assert_called_once()
        call_args = mock_db._fetch.call_args
        sql = call_args[0][0]

        assert "WHERE" in sql
        assert "jurisdiction" in sql
        assert "california" in str(call_args[0])

    @pytest.mark.asyncio
    async def test_query_with_multiple_filters(self):
        """Query with multiple filters should add AND clauses."""
        mock_db = MagicMock()
        mock_db._fetch = AsyncMock(return_value=[])

        backend = LocalPgVectorBackend(postgres_client=mock_db)

        embedding = [0.1] * 1536
        filters = {
            "jurisdiction": "california",
            "source_system": "openstates+leginfo",
            "bill_number": "SB 277",
        }
        await backend.query(embedding, top_k=5, filters=filters)

        mock_db._fetch.assert_called_once()
        call_args = mock_db._fetch.call_args
        sql = call_args[0][0]

        assert "WHERE" in sql
        assert sql.count("AND") >= 2


class TestMinScoreFilter:
    """Test that min_score filters results correctly."""

    @pytest.mark.asyncio
    async def test_query_respects_min_score(self):
        """Results below min_score should be excluded."""
        from llm_common.retrieval import RetrievedChunk

        mock_db = MagicMock()

        mock_rows = [
            {
                "id": "chunk-1",
                "content": "High relevance content",
                "metadata": {"jurisdiction": "california"},
                "similarity": 0.9,
                "document_id": "doc-1",
            },
            {
                "id": "chunk-2",
                "content": "Low relevance content",
                "metadata": {"jurisdiction": "california"},
                "similarity": 0.3,
                "document_id": "doc-1",
            },
        ]
        mock_db._fetch = AsyncMock(return_value=mock_rows)

        backend = LocalPgVectorBackend(postgres_client=mock_db)

        embedding = [0.1] * 1536
        results = await backend.query(embedding, top_k=5, min_score=0.5)

        assert len(results) == 1
        assert results[0].chunk_id == "chunk-1"
        assert results[0].score >= 0.5


class TestProductionFailClosed:
    """Test fail-closed production behavior."""

    def test_fail_closed_defaults_false(self):
        """fail_closed should default to True for safety."""
        backend = LocalPgVectorBackend()
        assert backend._fail_closed is True

    @pytest.mark.asyncio
    async def test_db_error_fails_closed(self):
        """DB errors should raise when fail_closed=True."""
        mock_db = MagicMock()
        mock_db._fetch = AsyncMock(side_effect=Exception("DB connection failed"))

        backend = LocalPgVectorBackend(postgres_client=mock_db, fail_closed=True)

        with pytest.raises(Exception) as exc_info:
            await backend.query([0.1] * 1536, top_k=5)

        assert "DB connection failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_db_error_returns_empty_when_not_fail_closed(self):
        """DB errors should return empty when fail_closed=False."""
        mock_db = MagicMock()
        mock_db._fetch = AsyncMock(side_effect=Exception("DB connection failed"))

        backend = LocalPgVectorBackend(postgres_client=mock_db, fail_closed=False)

        results = await backend.query([0.1] * 1536, top_k=5)

        assert results == []
