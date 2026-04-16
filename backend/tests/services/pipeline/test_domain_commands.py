from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from services.pipeline.domain.commands import (
    assess_reader_substance,
    rank_reader_candidates,
)
from services.pipeline.domain import (
    CommandEnvelope,
    FreshnessPolicy,
    InMemoryAnalyzer,
    InMemoryArtifactStore,
    InMemoryDomainState,
    InMemoryReaderProvider,
    InMemorySearchProvider,
    InMemoryVectorStore,
    PipelineDomainCommands,
    SearchResultItem,
    WindmillMetadata,
    build_v2_canonical_document_key,
)
from services.pipeline.domain.ports import ReaderDocument


class _StaticReaderProvider:
    def __init__(self, text: str) -> None:
        self.text = text

    def fetch(self, *, url: str) -> ReaderDocument:
        return ReaderDocument(
            url=url,
            title="San Jose City Council",
            text=self.text,
            fetched_at=datetime.now(timezone.utc),
            document_type="meeting_minutes",
            published_date="2026-04-13",
        )


class _RoutingReaderProvider:
    def __init__(
        self,
        *,
        by_url: dict[str, str],
        fail_urls: set[str] | None = None,
    ) -> None:
        self.by_url = by_url
        self.fail_urls = fail_urls or set()

    def fetch(self, *, url: str) -> ReaderDocument:
        if url in self.fail_urls:
            raise RuntimeError(f"reader_unavailable_for:{url}")
        return ReaderDocument(
            url=url,
            title="San Jose City Council",
            text=self.by_url.get(
                url,
                (
                    "San Jose City Council meeting minutes include agenda item 4.2 "
                    "where housing policy recommendations were adopted by vote."
                ),
            ),
            fetched_at=datetime.now(timezone.utc),
            document_type="meeting_minutes",
            published_date="2026-04-13",
        )


class _TrackingReaderProvider:
    def __init__(
        self,
        *,
        by_url: dict[str, str],
        forbidden_urls: set[str] | None = None,
    ) -> None:
        self.by_url = by_url
        self.forbidden_urls = forbidden_urls or set()
        self.fetch_calls: list[str] = []

    def fetch(self, *, url: str) -> ReaderDocument:
        self.fetch_calls.append(url)
        if url in self.forbidden_urls:
            raise AssertionError(f"forbidden_fetch:{url}")
        return ReaderDocument(
            url=url,
            title="San Jose City Council",
            text=self.by_url[url],
            fetched_at=datetime.now(timezone.utc),
            document_type="meeting_minutes",
            published_date="2026-04-13",
        )


class _RecordingAnalyzer:
    def __init__(self) -> None:
        self.last_question = ""
        self.last_evidence_chunks: list[dict[str, Any]] = []

    def analyze(
        self, *, question: str, evidence_chunks: list[dict[str, Any]]
    ) -> dict[str, Any]:
        self.last_question = question
        self.last_evidence_chunks = [dict(chunk) for chunk in evidence_chunks]
        return {
            "summary": "ok",
            "key_points": ["ok"],
            "sufficiency_state": "sufficient",
        }


def _envelope(command: str, key: str) -> CommandEnvelope:
    return CommandEnvelope(
        command=command,  # type: ignore[arg-type]
        jurisdiction_id="san-jose-ca",
        source_family="meeting_minutes",
        idempotency_key=key,
        windmill=WindmillMetadata(run_id="wm-run-1", job_id="wm-job-1"),
    )


def _service(
    *,
    state: InMemoryDomainState | None = None,
    search_results: list[SearchResultItem] | None = None,
    search_fail: str | None = None,
    reader_fail: str | None = None,
    artifact_fail: str | None = None,
    vector_fail: str | None = None,
) -> tuple[InMemoryDomainState, PipelineDomainCommands]:
    local_state = state or InMemoryDomainState()
    service = PipelineDomainCommands(
        state=local_state,
        search_provider=InMemorySearchProvider(results=search_results, fail_mode=search_fail),
        reader_provider=InMemoryReaderProvider(fail_mode=reader_fail),
        artifact_store=InMemoryArtifactStore(local_state, fail_mode=artifact_fail),
        vector_store=InMemoryVectorStore(local_state, fail_mode=vector_fail),
        analyzer=InMemoryAnalyzer(),
    )
    return local_state, service


def _default_policy() -> FreshnessPolicy:
    return FreshnessPolicy(
        fresh_hours=24,
        stale_usable_ceiling_hours=72,
        fail_closed_ceiling_hours=168,
    )


def test_v2_canonical_key_uses_jurisdiction_family_and_normalized_url() -> None:
    key = build_v2_canonical_document_key(
        jurisdiction_id="San Jose CA",
        source_family="Meeting Minutes",
        url="https://City.gov/Meetings/Agenda/?utm_source=email&b=2&a=1#download",
        metadata={"document_type": "Agenda"},
        data={},
    )
    assert key.startswith("v2|jurisdiction=san-jose-ca|family=meeting_minutes|doctype=agenda|url=")
    assert "utm_source" not in key
    assert "a=1&b=2" in key


