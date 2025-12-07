import pytest
from unittest.mock import AsyncMock, MagicMock
from services.ingestion_service import IngestionService
from contracts.storage import BlobStorage
from llm_common.embeddings import EmbeddingService
from llm_common.retrieval import SupabasePgVectorBackend

@pytest.fixture
def mock_supabase():
    client = MagicMock()
    # Mock table('raw_scrapes').select().eq().single().execute() chain
    client.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value.data = {
        "id": "test-scrape-123",
        "data": {"content": "<p>Test Content</p>"},
        "source_id": "test-source",
        "url": "http://example.com",
        "content_type": "text/html"
    }
    return client

@pytest.fixture
def mock_vector_backend():
    backend = AsyncMock(spec=SupabasePgVectorBackend)
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
async def test_process_raw_scrape_happy_path(mock_supabase, mock_vector_backend, mock_embedding_service):
    """Test standard ingestion flow without blob storage."""
    service = IngestionService(
        supabase_client=mock_supabase,
        vector_backend=mock_vector_backend,
        embedding_service=mock_embedding_service
    )
    
    count = await service.process_raw_scrape("test-scrape-123")
    
    assert count == 1
    # Verify vector upsert
    mock_vector_backend.upsert.assert_called_once()
    
    # Verify status update
    # We expect update to be called with a dict containing processed=True
    call_args = mock_supabase.table.return_value.update.call_args
    assert call_args is not None
    update_payload = call_args[0][0]
    assert update_payload['processed'] is True

@pytest.mark.asyncio
async def test_process_raw_scrape_with_blob_storage(mock_supabase, mock_vector_backend, mock_embedding_service, mock_blob_storage):
    """Test ingestion flow WITH blob storage upload."""
    service = IngestionService(
        supabase_client=mock_supabase,
        vector_backend=mock_vector_backend,
        embedding_service=mock_embedding_service,
        storage_backend=mock_blob_storage
    )
    
    count = await service.process_raw_scrape("test-scrape-123")
    
    assert count == 1
    # Verify Blob Upload
    mock_blob_storage.upload.assert_called_once()
    args, _ = mock_blob_storage.upload.call_args
    assert "test-scrape-123.html" in args[0] # Path check
    
    # Verify Raw Scrape updated with URI
    # Note: supabase calls are chained, hard to verify exact order without complex mock setup, 
    # but we can check if update was called with storage_uri at some point.
    # In implementation: update(uri) -> execute(), then upsert, then update(processed)
    
    # We expect table().update() to be called twice.
    # 1. storage_uri
    # 2. processed=True
    assert mock_supabase.table.return_value.update.call_count == 2
    
    # Check first update call args (storage uri)
    first_call_args = mock_supabase.table.return_value.update.call_args_list[0]
    assert first_call_args[0][0] == {'storage_uri': 's3://bucket/test.html'}

def test_extract_text_cleaning():
    """Test HTML cleaning logic."""
    service = IngestionService(MagicMock(), MagicMock(), MagicMock())
    
    raw_html = "<html><body><h1>Title</h1><p>Some   text.</p></body></html>"
    text = service._extract_text(raw_html)
    
    assert text == "Title Some text."

def test_chunk_text_logic():
    """Test text chunking with overlap."""
    service = IngestionService(MagicMock(), MagicMock(), MagicMock(), chunk_size=10, chunk_overlap=2)
    
    text = "123456789012345"
    chunks = service._chunk_text(text)
    
    # Expect: "1234567890", "9012345678"... wait logic splits by sentence if possible
    # With no sentences, strictly size based?
    # Logic: end = start + chunk_size.
    # Chunk 1: 0-10 -> "1234567890"
    # Start -> 10-2 = 8
    # Chunk 2: 8-18 -> "9012345"
    
    assert len(chunks) == 2
    assert chunks[0] == "1234567890"
    assert chunks[1] == "9012345"

    assert len(chunks) == 2
    assert chunks[0] == "1234567890"
    assert chunks[1] == "9012345"

