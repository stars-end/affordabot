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
    assert by_command["search_materialize"].status == "skipped"
    assert by_command["index"].status == "skipped"
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

