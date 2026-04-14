from __future__ import annotations

from datetime import datetime, timedelta, timezone

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
