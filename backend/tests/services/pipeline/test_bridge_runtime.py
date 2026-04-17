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
            if "SELECT created_at, data" in query:
                return _Row(
                    {
                        "created_at": raw["created_at"],
                        "data": raw["data"],
                    }
                )
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
                "created_at": __import__("datetime").datetime.now(
                    __import__("datetime").timezone.utc
                ),
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
        self.last_call: dict[str, Any] | None = None

    async def enrich(
        self,
        *,
        jurisdiction: str,
        source_family: str,
        search_query: str,
        selected_url: str,
        selected_candidate_context: str = "",
    ) -> StructuredEnrichmentResult:
        self.last_call = {
            "jurisdiction": jurisdiction,
            "source_family": source_family,
            "search_query": search_query,
            "selected_url": selected_url,
            "selected_candidate_context": selected_candidate_context,
        }
        return StructuredEnrichmentResult(
            status=self.status,
            candidates=self.candidates,
            alerts=self.alerts,
            source_catalog=self.source_catalog,
        )


def test_runtime_bridge_builds_structured_candidate_context_from_ranked_candidates() -> None:
    context = RailwayRuntimeBridge._structured_candidate_context(
        search_query="san jose commercial linkage fee policy",
        selected_url="https://sanjose.legistar.com/View.ashx?M=F&ID=8758120",
        ranked_candidates=[
            {
                "url": "https://sanjose.legistar.com/View.ashx?M=F&ID=8758120",
                "title": "Council Policy Priority # 5: Commercial Linkage Impact Fee",
                "snippet": "Matter 20-969 on September 1, 2020",
            }
        ],
    )
    assert "commercial linkage fee policy" in context
    assert "Council Policy Priority # 5: Commercial Linkage Impact Fee" in context
    assert "Matter 20-969 on September 1, 2020" in context


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
    provider_label = "private_searxng"

    def __init__(self, results: list[dict[str, Any]]) -> None:
        self.results = results
        self.queries: list[str] = []

    async def search(self, query: str, count: int = 10) -> list[dict[str, Any]]:
        _ = count
        self.queries.append(query)
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
    source_quality = run_context["source_quality_metrics"]
    assert source_quality["top_n_window"] >= 1
    assert source_quality["selected_candidate"]["url"] == refs["selected_url"]
    assert source_quality["provider_results"]["private_searxng"]["candidates"]
    assert source_quality["portal_skip_count"] >= 0
    assert source_quality["official_reader_error_count"] >= 0
    assert source_quality["fallback_materialization_count"] >= 0
    assert source_quality["source_shape_drift"]["drift_detected"] is False
    assert run_context["search_provider_runtime"]["provider_source"] == "client_label"
    assert "authoritative_policy_text" in run_context["policy_lineage"]["lineage_presence"]
    assert isinstance(run_context["source_reconciliation"]["records"], list)
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
        "related_attachment_refs": [
            {
                "attachment_id": "201",
                "title": "Resolution No. 80069",
                "url": "https://sanjoseca.legistar.com/View.ashx?M=F&ID=8758120",
                "source_family": "resolution",
            },
            {
                "attachment_id": "202",
                "title": "Commercial Linkage Nexus Study",
                "url": "https://sanjoseca.legistar.com/View.ashx?M=F&ID=8758132",
                "source_family": "nexus_study",
            },
        ],
        "lineage_metadata": {"matter_id": "7526"},
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
    assert run_context["policy_lineage"]["lineage_presence"]["related_attachments"] is True
    assert len(run_context["policy_lineage"]["related_attachment_refs"]) >= 2
    assert "resolution" in run_context["policy_lineage"]["related_attachment_source_families"]


def test_runtime_bridge_extracts_primary_fee_facts_from_analysis_chunks() -> None:
    analyze = SimpleNamespace(
        details={
            "evidence_selection": {
                "selected_chunks": [
                    {
                        "snippet": (
                            "Office (<100,000 sq. ft.) $3.00 Retail (<100,000 sq. ft.) "
                            "$0 Hotel $5.00 Residential Care $ 18.706.00"
                        )
                    }
                ]
            },
            "analysis": {
                "key_points": [
                    "Industrial/Research and Development (>=100,000 sq. ft.) $3.00"
                ]
            },
        }
    )

    facts, alerts = RailwayRuntimeBridge._extract_primary_fee_facts_from_analysis(
        analyze=analyze,  # type: ignore[arg-type]
        selected_url="https://sanjose.legistar.com/View.ashx?M=F&ID=8758120",
    )

    resolved_values = {fact["value"] for fact in facts if isinstance(fact.get("value"), float)}
    assert resolved_values == {0.0, 3.0, 5.0}
    assert any(fact.get("raw_value") == "$3.00" for fact in facts)
    assert any(fact.get("raw_value") == "$18.706.00" for fact in facts)
    assert any(fact.get("denominator") == "per_square_foot" for fact in facts)
    assert any(fact.get("category") == "office" for fact in facts)
    assert any(
        fact.get("ambiguity_flag") is True and fact.get("ambiguity_reason") == "currency_format_anomaly"
        for fact in facts
    )
    assert all(fact["source_hierarchy_status"] == "bill_or_reg_text" for fact in facts)
    assert "primary_parameter_money_format_anomaly" in alerts


def test_runtime_bridge_extracts_primary_fee_rows_with_subarea_and_locator_quality() -> None:
    facts, alerts = RailwayRuntimeBridge._extract_primary_fee_facts_from_text_parts(
        text_parts=[
            (
                "Commercial Linkage Fee table. Downtown Office (<100,000 sq. ft.) $3.00 "
                "Rest of City Office (<100,000 sq. ft.) $2.50. "
                "Adopted December 8, 2025 and effective January 1, 2026."
            )
        ],
        selected_url="https://sanjose.legistar.com/View.ashx?M=F&ID=8758120",
        source_locator_prefix="reader_content",
    )

    assert alerts == []
    assert len(facts) == 2
    downtown = next(item for item in facts if item["subarea"] == "downtown")
    assert downtown["land_use"] == "office"
    assert downtown["threshold"] == "<100,000 sq. ft."
    assert downtown["locator_quality"] == "table_row_chunk_locator"
    assert downtown["table_locator"] == "commercial_linkage_fee_table"
    assert downtown["adoption_date"] is not None
    assert downtown["effective_date"] is not None
    assert downtown["final_status"] == "adopted"


