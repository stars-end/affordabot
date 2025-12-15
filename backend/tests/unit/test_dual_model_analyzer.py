
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from services.llm.pipeline import DualModelAnalyzer, ReviewCritique
from schemas.analysis import LegislationAnalysisResponse
from services.research.zai import ResearchPackage, SearchResult

# Define mock response objects
@pytest.fixture
def mock_research_package():
    return ResearchPackage(
        summary="Research summary",
        key_facts=["Fact 1"],
        opposition_arguments=["Opp 1"],
        fiscal_estimates=["Est 1"],
        sources=[SearchResult(url="http://test.com", title="Test", snippet="Snippet")]
    )

@pytest.fixture
def mock_analysis_response():
    # Create a minimal valid response
    return LegislationAnalysisResponse(
        bill_number="AB-123",
        impacts=[], 
        total_impact_p50=100.0,
        analysis_timestamp="2025-01-01T00:00:00",
        model_used="test-model"
    )

@pytest.fixture
def mock_review_critique_passed():
    return ReviewCritique(
        passed=True,
        critique="Good",
        missing_impacts=[],
        factual_errors=[],
        citation_issues=[]
    )

@pytest.fixture
def mock_review_critique_failed():
    return ReviewCritique(
        passed=False,
        critique="Bad",
        missing_impacts=["Impact 1"],
        factual_errors=[],
        citation_issues=[]
    )

@pytest.fixture
def analyzer(mock_research_package):
    """
    Fixture that patches external dependencies and returns an analyzer instance
    with those mocks pre-configured.
    """
    with patch("services.llm.pipeline.ZaiResearchService") as MockResearcher, \
         patch("services.llm.pipeline.instructor.from_openai") as mock_from_openai, \
         patch("services.llm.pipeline.AsyncOpenAI") as mock_openai:
        
        # Setup Researcher Mock
        mock_researcher_instance = MockResearcher.return_value
        mock_researcher_instance.search_exhaustively = AsyncMock(return_value=mock_research_package)
        
        # Setup LLM Client Mock
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock()
        mock_from_openai.return_value = mock_client
        
        # Initialize analyzer
        analyzer_instance = DualModelAnalyzer()
        
        # Attach mocks to the instance for test access
        analyzer_instance._mock_llm_client = mock_client
        analyzer_instance._mock_researcher = mock_researcher_instance
        
        yield analyzer_instance

@pytest.mark.asyncio
async def test_analyze_flow_success(analyzer, mock_analysis_response, mock_review_critique_passed):
    """
    Verify the happy path:
    1. Research called
    2. Generation called -> Draft
    3. Review called -> Passed
    4. Returns Draft
    """
    # Setup LLM responses
    # The pipeline calls:
    # 1. _generate_draft (via _call_with_fallback)
    # 2. _review_draft (via _call_with_fallback)
    
    analyzer._mock_llm_client.chat.completions.create.side_effect = [
        mock_analysis_response, # Generation
        mock_review_critique_passed # Review
    ]
    
    result = await analyzer.analyze("bill text", "AB-123", "CA")
    
    assert result == mock_analysis_response
    assert analyzer._mock_researcher.search_exhaustively.called
    assert analyzer._mock_llm_client.chat.completions.create.call_count == 2

@pytest.mark.asyncio
async def test_analyze_flow_refinement(analyzer, mock_analysis_response, mock_review_critique_failed):
    """
    Verify refinement path:
    1. Research called
    2. Generation called -> Draft
    3. Review called -> Failed
    4. Refinement called -> Final (mocked as same response object for simplicity)
    5. Returns Final
    """
    
    analyzer._mock_llm_client.chat.completions.create.side_effect = [
        mock_analysis_response, # Generation
        mock_review_critique_failed, # Review (Failed)
        mock_analysis_response # Refinement
    ]
    
    result = await analyzer.analyze("bill text", "AB-123", "CA")
    
    assert result == mock_analysis_response
    assert analyzer._mock_llm_client.chat.completions.create.call_count == 3 
    # 1. Gen, 2. Review, 3. Refine

@pytest.mark.asyncio
async def test_check_health_all_healthy(analyzer):
    """Verify health check returns healthy when calls succeed."""
    
    # Setup successful ping
    class HealthCheck:
        status = "ok"
    
    analyzer._mock_llm_client.chat.completions.create.return_value = HealthCheck()
    
    status = await analyzer.check_health()
    
    assert status["generation"] == "healthy"
    assert status["review"] == "healthy"

@pytest.mark.asyncio
async def test_call_with_fallback_retry(analyzer, mock_analysis_response):
    """
    Verify fallback logic:
    If first model fails, try second model.
    """
    # Create a new analyzer with controlled models list for this test
    analyzer.gen_models = [
        ("model1", "provider1"),
        ("model2", "provider2")
    ]
    
    # The create method is called in loop.
    # First call raises Exception
    # Second call returns success
    analyzer._mock_llm_client.chat.completions.create.side_effect = [
        Exception("Model 1 failed"),
        mock_analysis_response
    ]
    
    response = await analyzer._call_with_fallback(
        analyzer.gen_models, "sys", "user", LegislationAnalysisResponse
    )
    
    assert response == mock_analysis_response
    assert analyzer._mock_llm_client.chat.completions.create.call_count == 2
