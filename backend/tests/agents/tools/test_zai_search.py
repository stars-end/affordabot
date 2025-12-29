import pytest
from unittest.mock import AsyncMock
from agents.tools.zai_search import ZaiSearchTool
from services.research.zai import ResearchPackage, Source

@pytest.fixture
def mock_zai_service():
    """Fixture to create a mock ZaiResearchService."""
    mock_service = AsyncMock()
    
    # Create a mock ResearchPackage
    mock_package = ResearchPackage(
        summary="This is a summary.",
        key_facts=["Fact 1", "Fact 2"],
        sources=[
            Source(
                url="http://example.com/source1",
                title="Source 1",
                publisher="Publisher 1",
                publish_date="2024-01-01",
                content="This is the content of source 1.",
            ),
            Source(
                url="http://example.com/source2",
                title="Source 2",
                publisher="Publisher 2",
                publish_date="2024-01-02",
                content="This is the content of source 2.",
            ),
        ],
        confidence_score=0.9,
    )
    
    mock_service.search_exhaustively = AsyncMock(return_value=mock_package)
    return mock_service

@pytest.mark.asyncio
async def test_zai_search_tool_returns_evidence_envelope(mock_zai_service):
    """
    Test that the ZaiSearchTool's execute method returns a ToolResult
    containing a valid EvidenceEnvelope.
    """
    # Arrange
    tool = ZaiSearchTool(service=mock_zai_service)
    bill_text = "This is a test bill."
    bill_number = "AB 123"
    
    # Act
    result = await tool.execute(bill_text, bill_number)
    
    # Assert
    assert result.success is True
    assert "envelope" in result.data
    
    # Validate the envelope
    envelope_data = result.data["envelope"]
    assert envelope_data["source_tool"] == "zai_search"
    assert envelope_data["source_query"] == bill_number
    
    # Check that evidence from sources, summary, and facts are all present
    assert len(envelope_data["evidence"]) == 2 + 1 + 2  # 2 sources, 1 summary, 2 facts
    
    # Check one piece of evidence in detail
    source_evidence = next(e for e in envelope_data["evidence"] if e["kind"] == "url" and e["url"] == "http://example.com/source1")
    assert source_evidence["label"] == "Source 1"
    assert source_evidence["metadata"]["publisher"] == "Publisher 1"
    
    summary_evidence = next(e for e in envelope_data["evidence"] if e["kind"] == "summary")
    assert summary_evidence["content"] == "This is a summary."
    
    fact_evidence = next(e for e in envelope_data["evidence"] if e["kind"] == "fact" and "Fact 1" in e["content"])
    assert fact_evidence is not None

    # Verify the service method was called correctly
    mock_zai_service.search_exhaustively.assert_called_once_with(
        bill_text=bill_text, bill_number=bill_number
    )