def test_runtime_bridge_extracts_payment_timing_reduction_and_exemption_context() -> None:
    facts, alerts = RailwayRuntimeBridge._extract_primary_fee_facts_from_text_parts(
        text_parts=[
            (
                "Office (>=100,000 sq. ft.) $14.31 when paid in full prior to the Building Permit issuance, "
                "$17.89 when paid at Scheduling of Final Building Inspection. "
                "Warehouse (<=50,000 sq. ft.) No fee ($0). "
                "Industrial/Research and Development (>=100,000 sq. ft.) $3.58 - "
                "When paid in full prior to the Building Permit issuance, a 20% reduction in the payment will apply."
            )
        ],
        selected_url="https://www.sanjoseca.gov/your-government/departments-offices/housing/developers/commercial-linkage-fee",
        source_locator_prefix="reader_content",
    )

    assert alerts == []
    assert len(facts) == 4
    before_permit = next(item for item in facts if item.get("normalized_value") == 14.31)
    assert before_permit["payment_timing"] == "paid_before_building_permit_issuance"
    final_inspection = next(item for item in facts if item.get("normalized_value") == 17.89)
    assert final_inspection["payment_timing"] == "paid_at_final_building_inspection"
    reduced = next(item for item in facts if item.get("normalized_value") == 3.58)
    assert reduced["payment_reduction_percent"] == 20.0
    assert "20% reduction" in str(reduced.get("payment_reduction_context") or "")
    no_fee = next(item for item in facts if item.get("normalized_value") == 0.0)
    assert no_fee["exemption_context"] == "no_fee_for_threshold:<=50,000 sq. ft."


def test_runtime_bridge_normalized_economic_rows_preserve_distinct_locators() -> None:
    primary_facts = [
        {
            "field": "commercial_linkage_fee_rate_usd_per_sqft",
            "raw_value": "$3.00",
            "normalized_value": 3.0,
            "unit": "usd_per_square_foot",
            "denominator": "per_square_foot",
            "land_use": "office",
            "subarea": "downtown",
            "threshold": "<100,000 sq. ft.",
            "source_url": "https://sanjose.legistar.com/View.ashx?M=F&ID=8758120",
            "source_locator": "analysis_chunk:1",
            "locator_quality": "chunk_locator_only",
            "source_hierarchy_status": "bill_or_reg_text",
            "confidence": 0.80,
            "ambiguity_flag": False,
            "currency_sanity": "valid",
            "unit_sanity": "valid",
        },
        {
            "field": "commercial_linkage_fee_rate_usd_per_sqft",
            "raw_value": "$3.00",
            "normalized_value": 3.0,
            "unit": "usd_per_square_foot",
            "denominator": "per_square_foot",
            "land_use": "office",
            "subarea": "downtown",
            "threshold": "<100,000 sq. ft.",
            "source_url": "https://sanjose.legistar.com/View.ashx?M=F&ID=8758120",
            "source_locator": "reader_content:1:fee_table_row",
            "table_locator": "commercial_linkage_fee_table",
            "locator_quality": "table_row_chunk_locator",
            "source_hierarchy_status": "bill_or_reg_text",
            "confidence": 0.90,
            "ambiguity_flag": False,
            "currency_sanity": "valid",
            "unit_sanity": "valid",
        },
    ]
    rows = RailwayRuntimeBridge._build_normalized_economic_rows(
        canonical_document_key="v2|jurisdiction=san-jose-ca|family=policy_documents|doctype=fee_schedule|url=https://sanjose.legistar.com/View.ashx?M=F&ID=8758120",
        selected_url="https://sanjose.legistar.com/View.ashx?M=F&ID=8758120",
        primary_facts=primary_facts,
        structured_facts=[],
    )

    assert len(rows) == 2
    assert {row["source_locator"] for row in rows} == {
        "analysis_chunk:1",
        "reader_content:1:fee_table_row",
    }
    assert all(row["sanity_checks"]["arithmetic_eligible"] is True for row in rows)
    assert all(row["source_lane_classification"] == "primary_official" for row in rows)
    assert all(row["row_id"].startswith("econ-row-") for row in rows)


def test_runtime_bridge_prefers_categorized_ambiguous_fee_fact() -> None:
    merged = RailwayRuntimeBridge._merge_primary_fee_facts(
        [
            {
                "field": "commercial_linkage_fee_rate_usd_per_sqft",
                "raw_value": "$18.706.00",
                "normalized_value": None,
                "category": "residential_care",
                "source_url": "https://sanjose.legistar.com/View.ashx?M=F&ID=8758120",
                "ambiguity_flag": True,
            }
        ],
        [
            {
                "field": "commercial_linkage_fee_rate_usd_per_sqft",
                "raw_value": "$18.706.00",
                "normalized_value": None,
                "category": "unknown",
                "source_url": "https://sanjose.legistar.com/View.ashx?M=F&ID=8758120",
                "ambiguity_flag": True,
            }
        ],
    )

    assert len(merged) == 1
    assert merged[0]["category"] == "residential_care"


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


def test_runtime_bridge_search_timeout_is_typed() -> None:
    db = FakeDB()
    storage = FakeStorage()
    runtime = RailwayRuntimeBridge(db=db, storage=storage)  # type: ignore[arg-type]
    runtime.reader_client = FakeReaderClient()
    runtime._llm_client = FakeLLMClient()
    runtime.zai_api_key = "x"

    class TimeoutSearchClient:
        provider_label = "private_searxng"

        async def search(self, query: str, count: int = 10) -> list[dict[str, Any]]:
            _ = (query, count)
            raise RuntimeError("request timed out after 180 seconds")

    runtime.search_client = TimeoutSearchClient()
    response = asyncio.run(runtime.run_scope_pipeline(_request(idempotency_key="wm:run-scope:search-timeout")))

    assert response["steps"]["search_materialize"]["decision_reason"] == "search_provider_timeout"
    assert "search_provider_timeout" in response["steps"]["search_materialize"]["alerts"]


def test_runtime_bridge_reader_timeout_is_typed() -> None:
    db = FakeDB()
    storage = FakeStorage()
    runtime = RailwayRuntimeBridge(db=db, storage=storage)  # type: ignore[arg-type]
    runtime.search_client = FakeSearchClient(
        [{"url": "https://www.sanjoseca.gov/agenda/1", "title": "SJ Agenda", "snippet": "Housing"}]
    )
    runtime.reader_client = FakeReaderClient(fail="reader request timed out")
    runtime._llm_client = FakeLLMClient()
    runtime.zai_api_key = "x"

    response = asyncio.run(runtime.run_scope_pipeline(_request(idempotency_key="wm:run-scope:reader-timeout")))

    assert response["status"] == "failed_retryable"
    assert response["steps"]["read_fetch"]["decision_reason"] == "reader_provider_timeout"
    assert "reader_provider_timeout" in response["steps"]["read_fetch"]["alerts"]


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


def test_runtime_bridge_llm_timeout_is_typed() -> None:
    db = FakeDB()
    storage = FakeStorage()
    runtime = RailwayRuntimeBridge(db=db, storage=storage)  # type: ignore[arg-type]
    runtime.search_client = FakeSearchClient(
        [{"url": "https://www.sanjoseca.gov/agenda/1", "title": "SJ Agenda", "snippet": "Housing"}]
    )
    runtime.reader_client = FakeReaderClient()
    runtime._llm_client = FakeLLMClient(fail="analysis request timed out")
    runtime.zai_api_key = "x"

    response = asyncio.run(runtime.run_scope_pipeline(_request(idempotency_key="wm:run-scope:llm-timeout")))

    analyze_step = response["steps"]["analyze"]
    assert analyze_step["status"] == "succeeded_with_alerts"
    assert analyze_step["decision_reason"] == "analysis_provider_timeout"
    assert "analysis_provider_timeout" in analyze_step["alerts"]
    assert "analysis_fail_closed_provider_timeout" in analyze_step["alerts"]
    assert "read_fetch:raw_scrapes_materialized" not in response["refs"]["fail_closed_reasons"]
    assert "analyze:analysis_provider_timeout" in response["refs"]["fail_closed_reasons"]


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


