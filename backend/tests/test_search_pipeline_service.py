import pytest
from unittest.mock import AsyncMock, MagicMock

# Imports from your application code
# Ensure these import paths match your project structure
from services.search_pipeline_service import SearchPipelineService, SearchResponse
from llm_common import WebSearchResult, LLMClient
from llm_common.retrieval import RetrievalBackend

# Mock Data Classes to behave like the real ones if needed, 
# but usually MagicMock/AsyncMock is enough for services.

@pytest.fixture
def mock_discovery():
    mock = AsyncMock()
    return mock

@pytest.fixture
def mock_ingestion():
    mock = AsyncMock()
    return mock

@pytest.fixture
def mock_retrieval():
    mock = AsyncMock(spec=RetrievalBackend)
    return mock

@pytest.fixture
def mock_llm():
    mock = AsyncMock(spec=LLMClient)
    return mock

@pytest.fixture
def service(mock_discovery, mock_ingestion, mock_retrieval, mock_llm):
    return SearchPipelineService(
        discovery=mock_discovery,
        ingestion=mock_ingestion,
        retrieval=mock_retrieval,
        llm=mock_llm
    )

@pytest.mark.asyncio
async def test_search_end_to_end_success(service, mock_discovery, mock_ingestion, mock_retrieval, mock_llm):
    """
    Verify the happy path:
    1. Discovery returns results
    2. Ingestion is triggered
    3. Retrieval fetches chunks
    4. LLM synthesis generates answer
    """
    # 1. Setup Mock Data
    search_results = [
        WebSearchResult(url="http://example.com/1", snippet="Snippet 1", title="T1", domain="d1"),
        WebSearchResult(url="http://example.com/2", snippet="Snippet 2", title="T2", domain="d2")
    ]
    mock_discovery.find_urls.return_value = search_results

    # Mock ingestion returning document IDs
    # Note: SearchPipelineService calls ingest_from_search_result
    mock_ingestion.ingest_from_search_result.side_effect = ["doc-1", "doc-2"]

    # Mock retrieval returning chunks
    mock_chunk = MagicMock()
    mock_chunk.content = "Relevant content about housing."
    mock_retrieval.retrieve.return_value = [mock_chunk]

    # Mock LLM response
    mock_llm_response = MagicMock()
    mock_llm_response.content = "The answer is X."
    mock_llm.chat_completion.return_value = mock_llm_response

    # 2. Execute
    response = await service.search("test query")

    # 3. Verify
    # Discovery called
    mock_discovery.find_urls.assert_called_once_with("test query")

    # Ingestion called for each result
    assert mock_ingestion.ingest_from_search_result.call_count == 2
    
    # Retrieval called
    mock_retrieval.retrieve.assert_called_once()
    args, kwargs = mock_retrieval.retrieve.call_args
    assert args[0] == "test query"
    
    # LLM called
    mock_llm.chat_completion.assert_called_once()
    
    # Response structure
    assert isinstance(response, SearchResponse)
    assert response.answer == "The answer is X."
    assert len(response.citations) == 2

@pytest.mark.asyncio
async def test_search_no_results(service, mock_discovery, mock_ingestion, mock_retrieval, mock_llm):
    """Verify behavior when discovery returns no sources."""
    mock_discovery.find_urls.return_value = []

    response = await service.search("query with no answers")

    # Verify early exit
    mock_ingestion.ingest_from_search_result.assert_not_called()
    mock_retrieval.retrieve.assert_not_called()
    mock_llm.chat_completion.assert_not_called()

    assert "couldn't find" in response.answer
    assert response.citations == []

@pytest.mark.asyncio
async def test_search_ingestion_failure_resilience(service, mock_discovery, mock_ingestion, mock_retrieval, mock_llm):
    """Verify pipeline continues if one source fails ingestion."""
    search_results = [
        WebSearchResult(url="http://good.com", snippet="Good", title="Good Title", domain="good.com"),
        WebSearchResult(url="http://bad.com", snippet="Bad", title="Bad Title", domain="bad.com")
    ]
    mock_discovery.find_urls.return_value = search_results

    # Side effect: First works, second raises Exception
    # The service uses return_exceptions=True in asyncio.gather
    mock_ingestion.ingest_from_search_result.side_effect = ["doc-1", Exception("Scrape failed")]

    # Mock retrieval
    mock_chunk = MagicMock()
    mock_chunk.content = "Content"
    mock_retrieval.retrieve.return_value = [mock_chunk]

    # Mock LLM
    mock_llm_response = MagicMock()
    mock_llm_response.content = "Answer"
    mock_llm.chat_completion.return_value = mock_llm_response

    response = await service.search("query")

    # Verify both tried
    assert mock_ingestion.ingest_from_search_result.call_count == 2
    
    # Retrieval should still happen (despite one failure, we have doc-1)
    mock_retrieval.retrieve.assert_called_once()
    
    # Check that logger warning was likely logged (implicit, can spy on logger if needed)
    assert response.answer == "Answer"
    # Citations should include the valid results passed to Valid Results list (which was filtered before ingestion)
    # The citation list is based on valid_results from discovery, NOT successful ingestion doc_ids in current impl.
    assert len(response.citations) == 2
