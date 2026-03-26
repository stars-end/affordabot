import pytest
import json
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
from llm_common.agents.provenance import Evidence, EvidenceEnvelope
from services.llm.orchestrator import STEP_INDEX, PrefixFixtureError


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
                        "excerpt": (
                            "The ordinance limits annual rent increases for covered "
                            "units, which directly lowers monthly rent growth for "
                            "tenants compared with market-rate adjustments."
                        ),
                    }
                ],
                chain_of_causality="ABC",
                confidence_score=0.9,
                impact_mode="direct_fiscal",
                scenario_bounds={
                    "conservative": 10.0,
                    "central": 50.0,
                    "aggressive": 200.0,
                },
            )
        ],
        aggregate_scenario_bounds={
            "conservative": 10.0,
            "central": 50.0,
            "aggressive": 200.0,
        },
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


def _seed_direct_fiscal_candidate(
    research_result: LegislationResearchResult,
    *,
    amount: float,
    source_url: str,
    source_excerpt: str,
) -> LegislationResearchResult:
    research_result.rag_chunks = [
        MagicMock(
            content=source_excerpt,
            score=0.91,
            metadata={"source_url": source_url, "source_type": "fiscal_note"},
        )
    ]
    research_result.impact_candidates = [
        {
            "impact_id": "impact-direct-fiscal",
            "impact_description": "Official fiscal impact reported for the measure.",
            "relevant_clauses": [],
            "evidence_refs": [source_url],
            "candidate_mode_hints": ["direct_fiscal"],
            "impact_scope": "bill",
        }
    ]
    research_result.parameter_candidates = {
        "impact-direct-fiscal": {
            "fiscal_amount": {
                "value": amount,
                "unit": "usd_per_month",
                "source_url": source_url,
                "source_excerpt": source_excerpt,
                "source_hierarchy_status": "fiscal_or_reg_impact_analysis",
                "excerpt_validation_status": "pass",
            }
        }
    }
    return research_result


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


def test_wave2_prerequisites_serializer_is_json_safe():
    mock_llm = MagicMock(spec=LLMClient)
    mock_search = MagicMock(spec=WebSearchClient)
    mock_db = MagicMock()
    pipeline = AnalysisPipeline(mock_llm, mock_search, mock_db)

    payload = {
        "impact_candidates": [
            {"impact_id": "impact-pass-through-incidence", "candidate_mode_hints": ["pass_through_incidence"]}
        ],
        "parameter_candidates": {
            "impact-pass-through-incidence": {
                "pass_through_rate": {"value": 0.7, "source_url": "https://example.org"}
            }
        },
        "curated_evidence_envelopes": [
            EvidenceEnvelope(
                id="curated-1",
                source_tool="curated_lookup",
                source_query="AB-1 wave2",
                evidence=[
                    Evidence(
                        id="ev-1",
                        kind="external",
                        label="Curated study",
                        url="https://example.org/study",
                        content="",
                        excerpt="Example excerpt",
                        metadata={"source_type": "academic_literature"},
                    )
                ],
            )
        ],
    }

    serialized = pipeline._serialize_wave2_prerequisites(payload)
    json.dumps(serialized)
    assert "curated_evidence_envelopes" not in serialized
    assert serialized["curated_evidence"][0]["source_tool"] == "curated_lookup"
    assert serialized["curated_evidence"][0]["evidence"][0]["source_type"] == "academic_literature"


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


@pytest.mark.asyncio
async def test_pipeline_overrides_model_generated_metadata_with_runtime_truth():
    mock_llm = MagicMock(spec=LLMClient)
    mock_search = MagicMock(spec=WebSearchClient)
    mock_db = MagicMock()

    analysis_obj = _make_legislation_response()
    analysis_obj.bill_number = "WRONG"
    analysis_obj.jurisdiction = "Wrong Place"
    analysis_obj.model_used = "hallucinated-model"
    analysis_obj.analysis_timestamp = "2024-05-22T00:00:00Z"
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
        result = await pipeline.run("AB-1234", "The bill text...", "San Jose", models)

    assert result.bill_number == "AB-1234"
    assert result.jurisdiction == "San Jose"
    assert result.model_used == "m2"
    assert result.analysis_timestamp != "2024-05-22T00:00:00Z"


