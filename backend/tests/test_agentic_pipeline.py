import pytest
from unittest.mock import AsyncMock, MagicMock
from services.llm.orchestrator import AnalysisPipeline, LegislationAnalysisResponse, ReviewCritique
from schemas.analysis import LegislationImpact
from llm_common.core import LLMClient
from llm_common.web_search import WebSearchClient

@pytest.mark.asyncio
async def test_analysis_pipeline_integration():
    # 1. Setup Mocks
    mock_llm = MagicMock(spec=LLMClient)
    mock_search = MagicMock(spec=WebSearchClient)
    mock_db = MagicMock()
    
    # Mock LLM Chat Responses
    # Needs to handle Sequence calls: generate, review, refine
    
    # Mock Generate Response
    analysis_obj = LegislationAnalysisResponse(
        bill_number="AB-1234",
        impacts=[
            LegislationImpact(
                impact_number=1, 
                relevant_clause="Rent Control", 
                legal_interpretation="Limits increase",
                impact_description="Lower rent",
                evidence=[
                    {"source_name": "Mock Source", "url": "http://example.com", "excerpt": "Rent control is good"}
                ],
                chain_of_causality="ABC",
                confidence_score=0.9,
                p10=10.0, p25=20.0, p50=50.0, p75=100.0, p90=200.0
            )
        ],
        total_impact_p50=50.0,
        analysis_timestamp="2025-01-01",
        model_used="test-model"
    )
    
    # Mock Review Response
    review_obj = ReviewCritique(passed=True, critique="Good", missing_impacts=[], factual_errors=[])
    
    # Mock Responses
    mock_resp_1 = MagicMock()
    mock_resp_1.content = analysis_obj.model_dump_json()
    
    mock_resp_2 = MagicMock()
    mock_resp_2.content = review_obj.model_dump_json()
    
    mock_llm.chat_completion.side_effect = [mock_resp_1, mock_resp_2]
    
    # Mock DB
    mock_db.create_pipeline_run = AsyncMock(return_value="run-1")
    mock_db.get_or_create_jurisdiction = AsyncMock(return_value=1)
    mock_db.store_legislation = AsyncMock(return_value=101)
    mock_db.store_impacts = AsyncMock()
    mock_db.complete_pipeline_run = AsyncMock()
    
    # 2. Initialize Pipeline
    pipeline = AnalysisPipeline(mock_llm, mock_search, mock_db)
    
    # Mock the internal ResearchAgent to skip actual planning/execution logic
    pipeline.research_agent.run = AsyncMock(return_value={
        "collected_data": [{"url": "http://example.com", "snippet": "Rent control passed"}]
    })
    
    # 3. Execution
    models = {"research": "m1", "generate": "m2", "review": "m3"}
    result = await pipeline.run("AB-1234", "The bill text...", "San Jose", models)
    
    # 4. Verification
    
    # Check Research Step
    pipeline.research_agent.run.assert_called_once()
    
    # Check Generate Step (LLM Called)
    assert mock_llm.chat_completion.call_count >= 2 # Generate + Review
    
    # Check DB Storage
    mock_db.store_legislation.assert_called_once()
    mock_db.store_impacts.assert_called_once()
    mock_db.complete_pipeline_run.assert_called_once()
    
    assert result.bill_number == "AB-1234"
    assert len(result.impacts) == 1
