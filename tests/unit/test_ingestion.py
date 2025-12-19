import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from backend.services.ingestion_service import IngestionService
from llm_common.retrieval import RetrievedChunk

# A sample raw scrape record from the database
SAMPLE_SCRAPE_ID = "scrape-123"
SAMPLE_DOCUMENT_ID = str(uuid4())
SAMPLE_SOURCE_ID = str(uuid4())

SAMPLE_RAW_SCRAPE = {
    "id": SAMPLE_SCRAPE_ID,
    "source_id": SAMPLE_SOURCE_ID,
    "url": "https://example.com/article",
    "data": {
        "content": "<html><body><h1>Main Title</h1><p>This is a paragraph of text. It contains multiple sentences.</p></body></html>",
        "title": "Example Article"
    },
    "metadata": {
        "publication_date": "2023-01-01",
        "author": "John Doe"
    },
    "content_type": "text/html",
    "processed": False,
    "document_id": None,
    "storage_uri": None,
}

@pytest.fixture
def mock_postgres_client():
    """Fixture for a mock async postgres client."""
    mock_pg = AsyncMock()
    # Configure _fetchrow to return the sample scrape when called with the correct ID
    async def fetchrow_side_effect(*args, **kwargs):
        if args[1] == SAMPLE_SCRAPE_ID:
            return SAMPLE_RAW_SCRAPE
        return None
    mock_pg._fetchrow.side_effect = fetchrow_side_effect
    mock_pg._execute = AsyncMock()
    return mock_pg

@pytest.fixture
def mock_vector_backend():
    """Fixture for a mock retrieval backend."""
    mock_vb = AsyncMock()
    mock_vb.upsert = AsyncMock()
    return mock_vb

@pytest.fixture
def mock_embedding_service():
    """Fixture for a mock embedding service."""
    mock_es = AsyncMock()
    # Mock the embedding service to return a fixed-size vector for each chunk
    async def embed_documents_side_effect(chunks):
        return [[0.1] * 128 for _ in chunks]
    mock_es.embed_documents.side_effect = embed_documents_side_effect
    return mock_es

@pytest.fixture
def mock_storage_backend():
    """Fixture for a mock blob storage backend."""
    mock_sb = AsyncMock()
    mock_sb.upload.return_value = "s3://bucket/path/to/file.html"
    return mock_sb

@pytest.mark.asyncio
async def test_process_raw_scrape_happy_path(
    mock_postgres_client,
    mock_vector_backend,
    mock_embedding_service,
    mock_storage_backend
):
    """
    Tests the successful processing of a raw scrape (the "happy path").
    """
    # 1. Arrange
    ingestion_service = IngestionService(
        postgres_client=mock_postgres_client,
        vector_backend=mock_vector_backend,
        embedding_service=mock_embedding_service,
        storage_backend=mock_storage_backend,
        chunk_size=50, # Use a small chunk size for predictable chunking
        chunk_overlap=10
    )

    # 2. Act
    num_chunks = await ingestion_service.process_raw_scrape(SAMPLE_SCRAPE_ID)

    # 3. Assert
    # Check that the raw scrape was fetched
    mock_postgres_client._fetchrow.assert_called_once_with(
        "SELECT * FROM raw_scrapes WHERE id = $1", SAMPLE_SCRAPE_ID
    )

    # Check that the text was extracted, chunked, and embedded
    # Extracted text: "Main Title This is a paragraph of text. It contains multiple sentences."
    # Expected chunks with size 50 and overlap 10:
    # chunk1: "Main Title This is a paragraph of text. It contains"
    # chunk2: "paragraph of text. It contains multiple sentences."
    mock_embedding_service.embed_documents.assert_called_once()
    assert len(mock_embedding_service.embed_documents.call_args[0][0]) == 2
    assert num_chunks == 2

    # Check that chunks were upserted to the vector backend
    mock_vector_backend.upsert.assert_called_once()
    upserted_chunks = mock_vector_backend.upsert.call_args[0][0]
    assert len(upserted_chunks) == 2
    
    # Verify the structure of the first chunk
    first_chunk = upserted_chunks[0]
    assert first_chunk['content'] == "Main Title This is a paragraph of text. It"
    assert "embedding" in first_chunk
    assert first_chunk['metadata']['scrape_id'] == SAMPLE_SCRAPE_ID
    assert first_chunk['metadata']['author'] == "John Doe"

    # Check that the raw scrape was marked as processed
    mock_postgres_client._execute.assert_any_call(
        "UPDATE raw_scrapes SET processed = $1, document_id = $2 WHERE id = $3",
        True, first_chunk['document_id'], SAMPLE_SCRAPE_ID
    )
    
    # Check that the content was uploaded to storage
    mock_storage_backend.upload.assert_called_once()
    
    # Check that the storage URI was updated
    mock_postgres_client._execute.assert_any_call(
        "UPDATE raw_scrapes SET storage_uri = $1 WHERE id = $2",
        "s3://bucket/path/to/file.html",
        SAMPLE_SCRAPE_ID
    )