@pytest.mark.asyncio
async def test_pipeline_forces_refine_when_review_lists_missing_impacts():
    mock_llm = MagicMock(spec=LLMClient)
    mock_search = MagicMock(spec=WebSearchClient)
    mock_db = MagicMock()

    analysis_obj = _make_legislation_response()
    review_obj = ReviewCritique(
        passed=True,
        critique="Mostly fine",
        missing_impacts=["State reimbursement timing"],
        factual_errors=[],
    )
    final_review_obj = _make_review_response()
    refined_obj = _make_legislation_response()
    refined_obj.impacts[0].impact_description = "Refined impact description"
    refined_obj.impacts[0].legal_interpretation = "Refined impact description"
    refined_obj.impacts[0].chain_of_causality = "Refined impact description"
    refined_obj.impacts[0].evidence[0].excerpt = (
        "Refined impact description is directly supported by the cited ordinance "
        "text and the tenant-facing cost change it describes."
    )

    mock_llm.chat_completion = AsyncMock(
        side_effect=[
            MagicMock(content=analysis_obj.model_dump_json()),
            MagicMock(content=review_obj.model_dump_json()),
            MagicMock(content=refined_obj.model_dump_json()),
            MagicMock(content=final_review_obj.model_dump_json()),
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
        result = await pipeline.run("AB-1234", "The bill text...", "San Jose", models)

    assert mock_llm.chat_completion.call_count == 4
    persisted = mock_db.complete_pipeline_run.call_args.args[1]
    assert persisted["review"]["passed"] is True
    assert result.impacts[0].impact_description == "Refined impact description"


@pytest.mark.asyncio
async def test_pipeline_ignores_non_fiscal_missing_impacts_for_review_pass():
    mock_llm = MagicMock(spec=LLMClient)
    mock_search = MagicMock(spec=WebSearchClient)
    mock_db = MagicMock()

    analysis_obj = _make_legislation_response()
    review_obj = ReviewCritique(
        passed=True,
        critique="Fiscal analysis is conservative and sound.",
        missing_impacts=[
            "Potential non-fiscal impacts related to civil liberties",
            "Potential public safety impacts of the new search requirements",
        ],
        factual_errors=[],
    )

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
        result = await pipeline.run("AB-1234", "The bill text...", "San Jose", models)

    assert mock_llm.chat_completion.call_count == 2
    persisted = mock_db.complete_pipeline_run.call_args.args[1]
    assert persisted["review"]["passed"] is True
    assert persisted["review"]["missing_impacts"] == []
    assert result.impacts[0].impact_description == "Lower rent"


@pytest.mark.asyncio
async def test_pipeline_fail_closed_when_claims_not_supported_by_excerpts():
    mock_llm = MagicMock(spec=LLMClient)
    mock_search = MagicMock(spec=WebSearchClient)
    mock_db = MagicMock()

    analysis_obj = _make_legislation_response()
    analysis_obj.impacts[0].relevant_clause = (
        "Resolved, That the Chief Clerk of the Assembly transmit copies "
        "of this resolution to the author for appropriate distribution."
    )
    analysis_obj.impacts[0].legal_interpretation = (
        "This concurrent resolution is non-binding and creates no new funding."
    )
    analysis_obj.impacts[0].impact_description = (
        "This resolution merely recognizes maternal-health work and creates no "
        "cost-of-living impact."
    )
    analysis_obj.impacts[0].evidence[0].excerpt = (
        "Resolved, That the Chief Clerk of the Assembly transmit copies of this "
        "resolution to the author for appropriate distribution."
    )
    review_obj = _make_review_response()
    final_review_obj = _make_review_response()
    refined_obj = _make_legislation_response()
    refined_obj.impacts[0].relevant_clause = analysis_obj.impacts[0].relevant_clause
    refined_obj.impacts[0].legal_interpretation = analysis_obj.impacts[0].legal_interpretation
    refined_obj.impacts[0].impact_description = analysis_obj.impacts[0].impact_description
    refined_obj.impacts[0].chain_of_causality = analysis_obj.impacts[0].chain_of_causality
    refined_obj.impacts[0].evidence[0].source_name = analysis_obj.impacts[0].evidence[0].source_name
    refined_obj.impacts[0].evidence[0].excerpt = (
        "Resolved, that the secretary transmits copies."
    )

    mock_llm.chat_completion = AsyncMock(
        side_effect=[
            MagicMock(content=analysis_obj.model_dump_json()),
            MagicMock(content=review_obj.model_dump_json()),
            MagicMock(content=refined_obj.model_dump_json()),
            MagicMock(content=final_review_obj.model_dump_json()),
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

    assert mock_llm.chat_completion.call_count == 4
    persisted = mock_db.complete_pipeline_run.call_args.args[1]
    assert persisted["review"]["passed"] is False
    assert any(
        "do not materially support" in err.lower()
        for err in persisted["review"]["factual_errors"]
    )


@pytest.mark.asyncio
async def test_review_prompt_includes_evidence_excerpts():
    mock_llm = MagicMock(spec=LLMClient)
    mock_search = MagicMock(spec=WebSearchClient)
    mock_db = MagicMock()

    analysis_obj = _make_legislation_response()
    review_obj = _make_review_response()
    refined_obj = _make_legislation_response()
    final_review_obj = _make_review_response()

    mock_llm.chat_completion = AsyncMock(
        side_effect=[
            MagicMock(content=analysis_obj.model_dump_json()),
            MagicMock(content=review_obj.model_dump_json()),
            MagicMock(content=refined_obj.model_dump_json()),
            MagicMock(content=final_review_obj.model_dump_json()),
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
    excerpt = (
        "Section 1 requires officers to advise consent is voluntary and record consent."
    )
    research_result.evidence_envelopes = [
        EvidenceEnvelope(
            id="env-1",
            source_tool="retriever",
            source_query="SB 277",
            evidence=[
                Evidence(
                    id="rag-1",
                    kind="internal",
                    label="SB 277 source",
                    url="https://leginfo.legislature.ca.gov/sb277",
                    content="",
                    excerpt=excerpt,
                )
            ],
        )
    ]
    _seed_direct_fiscal_candidate(
        research_result,
        amount=50.0,
        source_url="https://leginfo.legislature.ca.gov/sb277",
        source_excerpt=excerpt,
    )

    with patch.object(
        pipeline.research_service,
        "research",
        new_callable=AsyncMock,
        return_value=research_result,
    ):
        models = {"research": "m1", "generate": "m2", "review": "m3"}
        await pipeline.run("AB-1234", "The bill text...", "San Jose", models)

    review_call = mock_llm.chat_completion.await_args_list[1]
    review_user_message = review_call.kwargs["messages"][1].content
    assert "Evidence Excerpts:" in review_user_message
    assert "advise consent is voluntary" in review_user_message


@pytest.mark.asyncio
async def test_pipeline_hydrates_weak_excerpt_from_research_provenance():
    mock_llm = MagicMock(spec=LLMClient)
    mock_search = MagicMock(spec=WebSearchClient)
    mock_db = MagicMock()

    analysis_obj = _make_legislation_response()
    analysis_obj.impacts[0].impact_description = (
        "District compliance procedures increase local administrative costs."
    )
    analysis_obj.impacts[0].evidence[0].url = "https://leginfo.legislature.ca.gov/sb277"
    analysis_obj.impacts[0].evidence[0].excerpt = (
        "The secretary of the Senate shall transmit chaptered copies."
    )
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
    research_result.evidence_envelopes = [
        EvidenceEnvelope(
            id="env-1",
            source_tool="retriever",
            source_query="SB 277",
            evidence=[
                Evidence(
                    id="rag-1",
                    kind="internal",
                    label="SB 277 analysis",
                    url="https://leginfo.legislature.ca.gov/sb277",
                    content="",
                    excerpt=(
                        "This bill requires local educational agencies to track "
                        "immunization records and enforce compliance procedures, "
                        "which increases district administrative workload."
                    ),
                )
            ],
        )
    ]

    with patch.object(
        pipeline.research_service,
        "research",
        new_callable=AsyncMock,
        return_value=research_result,
    ):
        models = {"research": "m1", "generate": "m2", "review": "m3"}
        result = await pipeline.run("AB-1234", "The bill text...", "San Jose", models)

    assert mock_llm.chat_completion.call_count == 2
    assert "requires local educational agencies" in result.impacts[0].evidence[0].excerpt


@pytest.mark.asyncio
async def test_pipeline_backfills_missing_evidence_url_from_research_provenance():
    mock_llm = MagicMock(spec=LLMClient)
    mock_search = MagicMock(spec=WebSearchClient)
    mock_db = MagicMock()

    analysis_obj = _make_legislation_response()
    analysis_obj.impacts[0].impact_description = (
        "The resolution has no direct impact on household cost of living."
    )
    analysis_obj.impacts[0].evidence[0].source_name = "Curated Evidence Excerpts"
    analysis_obj.impacts[0].evidence[0].url = ""
    analysis_obj.impacts[0].evidence[0].excerpt = (
        "Resolved by the Assembly of the State of California, the Senate thereof "
        "concurring, That the Legislature proclaims January 23, 2026, as Maternal "
        "Health Awareness Day."
    )
    review_obj = _make_review_response()
    refined_obj = _make_legislation_response()
    refined_obj.impacts[0].impact_description = analysis_obj.impacts[0].impact_description
    refined_obj.impacts[0].evidence[0].source_name = analysis_obj.impacts[0].evidence[0].source_name
    refined_obj.impacts[0].evidence[0].url = analysis_obj.impacts[0].evidence[0].url
    refined_obj.impacts[0].evidence[0].excerpt = analysis_obj.impacts[0].evidence[0].excerpt
    final_review_obj = _make_review_response()

    mock_llm.chat_completion = AsyncMock(
        side_effect=[
            MagicMock(content=analysis_obj.model_dump_json()),
            MagicMock(content=review_obj.model_dump_json()),
            MagicMock(content=refined_obj.model_dump_json()),
            MagicMock(content=final_review_obj.model_dump_json()),
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
    research_result.evidence_envelopes = [
        EvidenceEnvelope(
            id="env-acr117",
            source_tool="retriever",
            source_query="ACR 117",
            evidence=[
                Evidence(
                    id="rag-acr117",
                    kind="internal",
                    label="ACR 117 Bill Text",
                    url="https://leginfo.legislature.ca.gov/faces/billPdf.xhtml?bill_id=202520260ACR117",
                    content="",
                    excerpt=(
                        "Resolved by the Assembly of the State of California, the Senate "
                        "thereof concurring, That the Legislature proclaims January 23, "
                        "2026, as Maternal Health Awareness Day."
                    ),
                )
            ],
        )
    ]

    with patch.object(
        pipeline.research_service,
        "research",
        new_callable=AsyncMock,
        return_value=research_result,
    ):
        models = {"research": "m1", "generate": "m2", "review": "m3"}
        result = await pipeline.run("ACR 117", "The bill text...", "California", models)

    hydrated = result.impacts[0].evidence[0]
    assert hydrated.url == "https://leginfo.legislature.ca.gov/faces/billPdf.xhtml?bill_id=202520260ACR117"
    assert hydrated.source_name == "ACR 117 Bill Text"
    assert hydrated.persisted_evidence_id == "rag-acr117"


@pytest.mark.asyncio
async def test_pipeline_fail_closed_when_quantified_claim_lacks_numeric_support():
    mock_llm = MagicMock(spec=LLMClient)
    mock_search = MagicMock(spec=WebSearchClient)
    mock_db = MagicMock()

    analysis_obj = _make_legislation_response()
    analysis_obj.impacts[0].impact_description = (
        "The ordinance lowers household rent burdens by roughly $50 per month."
    )
    analysis_obj.impacts[0].evidence[0].source_name = "Committee Analysis"
    analysis_obj.impacts[0].evidence[0].excerpt = (
        "The ordinance limits annual rent increases and may reduce future rent growth "
        "for covered tenants through stronger caps on adjustments."
    )
    review_obj = _make_review_response()
    final_review_obj = _make_review_response()
    refined_obj = _make_legislation_response()
    refined_obj.impacts[0].relevant_clause = analysis_obj.impacts[0].relevant_clause
    refined_obj.impacts[0].legal_interpretation = analysis_obj.impacts[0].legal_interpretation
    refined_obj.impacts[0].impact_description = analysis_obj.impacts[0].impact_description
    refined_obj.impacts[0].chain_of_causality = analysis_obj.impacts[0].chain_of_causality
    refined_obj.impacts[0].evidence[0].source_name = analysis_obj.impacts[0].evidence[0].source_name
    refined_obj.impacts[0].evidence[0].excerpt = analysis_obj.impacts[0].evidence[0].excerpt

    mock_llm.chat_completion = AsyncMock(
        side_effect=[
            MagicMock(content=analysis_obj.model_dump_json()),
            MagicMock(content=review_obj.model_dump_json()),
            MagicMock(content=refined_obj.model_dump_json()),
            MagicMock(content=final_review_obj.model_dump_json()),
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
    research_result.web_sources = [
        {
            "title": "Committee Fiscal Analysis",
            "url": "https://lao.ca.gov/fiscal-note",
            "snippet": "Fiscal impact analysis for the ordinance.",
        }
    ]
    research_result.evidence_envelopes = [
        EvidenceEnvelope(
            id="env-q1",
            source_tool="web_search",
            source_query="AB-1234 fiscal impact",
            evidence=[
                Evidence(
                    id="web-q1",
                    kind="external",
                    label="Committee Fiscal Analysis",
                    url="https://lao.ca.gov/fiscal-note",
                    content="",
                    excerpt=(
                        "Fiscal impact analysis finds the ordinance caps annual rent "
                        "increases for covered tenants."
                    ),
                )
            ],
        )
    ]
    _seed_direct_fiscal_candidate(
        research_result,
        amount=50.0,
        source_url="https://lao.ca.gov/fiscal-note",
        source_excerpt=(
            "Official fiscal note estimates median tenant savings of $50 per month "
            "under the ordinance."
        ),
    )
    with patch.object(
        pipeline.research_service,
        "research",
        new_callable=AsyncMock,
        return_value=research_result,
    ):
        models = {"research": "m1", "generate": "m2", "review": "m3"}
        await pipeline.run("AB-1234", "The bill text...", "San Jose", models)

    persisted = mock_db.complete_pipeline_run.call_args.args[1]
    assert persisted["review"]["passed"] is False
    assert any(
        "numeric fiscal support" in err.lower()
        for err in persisted["review"]["factual_errors"]
    )


@pytest.mark.asyncio
async def test_pipeline_allows_quantified_claim_with_numeric_fiscal_support():
    mock_llm = MagicMock(spec=LLMClient)
    mock_search = MagicMock(spec=WebSearchClient)
    mock_db = MagicMock()

    analysis_obj = _make_legislation_response()
    analysis_obj.impacts[0].impact_description = (
        "The ordinance lowers household rent burdens by roughly $50 per month."
    )
    analysis_obj.impacts[0].evidence[0].source_name = "LAO Fiscal Note"
    analysis_obj.impacts[0].evidence[0].excerpt = (
        "The LAO fiscal note estimates median tenant savings of $50 per month "
        "under the rent cap, with annual household savings near $600."
    )
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
    research_result.web_sources = [
        {
            "title": "LAO Fiscal Note",
            "url": "https://lao.ca.gov/fiscal-note",
            "snippet": "Estimated $50 monthly tenant savings under the ordinance.",
        }
    ]
    research_result.evidence_envelopes = [
        EvidenceEnvelope(
            id="env-q2",
            source_tool="web_search",
            source_query="AB-1234 fiscal impact",
            evidence=[
                Evidence(
                    id="web-q2",
                    kind="external",
                    label="LAO Fiscal Note",
                    url="https://lao.ca.gov/fiscal-note",
                    content="",
                    excerpt=(
                        "The LAO fiscal note estimates median tenant savings of "
                        "$50 per month under the rent cap, with annual savings "
                        "near $600 per household."
                    ),
                )
            ],
        )
    ]
    _seed_direct_fiscal_candidate(
        research_result,
        amount=50.0,
        source_url="https://lao.ca.gov/fiscal-note",
        source_excerpt=(
            "The LAO fiscal note estimates median tenant savings of $50 per month "
            "under the rent cap, with annual savings near $600 per household."
        ),
    )
    with patch.object(
        pipeline.research_service,
        "research",
        new_callable=AsyncMock,
        return_value=research_result,
    ):
        models = {"research": "m1", "generate": "m2", "review": "m3"}
        result = await pipeline.run("AB-1234", "The bill text...", "San Jose", models)

    assert mock_llm.chat_completion.call_count == 2
    assert result.impacts[0].scenario_bounds.central == 50.0


@pytest.mark.asyncio
async def test_pipeline_fail_closed_when_claim_extends_to_resident_burden_without_support():
    pipeline = AnalysisPipeline(
        MagicMock(spec=LLMClient),
        MagicMock(spec=WebSearchClient),
        MagicMock(),
    )
    analysis_obj = _make_legislation_response()
    analysis_obj.impacts[0].relevant_clause = (
        "If the Commission on State Mandates determines that this act contains "
        "costs mandated by the state, reimbursement to local agencies and school "
        "districts for those costs shall be made."
    )
    analysis_obj.impacts[0].legal_interpretation = (
        "The bill creates a reimbursement mechanism for local agency compliance costs."
    )
    analysis_obj.impacts[0].impact_description = (
        "Potential indirect impact on the cost of living through state expenditures "
        "and possible taxpayer burdens."
    )
    analysis_obj.impacts[0].chain_of_causality = (
        "State reimbursement could draw on taxpayer funds and therefore affect the "
        "cost of living for residents."
    )
    analysis_obj.impacts[0].evidence[0].source_name = "Bill Text"
    analysis_obj.impacts[0].evidence[0].excerpt = (
        "If the Commission on State Mandates determines that this act contains "
        "costs mandated by the state, reimbursement to local agencies and school "
        "districts for those costs shall be made."
    )
    issues = pipeline._collect_claim_support_issues(analysis_obj)
    assert any(
        "cost-of-living burdens without supporting evidence" in err.lower()
        for err in issues
    )


@pytest.mark.asyncio
async def test_pipeline_allows_negative_zero_impact_resolution_claim():
    pipeline = AnalysisPipeline(
        MagicMock(spec=LLMClient),
        MagicMock(spec=WebSearchClient),
        MagicMock(),
    )
    analysis_obj = _make_legislation_response()
    analysis_obj.impacts[0].relevant_clause = (
        "Resolved by the Assembly of the State of California, the Senate thereof "
        "concurring, That the Legislature proclaims January 23, 2026, as "
        "Maternal Health Awareness Day."
    )
    analysis_obj.impacts[0].legal_interpretation = (
        "The resolution proclaims a symbolic observance day and creates no binding fiscal or regulatory duty."
    )
    analysis_obj.impacts[0].impact_description = (
        "The resolution proclaims a day of observance and has no direct "
        "cost-of-living impact."
    )
    analysis_obj.impacts[0].chain_of_causality = (
        "Because a symbolic observance day proclamation does not impose taxes, "
        "fees, appropriations, or mandates, it does not directly change "
        "household costs."
    )
    analysis_obj.impacts[0].evidence[0].source_name = "Bill Text"
    analysis_obj.impacts[0].evidence[0].excerpt = (
        "Resolved by the Assembly of the State of California, the Senate thereof "
        "concurring, That the Legislature proclaims January 23, 2026, as "
        "Maternal Health Awareness Day."
    )

    issues = pipeline._collect_claim_support_issues(analysis_obj)
    assert not any(
        "cost-of-living burdens without supporting evidence" in err.lower()
        for err in issues
    )


@pytest.mark.asyncio
async def test_pipeline_zero_impact_discovery_completes_without_generation():
    mock_llm = MagicMock(spec=LLMClient)
    mock_search = MagicMock(spec=WebSearchClient)
    mock_db = MagicMock()

    mock_db.get_latest_scrape_for_bill = AsyncMock(return_value=None)
    mock_db.create_pipeline_run = AsyncMock(return_value="run-1")
    mock_db.get_or_create_jurisdiction = AsyncMock(return_value=1)
    mock_db.store_legislation = AsyncMock(return_value=101)
    mock_db.store_impacts = AsyncMock()
    mock_db.complete_pipeline_run = AsyncMock()
    mock_db.fail_pipeline_run = AsyncMock()
    mock_db._execute = AsyncMock()

    pipeline = AnalysisPipeline(mock_llm, mock_search, mock_db)

    research_result = _make_research_result()
    research_result.rag_chunks = [
        MagicMock(
            content="Symbolic resolution text with no direct fiscal mandate.",
            score=0.88,
            metadata={"source_url": "https://leginfo.legislature.ca.gov/sb277"},
        )
    ]
    research_result.web_sources = [
        {
            "title": "SB 277 text",
            "url": "https://leginfo.legislature.ca.gov/sb277",
            "snippet": "Resolution language without direct fiscal mechanism.",
        }
    ]
    research_result.evidence_envelopes = [
        EvidenceEnvelope(
            id="env-no-impact",
            source_tool="retriever",
            source_query="SB 277",
            evidence=[
                Evidence(
                    id="rag-no-impact",
                    kind="internal",
                    label="SB 277 text",
                    url="https://leginfo.legislature.ca.gov/sb277",
                    content="",
                    excerpt="Symbolic resolution text with no direct fiscal mandate.",
                )
            ],
        )
    ]
    with patch.object(
        pipeline.research_service,
        "research",
        new_callable=AsyncMock,
        return_value=research_result,
    ), patch.object(
        pipeline,
        "_generate_step",
        new_callable=AsyncMock,
        side_effect=AssertionError("generate step should be skipped for zero impacts"),
    ), patch.object(
        pipeline,
        "_review_step",
        new_callable=AsyncMock,
        side_effect=AssertionError("review step should be skipped for zero impacts"),
    ):
        result = await pipeline.run(
            "SB-277",
            "Bill text with enough content to count as source text." * 8,
            "California",
            {"research": "m1", "generate": "m2", "review": "m3"},
        )

    assert result.bill_number == "SB-277"
    assert result.impacts == []
    assert result.quantification_eligible is False
    mock_db.complete_pipeline_run.assert_called_once()

    skipped_steps = {
        call.args[3]: call.args[4]
        for call in mock_db._execute.await_args_list
        if len(call.args) >= 5
    }
    assert skipped_steps.get("generate") == "skipped"
    assert skipped_steps.get("parameter_validation") == "skipped"
    assert skipped_steps.get("review") == "skipped"
    assert skipped_steps.get("refine") == "skipped"


@pytest.mark.asyncio
async def test_prefix_run_halts_with_prefix_halted_status():
    mock_llm = MagicMock(spec=LLMClient)
    mock_search = MagicMock(spec=WebSearchClient)
    mock_db = MagicMock()

    mock_db.get_latest_scrape_for_bill = AsyncMock(return_value=None)
    mock_db.get_vector_stats = AsyncMock(return_value={"chunk_count": 0})
    mock_db.create_pipeline_run = AsyncMock(return_value="run-1")
    mock_db.get_or_create_jurisdiction = AsyncMock(return_value=1)
    mock_db.store_legislation = AsyncMock(return_value=None)
    mock_db.store_impacts = AsyncMock()
    mock_db._execute = AsyncMock()
    mock_db.complete_pipeline_run = AsyncMock()
    mock_db.fail_pipeline_run = AsyncMock()

    pipeline = AnalysisPipeline(mock_llm, mock_search, mock_db)
    result = await pipeline.run(
        "AB-1234",
        "The bill text...",
        "San Jose",
        {"research": "m1", "generate": "m2", "review": "m3"},
        stop_after_step=STEP_INDEX["mode_selection"],
        run_label="ingestion-through-mode",
    )

    assert result.bill_number == "AB-1234"
    assert mock_db._execute.await_count >= 1
    last_update = mock_db._execute.await_args_list[-1]
    assert "UPDATE pipeline_runs" in last_update.args[0]
    assert last_update.args[1] == "prefix_halted"


@pytest.mark.asyncio
async def test_prefix_run_requires_seed_when_starting_after_step_one():
    mock_llm = MagicMock(spec=LLMClient)
    mock_search = MagicMock(spec=WebSearchClient)
    mock_db = MagicMock()

    mock_db.get_latest_scrape_for_bill = AsyncMock(return_value=None)
    mock_db.create_pipeline_run = AsyncMock(return_value="run-1")
    mock_db._execute = AsyncMock()
    mock_db.fail_pipeline_run = AsyncMock()

    pipeline = AnalysisPipeline(mock_llm, mock_search, mock_db)

    with pytest.raises(PrefixFixtureError):
        await pipeline.run(
            "AB-1234",
            "The bill text...",
            "San Jose",
            {"research": "m1", "generate": "m2", "review": "m3"},
            start_at_step=STEP_INDEX["parameter_resolution"],
        )
