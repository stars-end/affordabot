from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any
import asyncio
import json

from services.pipeline.domain.bridge import RailwayRuntimeBridge, RunScopeRequest


@dataclass
class _Row:
    data: dict[str, Any]

    def __getitem__(self, key: str) -> Any:
        return self.data[key]


class FakeDB:
    def __init__(self) -> None:
        self.pipeline_runs: dict[str, str] = {}
        self.command_results: dict[tuple[str, str], dict[str, Any]] = {}
        self.snapshots: dict[str, dict[str, Any]] = {}
        self.snapshot_idempotency: dict[str, str] = {}
        self.artifacts: dict[tuple[str, str, str, str], dict[str, Any]] = {}
        self.raw_scrapes: dict[str, dict[str, Any]] = {}
        self.raw_by_identity: dict[tuple[str, str], str] = {}
        self.chunks: dict[str, dict[str, Any]] = {}
        self.sources: dict[str, str] = {}
        self.exec_queries: list[str] = []
        self.next_run = 0
        self.next_snapshot = 0

    async def get_or_create_source(self, jurisdiction_id: str, name: str, type: str, url: str | None = None) -> str:
        key = f"{jurisdiction_id}|{name}|{type}|{url or ''}"
        if key not in self.sources:
            self.sources[key] = f"00000000-0000-0000-0000-{len(self.sources)+1:012d}"
        return self.sources[key]

    async def _fetchrow(self, query: str, *args: Any) -> _Row | None:
        if "FROM pipeline_runs" in query and "windmill_run_id" in query:
            key = f"{args[0]}|{args[1]}|{args[2]}"
            run_id = self.pipeline_runs.get(key)
            return _Row({"id": run_id}) if run_id else None

        if "INSERT INTO pipeline_runs" in query:
            self.next_run += 1
            run_id = f"00000000-0000-0000-0000-{self.next_run:012d}"
            key = f"{args[4]}|{args[6]}|{args[1]}"
            self.pipeline_runs[key] = run_id
            return _Row({"id": run_id})

        if "FROM pipeline_command_results" in query:
            row = self.command_results.get((args[0], args[1]))
            return _Row(row) if row else None

        if "INSERT INTO search_result_snapshots" in query:
            idem = str(args[8])
            snapshot_id = self.snapshot_idempotency.get(idem)
            if not snapshot_id:
                self.next_snapshot += 1
                snapshot_id = f"00000000-0000-0000-0000-{self.next_snapshot:012d}"
                self.snapshot_idempotency[idem] = snapshot_id
            self.snapshots[snapshot_id] = {
                "result_count": int(args[5]),
                "captured_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc),
                "snapshot_payload": __import__("json").loads(args[6]),
            }
            return _Row({"id": snapshot_id, "result_count": int(args[5])})

        if "SELECT result_count, captured_at FROM search_result_snapshots" in query:
            row = self.snapshots.get(str(args[0]))
            return _Row(row) if row else None

        if "SELECT snapshot_payload FROM search_result_snapshots" in query:
            row = self.snapshots.get(str(args[0]))
            return _Row({"snapshot_payload": row["snapshot_payload"]}) if row else None

        if "SELECT storage_uri" in query and "FROM content_artifacts" in query:
            row = self.artifacts.get((args[0], args[1], "reader_output", args[2]))
            return _Row({"storage_uri": row["storage_uri"]}) if row else None

        if "FROM raw_scrapes" in query and "canonical_document_key = $1 AND content_hash = $2" in query:
            raw_id = self.raw_by_identity.get((args[0], args[1]))
            if not raw_id:
                return None
            row = self.raw_scrapes[raw_id]
            return _Row({"id": raw_id, "document_id": row["document_id"], "metadata": row["metadata"]})

        if "FROM raw_scrapes" in query and "WHERE id = $1::uuid" in query:
            raw = self.raw_scrapes.get(str(args[0]))
            if not raw:
                return None
            return _Row(
                {
                    "id": raw["id"],
                    "document_id": raw["document_id"],
                    "content_hash": raw["content_hash"],
                    "canonical_document_key": raw["canonical_document_key"],
                    "data": raw["data"],
                    "storage_uri": raw["storage_uri"],
                }
            )
        return None

    async def _fetch(self, query: str, *args: Any) -> list[_Row]:
        if "FROM document_chunks" in query and "WHERE document_id" in query:
            document_id = str(args[0])
            rows = [row for row in self.chunks.values() if row["document_id"] == document_id]
            rows = sorted(rows, key=lambda item: item["chunk_index"])
            return [_Row({"content": row["content"]}) for row in rows]
        return []

    async def _execute(self, query: str, *args: Any) -> str:
        self.exec_queries.append(query.strip())

        if "INSERT INTO pipeline_command_results" in query:
            self.command_results[(args[1], args[2])] = {
                "status": args[3],
                "decision_reason": args[4],
                "retry_class": args[5],
                "alerts": __import__("json").loads(args[6]),
                "refs": __import__("json").loads(args[7]),
                "counts": __import__("json").loads(args[8]),
                "details": __import__("json").loads(args[9]),
                "contract_version": args[10],
            }

        if "INSERT INTO content_artifacts" in query:
            self.artifacts[(args[0], args[1], "reader_output", args[2])] = {
                "storage_uri": args[3]
            }

        if "INSERT INTO raw_scrapes" in query:
            raw_id = str(args[0])
            self.raw_scrapes[raw_id] = {
                "id": raw_id,
                "document_id": str(args[8]),
                "content_hash": str(args[2]),
                "canonical_document_key": str(args[9]),
                "data": __import__("json").loads(args[4]),
                "storage_uri": str(args[7]),
                "metadata": __import__("json").loads(args[6]),
                "processed": False,
            }
            self.raw_by_identity[(str(args[9]), str(args[2]))] = raw_id

        if "UPDATE raw_scrapes" in query and "processed = true" in query:
            raw_id = str(args[1])
            if raw_id in self.raw_scrapes:
                self.raw_scrapes[raw_id]["processed"] = True

        if "INSERT INTO document_chunks" in query:
            chunk_id = str(args[0])
            self.chunks[chunk_id] = {
                "id": chunk_id,
                "document_id": str(args[1]),
                "content": str(args[2]),
                "embedding": args[3],
                "chunk_index": int(args[5]),
            }

        return "OK"


