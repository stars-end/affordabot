from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = ROOT / "backend" / "scripts" / "verification" / "verify_search_source_quality_bakeoff.py"
spec = spec_from_file_location("verify_search_source_quality_bakeoff", SCRIPT_PATH)
module = module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def test_normalize_scores_official_meeting_and_negative_nav_terms():
    records = module._normalize_records(
        provider="searxng",
        query="San Jose CA city council meeting minutes housing",
        raw_results=[
            {
                "url": "https://www.sanjoseca.gov/your-government/city-council/agenda.pdf",
                "title": "City Council Agenda",
                "snippet": "Housing ordinance discussion and planning item",
            },
            {
                "url": "https://www.sanjoseca.gov/residents/jobs",
                "title": "Residents and Jobs",
                "snippet": "Home menu and site map",
            },
        ],
        top_k=5,
        source_label="searxng",
    )

    assert len(records) == 2
    assert records[0]["score"] > records[1]["score"]
    assert "official_domain" in records[0]["signals"]
    assert "meeting_source_terms" in records[0]["signals"]
    assert "nav_only_negative" in records[1]["signals"]


def test_duplicate_handling_marks_second_url_duplicate():
    records = module._normalize_records(
        provider="tavily",
        query="housing",
        raw_results=[
            {"url": "https://example.com/path?utm_source=a", "title": "a", "snippet": "agenda"},
            {"url": "https://example.com/path?utm_source=b", "title": "b", "snippet": "agenda"},
        ],
        top_k=5,
        source_label="tavily",
    )
    assert len(records) == 2
    assert records[0]["duplicate"] is False
    assert records[1]["duplicate"] is True
    assert "duplicate" in records[1]["signals"]


def test_non_primary_domains_are_disqualified_for_governance_queries():
    score, signals = module._score_result(
        query=module.QuerySpec(
            query="Santa Clara County planning commission agenda housing development",
            jurisdiction="Santa Clara County CA",
            expected_signal_terms=("planning", "agenda", "housing development"),
            preferred_domains=("sccgov.org",),
            preferred_url_patterns=("/planning", "/agenda", ".pdf"),
        ),
        url="https://www.facebook.com/CityofSantaClara/videos/planning-commission-meeting-april-8-2026/961769026716717/",
        title="Planning Commission Meeting April 8, 2026",
        snippet="Planning commission meeting about housing development",
        duplicate=False,
    )

    assert score == 0.0
    assert signals == ["non_primary_source_domain"]


def test_non_preferred_records_platform_is_disqualified_on_jurisdiction_mismatch():
    score, signals = module._score_result(
        query=module.QuerySpec(
            query="Santa Clara County affordable housing committee minutes",
            jurisdiction="Santa Clara County CA",
            expected_signal_terms=("committee", "minutes", "affordable housing"),
            preferred_domains=("sccgov.org",),
            preferred_url_patterns=("/housing", "/minutes", ".pdf"),
        ),
        url="https://sanjose.legistar.com/View.ashx?M=AADA&ID=1345653",
        title="San Jose City Council agenda",
        snippet="Affordable housing committee minutes",
        duplicate=False,
    )

    assert score == 0.0
    assert signals == ["jurisdiction_mismatch"]


def test_city_domain_does_not_match_county_jurisdiction():
    score, signals = module._score_result(
        query=module.QuerySpec(
            query="Santa Clara County affordable housing committee minutes",
            jurisdiction="Santa Clara County CA",
            expected_signal_terms=("committee", "minutes", "affordable housing"),
            preferred_domains=("sccgov.org",),
            preferred_url_patterns=("/housing", "/minutes", ".pdf"),
        ),
        url="https://www.santaclaraca.gov/housing/affordable-housing-ordinance",
        title="Affordable Housing Ordinance",
        snippet="Housing committee minutes",
        duplicate=False,
    )

    assert score == 0.0
    assert signals == ["jurisdiction_mismatch"]


