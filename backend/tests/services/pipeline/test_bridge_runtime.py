from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any
import asyncio
import json

from services.pipeline.domain.bridge import RailwayRuntimeBridge, RunScopeRequest
from services.pipeline.policy_evidence_package_storage import InMemoryPolicyEvidencePackageStore
from services.pipeline.structured_source_enrichment import StructuredEnrichmentResult


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
            if len(args) > 1:
                rows = rows[: int(args[1])]
            return [
                _Row({"id": row["id"], "content": row["content"], "chunk_index": row["chunk_index"]})
                for row in rows
            ]
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


class FakeS3Client:
    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], bytes] = {}

    def put_object(
        self,
        bucket: str,
        object_name: str,
        data: Any,
        length: int,
        content_type: str = "application/octet-stream",
    ) -> None:
        _ = content_type
        payload = data.read(length)
        self.objects[(bucket, object_name)] = payload

    def stat_object(self, bucket: str, object_name: str) -> dict[str, Any]:
        if (bucket, object_name) not in self.objects:
            raise RuntimeError("not_found")
        return {"bucket": bucket, "object_name": object_name}


class FakeS3Storage(FakeStorage):
    def __init__(self, bucket: str = "affordabot-artifacts") -> None:
        super().__init__()
        self.bucket = bucket
        self.client = FakeS3Client()

    async def upload(
        self,
        path: str,
        content: bytes,
        content_type: str = "application/octet-stream",
    ) -> str:
        result = await super().upload(path, content, content_type)
        self.client.objects[(self.bucket, path)] = content
        return result


class FakeStructuredEnricher:
    def __init__(
        self,
        *,
        status: str = "integrated",
        candidates: list[dict[str, Any]] | None = None,
        alerts: list[str] | None = None,
        source_catalog: list[dict[str, Any]] | None = None,
    ) -> None:
        self.status = status
        self.candidates = list(candidates or [])
        self.alerts = list(alerts or [])
        self.source_catalog = list(source_catalog or [])

    async def enrich(
        self,
        *,
        jurisdiction: str,
        source_family: str,
        search_query: str,
        selected_url: str,
    ) -> StructuredEnrichmentResult:
        _ = (jurisdiction, source_family, search_query, selected_url)
        return StructuredEnrichmentResult(
            status=self.status,
            candidates=self.candidates,
            alerts=self.alerts,
            source_catalog=self.source_catalog,
        )


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
        self.fetch_calls: list[str] = []

    async def fetch_content(self, url: str, **kwargs: Any) -> dict[str, Any]:
        _ = kwargs
        self.fetch_calls.append(url)
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
    search_query: str = "San Jose housing meeting minutes",
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
        search_query=search_query,
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


def test_runtime_bridge_persists_policy_evidence_package_refs() -> None:
    db = FakeDB()
    storage = FakeStorage()
    package_store = InMemoryPolicyEvidencePackageStore()
    runtime = RailwayRuntimeBridge(
        db=db, storage=storage, package_store=package_store
    )  # type: ignore[arg-type]
    runtime.search_client = FakeSearchClient(
        [{"url": "https://www.sanjoseca.gov/agenda/1", "title": "SJ Agenda", "snippet": "Housing"}]
    )
    runtime.reader_client = FakeReaderClient()
    runtime._llm_client = FakeLLMClient()
    runtime.embedding_service = FakeEmbeddingService()
    runtime.zai_api_key = "x"

    first = asyncio.run(runtime.run_scope_pipeline(_request(idempotency_key="wm:run-scope:package")))
    second = asyncio.run(runtime.run_scope_pipeline(_request(idempotency_key="wm:run-scope:package")))

    refs = second["refs"]
    assert refs["backend_run_id"] == first["refs"]["backend_run_id"]
    assert refs["package_id"] == first["refs"]["package_id"]
    assert refs["storage_status"] in {"stored", "stored_reused"}
    assert refs["raw_scrape_id"]
    assert refs["document_id"]
    assert refs["selected_url"] == "https://www.sanjoseca.gov/agenda/1"
    assert refs["reader_artifact_uri"]
    assert refs["canonical_document_key"]
    assert refs["fail_closed_reasons"]
    assert len(package_store.by_idempotency) == 1
    persisted = next(iter(package_store.by_idempotency.values()))
    run_context = persisted.package_payload["run_context"]
    gate_projection = persisted.package_payload["gate_projection"]
    analyze_step = second["steps"]["analyze"]
    analysis_id = str(analyze_step["refs"]["analysis_id"])
    assert run_context["backend_run_id"] == refs["backend_run_id"]
    assert run_context["windmill_run_id"] == "wm-run-1"
    assert run_context["windmill_job_id"] == "wm-job-1"
    assert run_context["canonical_analysis_id"] == analysis_id
    assert run_context["canonical_pipeline_run_id"] == refs["backend_run_id"]
    assert run_context["canonical_pipeline_step_id"] == analysis_id
    assert run_context["canonical_breakdown_ref"] == f"analysis:{analysis_id}"
    assert gate_projection["canonical_pipeline_run_id"] == refs["backend_run_id"]
    assert gate_projection["canonical_pipeline_step_id"] == analysis_id
    assert gate_projection["canonical_breakdown_ref"] == f"analysis:{analysis_id}"


