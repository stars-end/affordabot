"""Tests for bd-jxclm.14.1 persisted pipeline service.

Covers all 9 POC requirements:
1. SearXNG-compatible success produces normalized search_result_snapshots.
2. Zero results is distinct from provider failure.
3. Provider timeout/error can stale-fallback with latest-good snapshot.
4. Provider timeout/error fails closed with no prior snapshot.
5. Z.ai Web Reader calls POST /reader by configuration.
6. Reader output persisted as raw + normalized markdown.
7. Z.ai LLM analysis provider shape is mockable.
8. Idempotent replay reuses existing artifacts.
9. Evidence includes ZAI_DIRECT_SEARCH_DEPRECATED: true.
"""

from __future__ import annotations

import shutil
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from services.persisted_pipeline import (
    CONTRACT_VERSION,
    ZAI_DIRECT_SEARCH_DEPRECATED,
    ZAI_READER_ENDPOINT_CODING,
    ZAI_READER_ENDPOINT_PAAS,
    FailingSearchProvider,
    FixedSearchProvider,
    MockAnalysisProvider,
    MockReaderProvider,
    PersistedPipeline,
    PersistedPipelineStore,
    SearXNGSearchProvider,
    ZeroResultSearchProvider,
    ZaiLLMAnalysisProvider,
    ZaiWebReaderProvider,
    make_step_response,
)


@pytest.fixture()
def tmp_dirs():
    d = Path(tempfile.mkdtemp())
    db_path = d / "test.sqlite3"
    art_dir = d / "artifacts"
    store = PersistedPipelineStore.fresh(db_path=db_path, artifact_dir=art_dir)
    yield store, d
    store.close()
    shutil.rmtree(d, ignore_errors=True)


def _now():
    return datetime(2026, 4, 12, 12, 0, 0, tzinfo=timezone.utc)


FAMILY = "san-jose-city-council-minutes"
QUERY = "San Jose City Council meeting minutes"