class FakeStorage:
    def __init__(self) -> None:
        self.upload_calls: list[tuple[str, bytes, str]] = []

    async def upload(self, path: str, content: bytes, content_type: str = "application/octet-stream") -> str:
        self.upload_calls.append((path, content, content_type))
        return path


class JsonStringFakeDB(FakeDB):
    async def _fetchrow(self, query: str, *args: Any) -> _Row | None:
        row = await super()._fetchrow(query, *args)
        if row and "SELECT snapshot_payload FROM search_result_snapshots" in query:
            return _Row({"snapshot_payload": json.dumps(row["snapshot_payload"])})
        if row and "FROM raw_scrapes" in query and "WHERE id = $1::uuid" in query:
            data = dict(row.data)
            data["data"] = json.dumps(data["data"])
            return _Row(data)
        if row and "FROM pipeline_command_results" in query:
            data = dict(row.data)
            data["alerts"] = json.dumps(data["alerts"])
            data["refs"] = json.dumps(data["refs"])
            data["counts"] = json.dumps(data["counts"])
            data["details"] = json.dumps(data["details"])
            return _Row(data)
        return row


class FakeSearchClient:
    def __init__(self, results: list[dict[str, Any]]) -> None:
        self.results = results

    async def search(self, query: str, count: int = 10) -> list[dict[str, Any]]:
        _ = (query, count)
        return self.results


class FakeReaderClient:
    def __init__(self, *, fail: str | None = None, content: str | None = None) -> None:
        self.fail = fail
        self.content = content or "# Meeting Minutes\nHousing item approved.\nFees moved to May.\n"

    async def fetch_content(self, url: str, **kwargs: Any) -> dict[str, Any]:
        _ = kwargs
        if self.fail:
            raise RuntimeError(self.fail)
        return {
            "content": self.content,
            "title": "San Jose Meeting Minutes",
            "url": url,
        }