def test_runtime_bridge_materializes_structured_sources_when_enrichment_available() -> None:
    db = FakeDB()
    storage = FakeStorage()
    package_store = InMemoryPolicyEvidencePackageStore()
    structured_candidate = {
        "source_lane": "structured",
        "provider": "legistar_web_api",
        "source_family": "legistar_web_api",
        "access_method": "public_api_json",
        "jurisdiction": "san_jose_ca",
        "artifact_url": "https://webapi.legistar.com/v1/sanjose/Events/13001",
        "artifact_type": "meeting_metadata",
        "source_tier": "tier_b",
        "retrieved_at": "2026-04-16T00:00:00+00:00",
        "structured_policy_facts": [
            {"field": "event_id", "value": 13001.0, "unit": "count"},
            {"field": "event_item_count", "value": 16.0, "unit": "count"},
        ],
        "excerpt": "Structured event metadata for San Jose agenda cycle.",
    }
    runtime = RailwayRuntimeBridge(
        db=db,
        storage=storage,
        package_store=package_store,
        structured_enricher=FakeStructuredEnricher(
            status="integrated",
            candidates=[structured_candidate],
            alerts=["structured_enrichment_source_family_context:meeting_minutes"],
            source_catalog=[
                {
                    "source_family": "legistar_web_api",
                    "access_method": "public_api_json",
                    "jurisdiction_coverage": "san_jose_ca",
                }
            ],
        ),
    )  # type: ignore[arg-type]
    runtime.search_client = FakeSearchClient(
        [{"url": "https://www.sanjoseca.gov/agenda/1", "title": "SJ Agenda", "snippet": "Housing"}]
    )
    runtime.reader_client = FakeReaderClient()
    runtime._llm_client = FakeLLMClient()
    runtime.embedding_service = FakeEmbeddingService()
    runtime.zai_api_key = "x"

    response = asyncio.run(runtime.run_scope_pipeline(_request(idempotency_key="wm:run-scope:structured")))
    refs = response["refs"]
    persisted = next(iter(package_store.by_idempotency.values()))
    package_payload = persisted.package_payload
    run_context = package_payload["run_context"]

    assert refs["storage_status"] in {"stored", "stored_reused"}
    assert set(package_payload["source_lanes"]) == {"scraped", "structured"}
    assert package_payload["structured_sources"]
    assert package_payload["structured_sources"][0]["source_family"] == "legistar_web_api"
    assert run_context["structured_enrichment_status"] == "integrated"
    assert run_context["structured_sources"]
    assert run_context["structured_source_catalog"][0]["source_family"] == "legistar_web_api"


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


