from pathlib import Path

from services.persisted_pipeline_poc import FailingSearchProvider
from services.persisted_pipeline_poc import FetchResult
from services.persisted_pipeline_poc import FixedSanJoseMinutesSearchProvider
from services.persisted_pipeline_poc import FIXTURE_EVENT
from services.persisted_pipeline_poc import PersistedPipelineStore
from services.persisted_pipeline_poc import SanJosePersistedPipelinePOC
from services.persisted_pipeline_poc import evaluate_checks
from services.persisted_pipeline_poc import json_dumps
from services.persisted_pipeline_poc import render_markdown_report
from services.persisted_pipeline_poc import run_three_pass_verification


class FixtureFetcher:
    def fetch(self, url: str) -> FetchResult:
        return FetchResult(
            url=url,
            body=json_dumps(FIXTURE_EVENT).encode("utf-8"),
            content_type="application/json",
            source="unit_fixture",
        )


def make_store(tmp_path: Path) -> PersistedPipelineStore:
    return PersistedPipelineStore(
        db_path=tmp_path / "poc.sqlite3",
        artifact_dir=tmp_path / "object_store",
    )


def test_three_pass_verification_populates_contract_tables(tmp_path):
    store = make_store(tmp_path)
    try:
        summary = run_three_pass_verification(store=store, network_enabled=False)

        assert all(summary["checks"].values())
        assert summary["row_counts"] == {
            "pipeline_runs": 3,
            "pipeline_steps": 6,
            "search_result_snapshots": 2,
            "content_artifacts": 2,
        }

        runs = store.rows("pipeline_runs")
        assert [run["status"] for run in runs] == [
            "completed",
            "completed",
            "completed",
        ]
        assert all(run["contract_version"] for run in runs)

        stale_snapshots = [
            row for row in store.rows("search_result_snapshots") if row["stale_backed"]
        ]
        assert len(stale_snapshots) == 1
        assert stale_snapshots[0]["source_snapshot_id"]
        assert stale_snapshots[0]["provider_failure_json"]

        artifacts = store.rows("content_artifacts")
        assert {artifact["artifact_kind"] for artifact in artifacts} == {
            "raw_event_json",
            "minutes_markdown",
        }
        for artifact in artifacts:
            assert Path(artifact["storage_uri"]).exists()
    finally:
        store.close()


def test_replay_reuses_fresh_search_snapshot_and_content_artifacts(tmp_path):
    store = make_store(tmp_path)
    try:
        first = SanJosePersistedPipelinePOC(
            store, FixedSanJoseMinutesSearchProvider(), FixtureFetcher()
        ).run(
            run_label="first",
            triggered_by="test",
        )
        second = SanJosePersistedPipelinePOC(
            store, FixedSanJoseMinutesSearchProvider(), FixtureFetcher()
        ).run(
            run_label="second",
            triggered_by="test",
            prefer_cached_search=True,
        )

        assert first["status"] == "completed"
        assert second["status"] == "completed"
        assert second["search_step"]["reused_snapshot_id"] == first["snapshot_id"]
        assert second["read_step"]["reused"] is True
        assert store.row_counts()["content_artifacts"] == 2
    finally:
        store.close()


def test_stale_fallback_fails_closed_without_prior_snapshot(tmp_path):
    store = make_store(tmp_path)
    try:
        run = SanJosePersistedPipelinePOC(
            store, FailingSearchProvider(), FixtureFetcher()
        ).run(
            run_label="no-fallback",
            triggered_by="test",
            allow_stale_fallback=True,
        )

        assert run["status"] == "failed"
        assert "no fresh fallback snapshot" in run["error"]
        assert store.row_counts()["search_result_snapshots"] == 0
        failed_steps = [
            step for step in store.rows("pipeline_steps") if step["status"] == "failed"
        ]
        assert len(failed_steps) == 1
    finally:
        store.close()


def test_report_contains_verdict_counts_and_artifact_paths(tmp_path):
    store = make_store(tmp_path)
    try:
        summary = run_three_pass_verification(store=store, network_enabled=False)
        report_path = tmp_path / "report.md"
        report = render_markdown_report(
            summary=summary,
            store=store,
            db_path=tmp_path / "poc.sqlite3",
            report_path=report_path,
        )

        assert "VERDICT: PASS" in report
        assert "pipeline_runs: 3" in report
        assert "search_result_snapshots: 2" in report
        assert "stale-backed-search-failure-drill" in report
        assert "minutes_markdown" in report
        assert evaluate_checks(store, summary["runs"]) == summary["checks"]
    finally:
        store.close()