def test_v2_canonical_key_fallback_title_and_date() -> None:
    key = build_v2_canonical_document_key(
        jurisdiction_id="San Jose CA",
        source_family="meeting_minutes",
        url="unknown://jurisdiction/meetings/source-name",
        metadata={"document_type": "minutes", "title": "City Council Minutes"},
        data={"published_date": "2026-03-31T19:00:00Z"},
    )
    assert (
        key
        == "v2|jurisdiction=san-jose-ca|family=meeting_minutes|doctype=minutes|title=city council minutes|date=2026-03-31"
    )


def test_happy_path_full_refresh_and_summary() -> None:
    state, service = _service(
        search_results=[
            SearchResultItem(
                url="https://www.sanjoseca.gov/meeting-minutes/2026-04-10",
                title="Meeting Minutes",
                snippet="housing updates",
            )
        ]
    )
    responses = service.full_refresh(
        query="san jose minutes housing",
        question="What are the housing updates?",
        search_envelope=_envelope("search_materialize", "k1"),
        freshness_envelope=_envelope("freshness_gate", "k2"),
        read_envelope=_envelope("read_fetch", "k3"),
        index_envelope=_envelope("index", "k4"),
        analyze_envelope=_envelope("analyze", "k5"),
        summarize_envelope=_envelope("summarize_run", "k6"),
        policy=_default_policy(),
    )
    by_command = {item.command: item for item in responses}
    assert by_command["search_materialize"].status == "succeeded"
    assert by_command["freshness_gate"].decision_reason == "fresh"
    assert by_command["read_fetch"].status == "succeeded"
    assert by_command["index"].counts["chunks"] > 0
    assert by_command["analyze"].status == "succeeded"
    assert by_command["summarize_run"].status == "succeeded"
    assert len(state.chunks) == by_command["index"].counts["chunks"]


def test_rerun_idempotency_keeps_counts_stable() -> None:
    state, service = _service(
        search_results=[
            SearchResultItem(
                url="https://www.sanjoseca.gov/meeting-minutes/2026-04-10",
                title="Meeting Minutes",
                snippet="housing updates",
            )
        ]
    )
    first = service.full_refresh(
        query="san jose minutes housing",
        question="What are the housing updates?",
        search_envelope=_envelope("search_materialize", "r1"),
        freshness_envelope=_envelope("freshness_gate", "r2"),
        read_envelope=_envelope("read_fetch", "r3"),
        index_envelope=_envelope("index", "r4"),
        analyze_envelope=_envelope("analyze", "r5"),
        summarize_envelope=_envelope("summarize_run", "r6"),
        policy=_default_policy(),
    )
    chunk_count = len(state.chunks)
    second = service.full_refresh(
        query="san jose minutes housing",
        question="What are the housing updates?",
        search_envelope=_envelope("search_materialize", "r1"),
        freshness_envelope=_envelope("freshness_gate", "r2"),
        read_envelope=_envelope("read_fetch", "r3"),
        index_envelope=_envelope("index", "r4"),
        analyze_envelope=_envelope("analyze", "r5"),
        summarize_envelope=_envelope("summarize_run", "r6"),
        policy=_default_policy(),
    )
    by_command = {item.command: item for item in second}
    assert by_command["search_materialize"].status == "succeeded"
    assert by_command["search_materialize"].details["idempotent_reuse"] is True
    assert by_command["index"].status == "succeeded"
    assert by_command["index"].details["idempotent_reuse"] is True
    assert len(state.chunks) == chunk_count
    assert first[-1].refs["run_id"] == second[-1].refs["run_id"]


def test_freshness_gate_stale_but_usable_alerts() -> None:
    state, service = _service(
        search_results=[
            SearchResultItem(
                url="https://www.sanjoseca.gov/minutes/stale",
                title="Older Minutes",
                snippet="older",
            )
        ]
    )
    search = service.search_materialize(envelope=_envelope("search_materialize", "s1"), query="q")
    snapshot_id = str(search.refs["search_snapshot_id"])
    # make snapshot stale but still under usable ceiling
    stale_time = state.now - timedelta(hours=30)
    state.search_snapshots[snapshot_id]["captured_at"] = stale_time.isoformat()
    result = service.freshness_gate(
        envelope=_envelope("freshness_gate", "s2"),
        snapshot_id=snapshot_id,
        policy=_default_policy(),
        latest_success_at=state.now - timedelta(hours=10),
    )
    assert result.status == "succeeded_with_alerts"
    assert result.decision_reason == "stale_but_usable"
    assert "source_search_failed_using_last_success" in result.alerts