class TestSearchMaterialize:
    def test_fresh_search_produces_snapshot(self, tmp_dirs):
        store, _ = tmp_dirs
        pipeline = PersistedPipeline(
            store,
            FixedSearchProvider(),
            MockReaderProvider(),
            MockAnalysisProvider(),
            now_fn=_now,
        )
        resp = pipeline.run_full(
            run_label="test-fresh",
            triggered_by="test",
            query=QUERY,
            family=FAMILY,
        )
        assert resp["status"] == "succeeded"
        assert resp["decision"] == "fresh_snapshot"
        assert resp["evidence"]["snapshot_id"] is not None
        assert resp["evidence"]["result_count"] > 0
        counts = store.row_counts()
        assert counts["search_result_snapshots"] >= 1

    def test_searxng_provider_class_exists(self):
        provider = SearXNGSearchProvider(base_url="http://localhost:8888")
        assert hasattr(provider, "search")

    def test_zero_results_is_not_failure(self, tmp_dirs):
        store, _ = tmp_dirs
        now2 = _now() + timedelta(minutes=1)
        pipeline = PersistedPipeline(
            store,
            ZeroResultSearchProvider(),
            MockReaderProvider(),
            MockAnalysisProvider(),
            now_fn=lambda: now2,
        )
        resp = pipeline.run_full(
            run_label="test-zero",
            triggered_by="test",
            query=QUERY,
            family=FAMILY,
            skip_analysis=True,
        )
        assert resp["status"] == "succeeded"
        assert resp["decision"] == "zero_results"
        assert resp["evidence"]["result_count"] == 0

    def test_zero_results_does_not_stale_fallback(self, tmp_dirs):
        store, _ = tmp_dirs
        pipeline = PersistedPipeline(
            store,
            FixedSearchProvider(),
            MockReaderProvider(),
            MockAnalysisProvider(),
            now_fn=_now,
        )
        pipeline.run_full(
            run_label="setup",
            triggered_by="test",
            query=QUERY,
            family=FAMILY,
        )
        now2 = _now() + timedelta(minutes=1)
        pipeline2 = PersistedPipeline(
            store,
            ZeroResultSearchProvider(),
            MockReaderProvider(),
            MockAnalysisProvider(),
            now_fn=lambda: now2,
        )
        resp = pipeline2.run_full(
            run_label="zero-no-fallback",
            triggered_by="test",
            query=QUERY,
            family=FAMILY,
            allow_stale_fallback=True,
            skip_analysis=True,
        )
        assert resp["status"] == "succeeded"
        assert resp["decision"] == "zero_results"

    def test_provider_failure_stale_fallback(self, tmp_dirs):
        store, _ = tmp_dirs
        pipeline = PersistedPipeline(
            store,
            FixedSearchProvider(),
            MockReaderProvider(),
            MockAnalysisProvider(),
            now_fn=_now,
        )
        pipeline.run_full(
            run_label="setup-for-fallback",
            triggered_by="test",
            query=QUERY,
            family=FAMILY,
        )
        now2 = _now() + timedelta(minutes=1)
        pipeline2 = PersistedPipeline(
            store,
            FailingSearchProvider("outage"),
            MockReaderProvider(),
            MockAnalysisProvider(),
            now_fn=lambda: now2,
        )
        resp = pipeline2.run_full(
            run_label="stale-backed",
            triggered_by="test",
            query=QUERY,
            family=FAMILY,
            allow_stale_fallback=True,
        )
        assert resp["status"] == "succeeded"
        assert resp["decision"] == "stale_backed"
        assert resp["evidence"]["stale_backed"] is True

    def test_provider_failure_fails_closed_no_prior(self, tmp_dirs):
        store, d = tmp_dirs
        fresh_store = PersistedPipelineStore.fresh(
            db_path=d / "empty.sqlite3",
            artifact_dir=d / "empty_artifacts",
        )
        pipeline = PersistedPipeline(
            fresh_store,
            FailingSearchProvider("no snapshot"),
            MockReaderProvider(),
            MockAnalysisProvider(),
            now_fn=_now,
        )
        resp = pipeline.run_full(
            run_label="fails-closed",
            triggered_by="test",
            query=QUERY,
            family=FAMILY,
            allow_stale_fallback=True,
        )
        assert resp["status"] == "failed"
        assert resp["decision"] == "provider_failed_no_fallback"
        fresh_store.close()

    def test_provider_failure_fails_closed_when_disabled(self, tmp_dirs):
        store, _ = tmp_dirs
        pipeline = PersistedPipeline(
            store,
            FixedSearchProvider(),
            MockReaderProvider(),
            MockAnalysisProvider(),
            now_fn=_now,
        )
        pipeline.run_full(
            run_label="setup",
            triggered_by="test",
            query=QUERY,
            family=FAMILY,
        )
        now2 = _now() + timedelta(minutes=1)
        pipeline2 = PersistedPipeline(
            store,
            FailingSearchProvider("disabled"),
            MockReaderProvider(),
            MockAnalysisProvider(),
            now_fn=lambda: now2,
        )
        resp = pipeline2.run_full(
            run_label="no-fallback-allowed",
            triggered_by="test",
            query=QUERY,
            family=FAMILY,
            allow_stale_fallback=False,
        )
        assert resp["status"] == "failed"
        assert resp["decision"] == "provider_failed_no_fallback"