def test_negative_control_scores_are_capped():
    score, signals = module._score_result(
        query=module.QuerySpec(
            query="San Jose city jobs police permits parks events",
            jurisdiction="San Jose CA",
            source_family="negative_control_noise",
            expected_signal_terms=("jobs", "permits", "parks", "events"),
            preferred_domains=("sanjoseca.gov",),
            preferred_url_patterns=("/home", "/departments", "/jobs"),
        ),
        url="https://www.sanjoseca.gov/your-government/departments-offices/special-events",
        title="Special Events",
        snippet="Jobs, permits, parks, and city events",
        duplicate=False,
    )

    assert score <= 40.0
    assert "negative_control_cap" in signals


def test_probe_exa_sends_user_agent_and_expected_payload(monkeypatch):
    captured = {}

    def _fake_request_json(*, method, url, headers, payload, timeout_seconds):
        captured["method"] = method
        captured["url"] = url
        captured["headers"] = headers
        captured["payload"] = payload
        captured["timeout_seconds"] = timeout_seconds
        return {
            "results": [
                {
                    "url": "https://sanjose.legistar.com/MeetingDetail.aspx",
                    "title": "Meeting Detail",
                    "highlights": ["Housing memo and zoning discussion"],
                }
            ]
        }

    monkeypatch.setattr(module, "_request_json", _fake_request_json)
    probe = module._probe_exa(
        query="San Jose city council housing",
        api_key="exa-key",
        top_k=3,
        timeout_seconds=11,
    )

    assert probe["status"] == "succeeded"
    assert captured["method"] == "POST"
    assert captured["url"] == module.EXA_SEARCH_URL
    assert captured["headers"]["User-Agent"] == module.DEFAULT_USER_AGENT
    assert captured["headers"]["x-api-key"] == "exa-key"
    assert captured["payload"]["numResults"] == 3
    assert captured["payload"]["type"] == "auto"
    assert captured["payload"]["contents"]["highlights"]["maxCharacters"] == 400


def test_run_bakeoff_marks_missing_env_providers_not_configured(monkeypatch):
    monkeypatch.setattr(module, "_env", lambda _name: None)
    monkeypatch.setattr(
        module,
        "_probe_searxng",
        lambda **_kwargs: {
            "provider": "searxng",
            "query": "q1",
            "status": "succeeded",
            "latency_ms": 7,
            "result_count": 1,
            "top_results": [
                {
                    "url": "https://www.sanjoseca.gov/agenda.pdf",
                    "canonical_url": "https://www.sanjoseca.gov/agenda.pdf",
                    "title": "Agenda",
                    "snippet": "Housing",
                    "source": "searxng",
                    "score": 6.0,
                    "signals": ["official_domain"],
                    "duplicate": False,
                }
            ],
            "top_score": 6.0,
            "average_score": 6.0,
            "failure_classification": None,
            "error": None,
        },
    )
    config = module.BakeoffConfig(
        providers=("searxng", "tavily", "exa"),
        queries=("q1",),
        top_k=3,
        timeout_seconds=10,
        searx_endpoint="https://searx.example/search",
        out_json=Path("/tmp/x.json"),
        out_md=Path("/tmp/x.md"),
    )

    report = module._run_bakeoff(config)
    by_provider = {item["provider"]: item for item in report["probes"]}
    assert by_provider["searxng"]["status"] == "succeeded"
    assert by_provider["tavily"]["status"] == "not_configured"
    assert by_provider["exa"]["status"] == "not_configured"
    assert report["recommendation"]["provider"] == "searxng"


def test_render_markdown_contains_summary_and_recommendation():
    report = {
        "generated_at": "2026-04-13T00:00:00Z",
        "feature_key": "bd-9qjof.8",
        "providers": ["searxng", "exa"],
        "top_k": 5,
        "timeout_seconds": 20,
        "provider_summary": [
            {
                "provider": "searxng",
                "success_rate_percent": 100.0,
                "query_success_rate_percent": 100.0,
                "mean_top_score": 5.2,
                "mean_average_score": 4.0,
                "median_query_score": 5.2,
                "median_latency_ms": 60,
                "p90_latency_ms": 60,
                "reader_ready_rate_percent": 100.0,
                "official_domain_hit_rate_percent": 100.0,
                "error_rate": 0.0,
                "rate_limit_rate": 0.0,
                "reliability_score": 100.0,
                "provider_score": 72.86,
                "eligible_for_mvp": False,
                "failures": [],
            }
        ],
        "recommendation": {
            "provider": "searxng",
            "reason": "no_provider_meets_mvp_threshold_best_candidate_only",
            "mvp_ready": False,
            "action": "do_not_lock_provider_run_full_reader_gate_or_tune_corpus",
        },
        "query_summary": [
            {
                "query": "San Jose minutes",
                "winner_provider": "searxng",
                "winner_top_score": 5.2,
                "winner_url": "https://example.com/minutes.pdf",
            }
        ],
    }
    markdown = module._render_markdown(report)
    assert "Provider Summary" in markdown
    assert "Best candidate: `searxng`" in markdown
    assert "https://example.com/minutes.pdf" in markdown