def test_freshness_gate_stale_blocked() -> None:
    state, service = _service(
        search_results=[
            SearchResultItem(
                url="https://www.sanjoseca.gov/minutes/very-old",
                title="Very Old Minutes",
                snippet="older",
            )
        ]
    )
    search = service.search_materialize(envelope=_envelope("search_materialize", "sb1"), query="q")
    snapshot_id = str(search.refs["search_snapshot_id"])
    state.search_snapshots[snapshot_id]["captured_at"] = (
        state.now - timedelta(hours=90)
    ).isoformat()
    result = service.freshness_gate(
        envelope=_envelope("freshness_gate", "sb2"),
        snapshot_id=snapshot_id,
        policy=_default_policy(),
        latest_success_at=state.now - timedelta(hours=10),
    )
    assert result.status == "blocked"
    assert result.decision_reason == "stale_blocked"
    assert result.retry_class == "operator_required"


def test_empty_results_uses_empty_but_usable_with_recent_success() -> None:
    state, service = _service(search_results=[])
    search = service.search_materialize(envelope=_envelope("search_materialize", "e1"), query="q")
    snapshot_id = str(search.refs["search_snapshot_id"])
    result = service.freshness_gate(
        envelope=_envelope("freshness_gate", "e2"),
        snapshot_id=snapshot_id,
        policy=_default_policy(),
        latest_success_at=state.now - timedelta(hours=6),
    )
    assert search.status == "succeeded_with_alerts"
    assert result.status == "succeeded_with_alerts"
    assert result.decision_reason == "empty_but_usable"


def test_source_failure_returns_retryable_transport() -> None:
    _, service = _service(search_fail="simulated_transport_error")
    result = service.search_materialize(
        envelope=_envelope("search_materialize", "f1"),
        query="q",
    )
    assert result.status == "failed_retryable"
    assert result.retry_class == "transport"


def test_rank_reader_candidates_prefers_legistar_gateway_pdf_with_action_snippet() -> None:
    ranked = rank_reader_candidates(
        [
            SearchResultItem(
                url="https://sanjose.granicus.com/AgendaViewer.php?clip_id=14442&view_id=60",
                title="City Council Meeting Amended Agenda",
                snippet="location council chambers interpretation is available",
            ),
            SearchResultItem(
                url="https://sanjose.legistar.com/gateway.aspx?ID=30dfe51f-d23d-4480-a407-44e17ef4c0c3.pdf&M=F",
                title="Ordinance No. 31303 Affordability Compliance",
                snippet="approved ordinance no. 31303 housing compliance options",
            ),
        ]
    )
    assert ranked[0]["url"].startswith("https://sanjose.legistar.com/gateway.aspx")


def test_rank_reader_candidates_penalizes_portal_urls_below_artifact_urls() -> None:
    ranked = rank_reader_candidates(
        [
            SearchResultItem(
                url="https://www.sanjoseca.gov/your-government/agendas-minutes",
                title="Agendas & Minutes | City of San Jose",
                snippet="City council agendas and minutes",
            ),
            SearchResultItem(
                url="https://sanjose.legistar.com/MeetingDetail.aspx?ID=12345&GUID=abc",
                title="Meeting Detail",
                snippet="Agenda item 4.2 housing ordinance",
            ),
            SearchResultItem(
                url="https://www.sanjoseca.gov/Calendar.aspx?CID=114",
                title="City Calendar",
                snippet="meeting calendar",
            ),
            SearchResultItem(
                url="https://sanjose.legistar.com/View.ashx?M=F&ID=12345&GUID=abc",
                title="Final Agenda Packet",
                snippet="ordinance no. 31303 approved",
            ),
        ]
    )
    ranked_urls = [item["url"] for item in ranked]
    ranked_by_url = {item["url"]: item for item in ranked}
    assert ranked_urls[0].startswith("https://sanjose.legistar.com/")
    assert ranked_urls[1].startswith("https://sanjose.legistar.com/")
    assert ranked_urls[-1].startswith("https://www.sanjoseca.gov/")
    assert "/agendas-minutes" in ranked_urls[-1] or "calendar.aspx" in ranked_urls[-1].lower()
    assert (
        ranked_by_url["https://sanjose.legistar.com/View.ashx?M=F&ID=12345&GUID=abc"]["score"]
        - ranked_by_url["https://www.sanjoseca.gov/your-government/agendas-minutes"]["score"]
    ) >= 10


def test_rank_reader_candidates_detects_concrete_artifacts_with_unordered_query_params() -> None:
    ranked = rank_reader_candidates(
        [
            SearchResultItem(
                url="https://www.sanjoseca.gov/your-government/agendas-minutes",
                title="Agendas & Minutes | City of San Jose",
                snippet="city council agendas and minutes",
            ),
            SearchResultItem(
                url="https://sanjose.legistar.com/View.ashx?GUID=59FCFBBE-ACEB-4329-9C02-9548AFD46D2D&ID=1328259&M=M",
                title="Minutes Packet",
                snippet="city council minutes and housing item",
            ),
            SearchResultItem(
                url="https://www.saratoga.ca.us/AgendaCenter/ViewFile/Minutes/_03182026-1422",
                title="City Council Minutes",
                snippet="minutes archive",
            ),
        ]
    )
    ranked_by_url = {item["url"]: item for item in ranked}
    assert ranked[0]["url"] == "https://sanjose.legistar.com/View.ashx?GUID=59FCFBBE-ACEB-4329-9C02-9548AFD46D2D&ID=1328259&M=M"
    assert (
        ranked_by_url["https://www.saratoga.ca.us/AgendaCenter/ViewFile/Minutes/_03182026-1422"]["score"]
        > ranked_by_url["https://www.sanjoseca.gov/your-government/agendas-minutes"]["score"]
    )


