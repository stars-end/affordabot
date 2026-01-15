import pytest
from unittest.mock import AsyncMock, MagicMock

from agents.tools.zai_search import ZaiSearchTool
from services.research.zai import ResearchPackage, Source as ZaiSource, ZaiResearchService
from llm_common.agents.provenance import EvidenceEnvelope

@pytest.mark.asyncio
async def test_zai_search_tool_success():
    """
    Tests that ZaiSearchTool successfully calls the research service
    and returns a properly formatted ToolResult with an EvidenceEnvelope.
    """
    # Arrange
    mock_service = MagicMock(spec=ZaiResearchService)
    mock_research_package = ResearchPackage(
        summary="This is a test summary.",
        key_facts=["Fact 1", "Fact 2"],
        sources=[
            ZaiSource(url="http://example.com/source1", title="Source 1", snippet="Snippet 1"),
            ZaiSource(url="http://example.com/source2", title="Source 2", snippet="Snippet 2"),
        ],
    )
    mock_service.search_exhaustively = AsyncMock(return_value=mock_research_package)

    tool = ZaiSearchTool(zai_service=mock_service)
    bill_text = "This is a sample bill text."
    bill_number = "AB-123"

    # Act
    result = await tool.execute(bill_text=bill_text, bill_number=bill_number)

    # Assert
    mock_service.search_exhaustively.assert_called_once_with(
        bill_text=bill_text, bill_number=bill_number
    )

    assert result.success is True
    assert result.error is None
    assert result.data["summary"] == "This is a test summary."
    assert len(result.source_urls) == 2
    assert "http://example.com/source1" in result.source_urls

    assert len(result.evidence) == 1
    envelope = result.evidence[0]
    assert isinstance(envelope, EvidenceEnvelope)
    assert envelope.source_tool == "zai_search"
    assert len(envelope.evidence) == 2
    assert envelope.evidence[0].kind == "url"
    assert envelope.evidence[0].label == "Source 1"
    assert envelope.evidence[0].content == "Snippet 1"

@pytest.mark.asyncio
async def test_zai_search_tool_failure():
    """
    Tests that ZaiSearchTool returns a failed ToolResult when the service raises an exception.
    """
    # Arrange
    mock_service = MagicMock(spec=ZaiResearchService)
    mock_service.search_exhaustively = AsyncMock(side_effect=Exception("Service unavailable"))

    tool = ZaiSearchTool(zai_service=mock_service)

    # Act
    result = await tool.execute(bill_text="test", bill_number="test-123")

    # Assert
    assert result.success is False
    assert "Service unavailable" in result.error
    assert result.data is None
    assert len(result.evidence) == 0