def test_candidate_classification_rules_for_san_jose_sources():
    assert (
        module._candidate_class("https://sanjose.legistar.com/MeetingDetail.aspx?ID=1234", "", "")
        == "final_artifact"
    )
    assert module._candidate_class("https://sanjose.legistar.com/View.ashx?M=F&ID=1234", "", "") == "final_artifact"
    assert (
        module._candidate_class("https://www.sanjoseca.gov/your-government/agendas-minutes", "", "") == "portal_seed"
    )
    assert (
        module._candidate_class("https://www.sanjoseca.gov/your-government/departments-offices/housing", "", "")
        == "likely_navigation"
    )
    assert module._candidate_class("https://www.reddit.com/r/SanJose/comments/abc", "", "") == "third_party_or_junk"


def test_candidate_classification_handles_query_param_order_and_agenda_center_files():
    assert (
        module._candidate_class(
            "https://sanjose.legistar.com/View.ashx?GUID=59FCFBBE-ACEB-4329-9C02-9548AFD46D2D&ID=1328259&M=M",
            "",
            "",
        )
        == "final_artifact"
    )
    assert (
        module._candidate_class(
            "https://sanjose.legistar.com/gateway.aspx?M=F&ID=30dfe51f-d23d-4480-a407-44e17ef4c0c3.pdf",
            "",
            "",
        )
        == "final_artifact"
    )
    assert (
        module._candidate_class(
            "https://www.saratoga.ca.us/AgendaCenter/ViewFile/Minutes/_03182026-1422",
            "",
            "",
        )
        == "final_artifact"
    )
    assert (
        module._candidate_class(
            "https://dig.abclocal.go.com/kgo/PDF/sjmemorandum.pdf",
            "sjmemorandum",
            "media mirror",
        )
        == "third_party_or_junk"
    )


def test_parse_unresponsive_engines_supports_dict_and_list_shapes():
    from_dict = module._parse_unresponsive_engines(
        {"unresponsive_engines": {"brave": "Suspended (too many requests)", "ddg": "access denied"}}
    )
    assert from_dict == [
        {"engine": "brave", "reason": "Suspended (too many requests)"},
        {"engine": "ddg", "reason": "access denied"},
    ]

    from_list = module._parse_unresponsive_engines({"unresponsive_engines": ["startpage", "karmasearch"]})
    assert from_list == [
        {"engine": "startpage", "reason": "unresponsive"},
        {"engine": "karmasearch", "reason": "unresponsive"},
    ]


def test_probe_searxng_emits_raw_candidates_and_unresponsive_metadata(monkeypatch):
    def _fake_request_json(*, method, url, headers, payload, timeout_seconds):
        assert method == "GET"
        assert "format=json" in url
        assert headers["User-Agent"] == module.DEFAULT_USER_AGENT
        assert payload is None
        assert timeout_seconds == 9
        return {
            "results": [
                {
                    "url": "https://sanjose.legistar.com/MeetingDetail.aspx?ID=1234",
                    "title": "Meeting Detail",
                    "content": "Affordable housing ordinance agenda item",
                },
                {
                    "url": "https://www.sanjoseca.gov/your-government/agendas-minutes",
                    "title": "Agendas and Minutes",
                    "content": "Menu and navigation",
                },
            ],
            "unresponsive_engines": {"brave": "Suspended (too many requests)"},
        }

    monkeypatch.setattr(module, "_request_json", _fake_request_json)
    probe = module._probe_searxng(
        query="San Jose city council housing",
        endpoint="https://example.test/search",
        top_k=1,
        timeout_seconds=9,
    )

    assert probe["status"] == "succeeded"
    assert probe["result_count"] == 2
    assert len(probe["top_results"]) == 1
    assert len(probe["raw_candidates"]) == 2
    assert probe["unresponsive_engines"] == [{"engine": "brave", "reason": "Suspended (too many requests)"}]