def test_rank_reader_candidates_does_not_apply_concrete_boost_to_third_party_pdf() -> None:
    ranked = rank_reader_candidates(
        [
            SearchResultItem(
                url="https://dig.abclocal.go.com/kgo/PDF/sjmemorandum.pdf",
                title="sjmemorandum",
                snippet="media mirror pdf",
            ),
            SearchResultItem(
                url="https://www.sanjoseca.gov/your-government/agendas-minutes",
                title="Agendas & Minutes | City of San Jose",
                snippet="city council agendas and minutes",
            ),
            SearchResultItem(
                url="https://sanjose.legistar.com/View.ashx?M=F&ID=12345&GUID=abc",
                title="Final Agenda Packet",
                snippet="ordinance no. 31303 approved",
            ),
        ]
    )
    ranked_by_url = {item["url"]: item for item in ranked}
    assert "url_concrete_artifact:parsed" not in ranked_by_url["https://dig.abclocal.go.com/kgo/PDF/sjmemorandum.pdf"][
        "reasons"
    ]
    assert "url_concrete_artifact:parsed" in ranked_by_url["https://sanjose.legistar.com/View.ashx?M=F&ID=12345&GUID=abc"][
        "reasons"
    ]


def test_assess_reader_substance_rejects_title_only_agendas_minutes_output() -> None:
    is_substantive, details = assess_reader_substance("Agendas & Minutes | City of San Jose")
    assert is_substantive is False
    assert details["reason"] == "content_too_short"


def test_reader_failure_stops_before_index() -> None:
    state, service = _service(
        search_results=[
            SearchResultItem(
                url="https://www.sanjoseca.gov/minutes/reader-error",
                title="Minutes",
                snippet="x",
            )
        ],
        reader_fail="reader_unavailable",
    )
    search = service.search_materialize(envelope=_envelope("search_materialize", "rf1"), query="q")
    read = service.read_fetch(
        envelope=_envelope("read_fetch", "rf2"),
        snapshot_id=str(search.refs["search_snapshot_id"]),
    )
    assert read.status == "failed_retryable"
    assert read.retry_class == "provider_unavailable"
    assert len(state.raw_scrapes) == 0


def test_read_fetch_tries_ranked_fallback_candidates_after_reader_error() -> None:
    state, service = _service(
        search_results=[
            SearchResultItem(
                url="https://sanjose.legistar.com/MeetingDetail.aspx?ID=123&GUID=abc",
                title="City Council Meeting Detail",
                snippet="agenda minutes housing item",
            ),
            SearchResultItem(
                url="https://granicus.com/AgendaViewer.php?view_id=12",
                title="City Council Agenda Viewer",
                snippet="meeting agenda council",
            ),
        ]
    )
    service.reader_provider = _RoutingReaderProvider(
        by_url={
            "https://granicus.com/AgendaViewer.php?view_id=12": (
                "City Council meeting minutes for San Jose. "
                "Agenda item 5.1 approved housing subsidy allocations after hearing."
            )
        },
        fail_urls={"https://sanjose.legistar.com/MeetingDetail.aspx?ID=123&GUID=abc"},
    )

    search = service.search_materialize(envelope=_envelope("search_materialize", "fb1"), query="q")
    read = service.read_fetch(
        envelope=_envelope("read_fetch", "fb2"),
        snapshot_id=str(search.refs["search_snapshot_id"]),
        max_reads=3,
    )

    assert read.status == "succeeded_with_alerts"
    assert read.decision_reason == "raw_scrapes_materialized_with_reader_alerts"
    assert any(alert.startswith("reader_error:") for alert in read.alerts)
    assert read.counts["raw_scrapes"] == 1
    assert len(read.details["candidate_audit"]) >= 2
    assert any(item["outcome"] == "reader_provider_error" for item in read.details["candidate_audit"])
    assert any(item["outcome"] == "materialized_raw_scrape" for item in read.details["candidate_audit"])
    assert len(state.raw_scrapes) == 1


