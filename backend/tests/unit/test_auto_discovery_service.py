import pytest
from unittest.mock import AsyncMock
from services.auto_discovery_service import AutoDiscoveryService
from llm_common.core.models import WebSearchResult

@pytest.mark.asyncio
async def test_discover_sources_success():
    """
    Test that `discover_sources` returns a list of dictionaries on successful search.
    """
    # Arrange
    mock_search_client = AsyncMock()
    mock_search_client.search.return_value = [
        WebSearchResult(
            url="http://example.com/city-council",
            title="City Council Meetings",
            snippet="Official website for city council meetings.",
            domain="example.com",
        )
    ]
    service = AutoDiscoveryService(search_client=mock_search_client)

    # Act
    results = await service.discover_sources("Example City", "city")

    # Assert
    assert len(results) == 1
    assert results[0]["url"] == "http://example.com/city-council"
    assert results[0]["title"] == "City Council Meetings"
    mock_search_client.search.assert_called_once_with(
        "city council meetings Example City"
    )

@pytest.mark.asyncio
async def test_discover_sources_no_results():
    """
    Test that `discover_sources` returns an empty list when the search client returns no results.
    """
    # Arrange
    mock_search_client = AsyncMock()
    mock_search_client.search.return_value = []
    service = AutoDiscoveryService(search_client=mock_search_client)

    # Act
    results = await service.discover_sources("No Results City", "city")

    # Assert
    assert len(results) == 0
    mock_search_client.search.assert_called_once_with(
        "city council meetings No Results City"
    )

@pytest.mark.asyncio
async def test_discover_sources_search_client_error():
    """
    Test that `discover_sources` returns an empty list when the search client raises an exception.
    """
    # Arrange
    mock_search_client = AsyncMock()
    mock_search_client.search.side_effect = Exception("Search failed")
    service = AutoDiscoveryService(search_client=mock_search_client)

    # Act
    results = await service.discover_sources("Error City", "city")

    # Assert
    assert len(results) == 0
    mock_search_client.search.assert_called_once_with(
        "city council meetings Error City"
    )

@pytest.mark.asyncio
async def test_discover_sources_invalid_jurisdiction_type():
    """
    Test that `discover_sources` returns an empty list for an unsupported jurisdiction type.
    """
    # Arrange
    mock_search_client = AsyncMock()
    service = AutoDiscoveryService(search_client=mock_search_client)

    # Act
    results = await service.discover_sources("Anywhere", "unsupported_type")

    # Assert
    assert len(results) == 0
    mock_search_client.search.assert_not_called()