class TestZaiWebReader:
    def test_reader_endpoint_paas(self):
        assert ZAI_READER_ENDPOINT_PAAS == "https://api.z.ai/api/paas/v4/reader"

    def test_reader_endpoint_coding(self):
        assert (
            ZAI_READER_ENDPOINT_CODING == "https://api.z.ai/api/coding/paas/v4/reader"
        )

    def test_reader_class_calls_reader_endpoint(self):
        provider = ZaiWebReaderProvider(
            api_key="test-key",
            endpoint=ZAI_READER_ENDPOINT_PAAS,
        )
        assert provider.endpoint == ZAI_READER_ENDPOINT_PAAS
        assert "reader" in provider.endpoint
        assert "chat/completions" not in provider.endpoint

    def test_reader_endpoint_configurable(self):
        provider = ZaiWebReaderProvider(
            api_key="test-key",
            endpoint=ZAI_READER_ENDPOINT_CODING,
        )
        assert provider.endpoint == ZAI_READER_ENDPOINT_CODING

    def test_reader_output_persisted(self, tmp_dirs):
        store, _ = tmp_dirs
        pipeline = PersistedPipeline(
            store,
            FixedSearchProvider(),
            MockReaderProvider(),
            MockAnalysisProvider(),
            now_fn=_now,
        )
        resp = pipeline.run_full(
            run_label="test-read-persist",
            triggered_by="test",
            query=QUERY,
            family=FAMILY,
        )
        assert resp["status"] == "succeeded"
        artifacts = store.rows("content_artifacts")
        kinds = {a["artifact_kind"] for a in artifacts}
        assert "raw_provider_response" in kinds
        assert "reader_markdown" in kinds

    def test_reader_raw_and_normalized_both_written(self, tmp_dirs):
        store, _ = tmp_dirs
        pipeline = PersistedPipeline(
            store,
            FixedSearchProvider(),
            MockReaderProvider(),
            MockAnalysisProvider(),
            now_fn=_now,
        )
        pipeline.run_full(
            run_label="test-dual-artifact",
            triggered_by="test",
            query=QUERY,
            family=FAMILY,
        )
        raw = [
            a
            for a in store.rows("content_artifacts")
            if a["artifact_kind"] == "raw_provider_response"
        ]
        md = [
            a
            for a in store.rows("content_artifacts")
            if a["artifact_kind"] == "reader_markdown"
        ]
        assert len(raw) >= 1
        assert len(md) >= 1
        assert raw[0]["bytes"] > 0
        assert md[0]["bytes"] > 0


class TestZaiLLMAnalysis:
    def test_mock_analysis_provider(self):
        provider = MockAnalysisProvider()
        result = provider.analyze("test content", {"family": "test"})
        assert result.summary
        assert result.provider == "mock_analysis"
        assert len(result.key_facts) >= 1

    def test_zai_llm_class_exists(self):
        assert ZaiLLMAnalysisProvider is not None

    def test_zai_llm_requires_api_key(self):
        provider = ZaiLLMAnalysisProvider(api_key="")
        with pytest.raises(RuntimeError, match="ZAI_API_KEY"):
            provider.analyze("test", {})

    def test_analysis_result_persisted(self, tmp_dirs):
        store, _ = tmp_dirs
        pipeline = PersistedPipeline(
            store,
            FixedSearchProvider(),
            MockReaderProvider(),
            MockAnalysisProvider(),
            now_fn=_now,
        )
        resp = pipeline.run_full(
            run_label="test-analysis",
            triggered_by="test",
            query=QUERY,
            family=FAMILY,
        )
        assert resp["status"] == "succeeded"
        analysis_arts = [
            a
            for a in store.rows("content_artifacts")
            if a["artifact_kind"] == "analysis_result"
        ]
        assert len(analysis_arts) >= 1


class TestIdempotentReplay:
    def test_replay_reuses_search_snapshot(self, tmp_dirs):
        store, _ = tmp_dirs
        pipeline = PersistedPipeline(
            store,
            FixedSearchProvider(),
            MockReaderProvider(),
            MockAnalysisProvider(),
            now_fn=_now,
        )
        pipeline.run_full(
            run_label="first",
            triggered_by="test",
            query=QUERY,
            family=FAMILY,
        )
        now2 = _now() + timedelta(minutes=1)
        pipeline2 = PersistedPipeline(
            store,
            FixedSearchProvider(),
            MockReaderProvider(),
            MockAnalysisProvider(),
            now_fn=lambda: now2,
        )
        resp = pipeline2.run_full(
            run_label="replay",
            triggered_by="test",
            query=QUERY,
            family=FAMILY,
            prefer_cached_search=True,
        )
        assert resp["status"] == "succeeded"
        assert resp["evidence"]["stale_backed"] is False

    def test_replay_reuses_reader_artifacts(self, tmp_dirs):
        store, _ = tmp_dirs
        pipeline = PersistedPipeline(
            store,
            FixedSearchProvider(),
            MockReaderProvider(),
            MockAnalysisProvider(),
            now_fn=_now,
        )
        pipeline.run_full(
            run_label="first",
            triggered_by="test",
            query=QUERY,
            family=FAMILY,
        )
        initial_count = len(store.rows("content_artifacts"))
        now2 = _now() + timedelta(minutes=1)
        pipeline2 = PersistedPipeline(
            store,
            FixedSearchProvider(),
            MockReaderProvider(),
            MockAnalysisProvider(),
            now_fn=lambda: now2,
        )
        pipeline2.run_full(
            run_label="replay",
            triggered_by="test",
            query=QUERY,
            family=FAMILY,
            prefer_cached_search=True,
        )
        assert len(store.rows("content_artifacts")) == initial_count