def test_runtime_bridge_prefers_artifact_candidate_over_official_fee_page_when_both_are_substantive() -> None:
    db = FakeDB()
    storage = FakeStorage()
    package_store = InMemoryPolicyEvidencePackageStore()
    runtime = RailwayRuntimeBridge(
        db=db, storage=storage, package_store=package_store
    )  # type: ignore[arg-type]
    runtime.search_client = FakeSearchClient(
        [
            {
                "url": "https://sanjose.legistar.com/View.ashx?M=F&ID=8758120&GUID=6C299331-91E9-48ED-B7A5-43601D63FBF6",
                "title": "CLF Fee Schedule",
                "snippet": "Commercial Linkage Fee schedule attachment",
            },
            {
                "url": "https://www.sanjoseca.gov/your-government/departments-offices/housing/developers/commercial-linkage-fee",
                "title": "Commercial Linkage Fee | City of San Jose",
                "snippet": "Official CLF page and references",
            },
        ]
    )
    runtime.reader_client = RoutingFakeReaderClient(
        by_url={
            "https://sanjose.legistar.com/View.ashx?M=F&ID=8758120&GUID=6C299331-91E9-48ED-B7A5-43601D63FBF6": (
                "# Resolution No. 80069\n"
                "Commercial Linkage Fee schedule table.\n"
                "Office projects pay $14.31 per square foot when paid in full prior to building permit issuance.\n"
                "Office projects pay $17.89 per square foot when paid at final inspection.\n"
            ),
            "https://www.sanjoseca.gov/your-government/departments-offices/housing/developers/commercial-linkage-fee": (
                "# Commercial Linkage Fee\n"
                "Agenda item 4.2 was approved by vote after public hearing.\n"
                "Office and retail fee details were adopted by council resolution.\n"
                "Staff recommendation and implementation timeline were accepted.\n"
                "The program applies to qualifying non-residential development "
                "projects and supports affordable housing production. The page "
                "describes fee categories, payment timing, exemptions, annual "
                "adjustments, nexus study background, and implementation rules "
                "for applicants seeking building permits in San Jose.\n"
            )
        },
    )
    runtime._llm_client = FakeLLMClient()
    runtime.embedding_service = FakeEmbeddingService()
    runtime.zai_api_key = "x"

    response = asyncio.run(
        runtime.run_scope_pipeline(
            _request(
                idempotency_key="wm:run-scope:selected-official-page",
                source_family="agenda_packet",
                search_query="San Jose Commercial Linkage Fee schedule",
            )
        )
    )
    persisted = next(iter(package_store.by_idempotency.values()))
    source_quality = persisted.package_payload["run_context"]["source_quality_metrics"]

    assert response["status"] in {"succeeded", "succeeded_with_alerts"}
    assert source_quality["top_n_artifact_recall_count"] >= 1
    assert source_quality["selected_artifact_family"] == "artifact"
    assert source_quality["selected_candidate"]["artifact_grade"] is True
    assert source_quality["selected_candidate"]["official_domain"] is True
    assert source_quality["artifact_quality_gate_status"] == "pass"
    assert source_quality["artifact_quality_gate_reason"] == "artifact_candidate_passed_quality_gate"


def test_runtime_bridge_identity_gate_fails_wrong_jurisdiction_artifact_for_san_jose_clf() -> None:
    db = FakeDB()
    storage = FakeStorage()
    package_store = InMemoryPolicyEvidencePackageStore()
    runtime = RailwayRuntimeBridge(
        db=db, storage=storage, package_store=package_store
    )  # type: ignore[arg-type]
    runtime.search_client = FakeSearchClient(
        [
            {
                "url": "https://www.hcd.ca.gov/housing-elements/docs/los altos_5th_draft011415.pdf",
                "title": "Los Altos Housing Element Draft",
                "snippet": "Housing element artifact from Los Altos",
            },
        ]
    )
    runtime.reader_client = RoutingFakeReaderClient(
        by_url={
            "https://www.hcd.ca.gov/housing-elements/docs/los altos_5th_draft011415.pdf": (
                "# Housing Element Draft\n"
                "Los Altos 5th draft policy summary for development impact fees.\n"
                "Office projects pay $7.00 per square foot in this schedule.\n"
                "Retail projects pay $3.00 per square foot and hotel projects pay $5.00 per square foot.\n"
                "The document covers land use assumptions, program background, and implementation details.\n"
                "This text is intentionally substantive for reader gate coverage in identity regression tests.\n"
            )
        },
    )
    runtime._llm_client = FakeLLMClient()
    runtime.embedding_service = FakeEmbeddingService()
    runtime.zai_api_key = "x"

    response = asyncio.run(
        runtime.run_scope_pipeline(
            _request(
                idempotency_key="wm:run-scope:identity-fail-los-altos",
                jurisdiction="San Jose CA",
                source_family="meeting_minutes",
                search_query="San Jose Commercial Linkage Fee Matter 7526 fee schedule",
            )
        )
    )
    persisted = next(iter(package_store.by_idempotency.values()))
    source_quality = persisted.package_payload["run_context"]["source_quality_metrics"]

    assert response["status"] in {"succeeded", "succeeded_with_alerts"}
    assert source_quality["selected_candidate"]["url"].startswith("https://www.hcd.ca.gov/")
    assert source_quality["jurisdiction_identity_status"] == "fail"
    assert source_quality["policy_identity_status"] == "fail"
    assert source_quality["identity_quality_status"] == "fail"
    assert source_quality["identity_quality_ready"] is False
    assert "jurisdiction_identity_mismatch" in source_quality["identity_failure_codes"]
    assert "policy_identity_mismatch" in source_quality["identity_failure_codes"]
    assert source_quality["identity_blocker_code"] == "jurisdiction_identity_mismatch"
    assert source_quality["selection_quality_status"] == "fail"