def test_runtime_bridge_analyze_ranks_late_policy_chunk_ahead_of_headers() -> None:
    db = FakeDB()
    storage = FakeStorage()
    runtime = RailwayRuntimeBridge(db=db, storage=storage)  # type: ignore[arg-type]
    runtime.search_client = FakeSearchClient(
        [{"url": "https://sanjose.legistar.com/gateway.aspx?ID=abc.pdf&M=F", "title": "SJ PDF", "snippet": "minutes"}]
    )
    early_lines = [f"Meeting logistics line {i}: call to order and roll call." for i in range(1, 181)]
    late_lines = [
        "Agenda Item 10.2: Ordinance No. 31303 was adopted and approved.",
        "Temporary multifamily housing incentive created with affordability compliance options.",
        "Mobilehome rent ordinance amendments and implementation timeline were approved by vote.",
    ]
    runtime.reader_client = FakeReaderClient(content="\n".join(early_lines + late_lines))
    runtime._llm_client = FakeLLMClient()
    runtime.zai_api_key = "x"

    response = asyncio.run(runtime.run_scope_pipeline(_request(idempotency_key="wm:run-scope:late-evidence")))
    selection = response["steps"]["analyze"]["details"]["evidence_selection"]

    assert response["steps"]["analyze"]["status"] in {"succeeded", "succeeded_with_alerts"}
    assert selection["candidate_chunk_count"] >= 180
    assert selection["selected_chunk_count"] > 0
    assert selection["selected_chunks"][0]["chunk_index"] >= 180
    assert any("housing" in chunk["snippet"].lower() for chunk in selection["selected_chunks"])


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
    analyze_step = llm_fail["steps"]["analyze"]
    assert analyze_step["status"] == "succeeded_with_alerts"
    assert analyze_step["decision_reason"] == "analysis_provider_unavailable"
    assert "analysis_provider_unavailable" in analyze_step["alerts"]
    assert "canonical_llm_narrative_not_proven" in analyze_step["alerts"]
    analysis_payload = analyze_step["details"]["analysis"]
    assert analysis_payload["sufficiency_state"] == "provider_unavailable"
    assert analysis_payload["canonical_llm_narrative_proven"] is False
    assert analysis_payload["analysis_not_proven"] is True
    assert analysis_payload["evidence_chunk_count"] > 0
    assert len(analysis_payload["evidence_refs"]) > 0
    assert llm_fail["steps"]["summarize_run"]["status"] == "succeeded_with_alerts"
    policy_package = llm_fail["steps"]["summarize_run"]["details"]["policy_evidence_package"]
    fail_closed_reasons = policy_package["refs"]["fail_closed_reasons"]
    assert "analyze:analysis_provider_unavailable" in fail_closed_reasons
    assert policy_package["storage_result"]["stored"] is True
    assert policy_package["storage_result"]["fail_closed"] is True
    projection = policy_package["package_payload"]["gate_projection"]
    assert projection["canonical_pipeline_run_id"] == ""
    assert projection["canonical_pipeline_step_id"] == ""
    assert projection["canonical_breakdown_ref"] == ""