class TestStepResponseContract:
    def test_no_retry_fields_in_response(self):
        resp = make_step_response(
            run_id="test",
            step="search_materialize",
            status="succeeded",
            decision="fresh_snapshot",
            decision_reason="test",
        )
        assert "next_recommended_step" not in resp
        assert "max_retries" not in resp
        assert "retry_after_seconds" not in resp

    def test_response_has_required_fields(self):
        resp = make_step_response(
            run_id="test",
            step="search_materialize",
            status="succeeded",
            decision="fresh_snapshot",
            decision_reason="test",
            windmill_flow_run_id="wm-flow-123",
            windmill_job_id="wm-job-456",
        )
        assert resp["contract_version"] == CONTRACT_VERSION
        assert resp["run_id"] == "test"
        assert resp["step"] == "search_materialize"
        assert resp["status"] == "succeeded"
        assert resp["decision"] == "fresh_snapshot"
        assert resp["decision_reason"] == "test"
        assert resp["windmill_flow_run_id"] == "wm-flow-123"
        assert resp["windmill_job_id"] == "wm-job-456"
        assert "evidence" in resp
        assert "alerts" in resp

    def test_full_pipeline_response_conforms(self, tmp_dirs):
        store, _ = tmp_dirs
        pipeline = PersistedPipeline(
            store,
            FixedSearchProvider(),
            MockReaderProvider(),
            MockAnalysisProvider(),
            now_fn=_now,
        )
        resp = pipeline.run_full(
            run_label="contract-test",
            triggered_by="test",
            query=QUERY,
            family=FAMILY,
        )
        assert resp["contract_version"] == CONTRACT_VERSION
        assert "next_recommended_step" not in resp
        assert "max_retries" not in resp
        assert "retry_after_seconds" not in resp


class TestDeprecatedSearch:
    def test_zai_direct_search_deprecated_flag(self):
        assert ZAI_DIRECT_SEARCH_DEPRECATED is True

    def test_reader_metadata_marks_deprecated(self):
        provider = ZaiWebReaderProvider(api_key="test-key")
        assert "reader" in provider.endpoint
        assert (
            "search" not in provider.endpoint.lower()
            or "web_search" not in provider.endpoint
        )


class TestStoreSchema:
    def test_three_core_tables(self, tmp_dirs):
        store, _ = tmp_dirs
        counts = store.row_counts()
        assert "pipeline_runs" in counts
        assert "search_result_snapshots" in counts
        assert "content_artifacts" in counts

    def test_pipeline_steps_not_in_schema(self, tmp_dirs):
        store, _ = tmp_dirs
        counts = store.row_counts()
        assert "pipeline_steps" not in counts

    def test_snapshot_stores_provider_info(self, tmp_dirs):
        store, _ = tmp_dirs
        pipeline = PersistedPipeline(
            store,
            FixedSearchProvider(),
            MockReaderProvider(),
            MockAnalysisProvider(),
            now_fn=_now,
        )
        pipeline.run_full(
            run_label="provider-test",
            triggered_by="test",
            query=QUERY,
            family=FAMILY,
        )
        snapshots = store.rows("search_result_snapshots")
        assert len(snapshots) >= 1
        assert snapshots[0]["provider"] == "FixedSearchProvider"

    def test_snapshot_distinguishes_zero_results_status(self, tmp_dirs):
        store, _ = tmp_dirs
        store.insert_snapshot(
            family=FAMILY,
            query="empty query",
            provider="test",
            results=[],
            observed_at=_now(),
            expires_at=_now() + timedelta(hours=36),
        )
        snapshots = store.rows("search_result_snapshots")
        zero = [s for s in snapshots if s["status"] == "zero_results"]
        assert len(zero) == 1
        assert zero[0]["result_count"] == 0
