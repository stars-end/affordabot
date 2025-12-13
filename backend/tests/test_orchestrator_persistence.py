import sys
from unittest.mock import MagicMock

# Mock llm_common before importing orchestrator
mock_llm_common = MagicMock()
sys.modules["llm_common"] = mock_llm_common
sys.modules["llm_common.core"] = mock_llm_common
sys.modules["llm_common.web_search"] = mock_llm_common
sys.modules["llm_common.agents"] = mock_llm_common

import pytest
from unittest.mock import AsyncMock
from services.llm.orchestrator import AnalysisPipeline, BillAnalysis, ReviewCritique

@pytest.fixture
def mock_db():
    db = MagicMock()
    db.create_pipeline_run = AsyncMock(return_value="run-123")
    db.update_pipeline_run = AsyncMock(return_value=True)
    db.get_or_create_jurisdiction = AsyncMock(return_value="jur-123")
    db.store_legislation = AsyncMock(return_value="leg-123")
    db.store_impacts = AsyncMock(return_value=True)
    return db

@pytest.fixture
def mock_llm():
    llm = MagicMock()
    llm.chat = AsyncMock()
    return llm

@pytest.fixture
def mock_search():
    search = MagicMock()
    return search

@pytest.mark.asyncio
async def test_create_pipeline_run_calls_db(mock_db, mock_llm, mock_search):
    pipeline = AnalysisPipeline(mock_llm, mock_search, mock_db)

    # Mock research agent to avoid errors or actual calls
    pipeline.research_agent = MagicMock()
    pipeline.research_agent.run = AsyncMock(return_value={"collected_data": []})

    # Mock internal steps to return dummy data so we don't need to mock LLM responses perfectly
    pipeline._research_step = AsyncMock(return_value=[])

    # Mock generate step response
    analysis_mock = BillAnalysis(
        summary="Test summary",
        impacts=[],
        confidence=0.9,
        sources=[]
    )
    pipeline._generate_step = AsyncMock(return_value=analysis_mock)

    # Mock review step response
    review_mock = ReviewCritique(
        passed=True,
        critique="Good",
        missing_impacts=[],
        factual_errors=[]
    )
    pipeline._review_step = AsyncMock(return_value=review_mock)

    bill_id = "BILL-123"
    models = {"research": "gpt", "generate": "claude", "review": "gpt"}
    jurisdiction = "San Jose"
    bill_text = "Some bill text"

    await pipeline.run(bill_id, bill_text, jurisdiction, models)

    # Verify create_pipeline_run was called
    mock_db.create_pipeline_run.assert_called_once_with(bill_id, models)

    # Verify update_pipeline_run was called with 'completed'
    mock_db.update_pipeline_run.assert_called_with("run-123", "completed")

@pytest.mark.asyncio
async def test_fail_pipeline_run_calls_db(mock_db, mock_llm, mock_search):
    pipeline = AnalysisPipeline(mock_llm, mock_search, mock_db)

    # Mock create to return a valid ID
    mock_db.create_pipeline_run.return_value = "run-fail-123"

    # Make research step fail
    pipeline._research_step = AsyncMock(side_effect=Exception("Research failed"))

    bill_id = "BILL-FAIL"
    models = {"research": "gpt", "generate": "claude", "review": "gpt"}
    jurisdiction = "San Jose"
    bill_text = "Some bill text"

    with pytest.raises(Exception, match="Research failed"):
        await pipeline.run(bill_id, bill_text, jurisdiction, models)

    # Verify create_pipeline_run was called
    mock_db.create_pipeline_run.assert_called_once_with(bill_id, models)

    # Verify update_pipeline_run was called with 'failed'
    mock_db.update_pipeline_run.assert_called_with("run-fail-123", "failed", "Research failed")