def test_runtime_bridge_uses_minio_artifact_writer_probe_and_indirect_hint() -> None:
    db = FakeDB()
    storage = FakeS3Storage()
    package_store = InMemoryPolicyEvidencePackageStore()
    runtime = RailwayRuntimeBridge(
        db=db, storage=storage, package_store=package_store
    )  # type: ignore[arg-type]
    runtime.search_client = FakeSearchClient(
        [
            {
                "url": "https://records.sanjoseca.gov/View.ashx?M=F&ID=13000001",
                "title": "Affordable Housing Impact Fee",
                "snippet": "multifamily housing development impact fee update",
            }
        ]
    )
    runtime.reader_client = FakeReaderClient(
        content=(
            "# Agenda Packet\n"
            "Council discussed increasing multifamily development impact fees.\n"
        )
    )
    runtime._llm_client = FakeLLMClient()
    runtime.embedding_service = FakeEmbeddingService()
    runtime.zai_api_key = "x"

    response = asyncio.run(
        runtime.run_scope_pipeline(
            _request(
                idempotency_key="wm:run-scope:pass-through",
                source_family="agenda_packet",
                search_query="San Jose multifamily housing development impact fee increase",
            )
        )
    )

    policy_package = response["steps"]["summarize_run"]["details"]["policy_evidence_package"]
    storage_result = policy_package["storage_result"]
    refs = response["refs"]
    persisted = next(iter(package_store.by_idempotency.values()))
    run_context = persisted.package_payload["run_context"]

    assert storage_result["artifact_write_status"] == "succeeded"
    assert storage_result["artifact_readback_status"] == "proven"
    assert refs["package_artifact_uri"].startswith(
        "minio://affordabot-artifacts/policy-evidence/packages/"
    )
    assert refs["reader_artifact_uri"].startswith("minio://affordabot-artifacts/")
    minio_uris = {
        ref["uri"]
        for ref in persisted.package_payload["storage_refs"]
        if ref["storage_system"] == "minio"
    }
    assert refs["package_artifact_uri"] in minio_uris
    assert refs["reader_artifact_uri"] in minio_uris
    assert run_context["mechanism_family_hint"] == "fee_or_tax_pass_through"
    assert run_context["impact_mode_hint"] == "pass_through_incidence"
    assert run_context["secondary_research_needed"] is True
    assert "secondary_research_needed:pass_through_incidence_rate_missing" in refs["fail_closed_reasons"]


def test_runtime_bridge_maps_licensing_to_compliance_cost_hint() -> None:
    db = FakeDB()
    storage = FakeStorage()
    package_store = InMemoryPolicyEvidencePackageStore()
    runtime = RailwayRuntimeBridge(
        db=db, storage=storage, package_store=package_store
    )  # type: ignore[arg-type]
    runtime.search_client = FakeSearchClient(
        [
            {
                "url": "https://records.sanjoseca.gov/ordinance/barber-license-training",
                "title": "Barber License Training Requirement",
                "snippet": "new two year licensing and training requirement",
            }
        ]
    )
    runtime.reader_client = FakeReaderClient(
        content="# Ordinance\nLicensing and compliance training requirements were adopted."
    )
    runtime._llm_client = FakeLLMClient()
    runtime.embedding_service = FakeEmbeddingService()
    runtime.zai_api_key = "x"

    asyncio.run(
        runtime.run_scope_pipeline(
            _request(
                idempotency_key="wm:run-scope:compliance-hint",
                source_family="ordinance_text",
                jurisdiction="san-jose-ca",
            )
        )
    )
    persisted = next(iter(package_store.by_idempotency.values()))
    run_context = persisted.package_payload["run_context"]

    assert run_context["mechanism_family_hint"] == "compliance_cost"
    assert run_context["impact_mode_hint"] == "compliance_cost"
    assert run_context["secondary_research_needed"] is False


def test_runtime_bridge_read_fetch_falls_back_after_ranked_reader_error() -> None:
    db = FakeDB()
    storage = FakeStorage()
    runtime = RailwayRuntimeBridge(db=db, storage=storage)  # type: ignore[arg-type]
    runtime.search_client = FakeSearchClient(
        [
            {
                "url": "https://sanjose.legistar.com/MeetingDetail.aspx?ID=123&GUID=abc",
                "title": "Meeting Detail",
                "snippet": "minutes and housing hearing",
            },
            {
                "url": "https://granicus.com/AgendaViewer.php?view_id=12",
                "title": "City Council Agenda Viewer",
                "snippet": "meeting agenda council",
            },
        ]
    )
    runtime.reader_client = RoutingFakeReaderClient(
        by_url={
            "https://granicus.com/AgendaViewer.php?view_id=12": (
                "# Meeting Minutes\nCouncil approved housing recommendations after hearing."
            )
        },
        fail_urls={"https://sanjose.legistar.com/MeetingDetail.aspx?ID=123&GUID=abc"},
    )
    runtime._llm_client = FakeLLMClient()
    runtime.zai_api_key = "x"

    response = asyncio.run(runtime.run_scope_pipeline(_request(idempotency_key="wm:run-scope:fallback")))

    assert response["steps"]["read_fetch"]["status"] == "succeeded_with_alerts"
    assert response["steps"]["read_fetch"]["decision_reason"] == "raw_scrapes_materialized_with_reader_alerts"
    assert any(alert.startswith("reader_error:") for alert in response["alerts"])
    assert any(
        item["outcome"] == "reader_provider_error"
        for item in response["steps"]["read_fetch"]["details"]["candidate_audit"]
    )
    assert any(
        item["outcome"] == "materialized_raw_scrape"
        for item in response["steps"]["read_fetch"]["details"]["candidate_audit"]
    )
    assert response["steps"]["index"]["status"] in {"succeeded", "succeeded_with_alerts"}
    assert response["steps"]["analyze"]["status"] in {"succeeded", "succeeded_with_alerts"}