class RoutingFakeReaderClient:
    def __init__(
        self,
        *,
        by_url: dict[str, str] | None = None,
        fail_urls: set[str] | None = None,
    ) -> None:
        self.by_url = by_url or {}
        self.fail_urls = fail_urls or set()

    async def fetch_content(self, url: str, **kwargs: Any) -> dict[str, Any]:
        _ = kwargs
        if url in self.fail_urls:
            raise RuntimeError(f"reader_down_for:{url}")
        return {
            "content": self.by_url.get(
                url,
                (
                    "# San Jose Meeting Minutes\n"
                    "Agenda item 4.2 approved housing policy updates after hearing.\n"
                ),
            ),
            "title": "San Jose Meeting Minutes",
            "url": url,
        }


class _FakeCompletions:
    def __init__(self, *, fail: str | None = None) -> None:
        self.fail = fail

    async def create(self, **kwargs: Any) -> Any:
        _ = kwargs
        if self.fail:
            raise RuntimeError(self.fail)
        content = '{"summary":"ok","key_points":["Housing item approved"],"sufficiency_state":"sufficient"}'
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
        )


class FakeLLMClient:
    def __init__(self, *, fail: str | None = None) -> None:
        self.chat = SimpleNamespace(completions=_FakeCompletions(fail=fail))


class FakeEmbeddingService:
    async def embed_documents(self, chunks: list[str]) -> list[list[float]]:
        return [[0.1] * 4096 for _ in chunks]


def _request(
    stale_status: str = "fresh",
    idempotency_key: str = "wm:run-scope:runtime",
    jurisdiction: str = "san-jose-ca",
    source_family: str = "meeting_minutes",
) -> RunScopeRequest:
    return RunScopeRequest(
        contract_version="2026-04-13.windmill-domain.v1",
        idempotency_key=idempotency_key,
        jurisdiction=jurisdiction,
        source_family=source_family,
        stale_status=stale_status,
        windmill_workspace="affordabot",
        windmill_flow_path="f/affordabot/pipeline_daily_refresh_domain_boundary__flow",
        windmill_run_id="wm-run-1",
        windmill_job_id="wm-job-1",
        search_query="San Jose housing meeting minutes",
        analysis_question="What housing decisions were made?",
    )


def test_runtime_bridge_writes_sql_storage_and_chunks() -> None:
    db = FakeDB()
    storage = FakeStorage()
    runtime = RailwayRuntimeBridge(db=db, storage=storage)  # type: ignore[arg-type]
    runtime.search_client = FakeSearchClient(
        [{"url": "https://www.sanjoseca.gov/agenda/1", "title": "SJ Agenda", "snippet": "Housing"}]
    )
    runtime.reader_client = FakeReaderClient()
    runtime._llm_client = FakeLLMClient()
    runtime.embedding_service = FakeEmbeddingService()
    runtime.zai_api_key = "x"

    response = asyncio.run(runtime.run_scope_pipeline(_request()))

    assert response["storage_mode"] == "railway_runtime"
    assert response["missing_runtime_adapters"] == []
    assert response["steps"]["index"]["counts"]["chunks"] > 0
    assert response["steps"]["index"]["details"]["embedding_count"] == response["steps"]["index"]["counts"]["chunks"]
    assert len(storage.upload_calls) == 1
    assert len(db.snapshots) == 1
    assert all(chunk["embedding"] for chunk in db.chunks.values())
    assert any("INSERT INTO content_artifacts" in query for query in db.exec_queries)
    assert any("INSERT INTO document_chunks" in query for query in db.exec_queries)


