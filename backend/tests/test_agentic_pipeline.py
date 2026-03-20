import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from services.llm.orchestrator import AnalysisPipeline
from services.legislation_research import LegislationResearchResult
from schemas.analysis import (
    LegislationAnalysisResponse,
    ReviewCritique,
    LegislationImpact,
)
from llm_common.core import LLMClient
from llm_common.web_search import WebSearchClient


def _make_legislation_response():
    return LegislationAnalysisResponse(
        bill_number="AB-1234",
        title="Test Bill",
        jurisdiction="San Jose",
        status="introduced",
        impacts=[
            LegislationImpact(
                impact_number=1,
                relevant_clause="Rent Control",
                legal_interpretation="Limits increase",
                impact_description="Lower rent",
                evidence=[
                    {
                        "source_name": "Mock Source",
                        "url": "http://example.com",
                        "excerpt": "Rent control is good",
                    }
                ],
                chain_of_causality="ABC",
                confidence_score=0.9,
                p10=10.0,
                p25=20.0,
                p50=50.0,
                p75=100.0,
                p90=200.0,
            )
        ],
        total_impact_p50=50.0,
        analysis_timestamp="2025-01-01",
        model_used="test-model",
    )


def _make_review_response():
    return ReviewCritique(
        passed=True, critique="Good", missing_impacts=[], factual_errors=[]
    )


def _make_research_result():
    return LegislationResearchResult(
        bill_id="AB-1234",
        jurisdiction="San Jose",
        evidence_envelopes=[],
        rag_chunks=[],
        web_sources=[],
        sufficiency_breakdown={
            "source_text_present": True,
            "rag_chunks_retrieved": 0,
            "web_research_sources_found": 0,
            "fiscal_notes_detected": False,
            "bill_text_chunks": 0,
        },
        is_sufficient=True,
    )


@pytest.mark.asyncio
async def test_analysis_pipeline_uses_research_service():
    mock_llm = MagicMock(spec=LLMClient)
    mock_search = MagicMock(spec=WebSearchClient)
    mock_db = MagicMock()

    analysis_obj = _make_legislation_response()
    review_obj = _make_review_response()

    mock_resp_1 = MagicMock()
    mock_resp_1.content = analysis_obj.model_dump_json()
    mock_resp_2 = MagicMock()
    mock_resp_2.content = review_obj.model_dump_json()

    mock_llm.chat_completion = AsyncMock(side_effect=[mock_resp_1, mock_resp_2])

    mock_db.get_latest_scrape_for_bill = AsyncMock(
        return_value={
            "id": 1,
            "document_id": "doc-123",
            "url": "http://example.com/bill",
            "content_hash": "abc",
            "metadata": {"title": "Test Bill"},
            "storage_uri": "s3://bucket/bill.pdf",
        }
    )
    mock_db.get_vector_stats = AsyncMock(return_value={"chunk_count": 5})
    mock_db.create_pipeline_run = AsyncMock(return_value="run-1")
    mock_db.get_or_create_jurisdiction = AsyncMock(return_value=1)
    mock_db.store_legislation = AsyncMock(return_value=101)
    mock_db.store_impacts = AsyncMock()
    mock_db.complete_pipeline_run = AsyncMock()
    mock_db.fail_pipeline_run = AsyncMock()

    pipeline = AnalysisPipeline(mock_llm, mock_search, mock_db)

    research_result = _make_research_result()
    with patch.object(
        pipeline.research_service,
        "research",
        new_callable=AsyncMock,
        return_value=research_result,
    ):
        models = {"research": "m1", "generate": "m2", "review": "m3"}
        result = await pipeline.run("AB-1234", "The bill text...", "San Jose", models)

    assert mock_llm.chat_completion.call_count >= 2
    mock_db.store_legislation.assert_called_once()
    mock_db.complete_pipeline_run.assert_called_once()

    assert result.bill_number == "AB-1234"
    assert len(result.impacts) == 1


@pytest.mark.asyncio
async def test_pipeline_stored_title_not_placeholder():
    mock_llm = MagicMock(spec=LLMClient)
    mock_search = MagicMock(spec=WebSearchClient)
    mock_db = MagicMock()

    analysis_obj = _make_legislation_response()
    review_obj = _make_review_response()

    mock_llm.chat_completion = AsyncMock(
        side_effect=[
            MagicMock(content=analysis_obj.model_dump_json()),
            MagicMock(content=review_obj.model_dump_json()),
        ]
    )

    mock_db.get_latest_scrape_for_bill = AsyncMock(return_value=None)
    mock_db.create_pipeline_run = AsyncMock(return_value="run-1")
    mock_db.get_or_create_jurisdiction = AsyncMock(return_value=1)
    mock_db.store_legislation = AsyncMock(return_value=101)
    mock_db.store_impacts = AsyncMock()
    mock_db.complete_pipeline_run = AsyncMock()
    mock_db.fail_pipeline_run = AsyncMock()

    pipeline = AnalysisPipeline(mock_llm, mock_search, mock_db)

    research_result = _make_research_result()
    with patch.object(
        pipeline.research_service,
        "research",
        new_callable=AsyncMock,
        return_value=research_result,
    ):
        models = {"research": "m1", "generate": "m2", "review": "m3"}
        await pipeline.run("AB-1234", "The bill text...", "San Jose", models)

    call_args = mock_db.store_legislation.call_args
    bill_data = (
        call_args[0][1]
        if len(call_args[0]) > 1
        else call_args[1].get("bill_data", call_args[0][1])
    )
    stored_title = bill_data.get("title", "")
    assert "Analysis: " not in stored_title
    assert "placeholder" not in stored_title.lower()