def test_runtime_bridge_blocks_weak_video_fallback_after_official_reader_error() -> None:
    db = FakeDB()
    storage = FakeStorage()
    runtime = RailwayRuntimeBridge(db=db, storage=storage)  # type: ignore[arg-type]
    runtime.search_client = FakeSearchClient(
        [
            {
                "url": "https://sanjose.legistar.com/MeetingDetail.aspx?ID=123&GUID=abc",
                "title": "Meeting Detail",
                "snippet": "minutes and housing hearing",
            },
            {
                "url": "https://www.youtube.com/watch?v=abc123",
                "title": "San Jose City Council Meeting Video Transcript",
                "snippet": "full transcript of meeting discussion",
            },
        ]
    )
    runtime.reader_client = RoutingFakeReaderClient(
        by_url={
            "https://www.youtube.com/watch?v=abc123": (
                "# Meeting Transcript\nCouncil discussed housing policy and ordinance updates."
            )
        },
        fail_urls={"https://sanjose.legistar.com/MeetingDetail.aspx?ID=123&GUID=abc"},
    )
    runtime._llm_client = FakeLLMClient()
    runtime.zai_api_key = "x"

    response = asyncio.run(runtime.run_scope_pipeline(_request(idempotency_key="wm:run-scope:video-blocked")))

    read_step = response["steps"]["read_fetch"]
    assert read_step["status"] == "failed_retryable"
    assert read_step["decision_reason"] == "reader_provider_error"
    assert read_step["retry_class"] == "provider_unavailable"
    assert any(alert.startswith("reader_error:") for alert in response["alerts"])
    assert "reader_fallback_blocked_after_official_reader_errors" in response["alerts"]
    assert any(
        item["outcome"] == "reader_provider_error"
        and item.get("candidate_is_official_artifact") is True
        for item in read_step["details"]["candidate_audit"]
    )
    assert any(
        item["outcome"] == "reader_fallback_blocked_after_official_reader_errors"
        and item["url"] == "https://www.youtube.com/watch?v=abc123"
        for item in read_step["details"]["candidate_audit"]
    )
    assert "index" not in response["steps"]
    assert "analyze" not in response["steps"]


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