def test_runtime_bridge_accepts_jsonb_values_returned_as_strings() -> None:
    db = JsonStringFakeDB()
    storage = FakeStorage()
    runtime = RailwayRuntimeBridge(db=db, storage=storage)  # type: ignore[arg-type]
    runtime.search_client = FakeSearchClient(
        [{"url": "https://www.sanjoseca.gov/agenda/1", "title": "SJ Agenda", "snippet": "Housing"}]
    )
    runtime.reader_client = FakeReaderClient()
    runtime._llm_client = FakeLLMClient()
    runtime.zai_api_key = "x"

    response = asyncio.run(runtime.run_scope_pipeline(_request()))
    rerun = asyncio.run(runtime.run_scope_pipeline(_request()))

    assert response["steps"]["read_fetch"]["status"] == "succeeded"
    assert response["steps"]["index"]["counts"]["chunks"] > 0
    assert rerun["steps"]["search_materialize"]["details"]["idempotent_reuse"] is True


def test_runtime_bridge_rerun_reuses_idempotent_rows_without_duplicate_blob() -> None:
    db = FakeDB()
    storage = FakeStorage()
    runtime = RailwayRuntimeBridge(db=db, storage=storage)  # type: ignore[arg-type]
    runtime.search_client = FakeSearchClient(
        [{"url": "https://www.sanjoseca.gov/agenda/1", "title": "SJ Agenda", "snippet": "Housing"}]
    )
    runtime.reader_client = FakeReaderClient()
    runtime._llm_client = FakeLLMClient()
    runtime.zai_api_key = "x"

    first = asyncio.run(runtime.run_scope_pipeline(_request()))
    second = asyncio.run(runtime.run_scope_pipeline(_request()))

    assert first["status"] in {"succeeded", "succeeded_with_alerts"}
    assert second["steps"]["search_materialize"]["details"]["idempotent_reuse"] is True
    assert second["steps"]["index"]["details"]["idempotent_reuse"] is True
    assert len(storage.upload_calls) == 1


def test_runtime_bridge_idempotency_is_scoped_to_jurisdiction_and_source_family() -> None:
    db = FakeDB()
    storage = FakeStorage()
    runtime = RailwayRuntimeBridge(db=db, storage=storage)  # type: ignore[arg-type]
    runtime.search_client = FakeSearchClient(
        [{"url": "https://www.sanjoseca.gov/agenda/1", "title": "SJ Agenda", "snippet": "Housing"}]
    )
    runtime.reader_client = FakeReaderClient()
    runtime._llm_client = FakeLLMClient()
    runtime.zai_api_key = "x"

    san_jose = asyncio.run(runtime.run_scope_pipeline(_request(idempotency_key="wm:fanout")))
    santa_clara = asyncio.run(
        runtime.run_scope_pipeline(
            _request(idempotency_key="wm:fanout", jurisdiction="santa-clara-county-ca")
        )
    )

    assert san_jose["scope_idempotency_key"] != santa_clara["scope_idempotency_key"]
    assert santa_clara["steps"]["search_materialize"]["details"].get("idempotent_reuse") is not True
    assert len(db.snapshots) == 2
    assert len(storage.upload_calls) == 2


def test_runtime_bridge_stale_paths() -> None:
    db = FakeDB()
    storage = FakeStorage()
    runtime = RailwayRuntimeBridge(db=db, storage=storage)  # type: ignore[arg-type]
    runtime.search_client = FakeSearchClient(
        [{"url": "https://www.sanjoseca.gov/agenda/1", "title": "SJ Agenda", "snippet": "Housing"}]
    )
    runtime.reader_client = FakeReaderClient()
    runtime._llm_client = FakeLLMClient()
    runtime.zai_api_key = "x"

    usable = asyncio.run(
        runtime.run_scope_pipeline(
            _request(stale_status="stale_but_usable", idempotency_key="wm:run-scope:stale-usable")
        )
    )
    blocked = asyncio.run(
        runtime.run_scope_pipeline(
            _request(stale_status="stale_blocked", idempotency_key="wm:run-scope:stale-blocked")
        )
    )

    assert usable["steps"]["freshness_gate"]["status"] == "succeeded_with_alerts"
    assert blocked["steps"]["freshness_gate"]["status"] == "blocked"
    assert "read_fetch" not in blocked["steps"]