def test_runtime_bridge_identity_gate_passes_matching_san_jose_clf_source() -> None:
    db = FakeDB()
    storage = FakeStorage()
    package_store = InMemoryPolicyEvidencePackageStore()
    runtime = RailwayRuntimeBridge(
        db=db, storage=storage, package_store=package_store
    )  # type: ignore[arg-type]
    runtime.search_client = FakeSearchClient(
        [
            {
                "url": "https://www.sanjoseca.gov/your-government/departments-offices/housing/developers/commercial-linkage-fee",
                "title": "Commercial Linkage Fee | City of San Jose",
                "snippet": "Matter 7526 fee schedule and nexus study references",
            },
        ]
    )
    runtime.reader_client = RoutingFakeReaderClient(
        by_url={
            "https://www.sanjoseca.gov/your-government/departments-offices/housing/developers/commercial-linkage-fee": (
                "# Commercial Linkage Fee\n"
                "Updated January 2026 and effective March 1, 2026.\n"
                "Office projects pay $14.31 per square foot.\n"
                "Industrial projects pay $3.58 per square foot.\n"
                "Matter 7526 includes ordinance, resolution, and nexus study lineage.\n"
            )
        },
    )
    runtime._llm_client = FakeLLMClient()
    runtime.embedding_service = FakeEmbeddingService()
    runtime.zai_api_key = "x"

    response = asyncio.run(
        runtime.run_scope_pipeline(
            _request(
                idempotency_key="wm:run-scope:identity-pass-sanjose-clf",
                jurisdiction="San Jose CA",
                source_family="meeting_minutes",
                search_query="San Jose Commercial Linkage Fee Matter 7526 fee schedule",
            )
        )
    )
    persisted = next(iter(package_store.by_idempotency.values()))
    source_quality = persisted.package_payload["run_context"]["source_quality_metrics"]

    assert response["status"] in {"succeeded", "succeeded_with_alerts"}
    assert source_quality["selected_candidate"]["url"].startswith("https://www.sanjoseca.gov/")
    assert source_quality["jurisdiction_identity_status"] == "pass"
    assert source_quality["policy_identity_status"] == "pass"
    assert source_quality["identity_quality_status"] == "pass"
    assert source_quality["identity_quality_ready"] is True
    assert source_quality["identity_failure_codes"] == []
    assert source_quality["identity_blocker_code"] == ""
    assert source_quality["selection_quality_status"] == "pass"


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


def test_runtime_bridge_records_lineage_negative_evidence_and_reconciliation_policy() -> None:
    db = FakeDB()
    storage = FakeStorage()
    package_store = InMemoryPolicyEvidencePackageStore()
    runtime = RailwayRuntimeBridge(
        db=db,
        storage=storage,
        package_store=package_store,
        structured_enricher=FakeStructuredEnricher(
            status="integrated",
            candidates=[
                {
                    "source_lane": "structured_secondary_source",
                    "provider": "tavily_search",
                    "source_family": "tavily_secondary_search",
                    "access_method": "tavily_search_api",
                    "jurisdiction": "san_jose_ca",
                    "artifact_url": "https://www.sanjoseca.gov/Home/Components/News/News/1801",
                    "artifact_type": "secondary_search_rate_snippet",
                    "source_tier": "tier_c",
                    "retrieved_at": "2026-04-16T00:00:00+00:00",
                    "structured_policy_facts": [
                        {
                            "field": "commercial_linkage_fee_rate_usd_per_sqft",
                            "value": 3.58,
                            "source_url": "https://www.sanjoseca.gov/Home/Components/News/News/1801",
                            "source_excerpt": "Updated fee of $3.58 per square foot.",
                        }
                    ],
                }
            ],
        ),
    )  # type: ignore[arg-type]
    runtime.search_client = FakeSearchClient(
        [
            {
                "url": "https://sanjose.legistar.com/View.ashx?M=F&ID=8758120&GUID=6C299331-91E9-48ED-B7A5-43601D63FBF6",
                "title": "CLF Fee Schedule",
                "snippet": "Commercial Linkage Fee schedule attachment",
            }
        ]
    )
    runtime.reader_client = FakeReaderClient(
        content=(
            "# Fee Schedule\n"
            "Office uses a $3.00 per square foot commercial linkage fee.\n"
        )
    )
    runtime._llm_client = FakeLLMClient()
    runtime.embedding_service = FakeEmbeddingService()
    runtime.zai_api_key = "x"

    asyncio.run(runtime.run_scope_pipeline(_request(idempotency_key="wm:run-scope:lineage-reconcile")))
    persisted = next(iter(package_store.by_idempotency.values()))
    run_context = persisted.package_payload["run_context"]

    lineage = run_context["policy_lineage"]
    assert "authoritative_policy_text" in lineage["lineage_presence"]
    assert isinstance(lineage["negative_evidence"], list)
    assert len(lineage["negative_evidence"]) >= 1

    reconciliation = run_context["source_reconciliation"]
    assert reconciliation["source_of_truth_policy"] == "primary_artifact_precedence_then_labeled_secondary"
    assert reconciliation["secondary_override_blocked"] is True
    assert reconciliation["records"]
    assert all(
        record.get("source_of_truth") != "secondary_search_derived"
        for record in reconciliation["records"]
    )


def test_runtime_bridge_reconciliation_marks_secondary_only_as_missing_true_structured() -> None:
    reconciliation = RailwayRuntimeBridge._reconcile_parameter_sources(
        primary_facts=[
            {
                "field": "commercial_linkage_fee_rate_usd_per_sqft",
                "land_use": "office",
                "subarea": "downtown",
                "threshold": "<100,000 sq. ft.",
                "normalized_value": 3.0,
                "source_url": "https://sanjose.legistar.com/View.ashx?M=F&ID=8758120",
                "source_locator": "reader_content:1:fee_table_row",
            }
        ],
        secondary_facts=[
            {
                "field": "commercial_linkage_fee_rate_usd_per_sqft",
                "land_use": "office",
                "subarea": "downtown",
                "threshold": "<100,000 sq. ft.",
                "normalized_value": 3.58,
                "source_family": "tavily_secondary_search",
                "source_lane_classification": "secondary_search_derived",
                "source_url": "https://www.sanjoseca.gov/fees",
            }
        ],
    )

    assert reconciliation["missing_true_structured_corroboration_count"] == 1
    assert reconciliation["true_structured_row_count"] == 0
    assert reconciliation["official_attachment_row_count"] == 0
    assert reconciliation["official_attachment_authoritative_row_count"] == 0
    assert reconciliation["secondary_override_blocked"] is True
    assert reconciliation["records"][0]["status"] == "missing_structured_corroboration"
    assert "primary_official_row_missing_true_structured_corroboration" in reconciliation["records"][0]["decision_reason"]
    assert reconciliation["records"][0]["fail_closed_signals"]


