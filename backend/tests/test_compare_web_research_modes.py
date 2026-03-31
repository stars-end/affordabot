from pathlib import Path

import pytest

from scripts.verification.compare_web_research_modes import (
    PIPELINE_RUNTIME_AVAILABLE,
    _coerce_fixture_rag_chunks,
    generate_comparison_report,
    overall_verdict_from_dimensions,
    verdict_from_final_conclusion,
    verdict_from_gate_behavior,
    verdict_from_parameter_resolution,
)


def test_final_conclusion_verdict_improves_when_quant_enabled() -> None:
    with_web = {
        "sufficiency_state": "quantified",
        "quantification_eligible": True,
        "insufficiency_reason": None,
    }
    without_web = {
        "sufficiency_state": "qualitative_only",
        "quantification_eligible": False,
        "insufficiency_reason": "insufficient_research_sources",
    }
    assert verdict_from_final_conclusion(with_web, without_web) == "improves"


def test_parameter_resolution_verdict_harms_when_missing_increases() -> None:
    with_web = {
        "impact_parameters": [
            {"resolved_parameters": {}, "missing_parameters": ["a", "b", "c"]}
        ]
    }
    without_web = {
        "impact_parameters": [
            {"resolved_parameters": {"a": {"value": 1}}, "missing_parameters": ["b"]}
        ]
    }
    assert verdict_from_parameter_resolution(with_web, without_web) == "harms"


def test_gate_behavior_verdict_no_effect_for_equal_payloads() -> None:
    payload = {
        "overall_quantification_eligible": False,
        "overall_sufficiency_state": "qualitative_only",
        "bill_level_failures": ["impact_discovery_failed"],
    }
    assert verdict_from_gate_behavior(payload, payload) == "no_effect"


def test_overall_verdict_prioritizes_harms() -> None:
    verdicts = {
        "final_conclusion": "no_effect",
        "parameter_resolution": "improves",
        "gate_behavior": "harms",
    }
    assert overall_verdict_from_dimensions(verdicts) == "harms"


def test_fixture_chunks_are_coerced_to_pipeline_shape() -> None:
    chunks = _coerce_fixture_rag_chunks(
        [
            {
                "chunk_id": "chunk-1",
                "content": "fixture content",
                "score": 0.7,
                "metadata": {"source_url": "https://example.test"},
            }
        ]
    )
    assert len(chunks) == 1
    chunk = chunks[0]
    assert hasattr(chunk, "metadata")
    assert isinstance(chunk.metadata, dict)
    assert chunk.metadata["source_url"] == "https://example.test"
    assert chunk.content == "fixture content"


@pytest.mark.asyncio
async def test_generate_comparison_report_smoke() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    report = await generate_comparison_report(
        repo_root=repo_root,
        bill_ids=["ca-acr-117-2024"],
    )

    assert report["schema_version"] == "1.0"
    assert report["feature_key"] == "bd-bkco.5"
    assert report["comparison_scope"]["bills_compared"] == ["ca-acr-117-2024"]
    assert len(report["comparisons"]) == 1
    comparison = report["comparisons"][0]
    assert set(comparison["variants"].keys()) == {"with_web", "without_web"}
    assert set(comparison["dimension_verdicts"].keys()) == {
        "final_conclusion",
        "parameter_resolution",
        "gate_behavior",
    }
    if PIPELINE_RUNTIME_AVAILABLE:
        assert report["runtime_engine"] == "analysis_pipeline"
        assert comparison["variants"]["with_web"]["run_id"].startswith(
            "fixture-only:"
        ) is False
    else:
        assert report["runtime_engine"] == "fixture_only_fallback"
