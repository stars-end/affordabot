import pytest

from services.discovery.round1_benchmark import (
    FixtureSearchProvider,
    classify_result,
    resolve_searxng_dependency,
    run_lane_benchmark,
    summarize_lane_metrics,
)


def test_classify_result_respects_official_domain_hints_for_non_gov_domains() -> None:
    classified = classify_result(
        {
            "url": "https://sccgov.org/sites/bos/Documents/agenda.pdf",
            "title": "Board Agenda",
            "snippet": "Agenda packet for board meeting",
        },
        intent="agenda",
        official_domain_hints=["sccgov.org"],
    )

    assert classified["is_official"] is True
    assert classified["is_useful"] is True
    assert classified["is_artifact_candidate"] is True


def test_resolve_searxng_dependency_fail_closed() -> None:
    assert resolve_searxng_dependency("") == "SEARXNG_BASE_URL"
    assert resolve_searxng_dependency(None) == "SEARXNG_BASE_URL"
    assert resolve_searxng_dependency("http://localhost:8080") is None


def test_summarize_lane_metrics_includes_required_rates() -> None:
    query_results = [
        {
            "query_id": "q1",
            "query": "query one",
            "result_count": 2,
            "non_empty": True,
            "official_source_top5": True,
            "useful_url_count": 1,
            "useful_urls": ["https://example.gov/a.pdf"],
            "artifact_useful_count": 1,
            "portal_useful_count": 0,
            "duplicate_url_count": 0,
            "latency_ms": 120,
            "hard_failure": False,
            "failure_mode": None,
            "top_results": [],
        },
        {
            "query_id": "q2",
            "query": "query two",
            "result_count": 0,
            "non_empty": False,
            "official_source_top5": False,
            "useful_url_count": 0,
            "useful_urls": [],
            "artifact_useful_count": 0,
            "portal_useful_count": 0,
            "duplicate_url_count": 0,
            "latency_ms": 240,
            "hard_failure": True,
            "failure_mode": "timeout",
            "top_results": [],
        },
    ]

    metrics = summarize_lane_metrics("baseline", query_results)

    assert metrics["empty_result_rate"] == pytest.approx(0.5)
    assert metrics["non_empty_result_rate"] == pytest.approx(0.5)
    assert metrics["official_source_top5_rate"] == pytest.approx(0.5)
    assert metrics["useful_url_yield"] == pytest.approx(0.5)
    assert metrics["unique_useful_url_yield"] == pytest.approx(0.5)
    assert metrics["artifact_vs_portal_rate"] == pytest.approx(1.0)
    assert metrics["duplicate_url_rate"] == pytest.approx(0.0)
    assert metrics["median_latency_ms"] == 180
    assert metrics["hard_failure_rate"] == pytest.approx(0.5)
    assert metrics["failure_modes"] == {"timeout": 1}


@pytest.mark.asyncio
async def test_run_lane_benchmark_with_fixture_provider() -> None:
    matrix = [
        {
            "id": "san-jose-agenda",
            "jurisdiction": "San Jose, CA",
            "intent": "agenda",
            "query": "San Jose city council agenda",
            "official_domain_hints": ["sanjoseca.gov"],
        }
    ]
    provider = FixtureSearchProvider(
        {
            "san-jose-agenda": [
                {
                    "url": "https://sanjoseca.gov/agendas/city-council-agenda.pdf",
                    "title": "Agenda packet",
                    "snippet": "Official agenda",
                }
            ]
        }
    )

    lane_result = await run_lane_benchmark(
        lane="baseline",
        matrix=matrix,
        provider=provider,
        result_count=5,
    )

    assert lane_result.metrics["query_count"] == 1
    assert lane_result.metrics["non_empty_result_rate"] == pytest.approx(1.0)
    assert lane_result.metrics["official_source_top5_rate"] == pytest.approx(1.0)
