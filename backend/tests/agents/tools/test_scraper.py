import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from agents.tools.scraper import ScraperTool
from services.scraper.base import ScrapedBill
from llm_common.agents.provenance import EvidenceEnvelope
from datetime import date

@pytest.fixture
def mock_scrapers():
    """Mocks the SCRAPERS registry."""
    # Create a mock scraper class that has an async scrape method
    mock_scraper_instance = MagicMock()
    mock_scraper_instance.scrape = AsyncMock(
        return_value=[
            ScrapedBill(
                bill_number="SB-456",
                title="A Test Bill",
                text="This is the text of the test bill.",
                introduced_date=date(2024, 1, 1),
                status="In Committee",
            )
        ]
    )
    
    # The factory function (the class itself) returns the instance
    mock_scraper_class = MagicMock(return_value=mock_scraper_instance)

    with patch(
        "agents.tools.scraper.SCRAPERS",
        {"test-jurisdiction": (mock_scraper_class, "city")},
    ) as mock:
        yield mock, mock_scraper_class, mock_scraper_instance

@pytest.mark.asyncio
async def test_scraper_tool_success(mock_scrapers):
    """
    Tests that ScraperTool successfully calls the correct scraper and returns a
    properly formatted ToolResult with an EvidenceEnvelope.
    """
    # Arrange
    _, mock_scraper_class, mock_scraper_instance = mock_scrapers
    tool = ScraperTool()
    jurisdiction = "test-jurisdiction"

    # Act
    result = await tool.execute(jurisdiction=jurisdiction)

    # Assert
    mock_scraper_class.assert_called_once_with(jurisdiction_name=jurisdiction)
    mock_scraper_instance.scrape.assert_called_once()

    assert result.success is True
    assert result.error is None
    assert len(result.data) == 1
    assert result.data[0]["bill_number"] == "SB-456"

    assert len(result.evidence) == 1
    envelope = result.evidence[0]
    assert isinstance(envelope, EvidenceEnvelope)
    assert envelope.source_tool == "scrape_legislation"
    assert len(envelope.evidence) == 1
    evidence = envelope.evidence[0]
    assert evidence.kind == "legislation"
    assert evidence.label == "SB-456: A Test Bill"
    assert evidence.content == "This is the text of the test bill."
    assert evidence.metadata["status"] == "In Committee"

@pytest.mark.asyncio
async def test_scraper_tool_invalid_jurisdiction():
    """
    Tests that ScraperTool returns a failed ToolResult for an invalid jurisdiction.
    """
    # Arrange
    tool = ScraperTool()

    # Act
    result = await tool.execute(jurisdiction="non-existent")

    # Assert
    assert result.success is False
    assert "Invalid jurisdiction" in result.error

@pytest.mark.asyncio
async def test_scraper_tool_failure(mock_scrapers):
    """
    Tests that ScraperTool returns a failed ToolResult when the scraper raises an exception.
    """
    # Arrange
    _, _, mock_scraper_instance = mock_scrapers
    mock_scraper_instance.scrape.side_effect = Exception("Scraper failed to load")
    tool = ScraperTool()

    # Act
    result = await tool.execute(jurisdiction="test-jurisdiction")

    # Assert
    assert result.success is False
    assert "Scraper failed to load" in result.error
