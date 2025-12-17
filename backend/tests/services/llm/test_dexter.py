from services.llm.tools import ToolResult
from services.llm.validators import CitationValidator

def test_tool_result_success():
    result = ToolResult.ok("Analysis complete", cost=0.05)
    assert result.success is True
    assert result.content == "Analysis complete"
    assert result.metadata["cost"] == 0.05

def test_tool_result_failure():
    result = ToolResult.fail("API Timeout")
    assert result.success is False
    assert result.error_message == "API Timeout"

def test_citation_validator():
    source = "The quick brown fox jumps over the lazy dog."
    
    # Valid quote
    analysis_valid = 'The text states "quick brown fox".'
    warnings = CitationValidator.validate_citations(analysis_valid, source)
    assert len(warnings) == 0
    
    # Invalid quote (hallucination)
    analysis_invalid = 'The text states "slow purple cat".'
    # Validator checks quotes > 20 chars usually, let's make it long enough or adjust validator logic
    # My implementation had > 20 chars check.
    
    analysis_long_invalid = 'The text explicitly says "the slow purple cat jumps over the moon and stars".'
    warnings = CitationValidator.validate_citations(analysis_long_invalid, source)
    assert len(warnings) == 1
    assert "Quote not found" in warnings[0]