def test_runtime_bridge_attachment_probe_rows_become_authoritative_and_emit_normalized_rows() -> None:
    structured_candidates = [
        {
            "source_lane": "structured",
            "provider": "legistar_web_api",
            "source_family": "legistar_web_api",
            "true_structured": True,
            "artifact_url": "https://webapi.legistar.com/v1/sanjose/Matters/7526",
            "policy_match_key": "legistar::matter::7526",
            "reconciliation_status": "pending_primary_reconciliation",
            "lineage_metadata": {"matter_id": "7526"},
            "structured_policy_facts": [
                {"field": "matter_attachment_count", "value": 2.0, "unit": "count"},
            ],
            "attachment_content_probes": [
                {
                    "attachment_id": "301",
                    "title": "Resolution No. 80069",
                    "url": "https://sanjoseca.legistar.com/View.ashx?M=F&ID=8758120",
                    "source_family": "resolution",
                    "status": "ingested_excerpt",
                    "content_ingested": True,
                    "economic_row_count": 2,
                    "excerpt": (
                        "Commercial Linkage Fee Schedule. "
                        "Downtown Office (>=100,000 sq. ft.) $14.31 when paid in full prior to the Building Permit issuance, "
                        "a 20% reduction applies. "
                        "Downtown Office (>=100,000 sq. ft.) $17.89 when paid at the scheduling of final building inspection. "
                        "Adopted December 8, 2025 and effective January 1, 2026."
                    ),
                }
            ],
        }
    ]

    structured_facts = RailwayRuntimeBridge._collect_secondary_numeric_facts(structured_candidates)
    assert len(structured_facts) >= 2
    assert all(fact["source_lane_classification"] == "true_structured_source" for fact in structured_facts)
    assert all(fact["source_family"] == "resolution" for fact in structured_facts)
    assert all(fact["attachment_id"] == "301" for fact in structured_facts)
    assert all(fact["attachment_title"] == "Resolution No. 80069" for fact in structured_facts)
    assert any(
        fact.get("payment_timing") == "paid_before_building_permit_issuance"
        for fact in structured_facts
    )
    assert any(fact.get("payment_reduction_context") for fact in structured_facts)

    normalized_rows = RailwayRuntimeBridge._build_normalized_economic_rows(
        canonical_document_key="legistar::matter::7526",
        selected_url="https://sanjoseca.legistar.com/View.ashx?M=F&ID=8758120",
        primary_facts=[],
        structured_facts=structured_facts,
    )
    assert len(normalized_rows) >= 2
    assert all(row["attachment_id"] == "301" for row in normalized_rows)
    assert all(row["attachment_title"] == "Resolution No. 80069" for row in normalized_rows)
    assert all(row["source_family"] == "resolution" for row in normalized_rows)
    required_fields = {
        "source_url",
        "source_ref",
        "source_family",
        "raw_value",
        "normalized_value",
        "unit",
        "land_use",
        "threshold",
        "payment_timing",
        "payment_reduction_context",
        "exemption_context",
        "effective_date",
        "adoption_date",
        "final_status",
        "source_locator",
        "locator_quality",
        "attachment_id",
        "attachment_title",
    }
    assert required_fields.issubset(set(normalized_rows[0].keys()))

    reconciliation = RailwayRuntimeBridge._reconcile_parameter_sources(
        primary_facts=[],
        secondary_facts=structured_facts,
    )
    assert reconciliation["true_structured_row_count"] >= 2
    assert reconciliation["official_attachment_row_count"] >= 2
    assert reconciliation["official_attachment_authoritative_row_count"] >= 2
    assert reconciliation["secondary_snippet_row_count"] == 0
    assert all(record["status"] == "authoritative_structured_attachment" for record in reconciliation["records"])
    assert all(record["source_of_truth"] == "true_structured_source" for record in reconciliation["records"])


def test_runtime_bridge_normalized_rows_do_not_collapse_distinct_locator_rows() -> None:
    structured_facts = [
        {
            "field": "commercial_linkage_fee_rate_usd_per_sqft",
            "normalized_value": 14.31,
            "raw_value": "$14.31",
            "value": 14.31,
            "source_family": "resolution",
            "source_url": "https://sanjoseca.legistar.com/View.ashx?M=F&ID=8758120",
            "source_ref": "legistar::matter::7526::attachment::301",
            "attachment_id": "301",
            "attachment_title": "Resolution No. 80069",
            "land_use": "office",
            "raw_land_use_label": "Downtown Office",
            "threshold": ">=100,000 sq. ft.",
            "payment_timing": "paid_before_building_permit_issuance",
            "source_locator": "attachment_probe:301:1:fee_table_row",
            "locator_quality": "table_row_chunk_locator",
            "unit": "usd_per_square_foot",
            "source_lane_classification": "true_structured_source",
        },
        {
            "field": "commercial_linkage_fee_rate_usd_per_sqft",
            "normalized_value": 14.31,
            "raw_value": "$14.31",
            "value": 14.31,
            "source_family": "resolution",
            "source_url": "https://sanjoseca.legistar.com/View.ashx?M=F&ID=8758120",
            "source_ref": "legistar::matter::7526::attachment::301",
            "attachment_id": "301",
            "attachment_title": "Resolution No. 80069",
            "land_use": "office",
            "raw_land_use_label": "Downtown Office",
            "threshold": ">=100,000 sq. ft.",
            "payment_timing": "paid_before_building_permit_issuance",
            "source_locator": "attachment_probe:301:2:fee_table_row",
            "locator_quality": "table_row_chunk_locator",
            "unit": "usd_per_square_foot",
            "source_lane_classification": "true_structured_source",
        },
    ]

    rows = RailwayRuntimeBridge._build_normalized_economic_rows(
        canonical_document_key="legistar::matter::7526",
        selected_url="https://sanjoseca.legistar.com/View.ashx?M=F&ID=8758120",
        primary_facts=[],
        structured_facts=structured_facts,
    )

    assert len(rows) == 2
    assert {row["source_locator"] for row in rows} == {
        "attachment_probe:301:1:fee_table_row",
        "attachment_probe:301:2:fee_table_row",
    }
    reconciliation = RailwayRuntimeBridge._reconcile_parameter_sources(
        primary_facts=[],
        secondary_facts=structured_facts,
    )
    assert reconciliation["true_structured_row_count"] == 2
    assert len(reconciliation["records"]) == 2