def test_read_fetch_blocks_weak_video_fallback_after_official_reader_error() -> None:
    state, service = _service(
        search_results=[
            SearchResultItem(
                url="https://sanjose.legistar.com/MeetingDetail.aspx?ID=123&GUID=abc",
                title="City Council Meeting Detail",
                snippet="agenda minutes housing item",
            ),
            SearchResultItem(
                url="https://www.youtube.com/watch?v=abc123",
                title="San Jose City Council Meeting Video Transcript",
                snippet="full transcript of meeting discussion",
            ),
        ]
    )
    service.reader_provider = _RoutingReaderProvider(
        by_url={
            "https://www.youtube.com/watch?v=abc123": (
                "City Council meeting transcript with discussion of housing policy changes."
            )
        },
        fail_urls={"https://sanjose.legistar.com/MeetingDetail.aspx?ID=123&GUID=abc"},
    )

    search = service.search_materialize(envelope=_envelope("search_materialize", "yt1"), query="q")
    read = service.read_fetch(
        envelope=_envelope("read_fetch", "yt2"),
        snapshot_id=str(search.refs["search_snapshot_id"]),
        max_reads=3,
    )

    assert read.status == "failed_retryable"
    assert read.decision_reason == "reader_provider_error"
    assert read.retry_class == "provider_unavailable"
    assert any(alert.startswith("reader_error:") for alert in read.alerts)
    assert "reader_fallback_blocked_after_official_reader_errors" in read.alerts
    assert any(
        item["outcome"] == "reader_provider_error"
        and item.get("candidate_is_official_artifact") is True
        for item in read.details["candidate_audit"]
    )
    assert any(
        item["outcome"] == "reader_fallback_blocked_after_official_reader_errors"
        and item["url"] == "https://www.youtube.com/watch?v=abc123"
        for item in read.details["candidate_audit"]
    )
    assert len(state.raw_scrapes) == 0


def test_read_fetch_falls_through_agenda_header_logistics_to_legistar_pdf() -> None:
    state, service = _service(
        search_results=[
            SearchResultItem(
                url="https://sanjose.granicus.com/AgendaViewer.php?clip_id=14442&view_id=60",
                title="City Council Meeting Amended Agenda",
                snippet="city council meeting agenda",
            ),
            SearchResultItem(
                url="https://sanjose.legistar.com/LegislationDetail.aspx?ID=31303",
                title="City Hall Resources",
                snippet="home departments and services",
            ),
        ]
    )
    service.reader_provider = _RoutingReaderProvider(
        by_url={
            "https://sanjose.granicus.com/AgendaViewer.php?clip_id=14442&view_id=60": (
                "CITY COUNCIL MEETING Amended Agenda Tuesday, June 11, 2024 1:30 PM "
                "LOCATION: Council Chambers Interpretation is available via webinar controls."
            ),
            "https://sanjose.legistar.com/LegislationDetail.aspx?ID=31303": (
                "Ordinance No. 31302 temporary multifamily housing incentive. "
                "Ordinance No. 31303 affordability compliance options were approved by vote."
            ),
        }
    )

    search = service.search_materialize(envelope=_envelope("search_materialize", "lg1"), query="q")
    read = service.read_fetch(
        envelope=_envelope("read_fetch", "lg2"),
        snapshot_id=str(search.refs["search_snapshot_id"]),
        max_reads=2,
    )

    assert read.status == "succeeded_with_alerts"
    assert read.decision_reason == "raw_scrapes_materialized_with_reader_alerts"
    assert read.details["candidate_audit"][0]["outcome"] == "reader_output_insufficient_substance"
    assert read.details["candidate_audit"][0]["reason"] == "agenda_header_logistics_only"
    assert read.details["candidate_audit"][1]["outcome"] == "materialized_raw_scrape"
    assert len(state.raw_scrapes) == 1


def test_read_fetch_prefetch_skips_obvious_portal_url_and_fetches_artifact() -> None:
    state, service = _service(
        search_results=[
            SearchResultItem(
                url="https://www.sanjoseca.gov/your-government/agendas-minutes",
                title="Agendas & Minutes | City of San Jose",
                snippet="agenda archive",
            ),
            SearchResultItem(
                url="https://sanjose.legistar.com/MeetingDetail.aspx?ID=12345&GUID=abc",
                title="Meeting Detail",
                snippet="agenda item 4.2 housing ordinance adopted",
            ),
        ]
    )
    tracker = _TrackingReaderProvider(
        by_url={
            "https://sanjose.legistar.com/MeetingDetail.aspx?ID=12345&GUID=abc": (
                "Agenda item 4.2 housing affordability ordinance was adopted by vote "
                "after public hearing and staff recommendation."
            )
        },
        forbidden_urls={"https://www.sanjoseca.gov/your-government/agendas-minutes"},
    )
    service.reader_provider = tracker

    search = service.search_materialize(envelope=_envelope("search_materialize", "ps1"), query="q")
    read = service.read_fetch(
        envelope=_envelope("read_fetch", "ps2"),
        snapshot_id=str(search.refs["search_snapshot_id"]),
        max_reads=2,
    )

    assert read.status == "succeeded_with_alerts"
    assert tracker.fetch_calls == ["https://sanjose.legistar.com/MeetingDetail.aspx?ID=12345&GUID=abc"]
    assert any(
        item["outcome"] == "reader_prefetch_skipped_low_value_portal"
        for item in read.details["candidate_audit"]
    )
    assert any(item["outcome"] == "materialized_raw_scrape" for item in read.details["candidate_audit"])
    assert len(state.raw_scrapes) == 1


