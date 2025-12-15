import pytest
from unittest.mock import AsyncMock, MagicMock
from services.ingestion_service import IngestionService
from contracts.storage import BlobStorage
from llm_common.embeddings import EmbeddingService
import json

@pytest.fixture
def mock_postgres():
    pg = MagicMock()
    pg._fetchrow = AsyncMock()
    pg._execute = AsyncMock()
    pg.get_or_create_source = AsyncMock(return_value="test-source-id")
    pg.create_raw_scrape = AsyncMock(return_value="test-scrape-id")
    # Define side effect for _fetchrow to handle different queries
    async def fetchrow_side_effect(query, *args):
        if "FROM sources" in query:
             return None # Default: source not found
        if "FROM raw_scrapes" in query:
             return {
                "id": "test-scrape-123",
                "data": json.dumps({"content": "Title Some text."}),
                "source_id": "test-source",
                "url": "http://example.com",
                "content_type": "text/html",
                "metadata": "{}"
            }
        return None

    pg._fetchrow.side_effect = fetchrow_side_effect
    pg._execute = AsyncMock()
    pg.get_or_create_source = AsyncMock(return_value="test-source-id")
    pg.create_raw_scrape = AsyncMock(return_value="test-scrape-id")
    return pg

@pytest.fixture
def mock_vector_backend():
    backend = AsyncMock()
    backend.upsert = AsyncMock(return_value=1)
    return backend

@pytest.fixture
def mock_embedding_service():
    service = AsyncMock(spec=EmbeddingService)
    service.embed_documents.return_value = [[0.1, 0.2, 0.3]] # Mock embedding
    return service

@pytest.fixture
def mock_blob_storage():
    storage = AsyncMock(spec=BlobStorage)
    storage.upload.return_value = "s3://bucket/test.html"
    return storage

@pytest.mark.asyncio
async def test_process_raw_scrape_happy_path(mock_postgres, mock_vector_backend, mock_embedding_service):
    """Test standard ingestion flow without blob storage."""
    service = IngestionService(
        postgres_client=mock_postgres,
        vector_backend=mock_vector_backend,
        embedding_service=mock_embedding_service
    )
    
    count = await service.process_raw_scrape("test-scrape-123")
    
    assert count == 1
    # Verify vector upsert
    mock_vector_backend.upsert.assert_called_once()
    
    # Verify status update
    # We expect update call: _execute(query, True, doc_id, scrape_id)
    mock_postgres._execute.assert_called()
    found_update = False
    for call in mock_postgres._execute.call_args_list:
        query = call[0][0]
        args = call[0][1:]
        if "UPDATE raw_scrapes" in query and "processed =" in query:
            # Check if True is passed as argument
            if True in args:
                found_update = True
    assert found_update, "Postgres UPDATE not called for processed status"

@pytest.mark.asyncio
async def test_process_raw_scrape_with_blob_storage(mock_postgres, mock_vector_backend, mock_embedding_service, mock_blob_storage):
    """Test ingestion flow WITH blob storage upload."""
    service = IngestionService(
        postgres_client=mock_postgres,
        vector_backend=mock_vector_backend,
        embedding_service=mock_embedding_service,
        storage_backend=mock_blob_storage
    )
    
    count = await service.process_raw_scrape("test-scrape-123")
    
    assert count == 1
    # Verify Blob Upload
    mock_blob_storage.upload.assert_called_once()
    args, _ = mock_blob_storage.upload.call_args
    assert "test-scrape-123.html" in args[0] or "test-scrape-123" in args[0]
    
    # Verify Raw Scrape updated with URI
    # In implementation: UPDATE ... storage_uri = $1
    mock_postgres._execute.assert_called()
    found_uri_update = False
    for call in mock_postgres._execute.call_args_list:
        if "UPDATE raw_scrapes" in call[0][0] and "storage_uri" in call[0][0]:
            found_uri_update = True
            # Check argument
            assert call[0][1] == "s3://bucket/test.html"
    assert found_uri_update, "Postgres UPDATE not called for storage_uri"

def test_extract_text_cleaning():
    """Test HTML cleaning logic."""
    service = IngestionService(MagicMock(), MagicMock(), MagicMock())
    
    raw_html = "<html><body><h1>Title</h1><p>Some   text.</p></body></html>"
    text = service._extract_text(raw_html)
    
    # Simple extraction check
    assert "Title" in text
    assert "Some text" in text

def test_chunk_text_logic():
    """Test text chunking logic."""
    service = IngestionService(MagicMock(), MagicMock(), MagicMock(), chunk_size=10, chunk_overlap=2)
    
    text = "123456789012345"
    chunks = service._chunk_text(text)
    
    assert len(chunks) == 2
    assert chunks[0] == "1234567890"
    assert chunks[1] == "9012345"
    
import datetime

@pytest.mark.asyncio
async def test_ingest_from_search_result_new(mock_postgres, mock_vector_backend, mock_embedding_service):
    """Test ingestion from WebSearchResult (New Source)."""
    service = IngestionService(postgres_client=mock_postgres, vector_backend=mock_vector_backend, embedding_service=mock_embedding_service)
    
    from llm_common import WebSearchResult
    result = WebSearchResult(url="http://new.com", snippet="Snippet", content="Full Content", title="Title", domain="new.com")

    # Call
    doc_id = await service.ingest_from_search_result(result)
    
    # Verify calls
    mock_postgres.get_or_create_source.assert_called_once_with(
        jurisdiction_id="web",
        name="Title", 
        type="general"
    )
    mock_postgres.create_raw_scrape.assert_called_once()
    
    # And process_raw_scrape called (which calls _fetchrow etc, already verified in other test)
    # Since we mocked internal fetch, it should succeed.
    
@pytest.mark.asyncio
async def test_ingest_from_search_result_existing_source(mock_postgres, mock_vector_backend, mock_embedding_service):
    """Test ingestion when Source exists."""
    service = IngestionService(postgres_client=mock_postgres, vector_backend=mock_vector_backend, embedding_service=mock_embedding_service)
    
    from llm_common import WebSearchResult
    result = WebSearchResult(url="http://exists.com", snippet="Existing", title="T", domain="exists.com")
    
    # Mock _fetchrow to return existing source
    async def fetchrow_side_effect(query, *args):
        if "FROM sources" in query:
             return {"id": "existing-source-id"}
        return { # Default scrape return for process_raw_scrape
            "id": "new-scrape-id-2",
            "data": json.dumps({"content": "Existing"}),
            "source_id": "existing-source-id"
        }

    mock_postgres._fetchrow.side_effect = fetchrow_side_effect
    mock_postgres.get_or_create_source.return_value = "existing-source-id"

    await service.ingest_from_search_result(result)
    
    mock_postgres.create_raw_scrape.assert_called()
    args = mock_postgres.create_raw_scrape.call_args[0][0]
    assert args['source_id'] == "existing-source-id"