def test_build_searxng_fanout_health_summary_reports_class_counts_and_verdict():
    probes = [
        {
            "provider": "searxng",
            "query": "q1",
            "status": "succeeded",
            "result_count": 2,
            "top_results": [
                {"url": "https://sanjose.legistar.com/MeetingDetail.aspx?ID=99", "title": "Meeting", "score": 70.0}
            ],
            "raw_candidates": [
                {
                    "url": "https://sanjose.legistar.com/MeetingDetail.aspx?ID=99",
                    "title": "Meeting",
                    "snippet": "agenda item",
                    "score": 70.0,
                },
                {
                    "url": "https://www.sanjoseca.gov/your-government/agendas-minutes",
                    "title": "Agendas and Minutes",
                    "snippet": "menu",
                    "score": 10.0,
                },
            ],
            "unresponsive_engines": [],
        },
        {
            "provider": "searxng",
            "query": "q2",
            "status": "succeeded",
            "result_count": 0,
            "top_results": [],
            "raw_candidates": [],
            "unresponsive_engines": [{"engine": "duckduckgo", "reason": "Suspended (access denied)"}],
        },
    ]

    summary = module._build_searxng_fanout_health_summary(probes=probes)
    assert summary["provider"] == "searxng"
    assert summary["query_count"] == 2
    assert summary["raw_candidate_count"] == 2
    assert summary["deduped_candidate_count"] == 2
    assert summary["candidate_class_counts"]["final_artifact"] == 1
    assert summary["candidate_class_counts"]["portal_seed"] == 1
    assert summary["health_verdict"] == "degraded"
    assert summary["critical_unresponsive_engine_count"] == 1
    assert len(summary["selected_shortlist"]) >= 1


def test_build_searxng_fanout_health_summary_shortlist_sorts_by_class_priority_then_score():
    probes = [
        {
            "provider": "searxng",
            "query": "q1",
            "status": "succeeded",
            "result_count": 4,
            "top_results": [],
            "raw_candidates": [
                {
                    "url": "https://www.sanjoseca.gov/your-government/agendas-minutes",
                    "title": "Agendas and Minutes",
                    "snippet": "portal",
                    "score": 91.0,
                },
                {
                    "url": "https://www.saratoga.ca.us/AgendaCenter/ViewFile/Minutes/_03182026-1422",
                    "title": "Minutes File",
                    "snippet": "minutes",
                    "score": 60.0,
                },
                {
                    "url": "https://www.sanjoseca.gov/your-government/departments-offices/housing",
                    "title": "Housing Department",
                    "snippet": "navigation",
                    "score": 95.0,
                },
                {
                    "url": "https://www.reddit.com/r/SanJose/comments/abc",
                    "title": "Thread",
                    "snippet": "discussion",
                    "score": 99.0,
                },
                {
                    "url": "https://dig.abclocal.go.com/kgo/PDF/sjmemorandum.pdf",
                    "title": "sjmemorandum",
                    "snippet": "media mirror",
                    "score": 98.0,
                },
            ],
            "unresponsive_engines": [],
        }
    ]

    summary = module._build_searxng_fanout_health_summary(probes=probes, shortlist_size=3)
    shortlist = summary["selected_shortlist"]
    assert [item["class"] for item in shortlist] == ["final_artifact", "portal_seed", "likely_navigation"]
    assert shortlist[0]["url"] == "https://www.saratoga.ca.us/AgendaCenter/ViewFile/Minutes/_03182026-1422"
    assert all(item["url"] != "https://dig.abclocal.go.com/kgo/PDF/sjmemorandum.pdf" for item in shortlist)