def test_storage_failure_on_reader_artifact_is_terminal() -> None:
    _, service = _service(
        search_results=[
            SearchResultItem(
                url="https://www.sanjoseca.gov/minutes/storage-error",
                title="Minutes",
                snippet="x",
            )
        ],
        artifact_fail="artifact_store_down",
    )
    search = service.search_materialize(envelope=_envelope("search_materialize", "sf1"), query="q")
    read = service.read_fetch(
        envelope=_envelope("read_fetch", "sf2"),
        snapshot_id=str(search.refs["search_snapshot_id"]),
    )
    assert read.status == "failed_terminal"
    assert read.retry_class == "transient_storage"


def test_navigation_heavy_reader_output_blocks_with_alert_reason() -> None:
    state, service = _service(
        search_results=[
            SearchResultItem(
                url="https://www.sanjoseca.gov/city-hall",
                title="City Hall",
                snippet="navigation shell",
            )
        ]
    )
    service.reader_provider = _StaticReaderProvider(
        "\n".join(
            [
                "Home",
                "Contact Us",
                "Sitemap",
                "Departments",
                "Sign Up for Alerts",
                "Accessibility",
                "Privacy Policy",
                "Menu",
            ]
        )
    )

    search = service.search_materialize(envelope=_envelope("search_materialize", "ns1"), query="q")
    read = service.read_fetch(
        envelope=_envelope("read_fetch", "ns2"),
        snapshot_id=str(search.refs["search_snapshot_id"]),
    )

    assert read.status == "blocked"
    assert read.decision_reason == "reader_output_insufficient_substance"
    assert read.retry_class == "insufficient_evidence"
    assert "reader_output_insufficient_substance:navigation_heavy" in read.alerts
    assert read.details["reader_quality_failures"][0]["reason"] == "navigation_heavy"
    assert len(state.raw_scrapes) == 0


def test_navigation_table_of_contents_with_agenda_words_still_blocks() -> None:
    state, service = _service(
        search_results=[
            SearchResultItem(
                url="https://www.sanjoseca.gov/council-agendas",
                title="Council Agendas",
                snippet="agenda page",
            )
        ]
    )
    service.reader_provider = _StaticReaderProvider(
        "\n".join(
            [
                "Council Agendas | City of San Jose",
                "![Image 1: Skip to page body](https://www.sanjoseca.gov/spacer.gif)",
                "![Image 2: Home](https://www.sanjoseca.gov/spacer.gif)",
                "![Image 3: Residents](https://www.sanjoseca.gov/spacer.gif)",
                "![Image 4: Businesses](https://www.sanjoseca.gov/spacer.gif)",
                "![Image 5: Jobs](https://www.sanjoseca.gov/spacer.gif)",
                "![Image 6: Your Government](https://www.sanjoseca.gov/spacer.gif)",
                "![Image 7: News & Stories](https://www.sanjoseca.gov/spacer.gif)",
                "![Image 8: facebook](https://www.sanjoseca.gov/social.gif)",
                "Home",
                "Menu",
                "Accessibility",
                "- Residents",
                "- Housing",
                "- Businesses",
                "- Jobs",
                "- Your Government",
                "- Mayor",
                "- City Council",
                "- City Clerk",
                "- Agendas & Minutes",
                "- Council Agendas 2019 - Present",
                "- Archived Council Minutes 1950-2011",
                "- Participate & Watch Public Meetings",
                "- Open Government Provisions",
                "- Departments & Offices",
                "- Planning, Building & Code Enforcement",
                "- Transportation",
                "- News",
                "- Blog",
                "- City Calendar",
            ]
        )
    )

    search = service.search_materialize(envelope=_envelope("search_materialize", "toc1"), query="q")
    read = service.read_fetch(
        envelope=_envelope("read_fetch", "toc2"),
        snapshot_id=str(search.refs["search_snapshot_id"]),
    )

    assert read.status == "blocked"
    assert read.decision_reason == "reader_output_insufficient_substance"
    assert read.details["reader_quality_failures"][0]["quality_details"]["markdown_image_count"] >= 8
    assert len(state.raw_scrapes) == 0


def test_navigation_shell_with_images_and_bullets_blocks_despite_generic_meeting_terms() -> None:
    state, service = _service(
        search_results=[
            SearchResultItem(
                url="https://www.sanjoseca.gov/council-agendas",
                title="Council Agendas",
                snippet="agenda page",
            )
        ]
    )
    nav_shell_markdown = "\n".join(
        [
            "Council Agendas | City of San Jose",
            "Home",
            "Contact Us",
            "Sitemap",
            "Menu",
            "Accessibility",
            "Privacy Policy",
            "Sign Up for Alerts",
            "Meeting minutes agenda council housing budget policy hearing public comment resolution ordinance vote",
            "Council approved the consent calendar.",
            "Staff recommendation was posted.",
            "Public hearing information is listed below.",
            *[f"![Image {i}: Nav Icon](https://www.sanjoseca.gov/nav/{i}.gif)" for i in range(1, 22)],
            *[f"- Council agendas and minutes archive link {i}" for i in range(1, 225)],
        ]
    )
    service.reader_provider = _StaticReaderProvider(nav_shell_markdown)

    search = service.search_materialize(envelope=_envelope("search_materialize", "nsx1"), query="q")
    read = service.read_fetch(
        envelope=_envelope("read_fetch", "nsx2"),
        snapshot_id=str(search.refs["search_snapshot_id"]),
    )

    quality = read.details["reader_quality_failures"][0]["quality_details"]
    assert read.status == "blocked"
    assert read.decision_reason == "reader_output_insufficient_substance"
    assert quality["navigation_marker_hits"] >= 4
    assert quality["line_count"] >= 250
    assert quality["markdown_image_count"] >= 21
    assert quality["bullet_line_count"] >= 224
    assert len(state.raw_scrapes) == 0