def test_runtime_bridge_structured_attachment_facts_with_required_fields_are_authoritative() -> None:
    structured_candidates = [
        {
            "source_lane": "structured",
            "provider": "legistar_web_api",
            "source_family": "legistar_web_api",
            "true_structured": True,
            "artifact_url": "https://webapi.legistar.com/v1/sanjose/Matters/7526",
            "policy_match_key": "legistar::matter::7526",
            "lineage_metadata": {"matter_id": "7526"},
            "structured_policy_facts": [
                {
                    "field": "commercial_linkage_fee_rate_usd_per_sqft",
                    "normalized_value": 10.0,
                    "unit": "usd_per_square_foot",
                    "land_use": "office",
                    "raw_land_use_label": "Downtown Office",
                    "threshold": ">=100,000 sq. ft.",
                    "source_url": "https://sanjoseca.legistar.com/View.ashx?M=F&ID=8758120",
                    "source_ref": "legistar::matter::7526::attachment::301",
                    "attachment_id": "301",
                    "attachment_title": "Resolution No. 80069",
                    "source_excerpt": "Downtown Office (>=100,000 sq. ft.) $10.00",
                    "source_locator": "attachment_probe:301:1:fee_table_row",
                    "locator_quality": "table_row_chunk_locator",
                    "table_locator": "commercial_linkage_fee_table",
                    "chunk_locator": "attachment_probe:301:1",
                },
                {
                    "field": "commercial_linkage_fee_rate_usd_per_sqft",
                    "normalized_value": 5.0,
                    "unit": "usd_per_square_foot",
                    "land_use": "hotel",
                    "raw_land_use_label": "Hotel",
                    "source_url": "https://sanjoseca.legistar.com/View.ashx?M=F&ID=8758120",
                    "source_ref": "legistar::matter::7526::attachment::301",
                    "attachment_id": "301",
                    "attachment_title": "Resolution No. 80069",
                    "source_excerpt": "Hotel $5.00",
                    "source_locator": "attachment_probe:301:2:fee_table_row",
                    "locator_quality": "table_row_chunk_locator",
                    "table_locator": "commercial_linkage_fee_table",
                    "chunk_locator": "attachment_probe:301:2",
                },
                {
                    "field": "commercial_linkage_fee_rate_usd_per_sqft",
                    "raw_value": "$ 18.706.00",
                    "unit": "usd_per_square_foot",
                    "land_use": "residential_care",
                    "raw_land_use_label": "Residential Care",
                    "source_url": "https://sanjoseca.legistar.com/View.ashx?M=F&ID=8758120",
                    "source_ref": "legistar::matter::7526::attachment::301",
                    "attachment_id": "301",
                    "attachment_title": "Resolution No. 80069",
                    "source_excerpt": "Residential Care $ 18.706.00",
                    "ambiguity_flag": True,
                    "ambiguity_reason": "currency_format_anomaly",
                    "source_locator": "attachment_probe:301:3:fee_table_row",
                    "locator_quality": "table_row_chunk_locator",
                    "table_locator": "commercial_linkage_fee_table",
                    "chunk_locator": "attachment_probe:301:3",
                },
            ],
        }
    ]

    structured_facts = RailwayRuntimeBridge._collect_secondary_numeric_facts(structured_candidates)
    assert len(structured_facts) >= 3
    assert all(fact["source_lane_classification"] == "true_structured_source" for fact in structured_facts)
    office_row = next(item for item in structured_facts if item.get("normalized_value") == 10.0)
    assert office_row["source_locator"] == "attachment_probe:301:1:fee_table_row"
    assert office_row["locator_quality"] == "table_row_chunk_locator"
    anomaly_row = next(
        item
        for item in structured_facts
        if item.get("ambiguity_reason") == "currency_format_anomaly"
    )
    assert anomaly_row["normalized_value"] is None
    assert anomaly_row["currency_sanity"] == "invalid"

    reconciliation = RailwayRuntimeBridge._reconcile_parameter_sources(
        primary_facts=[],
        secondary_facts=structured_facts,
    )
    assert reconciliation["official_attachment_row_count"] == 2
    assert reconciliation["official_attachment_authoritative_row_count"] == 2
    assert any(
        record["status"] == "authoritative_structured_attachment"
        for record in reconciliation["records"]
    )
    assert any(
        record["status"] == "conflict_unresolved"
        and record["secondary_value"] is None
        for record in reconciliation["records"]
    )


def test_runtime_bridge_tavily_attachment_like_rows_do_not_satisfy_official_attachment_depth() -> None:
    structured_facts = RailwayRuntimeBridge._collect_secondary_numeric_facts(
        [
            {
                "source_lane": "structured_secondary_source",
                "provider": "tavily_search",
                "source_family": "tavily_secondary_search",
                "access_method": "tavily_search_api",
                "true_structured": True,
                "structured_policy_facts": [
                    {
                        "field": "commercial_linkage_fee_rate_usd_per_sqft",
                        "normalized_value": 10.0,
                        "unit": "usd_per_square_foot",
                        "land_use": "office",
                        "threshold": ">=100,000 sq. ft.",
                        "source_url": "https://sanjoseca.legistar.com/View.ashx?M=F&ID=8758120",
                        "attachment_id": "301",
                        "attachment_title": "Resolution No. 80069",
                        "source_excerpt": "Downtown Office (>=100,000 sq. ft.) $10.00",
                        "source_locator": "attachment_probe:301:1:fee_table_row",
                        "chunk_locator": "attachment_probe:301:1",
                        "table_locator": "commercial_linkage_fee_table",
                        "locator_quality": "table_row_chunk_locator",
                    }
                ],
            }
        ]
    )
    assert len(structured_facts) == 1
    assert structured_facts[0]["source_lane_classification"] == "secondary_search_derived"

    reconciliation = RailwayRuntimeBridge._reconcile_parameter_sources(
        primary_facts=[],
        secondary_facts=structured_facts,
    )
    assert reconciliation["true_structured_row_count"] == 0
    assert reconciliation["secondary_snippet_row_count"] == 1
    assert reconciliation["official_attachment_row_count"] == 0
    assert reconciliation["official_attachment_authoritative_row_count"] == 0
    assert reconciliation["records"][0]["status"] == "secondary_only_not_authoritative"