@pytest.mark.asyncio
async def test_process_raw_scrape_not_found(mock_postgres_client):
    """
    Tests that the service handles a missing scrape_id gracefully.
    """
    # 1. Arrange
    ingestion_service = IngestionService(postgres_client=mock_postgres_client)
    
    # 2. Act
    num_chunks = await ingestion_service.process_raw_scrape("non-existent-id")
    
    # 3. Assert
    assert num_chunks == 0
    mock_postgres_client._fetchrow.assert_called_once_with(
        "SELECT * FROM raw_scrapes WHERE id = $1", "non-existent-id"
    )

@pytest.mark.asyncio
async def test_process_raw_scrape_no_text(
    mock_postgres_client,
    mock_vector_backend,
    mock_embedding_service
):
    """
    Tests that the service handles a scrape with no extractable text.
    """
    # 1. Arrange
    # Modify the sample scrape to have no text content
    no_text_scrape = SAMPLE_RAW_SCRAPE.copy()
    no_text_scrape['data'] = {"title": "Title Only", "other_field": "metadata"}
    
    # Configure the mock to return this modified scrape
    mock_postgres_client._fetchrow.side_effect = lambda *args, **kwargs: no_text_scrape if args[1] == SAMPLE_SCRAPE_ID else None

    ingestion_service = IngestionService(
        postgres_client=mock_postgres_client,
        vector_backend=mock_vector_backend,
        embedding_service=mock_embedding_service,
    )
    
    # 2. Act
    num_chunks = await ingestion_service.process_raw_scrape(SAMPLE_SCRAPE_ID)
    
    # 3. Assert
    assert num_chunks == 0
    mock_embedding_service.embed_documents.assert_not_called()
    mock_vector_backend.upsert.assert_not_called()

@pytest.mark.asyncio
async def test_process_raw_scrape_malformed_metadata(
    mock_postgres_client,
    mock_vector_backend,
    mock_embedding_service
):
    """
    Tests that the service handles malformed (non-dict) metadata.
    """
    # 1. Arrange
    malformed_scrape = SAMPLE_RAW_SCRAPE.copy()
    malformed_scrape['metadata'] = "just a string, not a dict"
    
    mock_postgres_client._fetchrow.side_effect = lambda *args, **kwargs: malformed_scrape

    ingestion_service = IngestionService(
        postgres_client=mock_postgres_client,
        vector_backend=mock_vector_backend,
        embedding_service=mock_embedding_service
    )
    
    # 2. Act
    num_chunks = await ingestion_service.process_raw_scrape(SAMPLE_SCRAPE_ID)
    
    # 3. Assert
    # The Pydantic model should fail validation
    assert num_chunks == 0
    mock_vector_backend.upsert.assert_not_called()

@pytest.mark.asyncio
async def test_process_raw_scrape_embedding_failure(
    mock_postgres_client,
    mock_vector_backend,
    mock_embedding_service
):
    """
    Tests that the service handles an exception from the embedding service.
    """
    # 1. Arrange
    mock_embedding_service.embed_documents.side_effect = Exception("Embedding API is down")
    
    ingestion_service = IngestionService(
        postgres_client=mock_postgres_client,
        vector_backend=mock_vector_backend,
        embedding_service=mock_embedding_service
    )
    
    # 2. Act
    num_chunks = await ingestion_service.process_raw_scrape(SAMPLE_SCRAPE_ID)
    
    # 3. Assert
    assert num_chunks == 0
    mock_vector_backend.upsert.assert_not_called()
    # Check that we do not mark the scrape as processed
    assert not any(
        "UPDATE raw_scrapes SET processed = $1" in call[0][0] for call in mock_postgres_client._execute.call_args_list
    )

@pytest.mark.asyncio
async def test_ingest_from_search_result(
    mock_postgres_client,
    mock_vector_backend,
    mock_embedding_service
):
    """
    Tests the end-to-end ingestion from a WebSearchResult.
    """
    from llm_common import WebSearchResult
    from datetime import datetime

    # 1. Arrange
    search_result = WebSearchResult(
        url="https://example.com/search-result",
        title="Search Result Title",
        content="This is the content of the search result.",
        snippet="A snippet of the result.",
        published_date=datetime.now(),
        domain="example.com"
    )

    # Mock the database interactions
    mock_postgres_client.get_or_create_source.return_value = SAMPLE_SOURCE_ID
    mock_postgres_client.create_raw_scrape.return_value = "new-scrape-id"
    
    # When process_raw_scrape is called for the new ID, it should fetch the sample data
    async def fetchrow_side_effect(*args, **kwargs):
        if args[1] == "new-scrape-id":
            # Return a valid scrape structure for the new ID
            return {
                "id": "new-scrape-id", "source_id": SAMPLE_SOURCE_ID, "url": search_result.url,
                "data": {"content": search_result.content}, "metadata": {"title": search_result.title},
                "content_type": "text/html", "processed": False
            }
        return None
    mock_postgres_client._fetchrow.side_effect = fetchrow_side_effect

    ingestion_service = IngestionService(
        postgres_client=mock_postgres_client,
        vector_backend=mock_vector_backend,
        embedding_service=mock_embedding_service,
        storage_backend=None # Disable storage for this test
    )

    # 2. Act
    num_chunks = await ingestion_service.ingest_from_search_result(search_result)
    
    # 3. Assert
    assert num_chunks > 0
    mock_postgres_client.get_or_create_source.assert_called_once()
    mock_postgres_client.create_raw_scrape.assert_called_once()
    mock_vector_backend.upsert.assert_called_once()