def test_runtime_bridge_falls_through_agenda_header_logistics_to_legistar_pdf() -> None:
    db = FakeDB()
    storage = FakeStorage()
    runtime = RailwayRuntimeBridge(db=db, storage=storage)  # type: ignore[arg-type]
    runtime.search_client = FakeSearchClient(
        [
            {
                "url": "https://sanjose.granicus.com/AgendaViewer.php?clip_id=14442&view_id=60",
                "title": "City Council Meeting Amended Agenda",
                "snippet": "city council meeting agenda",
            },
            {
                "url": "https://sanjose.legistar.com/LegislationDetail.aspx?ID=31303",
                "title": "City Hall Resources",
                "snippet": "home departments and services",
            },
        ]
    )
    runtime.reader_client = RoutingFakeReaderClient(
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
    runtime._llm_client = FakeLLMClient()
    runtime.zai_api_key = "x"

    response = asyncio.run(runtime.run_scope_pipeline(_request(idempotency_key="wm:run-scope:header-fallback")))

    assert response["steps"]["read_fetch"]["status"] == "succeeded_with_alerts"
    assert response["steps"]["read_fetch"]["details"]["candidate_audit"][0]["reason"] == "agenda_header_logistics_only"
    assert response["steps"]["read_fetch"]["details"]["candidate_audit"][1]["outcome"] == "materialized_raw_scrape"
    assert response["steps"]["index"]["status"] in {"succeeded", "succeeded_with_alerts"}
    assert response["steps"]["analyze"]["status"] in {"succeeded", "succeeded_with_alerts"}


def test_runtime_bridge_prefetch_skips_portal_url_and_fetches_artifact_candidate() -> None:
    db = FakeDB()
    storage = FakeStorage()
    runtime = RailwayRuntimeBridge(db=db, storage=storage)  # type: ignore[arg-type]
    runtime.search_client = FakeSearchClient(
        [
            {
                "url": "https://www.sanjoseca.gov/your-government/agendas-minutes",
                "title": "Agendas & Minutes | City of San Jose",
                "snippet": "agenda archive and calendar",
            },
            {
                "url": "https://records.sanjoseca.gov/documents/12345",
                "title": "Home Resources Departments",
                "snippet": "services menu",
            },
        ]
    )
    runtime.reader_client = RoutingFakeReaderClient(
        by_url={
            "https://records.sanjoseca.gov/documents/12345": (
                "# Meeting Minutes\n"
                "Agenda item 4.2 housing affordability ordinance was adopted by vote.\n"
            )
        }
    )
    runtime._llm_client = FakeLLMClient()
    runtime.zai_api_key = "x"

    response = asyncio.run(runtime.run_scope_pipeline(_request(idempotency_key="wm:run-scope:prefetch-skip")))

    assert response["steps"]["read_fetch"]["status"] == "succeeded_with_alerts"
    assert runtime.reader_client.fetch_calls == [
        "https://records.sanjoseca.gov/documents/12345"
    ]
    assert any(
        item["outcome"] == "reader_prefetch_skipped_low_value_portal"
        for item in response["steps"]["read_fetch"]["details"]["candidate_audit"]
    )
    assert any(
        item["outcome"] == "materialized_raw_scrape"
        for item in response["steps"]["read_fetch"]["details"]["candidate_audit"]
    )
    assert "reader_prefetch_skipped_low_value_portal" in response["alerts"]


def test_runtime_bridge_blocks_when_all_candidates_are_agenda_header_logistics() -> None:
    db = FakeDB()
    storage = FakeStorage()
    runtime = RailwayRuntimeBridge(db=db, storage=storage)  # type: ignore[arg-type]
    runtime.search_client = FakeSearchClient(
        [
            {
                "url": "https://sanjose.granicus.com/AgendaViewer.php?clip_id=1&view_id=60",
                "title": "Amended Agenda",
                "snippet": "LOCATION: Council Chambers Interpretation is available",
            },
            {
                "url": "https://sanjose.granicus.com/AgendaViewer.php?clip_id=2&view_id=60",
                "title": "Special Meeting Agenda",
                "snippet": "webinar teleconference dial-in logistics",
            },
        ]
    )
    runtime.reader_client = RoutingFakeReaderClient(
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
    runtime._llm_client = FakeLLMClient()
    runtime.zai_api_key = "x"

    response = asyncio.run(runtime.run_scope_pipeline(_request(idempotency_key="wm:run-scope:all-header")))

    assert response["steps"]["read_fetch"]["status"] == "blocked"
    assert response["steps"]["read_fetch"]["decision_reason"] == "reader_output_insufficient_substance"
    assert all(
        item["reason"] == "agenda_header_logistics_only"
        for item in response["steps"]["read_fetch"]["details"]["reader_quality_failures"]
    )
    assert "index" not in response["steps"]
    assert "analyze" not in response["steps"]
