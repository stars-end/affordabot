
import pytest
from unittest.mock import AsyncMock, patch
from services.llm.analyzer import LegislationAnalyzer
from schemas.analysis import LegislationAnalysisResponse

@pytest.fixture
def analyzer():
    """
    Fixture that patches external dependencies and returns an analyzer instance
    with those mocks pre-configured.
    """
    with patch("services.llm.analyzer.instructor.from_openai") as mock_from_openai, \
         patch("services.llm.analyzer.AsyncOpenAI"), \
         patch("services.llm.analyzer.PostgresDB") as MockPostgresDB:
        
        # Setup LLM Client Mock
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock()
        mock_from_openai.return_value = mock_client
        
        # Setup DB Mock
        mock_db_instance = MockPostgresDB.return_value
        mock_db_instance.get_system_prompt = AsyncMock()
        
        # Initialize analyzer
        analyzer_instance = LegislationAnalyzer()
        
        # Attach mocks to the instance for test access
        analyzer_instance._mock_llm_client = mock_client
        analyzer_instance.db = mock_db_instance
        
        yield analyzer_instance

@pytest.mark.asyncio
async def test_analyze_fetches_prompt_from_db(analyzer):
    """
    Verify that the analyzer fetches the system prompt from the database.
    """
    # Setup DB to return a specific prompt
    db_prompt = {"system_prompt": "This is a test prompt from the database."}
    analyzer.db.get_system_prompt.return_value = db_prompt
    
    # Mock the LLM response
    mock_llm_response = LegislationAnalysisResponse(
        bill_number="AB-123",
        impacts=[],
        total_impact_p50=0.0,
        analysis_timestamp="2025-01-01T00:00:00",
        model_used="test-model"
    )
    analyzer._mock_llm_client.chat.completions.create.return_value = mock_llm_response
    
    # Call the analyze method
    await analyzer.analyze("bill text", "AB-123", "CA")
    
    # Assert that get_system_prompt was called
    analyzer.db.get_system_prompt.assert_called_once_with('legislation_analysis')
    
    # Assert that the LLM was called with the correct prompt
    call_args = analyzer._mock_llm_client.chat.completions.create.call_args
    messages = call_args.kwargs['messages']
    system_message = next((m for m in messages if m['role'] == 'system'), None)
    
    assert system_message is not None
    assert system_message['content'] == db_prompt['system_prompt']

@pytest.mark.asyncio
async def test_analyze_uses_fallback_prompt_on_db_failure(analyzer):
    """
    Verify that the analyzer uses the fallback prompt when the DB call fails.
    """
    # Setup DB to return None
    analyzer.db.get_system_prompt.return_value = None
    
    # Mock the LLM response
    mock_llm_response = LegislationAnalysisResponse(
        bill_number="AB-123",
        impacts=[],
        total_impact_p50=0.0,
        analysis_timestamp="2025-01-01T00:00:00",
        model_used="test-model"
    )
    analyzer._mock_llm_client.chat.completions.create.return_value = mock_llm_response
    
    # Call the analyze method
    await analyzer.analyze("bill text", "AB-123", "CA")
    
    # Assert that get_system_prompt was called
    analyzer.db.get_system_prompt.assert_called_once_with('legislation_analysis')
    
    # Assert that the LLM was called with the fallback prompt
    call_args = analyzer._mock_llm_client.chat.completions.create.call_args
    messages = call_args.kwargs['messages']
    system_message = next((m for m in messages if m['role'] == 'system'), None)
    
    assert system_message is not None
    assert "You are an expert policy analyst for AffordaBot" in system_message['content']