def test_read_fetch_blocks_when_all_ranked_candidates_are_navigation_shells() -> None:
    state, service = _service(
        search_results=[
            SearchResultItem(
                url="https://www.sanjoseca.gov/home",
                title="City of San Jose Home",
                snippet="departments and services",
            ),
            SearchResultItem(
                url="https://www.sanjoseca.gov/city-hall",
                title="City Hall",
                snippet="resource library and menu",
            ),
            SearchResultItem(
                url="https://www.sanjoseca.gov/resources",
                title="Resources",
                snippet="navigation links",
            ),
        ]
    )
    service.reader_provider = _RoutingReaderProvider(
        by_url={
            "https://www.sanjoseca.gov/home": "Home Contact Sitemap Menu Departments",
            "https://www.sanjoseca.gov/city-hall": "Home Menu Accessibility Privacy Sign Up",
            "https://www.sanjoseca.gov/resources": "Navigation Resources Contact Sitemap",
        }
    )
    search = service.search_materialize(envelope=_envelope("search_materialize", "allnav1"), query="q")
    read = service.read_fetch(
        envelope=_envelope("read_fetch", "allnav2"),
        snapshot_id=str(search.refs["search_snapshot_id"]),
        max_reads=3,
    )

    assert read.status == "blocked"
    assert read.decision_reason == "reader_output_insufficient_substance"
    assert read.retry_class == "insufficient_evidence"
    assert len(read.details["reader_quality_failures"]) == 3
    assert all(
        item["outcome"] == "reader_output_insufficient_substance"
        for item in read.details["candidate_audit"]
    )
    assert len(state.raw_scrapes) == 0


def test_read_fetch_blocks_when_all_candidates_are_agenda_header_logistics() -> None:
    state, service = _service(
        search_results=[
            SearchResultItem(
                url="https://sanjose.granicus.com/AgendaViewer.php?clip_id=1&view_id=60",
                title="City Council Amended Agenda",
                snippet="LOCATION: Council Chambers Interpretation is available",
            ),
            SearchResultItem(
                url="https://sanjose.granicus.com/AgendaViewer.php?clip_id=2&view_id=60",
                title="Special Meeting Agenda",
                snippet="webinar controls and teleconference logistics",
            ),
        ]
    )
    service.reader_provider = _RoutingReaderProvider(
        by_url={
            "https://sanjose.granicus.com/AgendaViewer.php?clip_id=1&view_id=60": (
                "CITY COUNCIL MEETING Amended Agenda LOCATION: Council Chambers "
                "Interpretation is available."
            ),
            "https://sanjose.granicus.com/AgendaViewer.php?clip_id=2&view_id=60": (
                "SPECIAL MEETING AGENDA Webinar details Dial-in and teleconference "
                "location information."
            ),
        }
    )
    search = service.search_materialize(envelope=_envelope("search_materialize", "ahl1"), query="q")
    read = service.read_fetch(
        envelope=_envelope("read_fetch", "ahl2"),
        snapshot_id=str(search.refs["search_snapshot_id"]),
        max_reads=2,
    )

    assert read.status == "blocked"
    assert read.decision_reason == "reader_output_insufficient_substance"
    assert len(read.details["reader_quality_failures"]) == 2
    assert all(
        item["reason"] == "agenda_header_logistics_only"
        for item in read.details["reader_quality_failures"]
    )
    assert len(state.raw_scrapes) == 0


def test_substantive_meeting_reader_output_is_allowed() -> None:
    _, service = _service(
        search_results=[
            SearchResultItem(
                url="https://www.sanjoseca.gov/council/agenda/2026-04-13",
                title="Agenda and Minutes",
                snippet="housing hearing",
            )
        ]
    )
    service.reader_provider = _StaticReaderProvider(
        (
            "San Jose City Council meeting minutes for April 13, 2026. "
            "Agenda item 4.2 covered housing affordability policy updates. "
            "Council voted 9-2 to advance tenant protection ordinance amendments "
            "after public comment and budget hearing."
        )
    )

    search = service.search_materialize(envelope=_envelope("search_materialize", "sm1"), query="q")
    read = service.read_fetch(
        envelope=_envelope("read_fetch", "sm2"),
        snapshot_id=str(search.refs["search_snapshot_id"]),
    )

    assert read.status == "succeeded"
    assert read.decision_reason == "raw_scrapes_materialized"
    assert read.counts["raw_scrapes"] == 1
    assert read.alerts == []