@pytest.mark.asyncio
async def test_ingest_from_search_result_new(mock_supabase, mock_vector_backend, mock_embedding_service):
    """Test ingestion from WebSearchResult (New Source)."""
    service = IngestionService(mock_supabase, mock_vector_backend, mock_embedding_service)
    
    from llm_common import WebSearchResult
    result = WebSearchResult(url="http://new.com", snippet="Snippet", content="Full Content", title="Title", domain="new.com")

    # Mock Table Separation
    mock_sources = MagicMock()
    mock_scrapes = MagicMock()
    
    def table_side_effect(name):
        if name == 'sources':
            return mock_sources
        if name == 'raw_scrapes':
            return mock_scrapes
        return MagicMock()
    
    mock_supabase.table.side_effect = table_side_effect

    # 1. Source Check (Returns empty -> Not Found)
    mock_sources.select.return_value.eq.return_value.execute.return_value.data = []
    
    # 2. Source Insert (Returns new ID)
    mock_sources.insert.return_value.execute.return_value.data = [{'id': 'new-source-id'}]
    
    # 3. Scrape Insert (Returns new ID)
    mock_scrapes.insert.return_value.execute.return_value.data = [{'id': 'new-scrape-id'}]
    
    # 4. Scrape Fetch (for process_raw_scrape)
    # The service calls .single().execute(), returning object with .data attribute
    scrape_data_obj = MagicMock()
    scrape_data_obj.data = { # Content of the scrape we just inserted
        'id': 'new-scrape-id',
        'source_id': 'new-source-id',
        'data': {'content': 'Full Content', 'title': 'Title'},
        'url': 'http://new.com',
        'metadata': {}
    }
    mock_scrapes.select.return_value.eq.return_value.single.return_value.execute.side_effect = [
        scrape_data_obj,        # Call inside process_raw_scrape (fetch raw)
        MagicMock(data={'document_id': 'gen-doc-id'}) # Call at end (fetch doc id)
    ]

    # Call
    doc_id = await service.ingest_from_search_result(result)

    # Verify
    assert doc_id == "gen-doc-id"
    
    # Verify Source Creation
    mock_sources.insert.assert_called()
    
    # Verify Scrape Creation
    mock_scrapes.insert.assert_called()
    insert_payload = mock_scrapes.insert.call_args[0][0]
    assert insert_payload['source_id'] == 'new-source-id'
    
    # Verify Upsert triggered
    mock_vector_backend.upsert.assert_called()

@pytest.mark.asyncio
async def test_ingest_from_search_result_existing_source(mock_supabase, mock_vector_backend, mock_embedding_service):
    """Test ingestion when Source exists (but logic still processes scrape)."""
    service = IngestionService(mock_supabase, mock_vector_backend, mock_embedding_service)
    
    from llm_common import WebSearchResult
    result = WebSearchResult(url="http://exists.com", snippet="Existing", title="T", domain="exists.com")

    # Mock Table Separation
    mock_sources = MagicMock()
    mock_scrapes = MagicMock()
    mock_supabase.table.side_effect = lambda n: mock_sources if n == 'sources' else mock_scrapes

    # 1. Source Check (Returns EXISTING ID)
    mock_sources.select.return_value.eq.return_value.execute.return_value.data = [{'id': 'existing-source-id'}]
    
    # 2. Scrape Insert (Returns new ID)
    mock_scrapes.insert.return_value.execute.return_value.data = [{'id': 'new-scrape-id-2'}]

    # 3. Scrape Fetch Sequence
    scrape_data = {
        'id': 'new-scrape-id-2',
        'source_id': 'existing-source-id',
        'data': 'Existing Content',
        'url': 'http://exists.com'
    }
    mock_response = MagicMock()
    mock_response.data = scrape_data
    
    mock_scrapes.select.return_value.eq.return_value.single.return_value.execute.side_effect = [
        mock_response,
        MagicMock(data={'document_id': 'doc-id-2'})
    ]

    doc_id = await service.ingest_from_search_result(result)

    assert doc_id == 'doc-id-2'
    
    # Should NOT insert Source
    mock_sources.insert.assert_not_called()
    
    # Should Insert raw_scrape (current logic always inserts)
    mock_scrapes.insert.assert_called()