def test_runtime_bridge_row_quality_gate_blocks_excerpt_only_attachment_rows_from_authoritative_depth() -> None:
    structured_facts = [
        {
            "field": "commercial_linkage_fee_rate_usd_per_sqft",
            "normalized_value": 6.0,
            "raw_value": "$6.00",
            "unit": "usd_per_square_foot",
            "denominator": "per_square_foot",
            "land_use": "office",
            "raw_land_use_label": "Downtown Office",
            "source_url": "https://sanjoseca.legistar.com/View.ashx?M=F&ID=8758120",
            "source_family": "resolution",
            "attachment_id": "301",
            "attachment_title": "Resolution No. 80069",
            "source_excerpt": "Downtown Office (>=100,000 sq. ft.) $6.00 per square foot.",
            "source_locator": "attachment_probe:301:1:fee_table_row",
            "chunk_locator": "attachment_probe:301:1",
            "table_locator": "commercial_linkage_fee_table",
            "locator_quality": "chunk_locator_only",
            "source_lane_classification": "true_structured_source",
        },
        {
            "field": "commercial_linkage_fee_rate_usd_per_sqft",
            "normalized_value": 600.0,
            "raw_value": "$600",
            "unit": "usd",
            "land_use": "unknown",
            "category": "unknown",
            "source_url": "https://sanjoseca.legistar.com/View.ashx?M=F&ID=8758121",
            "source_family": "memorandum",
            "attachment_id": "302",
            "attachment_title": "Memorandum",
            "source_excerpt": "Excerpt-only memorandum claim: $600",
            "source_locator": "attachment_probe:excerpt",
            "locator_quality": "attachment_probe_excerpt",
            "source_lane_classification": "true_structured_source",
        },
        {
            "field": "commercial_linkage_fee_rate_usd_per_sqft",
            "normalized_value": 52.3,
            "raw_value": "$52.30",
            "unit": "usd",
            "land_use": "unknown",
            "category": "unknown",
            "source_url": "https://sanjoseca.legistar.com/View.ashx?M=F&ID=8758122",
            "source_family": "memorandum",
            "attachment_id": "303",
            "attachment_title": "Memorandum",
            "source_excerpt": "Excerpt-only memorandum claim: $52.30",
            "source_locator": "attachment_probe:302:excerpt",
            "locator_quality": "attachment_probe_excerpt",
            "source_lane_classification": "true_structured_source",
        },
        {
            "field": "commercial_linkage_fee_rate_usd_per_sqft",
            "normalized_value": 14.31,
            "raw_value": "$14.31",
            "unit": "usd_per_square_foot",
            "land_use": "office",
            "raw_land_use_label": "Office",
            "source_url": "https://sanjoseca.legistar.com/View.ashx?M=F&ID=8758123",
            "source_family": "memorandum",
            "attachment_id": "304",
            "attachment_title": "Mayor/Jones/Diep/Davis/Foley Memo",
            "source_excerpt": "Office projects pay $14.31 per square foot.",
            "source_locator": "attachment_probe:line_segment",
            "locator_quality": "attachment_probe_line_rate",
            "source_lane_classification": "true_structured_source",
        },
        {
            "field": "commercial_linkage_fee_rate_usd_per_sqft",
            "normalized_value": 600.0,
            "raw_value": "$600",
            "unit": "usd_per_square_foot",
            "land_use": "residential_care",
            "raw_land_use_label": "Residential Care",
            "source_url": "https://sanjoseca.legistar.com/View.ashx?M=F&ID=8758124",
            "source_family": "memorandum",
            "attachment_id": "305",
            "attachment_title": "Supplemental Memo",
            "source_excerpt": "Cost of development assumes $600 per square foot.",
            "source_locator": "attachment_probe:line_segment",
            "locator_quality": "attachment_probe_line_rate",
            "source_lane_classification": "true_structured_source",
        },
    ]

    normalized_rows = RailwayRuntimeBridge._build_normalized_economic_rows(
        canonical_document_key="legistar::matter::7526",
        selected_url="https://sanjoseca.legistar.com/View.ashx?M=F&ID=8758120",
        primary_facts=[],
        structured_facts=structured_facts,
    )
    assert len(normalized_rows) == 5
    approved_rows = [row for row in normalized_rows if row.get("row_quality_approved")]
    rejected_rows = [row for row in normalized_rows if not row.get("row_quality_approved")]
    assert [row["normalized_value"] for row in approved_rows] == [6.0, 14.31]
    assert len(rejected_rows) == 3
    assert all(
        "row_quality_not_approved_for_economic_handoff" in (row.get("fail_closed_signals") or [])
        for row in rejected_rows
    )

    reconciliation = RailwayRuntimeBridge._reconcile_parameter_sources(
        primary_facts=[],
        secondary_facts=structured_facts,
    )
    assert reconciliation["true_structured_row_count"] == 5
    assert reconciliation["official_attachment_row_count"] == 2
    assert reconciliation["official_attachment_authoritative_row_count"] == 2
    statuses = {record["status"] for record in reconciliation["records"]}
    assert "authoritative_structured_attachment" in statuses
    assert "conflict_unresolved" in statuses


def test_runtime_bridge_reconciliation_keeps_distinct_primary_rows_by_value_timing_threshold_locator() -> None:
    reconciliation = RailwayRuntimeBridge._reconcile_parameter_sources(
        primary_facts=[
            {
                "field": "commercial_linkage_fee_rate_usd_per_sqft",
                "land_use": "office",
                "raw_land_use_label": "Office",
                "subarea": None,
                "threshold": ">=100,000 sq. ft.",
                "payment_timing": "paid_before_building_permit_issuance",
                "normalized_value": 14.31,
                "source_locator": "reader_content:1:row-1",
                "locator_quality": "chunk_locator_only",
                "source_url": "https://example.org/clf",
            },
            {
                "field": "commercial_linkage_fee_rate_usd_per_sqft",
                "land_use": "office",
                "raw_land_use_label": "Office",
                "subarea": None,
                "threshold": ">=100,000 sq. ft.",
                "payment_timing": "paid_at_final_building_inspection",
                "normalized_value": 17.89,
                "source_locator": "reader_content:1:row-2",
                "locator_quality": "chunk_locator_only",
                "source_url": "https://example.org/clf",
            },
            {
                "field": "commercial_linkage_fee_rate_usd_per_sqft",
                "land_use": "office",
                "raw_land_use_label": "Office",
                "subarea": None,
                "threshold": "<=50,000 sq. ft.",
                "exemption_context": "no_fee_for_threshold:<=50,000 sq. ft.",
                "normalized_value": 0.0,
                "source_locator": "reader_content:1:row-3",
                "locator_quality": "chunk_locator_only",
                "source_url": "https://example.org/clf",
            },
        ],
        secondary_facts=[
            {
                "field": "commercial_linkage_fee_rate_usd_per_sqft",
                "land_use": "office",
                "raw_land_use_label": "Office",
                "subarea": None,
                "threshold": ">=100,000 sq. ft.",
                "payment_timing": "paid_before_building_permit_issuance",
                "normalized_value": 14.31,
                "source_family": "tavily_secondary_search",
                "source_lane_classification": "secondary_search_derived",
                "source_url": "https://secondary.example.org",
            }
        ],
    )

    records = reconciliation["records"]
    primary_records = [item for item in records if item["source_of_truth"] == "primary_scraped_document"]
    assert len(primary_records) == 3
    assert {item["primary_value"] for item in primary_records} == {0.0, 14.31, 17.89}
    assert {item["payment_timing"] for item in primary_records} == {
        None,
        "paid_before_building_permit_issuance",
        "paid_at_final_building_inspection",
    }
    assert all(item["row_identity"] for item in primary_records)
    assert all(item["fail_closed_signals"] for item in primary_records)
    assert reconciliation["primary_official_row_count"] == 3
    assert reconciliation["true_structured_row_count"] == 0
    assert reconciliation["secondary_snippet_row_count"] == 1
    assert reconciliation["secondary_override_blocked"] is True


def test_runtime_bridge_build_policy_lineage_surfaces_matter_7526_attachment_refs() -> None:
    lineage = RailwayRuntimeBridge._build_policy_lineage(
        selected_url="https://sanjoseca.legistar.com/LegislationDetail.aspx?ID=7526",
        source_family="meeting_minutes",
        candidate_audit=[],
        structured_candidates=[
            {
                "source_family": "legistar_web_api",
                "lineage_metadata": {"matter_id": "7526"},
                "related_attachment_refs": [
                    {
                        "attachment_id": "201",
                        "title": "Resolution No. 80069",
                        "url": "https://sanjoseca.legistar.com/View.ashx?M=F&ID=8758120",
                        "source_family": "resolution",
                    },
                    {
                        "attachment_id": "202",
                        "title": "Commercial Linkage Nexus Study",
                        "url": "https://sanjoseca.legistar.com/View.ashx?M=F&ID=8758132",
                        "source_family": "nexus_study",
                    },
                ],
            }
        ],
    )

    assert lineage["lineage_presence"]["related_attachments"] is True
    assert len(lineage["related_attachment_refs"]) == 2
    assert {ref["source_family"] for ref in lineage["related_attachment_refs"]} == {
        "resolution",
        "nexus_study",
    }
    assert len(lineage["related_artifacts"]) == 2