def test_full_refresh_surfaces_reader_quality_alert_to_summary() -> None:
    state, service = _service(
        search_results=[
            SearchResultItem(
                url="https://www.sanjoseca.gov/city-hall",
                title="City Hall",
                snippet="navigation shell",
            )
        ]
    )
    service.reader_provider = _StaticReaderProvider(
        "Home Contact Sitemap Menu Accessibility Privacy Sign Up for Alerts Departments"
    )
    state.now = datetime(2026, 4, 13, tzinfo=timezone.utc)

    responses = service.full_refresh(
        query="q",
        question="What changed?",
        search_envelope=_envelope("search_materialize", "rq1"),
        freshness_envelope=_envelope("freshness_gate", "rq2"),
        read_envelope=_envelope("read_fetch", "rq3"),
        index_envelope=_envelope("index", "rq4"),
        analyze_envelope=_envelope("analyze", "rq5"),
        summarize_envelope=_envelope("summarize_run", "rq6"),
        policy=_default_policy(),
    )
    by_command = {item.command: item for item in responses}

    assert by_command["read_fetch"].status == "blocked"
    assert by_command["read_fetch"].decision_reason == "reader_output_insufficient_substance"
    assert "reader_output_insufficient_substance:navigation_heavy" in by_command["summarize_run"].alerts
    assert "index" not in by_command
    assert "analyze" not in by_command
    assert by_command["summarize_run"].status == "blocked"


def test_no_analysis_without_evidence_is_blocked() -> None:
    _, service = _service()
    result = service.analyze(
        envelope=_envelope("analyze", "na1"),
        question="What changed?",
        jurisdiction_id="san-jose-ca",
        source_family="meeting_minutes",
    )
    assert result.status == "blocked"
    assert result.retry_class == "insufficient_evidence"


def test_analyze_ranks_late_housing_action_chunks_over_early_headers() -> None:
    state, service = _service()
    recorder = _RecordingAnalyzer()
    service.analyzer = recorder
    canonical_key = "v2|jurisdiction=san-jose-ca|family=meeting_minutes|doctype=minutes|url=https://example.com"
    artifact_ref = "artifacts/2026-04-13.windmill-domain.v1/san-jose-ca/meeting_minutes/reader_output/example.md"

    state.chunks["chunk-early-0"] = {
        "chunk_id": "chunk-early-0",
        "canonical_document_key": canonical_key,
        "artifact_ref": artifact_ref,
        "jurisdiction_id": "san-jose-ca",
        "source_family": "meeting_minutes",
        "chunk_index": 0,
        "content": "CITY COUNCIL MEETING AGENDA Tuesday 1:30 PM Council Chambers location and dial-in.",
    }
    state.chunks["chunk-early-1"] = {
        "chunk_id": "chunk-early-1",
        "canonical_document_key": canonical_key,
        "artifact_ref": artifact_ref,
        "jurisdiction_id": "san-jose-ca",
        "source_family": "meeting_minutes",
        "chunk_index": 1,
        "content": "ROLL CALL, ANNOUNCEMENTS, ceremonial items, and public comment instructions.",
    }
    state.chunks["chunk-late-220"] = {
        "chunk_id": "chunk-late-220",
        "canonical_document_key": canonical_key,
        "artifact_ref": artifact_ref,
        "jurisdiction_id": "san-jose-ca",
        "source_family": "meeting_minutes",
        "chunk_index": 220,
        "content": (
            "Agenda Item 10.2. Ordinance No. 31303 was adopted and approved to create a temporary "
            "multifamily housing incentive with affordability compliance options and mobilehome rent updates."
        ),
    }

    result = service.analyze(
        envelope=_envelope("analyze", "rank-a1"),
        question="Summarize housing decisions and ordinance actions from this San Jose meeting.",
        jurisdiction_id="san-jose-ca",
        source_family="meeting_minutes",
    )

    assert result.status == "succeeded"
    assert recorder.last_evidence_chunks[0]["chunk_id"] == "chunk-late-220"
    assert result.details["evidence_selection"]["selected_chunks"][0]["chunk_id"] == "chunk-late-220"
    assert result.details["evidence_selection"]["selected_chunks"][0]["score"] > 0


def test_empty_blocked_flow_summarizes_and_stops() -> None:
    state, service = _service(search_results=[])
    state.now = datetime(2026, 4, 13, tzinfo=timezone.utc)
    responses = service.full_refresh(
        query="q",
        question="What changed?",
        search_envelope=_envelope("search_materialize", "b1"),
        freshness_envelope=_envelope("freshness_gate", "b2"),
        read_envelope=_envelope("read_fetch", "b3"),
        index_envelope=_envelope("index", "b4"),
        analyze_envelope=_envelope("analyze", "b5"),
        summarize_envelope=_envelope("summarize_run", "b6"),
        policy=_default_policy(),
    )
    by_command = {item.command: item for item in responses}
    assert by_command["freshness_gate"].decision_reason == "empty_blocked"
    assert "read_fetch" not in by_command
    assert by_command["summarize_run"].status == "blocked"