def test_runtime_bridge_blocks_navigation_heavy_reader_output_before_persistence() -> None:
    db = FakeDB()
    storage = FakeStorage()
    runtime = RailwayRuntimeBridge(db=db, storage=storage)  # type: ignore[arg-type]
    runtime.search_client = FakeSearchClient(
        [{"url": "https://www.sanjoseca.gov/agenda/1", "title": "SJ Agenda", "snippet": "Housing"}]
    )
    runtime.reader_client = FakeReaderClient(
        content="\n".join(
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
    runtime._llm_client = FakeLLMClient()
    runtime.zai_api_key = "x"

    response = asyncio.run(runtime.run_scope_pipeline(_request(idempotency_key="wm:run-scope:nav-block")))

    assert response["status"] == "blocked"
    assert response["steps"]["read_fetch"]["status"] == "blocked"
    assert response["steps"]["read_fetch"]["decision_reason"] == "reader_output_insufficient_substance"
    assert "reader_output_insufficient_substance:navigation_heavy" in response["alerts"]
    assert response["steps"]["read_fetch"]["details"]["reader_quality_failures"][0]["reason"] == "navigation_heavy"
    assert "index" not in response["steps"]
    assert "analyze" not in response["steps"]
    assert db.raw_scrapes == {}
    assert storage.upload_calls == []


def test_runtime_bridge_blocks_navigation_heavy_cached_reader_output_reuse() -> None:
    db = FakeDB()
    storage = FakeStorage()
    runtime = RailwayRuntimeBridge(db=db, storage=storage)  # type: ignore[arg-type]
    runtime.search_client = FakeSearchClient(
        [{"url": "https://www.sanjoseca.gov/agenda/1", "title": "SJ Agenda", "snippet": "Housing"}]
    )
    runtime.reader_client = FakeReaderClient()
    runtime._llm_client = FakeLLMClient()
    runtime.zai_api_key = "x"

    first = asyncio.run(runtime.run_scope_pipeline(_request(idempotency_key="wm:run-scope:cached-nav")))
    raw_scrape_id = str(first["steps"]["read_fetch"]["refs"]["raw_scrape_ids"][0])
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
    db.raw_scrapes[raw_scrape_id]["data"] = {"content": nav_shell_markdown}

    second = asyncio.run(runtime.run_scope_pipeline(_request(idempotency_key="wm:run-scope:cached-nav")))

    assert first["status"] in {"succeeded", "succeeded_with_alerts"}
    assert second["status"] == "blocked"
    assert second["steps"]["read_fetch"]["status"] == "blocked"
    assert second["steps"]["read_fetch"]["decision_reason"] == "reader_output_insufficient_substance"
    assert second["steps"]["read_fetch"]["details"]["cached_reader_reuse_blocked"] is True
    assert second["steps"]["read_fetch"]["details"]["idempotent_reuse"] is True
    assert "reader_output_insufficient_substance:navigation_heavy" in second["alerts"]
    assert "index" not in second["steps"]
    assert "analyze" not in second["steps"]


def test_runtime_bridge_reader_and_llm_failures_classify() -> None:
    db = FakeDB()
    storage = FakeStorage()
    runtime = RailwayRuntimeBridge(db=db, storage=storage)  # type: ignore[arg-type]
    runtime.search_client = FakeSearchClient(
        [{"url": "https://www.sanjoseca.gov/agenda/1", "title": "SJ Agenda", "snippet": "Housing"}]
    )
    runtime.zai_api_key = "x"

    runtime.reader_client = FakeReaderClient(fail="reader_down")
    runtime._llm_client = FakeLLMClient()
    reader_fail = asyncio.run(runtime.run_scope_pipeline(_request(idempotency_key="wm:run-scope:reader-fail")))
    assert reader_fail["steps"]["read_fetch"]["decision_reason"] == "reader_provider_error"

    runtime.reader_client = FakeReaderClient()
    runtime._llm_client = FakeLLMClient(fail="analysis_down")
    llm_fail = asyncio.run(runtime.run_scope_pipeline(_request(idempotency_key="wm:run-scope:llm-fail")))
    assert llm_fail["steps"]["analyze"]["decision_reason"] == "analysis_failed"


def test_runtime_bridge_read_fetch_falls_back_after_ranked_reader_error() -> None:
    db = FakeDB()
    storage = FakeStorage()
    runtime = RailwayRuntimeBridge(db=db, storage=storage)  # type: ignore[arg-type]
    runtime.search_client = FakeSearchClient(
        [
            {
                "url": "https://www.sanjoseca.gov/home",
                "title": "City Home",
                "snippet": "services and resources",
            },
            {
                "url": "https://granicus.com/AgendaViewer.php?view_id=12",
                "title": "Agenda Viewer",
                "snippet": "city council agenda packet",
            },
            {
                "url": "https://sanjose.legistar.com/MeetingDetail.aspx?ID=123&GUID=abc",
                "title": "Meeting Detail",
                "snippet": "minutes and housing hearing",
            },
        ]
    )
    runtime.reader_client = RoutingFakeReaderClient(
        by_url={
            "https://www.sanjoseca.gov/home": "Home Contact Sitemap Menu Departments",
            "https://sanjose.legistar.com/MeetingDetail.aspx?ID=123&GUID=abc": (
                "# Meeting Minutes\nCouncil approved housing recommendations after hearing."
            )
        },
        fail_urls={"https://granicus.com/AgendaViewer.php?view_id=12"},
    )
    runtime._llm_client = FakeLLMClient()
    runtime.zai_api_key = "x"

    response = asyncio.run(runtime.run_scope_pipeline(_request(idempotency_key="wm:run-scope:fallback")))

    assert response["steps"]["read_fetch"]["status"] == "succeeded_with_alerts"
    assert response["steps"]["read_fetch"]["decision_reason"] == "raw_scrapes_materialized_with_reader_alerts"
    assert any(alert.startswith("reader_error:") for alert in response["alerts"])
    assert response["steps"]["read_fetch"]["details"]["candidate_audit"][0]["outcome"] == "reader_provider_error"
    assert response["steps"]["read_fetch"]["details"]["candidate_audit"][1]["outcome"] == "materialized_raw_scrape"
    assert response["steps"]["index"]["status"] in {"succeeded", "succeeded_with_alerts"}
    assert response["steps"]["analyze"]["status"] in {"succeeded", "succeeded_with_alerts"}


def test_runtime_bridge_blocks_when_all_ranked_candidates_are_navigation_shells() -> None:
    db = FakeDB()
    storage = FakeStorage()
    runtime = RailwayRuntimeBridge(db=db, storage=storage)  # type: ignore[arg-type]
    runtime.search_client = FakeSearchClient(
        [
            {"url": "https://www.sanjoseca.gov/home", "title": "Home", "snippet": "services"},
            {"url": "https://www.sanjoseca.gov/resources", "title": "Resources", "snippet": "library"},
            {"url": "https://www.sanjoseca.gov/departments", "title": "Departments", "snippet": "menu"},
        ]
    )
    runtime.reader_client = RoutingFakeReaderClient(
        by_url={
            "https://www.sanjoseca.gov/home": "Home Contact Sitemap Menu Departments",
            "https://www.sanjoseca.gov/resources": "Resources Navigation Menu Contact",
            "https://www.sanjoseca.gov/departments": "Departments Menu Home Accessibility",
        }
    )
    runtime._llm_client = FakeLLMClient()
    runtime.zai_api_key = "x"

    response = asyncio.run(runtime.run_scope_pipeline(_request(idempotency_key="wm:run-scope:all-nav")))

    assert response["steps"]["read_fetch"]["status"] == "blocked"
    assert response["steps"]["read_fetch"]["decision_reason"] == "reader_output_insufficient_substance"
    assert len(response["steps"]["read_fetch"]["details"]["reader_quality_failures"]) == 3
    assert "index" not in response["steps"]
    assert "analyze" not in response["steps"]