def test_runtime_bridge_policy_lineage_distinguishes_attachment_refs_vs_ingested_content() -> None:
    lineage = RailwayRuntimeBridge._build_policy_lineage(
        selected_url="https://www.sanjoseca.gov/your-government/departments-offices/housing/developers/commercial-linkage-fee",
        source_family="meeting_minutes",
        candidate_audit=[
            {
                "url": "https://www.sanjoseca.gov/your-government/departments-offices/housing/developers/commercial-linkage-fee",
                "outcome": "materialized_raw_scrape",
                "fee_schedule_gate": {
                    "classified_as_maintained_fee_schedule": True,
                    "passed": True,
                    "authoritative_policy_text_ok": False,
                },
            }
        ],
        structured_candidates=[
            {
                "source_family": "legistar_web_api",
                "related_attachment_refs": [
                    {
                        "attachment_id": "301",
                        "title": "Resolution No. 80069",
                        "url": "https://sanjoseca.legistar.com/View.ashx?M=F&ID=8758120",
                        "source_family": "resolution",
                    }
                ],
                "attachment_content_probes": [
                    {
                        "attachment_id": "301",
                        "title": "Resolution No. 80069",
                        "url": "https://sanjoseca.legistar.com/View.ashx?M=F&ID=8758120",
                        "source_family": "resolution",
                        "status": "binary_pdf_unparsed",
                        "read_status": "binary_unparsed",
                        "failure_class": "binary_pdf_unparsed",
                        "content_ingested": False,
                        "economic_row_count": 0,
                        "content_hash": "hash-resolution",
                    },
                    {
                        "attachment_id": "302",
                        "title": "Commercial Linkage Memorandum",
                        "url": "https://example.org/memo.txt",
                        "source_family": "memorandum",
                        "status": "ingested_excerpt",
                        "read_status": "read_text",
                        "failure_class": None,
                        "content_ingested": True,
                        "economic_row_count": 2,
                        "excerpt": "Office fee is $14.31 per square foot.",
                        "content_hash": "hash-memo",
                    },
                ],
            }
        ],
    )

    assert lineage["selected_artifact_family"] == "maintained_fee_schedule"
    assert lineage["lineage_presence"]["related_attachments"] is True
    assert lineage["lineage_presence"]["attachment_content_ingested"] is True
    assert lineage["lineage_presence"]["attachment_economic_rows"] is True
    assert lineage["attachment_state"]["refs_present"] is True
    assert lineage["attachment_state"]["content_ingested"] is True
    assert lineage["attachment_state"]["economic_rows_available"] is True
    assert lineage["attachment_state"]["attachment_ref_count"] == 1
    assert lineage["attachment_state"]["attachment_probe_count"] == 2
    assert lineage["attachment_state"]["attachment_ingested_count"] == 1
    assert lineage["attachment_state"]["attachment_economic_row_count"] == 2
    probes = lineage["attachment_content_probes"]
    assert probes[0]["read_status"] in {"binary_unparsed", "read_text"}
    assert {probe["failure_class"] for probe in probes} == {"binary_pdf_unparsed", None}
    assert all("content_hash" in probe for probe in probes)


def test_runtime_bridge_identity_quality_accepts_legistar_view_attachment_from_matter_lineage() -> None:
    selected_url = "https://sanjoseca.legistar.com/View.ashx?M=F&ID=8758120"
    identity = RailwayRuntimeBridge._evaluate_identity_quality(
        jurisdiction="San Jose CA",
        search_query="San Jose Commercial Linkage Fee Matter 7526 fee schedule",
        selected_url=selected_url,
        selected_title="",
        selected_snippet="",
        structured_candidates=[
            {
                "source_family": "legistar_web_api",
                "artifact_url": "https://webapi.legistar.com/v1/sanjose/Matters/7526",
                "lineage_metadata": {
                    "matter_id": "7526",
                    "related_attachment_refs": [
                        {
                            "attachment_id": "301",
                            "title": "Resolution No. 80069",
                            "url": selected_url,
                            "source_family": "resolution",
                        }
                    ],
                },
                "related_attachment_refs": [
                    {
                        "attachment_id": "301",
                        "title": "Resolution No. 80069",
                        "url": selected_url,
                        "source_family": "resolution",
                    }
                ],
            }
        ],
    )

    assert identity["identity_quality_ready"] is True
    assert identity["explicit_lineage_linked"] is True
    assert identity["identity_failure_codes"] == []
    assert "lineage_ref_view_attachment_signal" in identity["policy_signal_hits"]


def test_runtime_bridge_reconciliation_ignores_structured_diagnostic_counts() -> None:
    facts = RailwayRuntimeBridge._collect_secondary_numeric_facts(
        [
            {
                "source_family": "legistar_web_api",
                "artifact_url": "https://sanjose.legistar.com/MeetingDetail.aspx?LEGID=7927",
                "structured_policy_facts": [
                    {"field": "event_attachment_hint_count", "value": 0.0, "unit": "count"},
                    {
                        "field": "commercial_linkage_fee_rate_usd_per_sqft",
                        "value": 3.0,
                        "unit": "usd_per_square_foot",
                    },
                ],
            }
        ]
    )

    assert [item["field"] for item in facts] == ["commercial_linkage_fee_rate_usd_per_sqft"]


def test_runtime_bridge_extracts_primary_fee_facts_from_reader_content() -> None:
    facts, alerts = RailwayRuntimeBridge._extract_primary_fee_facts_from_text_parts(
        text_parts=[
            (
                "The Commercial Linkage Fee is an impact fee. "
                "Industrial/Research and Development projects pay $3.58 per square foot "
                "when paid in full before building permit issuance."
            )
        ],
        selected_url="https://www.sanjoseca.gov/your-government/departments-offices/housing/developers/commercial-linkage-fee",
        source_locator_prefix="reader_content",
    )

    assert alerts == []
    assert len(facts) == 1
    assert facts[0]["normalized_value"] == 3.58
    assert facts[0]["source_locator"] == "reader_content:1"
    assert facts[0]["provenance_lane"] == "primary_scraped_document"


def test_runtime_bridge_ignores_reader_content_dollars_without_unit_context() -> None:
    facts, alerts = RailwayRuntimeBridge._extract_primary_fee_facts_from_text_parts(
        text_parts=[
            (
                "The Commercial Linkage Fee page says the Council voted on September 1, 2020. "
                "The program could generate $1 million annually. "
                "Industrial projects pay $3.58 per square foot."
            )
        ],
        selected_url="https://www.sanjoseca.gov/your-government/departments-offices/housing/developers/commercial-linkage-fee",
        source_locator_prefix="reader_content",
    )

    assert alerts == []
    assert [fact["normalized_value"] for fact in facts] == [3.58]


def test_runtime_bridge_detects_source_shape_drift() -> None:
    drift = RailwayRuntimeBridge._detect_source_shape_drift(
        [
            {"title": "No URL Candidate", "snippet": "candidate missing URL"},
            {"url": "https://example.gov/1", "title": "No Snippet"},
        ]
    )

    assert drift["drift_detected"] is True
    assert drift["missing_url_count"] == 1
    assert drift["missing_snippet_count"] == 1
    assert drift["candidate_count"] == 2


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
