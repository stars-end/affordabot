"""Tests for generic PgVectorBackend.

Uses mocks to avoid requiring a real database connection in CI.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Any

# Mock imports for optional dependencies
pytest.importorskip("sqlalchemy")
pytest.importorskip("asyncpg")
pytest.importorskip("pgvector")

from llm_common.retrieval.backends.pg_backend import PgVectorBackend, create_pg_backend
from llm_common.retrieval.models import RetrievedChunk


@pytest.fixture
async def mock_embed_fn():
    """Mock embedding function."""

    async def embed(text: str) -> list[float]:
        # Return fake embedding based on text length (deterministic for testing)
        return [0.1] * 1536

    return embed


@pytest.fixture
def mock_engine():
    """Mock SQLAlchemy async engine."""
    engine = MagicMock()
    engine.begin = MagicMock()
    engine.dispose = AsyncMock()
    return engine


@pytest.fixture
async def backend(mock_embed_fn, mock_engine):
    """Create PgVectorBackend with mocked engine."""
    with patch("llm_common.retrieval.backends.pg_backend.create_async_engine") as mock_create:
        mock_create.return_value = mock_engine
        backend = PgVectorBackend(
            database_url="postgresql+asyncpg://test:test@localhost/test",
            table="test_chunks",
            embed_fn=mock_embed_fn,
            vector_dimensions=1536,
        )
        yield backend


@pytest.mark.asyncio
async def test_retrieve_basic(backend, mock_engine):
    """Test basic retrieval without filters."""
    # Mock database response
    mock_row = MagicMock()
    mock_row.id = "chunk_1"
    mock_row.content = "Test content"
    mock_row.source = "test.txt"
    mock_row.metadata = {"key": "value"}
    mock_row.similarity = 0.95

    mock_result = MagicMock()
    mock_result.fetchall.return_value = [mock_row]

    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock(return_value=mock_result)

    # Mock context manager
    mock_engine.begin.return_value.__aenter__.return_value = mock_conn
    mock_engine.begin.return_value.__aexit__.return_value = None

    # Execute retrieval
    results = await backend.retrieve("test query", top_k=5)

    # Assertions
    assert len(results) == 1
    assert isinstance(results[0], RetrievedChunk)
    assert results[0].content == "Test content"
    assert results[0].score == 0.95
    assert results[0].source == "test.txt"
    assert results[0].metadata == {"key": "value"}
    assert results[0].chunk_id == "chunk_1"

    # Verify embed function was called
    mock_conn.execute.assert_called_once()


@pytest.mark.asyncio
async def test_retrieve_with_min_score(backend, mock_engine):
    """Test retrieval with minimum score filter."""
    # Mock rows with different scores
    mock_row_1 = MagicMock()
    mock_row_1.content = "High score"
    mock_row_1.source = "high.txt"
    mock_row_1.metadata = {}
    mock_row_1.similarity = 0.9
    mock_row_1.id = "1"

    mock_row_2 = MagicMock()
    mock_row_2.content = "Low score"
    mock_row_2.source = "low.txt"
    mock_row_2.metadata = {}
    mock_row_2.similarity = 0.5
    mock_row_2.id = "2"

    mock_result = MagicMock()
    mock_result.fetchall.return_value = [mock_row_1, mock_row_2]

    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock(return_value=mock_result)

    mock_engine.begin.return_value.__aenter__.return_value = mock_conn
    mock_engine.begin.return_value.__aexit__.return_value = None

    # Execute with min_score filter
    results = await backend.retrieve("test query", top_k=10, min_score=0.7)

    # Should only return high score result
    assert len(results) == 1
    assert results[0].content == "High score"
    assert results[0].score == 0.9


@pytest.mark.asyncio
async def test_retrieve_with_filters(backend, mock_engine):
    """Test retrieval with metadata filters."""
    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock()

    mock_engine.begin.return_value.__aenter__.return_value = mock_conn
    mock_engine.begin.return_value.__aexit__.return_value = None

    # Execute with filters
    await backend.retrieve(
        "test query", top_k=5, filters={"section": "intro", "category": "docs"}
    )

    # Verify execute was called with filters
    mock_conn.execute.assert_called_once()


@pytest.mark.asyncio
async def test_upsert_chunks(backend, mock_engine):
    """Test upserting chunks."""
    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock()

    mock_engine.begin.return_value.__aenter__.return_value = mock_conn
    mock_engine.begin.return_value.__aexit__.return_value = None

    # Prepare chunks
    chunks = [
        {
            "content": "Test content 1",
            "source": "test1.txt",
            "metadata": {"key": "value1"},
            "chunk_id": "chunk_1",
        },
        {
            "content": "Test content 2",
            "source": "test2.txt",
            "metadata": {"key": "value2"},
        },
    ]

    # Execute upsert
    await backend.upsert(chunks)

    # Should call execute twice (once per chunk)
    assert mock_conn.execute.call_count == 2


@pytest.mark.asyncio
async def test_upsert_validates_required_fields(backend):
    """Test that upsert validates required fields."""
    invalid_chunks = [{"content": "Missing source"}]

    with pytest.raises(ValueError, match="must have 'content' and 'source'"):
        await backend.upsert(invalid_chunks)


@pytest.mark.asyncio
async def test_upsert_empty_list(backend):
    """Test upserting empty list is a no-op."""
    # Should not raise, just return
    await backend.upsert([])


@pytest.mark.asyncio
async def test_get_by_id_found(backend, mock_engine):
    """Test retrieving chunk by ID when found."""
    mock_row = MagicMock()
    mock_row.id = "chunk_1"
    mock_row.content = "Test content"
    mock_row.source = "test.txt"
    mock_row.metadata = {"key": "value"}

    mock_result = MagicMock()
    mock_result.fetchone.return_value = mock_row

    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock(return_value=mock_result)

    mock_engine.begin.return_value.__aenter__.return_value = mock_conn
    mock_engine.begin.return_value.__aexit__.return_value = None

    # Execute get_by_id
    result = await backend.get_by_id("chunk_1")

    # Assertions
    assert result is not None
    assert result.content == "Test content"
    assert result.source == "test.txt"
    assert result.score == 1.0  # Direct retrieval has perfect score
    assert result.chunk_id == "chunk_1"


@pytest.mark.asyncio
async def test_get_by_id_not_found(backend, mock_engine):
    """Test retrieving chunk by ID when not found."""
    mock_result = MagicMock()
    mock_result.fetchone.return_value = None

    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock(return_value=mock_result)

    mock_engine.begin.return_value.__aenter__.return_value = mock_conn
    mock_engine.begin.return_value.__aexit__.return_value = None

    # Execute get_by_id
    result = await backend.get_by_id("nonexistent")

    # Should return None
    assert result is None


@pytest.mark.asyncio
async def test_get_by_id_handles_exception(backend, mock_engine):
    """Test get_by_id handles exceptions gracefully."""
    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock(side_effect=Exception("Database error"))

    mock_engine.begin.return_value.__aenter__.return_value = mock_conn
    mock_engine.begin.return_value.__aexit__.return_value = None

    # Should return None on exception
    result = await backend.get_by_id("chunk_1")
    assert result is None


@pytest.mark.asyncio
async def test_health_check_healthy(backend, mock_engine):
    """Test health check when database is healthy."""
    mock_row = MagicMock()
    mock_row.__getitem__.return_value = 1  # Extension exists

    mock_result = MagicMock()
    mock_result.fetchone.return_value = mock_row

    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock(return_value=mock_result)

    mock_engine.begin.return_value.__aenter__.return_value = mock_conn
    mock_engine.begin.return_value.__aexit__.return_value = None

    # Execute health check
    is_healthy = await backend.health_check()

    # Should be healthy
    assert is_healthy is True


@pytest.mark.asyncio
async def test_health_check_unhealthy(backend, mock_engine):
    """Test health check when pgvector extension missing."""
    mock_row = MagicMock()
    mock_row.__getitem__.return_value = 0  # No extension

    mock_result = MagicMock()
    mock_result.fetchone.return_value = mock_row

    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock(return_value=mock_result)

    mock_engine.begin.return_value.__aenter__.return_value = mock_conn
    mock_engine.begin.return_value.__aexit__.return_value = None

    # Execute health check
    is_healthy = await backend.health_check()

    # Should be unhealthy
    assert is_healthy is False


@pytest.mark.asyncio
async def test_health_check_handles_exception(backend, mock_engine):
    """Test health check handles exceptions."""
    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock(side_effect=Exception("Connection failed"))

    mock_engine.begin.return_value.__aenter__.return_value = mock_conn
    mock_engine.begin.return_value.__aexit__.return_value = None

    # Should return False on exception
    is_healthy = await backend.health_check()
    assert is_healthy is False


@pytest.mark.asyncio
async def test_close(backend, mock_engine):
    """Test closing the backend."""
    await backend.close()

    # Should dispose engine
    mock_engine.dispose.assert_called_once()


@pytest.mark.asyncio
async def test_context_manager(mock_embed_fn, mock_engine):
    """Test using backend as async context manager."""
    with patch("llm_common.retrieval.backends.pg_backend.create_async_engine") as mock_create:
        mock_create.return_value = mock_engine

        async with PgVectorBackend(
            database_url="postgresql+asyncpg://test:test@localhost/test",
            table="test_chunks",
            embed_fn=mock_embed_fn,
            vector_dimensions=1536,
        ) as backend:
            assert backend is not None

        # Should have disposed engine on exit
        mock_engine.dispose.assert_called_once()


@pytest.mark.asyncio
async def test_retrieve_raises_on_db_error(backend, mock_engine):
    """Test that retrieve raises RuntimeError on database errors."""
    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock(side_effect=Exception("Database error"))

    mock_engine.begin.return_value.__aenter__.return_value = mock_conn
    mock_engine.begin.return_value.__aexit__.return_value = None

    # Should raise RuntimeError
    with pytest.raises(RuntimeError, match="Failed to execute similarity search"):
        await backend.retrieve("test query")


@pytest.mark.asyncio
async def test_upsert_raises_on_db_error(backend, mock_engine):
    """Test that upsert raises RuntimeError on database errors."""
    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock(side_effect=Exception("Database error"))

    mock_engine.begin.return_value.__aenter__.return_value = mock_conn
    mock_engine.begin.return_value.__aexit__.return_value = None

    chunks = [{"content": "Test", "source": "test.txt"}]

    # Should raise RuntimeError
    with pytest.raises(RuntimeError, match="Failed to upsert chunks"):
        await backend.upsert(chunks)


def test_create_pg_backend_factory(mock_embed_fn):
    """Test factory function creates backend correctly."""
    with patch("llm_common.retrieval.backends.pg_backend.create_async_engine"):
        backend = create_pg_backend(
            database_url="postgresql+asyncpg://test:test@localhost/test",
            table="test_chunks",
            embed_fn=mock_embed_fn,
            vector_dimensions=1536,
        )

        assert backend is not None
        assert backend.table == "test_chunks"
        assert backend.vector_dimensions == 1536


def test_create_pg_backend_with_kwargs(mock_embed_fn):
    """Test factory function passes kwargs correctly."""
    with patch("llm_common.retrieval.backends.pg_backend.create_async_engine"):
        backend = create_pg_backend(
            database_url="postgresql+asyncpg://test:test@localhost/test",
            table="custom_table",
            embed_fn=mock_embed_fn,
            vector_dimensions=768,
            vector_col="vec",
            text_col="text",
            pool_size=10,
        )

        assert backend.table == "custom_table"
        assert backend.vector_dimensions == 768
        assert backend.vector_col == "vec"
        assert backend.text_col == "text"


@pytest.mark.asyncio
async def test_embedding_conversion_from_numpy(backend, mock_engine):
    """Test that embeddings are converted from numpy arrays to lists."""

    async def embed_numpy(text: str) -> Any:
        # Simulate numpy array with __iter__
        class FakeArray:
            def __iter__(self):
                return iter([0.1, 0.2, 0.3])

        return FakeArray()

    backend.embed_fn = embed_numpy

    mock_result = MagicMock()
    mock_result.fetchall.return_value = []

    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock(return_value=mock_result)

    mock_engine.begin.return_value.__aenter__.return_value = mock_conn
    mock_engine.begin.return_value.__aexit__.return_value = None

    # Should convert numpy-like array to list without error
    results = await backend.retrieve("test query")
    assert results == []


@pytest.mark.asyncio
async def test_retrieve_with_empty_metadata(backend, mock_engine):
    """Test retrieval handles null/empty metadata correctly."""
    mock_row = MagicMock()
    mock_row.id = "chunk_1"
    mock_row.content = "Test"
    mock_row.source = "test.txt"
    mock_row.metadata = None  # Null metadata
    mock_row.similarity = 0.9

    mock_result = MagicMock()
    mock_result.fetchall.return_value = [mock_row]

    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock(return_value=mock_result)

    mock_engine.begin.return_value.__aenter__.return_value = mock_conn
    mock_engine.begin.return_value.__aexit__.return_value = None

    results = await backend.retrieve("test query")

    # Should handle None metadata gracefully
    assert len(results) == 1
    assert results[0].metadata == {}


@pytest.mark.asyncio
async def test_custom_column_names(mock_embed_fn, mock_engine):
    """Test backend works with custom column names."""
    with patch("llm_common.retrieval.backends.pg_backend.create_async_engine") as mock_create:
        mock_create.return_value = mock_engine

        backend = PgVectorBackend(
            database_url="postgresql+asyncpg://test:test@localhost/test",
            table="custom_table",
            embed_fn=mock_embed_fn,
            vector_dimensions=1536,
            vector_col="vec",
            text_col="txt",
            source_col="src",
            id_col="pk",
            metadata_col="meta",
        )

        assert backend.vector_col == "vec"
        assert backend.text_col == "txt"
        assert backend.source_col == "src"
        assert backend.id_col == "pk"
        assert backend.metadata_col == "meta"
