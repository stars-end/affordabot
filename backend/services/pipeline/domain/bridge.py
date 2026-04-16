"""Backend-owned command bridge for Windmill run_scope_pipeline calls."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
from io import BytesIO
from threading import Lock
from typing import Any
from urllib.parse import urlsplit
import uuid

from openai import AsyncOpenAI

from db.postgres_client import PostgresDB
from services.llm.web_search_factory import create_web_search_client
from services.pipeline.domain.commands import (
    PipelineDomainCommands,
    _is_concrete_artifact_url,
    _is_weak_reader_fallback_candidate,
    assess_reader_substance,
    prefetch_skip_reason,
    rank_evidence_chunks,
    rank_reader_candidates,
)
from services.pipeline.domain.constants import CONTRACT_VERSION
from services.pipeline.domain.identity import build_v2_canonical_document_key
from services.pipeline.domain.in_memory import (
    InMemoryAnalyzer,
    InMemoryArtifactStore,
    InMemoryDomainState,
    InMemoryReaderProvider,
    InMemorySearchProvider,
    InMemoryVectorStore,
)
from services.pipeline.domain.models import (
    CommandEnvelope,
    CommandResponse,
    FreshnessPolicy,
    WindmillMetadata,
)
from services.pipeline.domain.ports import SearchResultItem
from services.pipeline.domain.storage import (
    build_artifact_object_key,
    chunk_markdown_lines,
    sha256_text,
)
from services.pipeline.policy_evidence_package_builder import PolicyEvidencePackageBuilder
from services.pipeline.policy_evidence_package_storage import (
    ArtifactProbe,
    ArtifactWriter,
    InMemoryPolicyEvidencePackageStore,
    PolicyEvidencePackageStorageService,
    PolicyEvidencePackageStore,
    PostgresPolicyEvidencePackageStore,
)
from services.pipeline.structured_source_enrichment import (
    StructuredEnrichmentResult,
    StructuredSourceEnricher,
)
from services.storage import S3Storage
from schemas.analysis import ImpactMode
from schemas.economic_evidence import MechanismFamily

EMBEDDING_DIMENSIONS = 4096

ALLOWED_STALE_STATUSES = {
    "fresh",
    "stale_but_usable",
    "stale_blocked",
    "empty_but_usable",
    "empty_blocked",
}

STEP_NUMBER_BY_COMMAND = {
    "search_materialize": 1,
    "freshness_gate": 2,
    "read_fetch": 3,
    "index": 4,
    "analyze": 5,
    "summarize_run": 6,
}

READ_FETCH_MAX_CANDIDATES = 5
ANALYZE_CANDIDATE_CHUNK_LIMIT = 250
ANALYZE_SELECTED_CHUNK_LIMIT = 20


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True)


def _db_json(value: Any, fallback: Any) -> Any:
    if value is None:
        return fallback
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return fallback
    return value


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _stable_uuid(*parts: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "|".join(parts)))


def _scope_idempotency_key(request: "RunScopeRequest") -> str:
    """Scope fanout idempotency to the product identity boundary.

    Windmill supplies a flow-level idempotency key. The backend persists command
    results per jurisdiction/source-family scope so one flow fanout cannot
    accidentally reuse another scope's search, reader, index, or analysis row.
    """
    scope = f"{request.jurisdiction.strip().lower()}::{request.source_family.strip().lower()}"
    return f"{request.idempotency_key}::{_hash(scope)[:16]}"


@dataclass(frozen=True)
class _EconomicMechanismHint:
    mechanism_family: str | None
    impact_mode: str
    secondary_research_needed: bool
    secondary_research_reason: str | None = None


class _NoopStructuredSourceEnricher:
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
            status="not_configured",
            candidates=[],
            alerts=["structured_enrichment_not_configured"],
            source_catalog=[],
        )


class _S3PolicyEvidenceArtifactWriter(ArtifactWriter):
    def __init__(self, *, storage: S3Storage) -> None:
        self._storage = storage

    def write_package_artifact(self, *, package_id: str, payload: dict[str, Any]) -> str:
        client = getattr(self._storage, "client", None)
        bucket = str(getattr(self._storage, "bucket", "") or "").strip()
        if client is None or not bucket:
            raise RuntimeError("artifact_write_failed")
        object_key = f"policy-evidence/packages/{package_id}.json"
        body = json.dumps(payload, ensure_ascii=True, sort_keys=True).encode("utf-8")
        try:
            client.put_object(
                bucket,
                object_key,
                BytesIO(body),
                length=len(body),
                content_type="application/json",
            )
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError("artifact_write_failed") from exc
        return f"minio://{bucket}/{object_key}"


class _S3PolicyEvidenceArtifactProbe(ArtifactProbe):
    def __init__(self, *, storage: S3Storage) -> None:
        self._storage = storage

    def exists(self, *, uri: str) -> bool:
        parsed = RailwayRuntimeBridge._parse_minio_uri(uri)
        if parsed is None:
            return False
        bucket, object_key = parsed
        client = getattr(self._storage, "client", None)
        if client is None:
            return False
        try:
            client.stat_object(bucket, object_key)
            return True
        except Exception:  # noqa: BLE001
            return False


@dataclass(frozen=True)
class RunScopeRequest:
    contract_version: str
    idempotency_key: str
    jurisdiction: str
    source_family: str
    stale_status: str
    windmill_workspace: str
    windmill_flow_path: str
    windmill_run_id: str
    windmill_job_id: str
    search_query: str
    analysis_question: str


class RailwayRuntimeBridge:
    """Railway-compatible runtime for persisted bridge execution."""

    def __init__(
        self,
        *,
        db: PostgresDB,
        storage: S3Storage,
        package_store: PolicyEvidencePackageStore | None = None,
        structured_enricher: StructuredSourceEnricher | None = None,
    ) -> None:
        self.db = db
        self.storage = storage
        self._package_store_override = package_store
        if structured_enricher is not None:
            self.structured_enricher = structured_enricher
        elif isinstance(db, PostgresDB):
            self.structured_enricher = StructuredSourceEnricher()
        else:
            self.structured_enricher = _NoopStructuredSourceEnricher()
        self.search_client = create_web_search_client(api_key=os.getenv("ZAI_API_KEY"))
        self.reader_client: Any | None = None
        try:
            from clients.web_reader_client import WebReaderClient

            self.reader_client = WebReaderClient(api_key=os.getenv("ZAI_API_KEY"))
        except ModuleNotFoundError:
            self.reader_client = None
        self.zai_api_key = os.getenv("ZAI_API_KEY", "").strip()
        self.zai_model = os.getenv("LLM_MODEL_RESEARCH", "glm-4.7")
        self.embedding_service: Any | None = None
        openrouter_api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
        if openrouter_api_key:
            try:
                from llm_common.embeddings.openai import OpenAIEmbeddingService

                self.embedding_service = OpenAIEmbeddingService(
                    base_url="https://openrouter.ai/api/v1",
                    api_key=openrouter_api_key,
                    model="qwen/qwen3-embedding-8b",
                    dimensions=EMBEDDING_DIMENSIONS,
                )
            except Exception:
                self.embedding_service = None
        self._llm_client = (
            AsyncOpenAI(
                api_key=self.zai_api_key,
                base_url="https://api.z.ai/api/coding/paas/v4",
            )
            if self.zai_api_key
            else None
        )

    async def run_scope_pipeline(self, request: RunScopeRequest) -> dict[str, Any]:
        run_id = await self._get_or_create_run_id(request)
        policy = FreshnessPolicy(
            fresh_hours=24,
            stale_usable_ceiling_hours=72,
            fail_closed_ceiling_hours=168,
        )
        meta = WindmillMetadata(
            run_id=request.windmill_run_id,
            job_id=request.windmill_job_id,
            workspace=request.windmill_workspace,
            flow_path=request.windmill_flow_path,
        )

        responses: list[CommandResponse] = []
        search = await self._search_materialize(request=request, run_id=run_id, meta=meta)
        responses.append(search)
        snapshot_id = str(search.refs.get("search_snapshot_id", ""))

        freshness = await self._freshness_gate(
            request=request,
            run_id=run_id,
            meta=meta,
            snapshot_id=snapshot_id,
            policy=policy,
        )
        responses.append(freshness)

        if freshness.decision_reason not in {"stale_blocked", "empty_blocked"}:
            read_fetch = await self._read_fetch(
                request=request,
                run_id=run_id,
                meta=meta,
                snapshot_id=snapshot_id,
            )
            responses.append(read_fetch)
            if read_fetch.status in {"succeeded", "succeeded_with_alerts", "skipped"}:
                index = await self._index(
                    request=request,
                    run_id=run_id,
                    meta=meta,
                    raw_scrape_ids=list(read_fetch.refs.get("raw_scrape_ids", [])),
                )
                responses.append(index)
                analyze = await self._analyze(
                    request=request,
                    run_id=run_id,
                    meta=meta,
                    document_id=str(index.refs.get("document_id", "")),
                )
                responses.append(analyze)

        summary = await self._summarize(
            request=request,
            run_id=run_id,
            meta=meta,
            command_responses=responses,
        )
        package_materialization = await self._materialize_policy_evidence_package(
            request=request,
            run_id=run_id,
            command_responses=responses,
        )
        summary.refs.update(package_materialization["refs"])
        summary.alerts = list(
            dict.fromkeys([*summary.alerts, *package_materialization.get("alerts", [])])
        )
        summary.details["policy_evidence_package"] = package_materialization
        summary = await self._persist_response(run_id=run_id, request=request, response=summary)
        responses.append(summary)

        await self.db._execute(
            """
            UPDATE pipeline_runs
            SET status = $1, result = $2::jsonb, completed_at = NOW()
            WHERE id = $3::uuid
            """,
            summary.status,
            _json(summary.to_dict()),
            run_id,
        )

        steps = {response.command: self._step_payload(response, request) for response in responses}
        return {
            "contract_version": CONTRACT_VERSION,
            "command": "run_scope_pipeline",
            "status": summary.status,
            "decision_reason": summary.decision_reason,
            "idempotency_key": request.idempotency_key,
            "scope_idempotency_key": _scope_idempotency_key(request),
            "jurisdiction": request.jurisdiction,
            "source_family": request.source_family,
            "stale_status": freshness.decision_reason,
            "stale_status_requested": request.stale_status,
            "windmill_workspace": request.windmill_workspace,
            "windmill_flow_path": request.windmill_flow_path,
            "windmill_run_id": request.windmill_run_id,
            "windmill_job_id": request.windmill_job_id,
            "search_query": request.search_query,
            "analysis_question": request.analysis_question,
            "alerts": summary.alerts,
            "counts": summary.counts,
            "refs": summary.refs,
            "steps": steps,
            "storage_mode": "railway_runtime",
            "missing_runtime_adapters": [],
        }

    @staticmethod
    def _response_by_command(
        command_responses: list[CommandResponse], command: str
    ) -> CommandResponse | None:
        for response in command_responses:
            if response.command == command:
                return response
        return None

    @staticmethod
    def _selected_url_from_read_fetch(read_fetch: CommandResponse | None) -> str:
        if not read_fetch:
            return ""
        audit = read_fetch.details.get("candidate_audit", [])
        if not isinstance(audit, list):
            return ""
        for entry in audit:
            if not isinstance(entry, dict):
                continue
            if entry.get("outcome") in {"materialized_raw_scrape", "reused_existing_raw_scrape"}:
                return str(entry.get("url") or "").strip()
        return ""

    def _resolve_package_store(self) -> PolicyEvidencePackageStore:
        if self._package_store_override is not None:
            return self._package_store_override
        if not isinstance(self.db, PostgresDB):
            return InMemoryPolicyEvidencePackageStore()
        database_url = (
            os.getenv("DATABASE_URL_PUBLIC", "").strip()
            or os.getenv("DATABASE_URL", "").strip()
        )
        if database_url:
            return PostgresPolicyEvidencePackageStore(database_url=database_url)
        return InMemoryPolicyEvidencePackageStore()

    @staticmethod
    def _parse_minio_uri(uri: str) -> tuple[str, str] | None:
        if not uri.startswith("minio://"):
            return None
        payload = uri[len("minio://") :]
        if "/" not in payload:
            return None
        bucket, object_key = payload.split("/", 1)
        bucket = bucket.strip()
        object_key = object_key.strip()
        if not bucket or not object_key:
            return None
        return bucket, object_key

    def _normalize_artifact_uri(self, uri: str) -> str:
        value = str(uri or "").strip()
        if not value:
            return ""
        if "://" in value:
            return value
        bucket = str(getattr(self.storage, "bucket", "") or "").strip()
        if not bucket:
            return value
        return f"minio://{bucket}/{value.lstrip('/')}"

    def _package_artifact_uri(self, package_id: str) -> str:
        bucket = str(getattr(self.storage, "bucket", "") or "").strip() or "policy-evidence"
        return f"minio://{bucket}/policy-evidence/packages/{package_id}.json"

    @staticmethod
    def _is_official_domain_url(url: str) -> bool:
        host = urlsplit(url).netloc.lower()
        if not host:
            return False
        if host.endswith(".gov") or ".gov." in host:
            return True
        return any(
            signal in host
            for signal in (
                "legistar.com",
                "granicus.com",
                "records.",
                "cityof",
                "countyof",
            )
        )

    @classmethod
    def _classify_selected_artifact_family(cls, url: str) -> str:
        normalized = str(url or "").strip()
        if not normalized:
            return "missing"
        if _is_concrete_artifact_url(normalized):
            return "artifact"
        if prefetch_skip_reason(normalized):
            return "portal"
        if cls._is_official_domain_url(normalized):
            return "official_page"
        return "external_page"

    @staticmethod
    def _selection_reason_from_audit(candidate_audit: list[dict[str, Any]], selected_url: str) -> str:
        for item in candidate_audit:
            if str(item.get("url") or "").strip() != selected_url:
                continue
            outcome = str(item.get("outcome") or "").strip()
            if outcome:
                return outcome
        return "selected_candidate_recorded"

    @classmethod
    def _build_source_quality_metrics(
        cls,
        *,
        search_provider: str,
        search_provider_runtime: dict[str, Any],
        selected_url: str,
        search_candidates: list[dict[str, Any]],
        ranked_candidates: list[dict[str, Any]],
        candidate_audit: list[dict[str, Any]],
        reader_provider_errors: list[dict[str, Any]],
        reader_quality_failures: list[dict[str, Any]],
        structured_candidates: list[dict[str, Any]],
    ) -> dict[str, Any]:
        top_n_window = min(
            5,
            len(ranked_candidates) if ranked_candidates else len(search_candidates),
        )
        candidate_pool = ranked_candidates[:top_n_window] if ranked_candidates else [
            {
                "url": str(item.get("url") or "").strip(),
                "rank": index + 1,
                "score": 0,
            }
            for index, item in enumerate(search_candidates[:top_n_window])
        ]
        candidate_pool = [item for item in candidate_pool if str(item.get("url") or "").strip()]

        official_recall = sum(
            1 for item in candidate_pool if cls._is_official_domain_url(str(item.get("url") or ""))
        )
        artifact_recall = sum(
            1 for item in candidate_pool if _is_concrete_artifact_url(str(item.get("url") or ""))
        )
        selected_rank = None
        for item in candidate_pool:
            if str(item.get("url") or "").strip() == selected_url:
                selected_rank = item.get("rank")
                break
        if selected_rank is None:
            for item in candidate_audit:
                if str(item.get("url") or "").strip() == selected_url:
                    selected_rank = item.get("rank")
                    break
        selected_artifact_family = cls._classify_selected_artifact_family(selected_url)
        selected_candidate = {
            "url": selected_url,
            "provider": search_provider,
            "rank": selected_rank,
            "selection_reason": cls._selection_reason_from_audit(candidate_audit, selected_url),
            "artifact_grade": selected_artifact_family == "artifact",
            "official_domain": cls._is_official_domain_url(selected_url),
            "artifact_family": selected_artifact_family,
        }
        selected_outcome = cls._selection_reason_from_audit(candidate_audit, selected_url)
        reader_substance_observed = selected_outcome in {
            "materialized_raw_scrape",
            "reused_existing_raw_scrape",
        }
        secondary_lane_used = any(
            str(item.get("source_family") or "").strip().lower() in {"tavily_secondary_search", "exa_secondary_search"}
            for item in structured_candidates
            if isinstance(item, dict)
        )
        secondary_numeric_parameter_count = 0
        for item in structured_candidates:
            if not isinstance(item, dict):
                continue
            facts = item.get("structured_policy_facts")
            if not isinstance(facts, list):
                continue
            for fact in facts:
                if not isinstance(fact, dict):
                    continue
                value = fact.get("value")
                if isinstance(value, (int, float)):
                    secondary_numeric_parameter_count += 1
        provider_candidates = [
            {
                "url": str(item.get("url") or "").strip(),
                "rank": item.get("rank"),
                "artifact_grade": _is_concrete_artifact_url(str(item.get("url") or "")),
                "official_domain": cls._is_official_domain_url(str(item.get("url") or "")),
            }
            for item in candidate_pool
        ]
        portal_skip_count = sum(
            1
            for item in candidate_audit
            if str(item.get("outcome") or "").strip() == "reader_prefetch_skipped_low_value_portal"
        )
        official_reader_error_count = sum(
            1
            for item in candidate_audit
            if str(item.get("outcome") or "").strip() == "reader_provider_error"
            and bool(item.get("candidate_is_official_artifact"))
        )
        fallback_materialization_count = sum(
            1
            for item in candidate_audit
            if str(item.get("outcome") or "").strip() == "materialized_raw_scrape"
            and int(item.get("rank") or 0) > 1
        )
        return {
            "top_n_window": top_n_window,
            "top_n_official_recall_count": official_recall,
            "top_n_artifact_recall_count": artifact_recall,
            "selected_candidate": selected_candidate,
            "selected_artifact_family": selected_artifact_family,
            "reader_substance_observed": reader_substance_observed,
            "reader_substance_selection_outcome": selected_outcome,
            "secondary_numeric_rescue_detected": secondary_lane_used
            and secondary_numeric_parameter_count > 0,
            "secondary_numeric_parameter_count": secondary_numeric_parameter_count,
            "portal_skip_count": portal_skip_count,
            "official_reader_error_count": official_reader_error_count,
            "fallback_materialization_count": fallback_materialization_count,
            "provider_summary": {
                "primary_provider": search_provider,
                "provider_error_count": len(reader_provider_errors),
                "quality_failure_count": len(reader_quality_failures),
                "provider_error_urls": [
                    str(item.get("url") or "")
                    for item in reader_provider_errors
                    if str(item.get("url") or "").strip()
                ],
                "runtime": search_provider_runtime,
            },
            "provider_results": {
                search_provider: {
                    "status": "succeeded" if provider_candidates else "empty",
                    "reason_code": selected_candidate["selection_reason"],
                    "candidates": provider_candidates,
                }
            },
        }

    def _active_search_provider_provenance(self) -> dict[str, Any]:
        client = self.search_client
        explicit_label = str(getattr(client, "provider_label", "") or "").strip()
        class_name = client.__class__.__name__
        class_key = class_name.lower()
        configured_provider = os.getenv("WEB_SEARCH_PROVIDER", "").strip().lower()

        if explicit_label:
            provider = explicit_label
            provider_source = "client_label"
        elif "searxng" in class_key or "searx" in class_key:
            provider = "private_searxng"
            provider_source = "class_inference"
        elif "tavily" in class_key:
            provider = "tavily"
            provider_source = "class_inference"
        elif "exa" in class_key:
            provider = "exa"
            provider_source = "class_inference"
        elif "zai" in class_key:
            provider = "zai_search"
            provider_source = "class_inference"
        else:
            provider = configured_provider or "other"
            provider_source = "env_fallback" if configured_provider else "unknown"

        endpoint = str(getattr(client, "endpoint", "") or "").strip()
        endpoint_host = urlsplit(endpoint).netloc if endpoint else ""
        return {
            "provider": provider,
            "provider_source": provider_source,
            "client_class": class_name,
            "configured_provider": configured_provider or None,
            "endpoint_host": endpoint_host or None,
            "endpoint_configured": bool(endpoint),
        }

    @staticmethod
    def _analysis_text_parts(analyze: CommandResponse | None) -> list[str]:
        if analyze is None:
            return []
        details = analyze.details if isinstance(analyze.details, dict) else {}
        parts: list[str] = []
        evidence_selection = details.get("evidence_selection")
        if isinstance(evidence_selection, dict):
            selected_chunks = evidence_selection.get("selected_chunks")
            if isinstance(selected_chunks, list):
                for chunk in selected_chunks:
                    if not isinstance(chunk, dict):
                        continue
                    snippet = str(chunk.get("snippet") or "").strip()
                    if snippet:
                        parts.append(snippet)
        analysis = details.get("analysis")
        if isinstance(analysis, dict):
            for item in analysis.get("key_points") or []:
                text = str(item or "").strip()
                if text:
                    parts.append(text)
            summary = str(analysis.get("summary") or "").strip()
            if summary:
                parts.append(summary)
        return parts

    @classmethod
    def _extract_primary_fee_facts_from_analysis(
        cls,
        *,
        analyze: CommandResponse | None,
        selected_url: str,
    ) -> tuple[list[dict[str, Any]], list[str]]:
        facts: list[dict[str, Any]] = []
        alerts: list[str] = []
        seen: set[tuple[float, str]] = set()
        for chunk_index, text in enumerate(cls._analysis_text_parts(analyze), start=1):
            lowered = text.lower()
            if not any(signal in lowered for signal in ("fee", "fees", "per sq", "square foot", "sq. ft")):
                continue
            if re.search(r"\$[0-9]+(?:\.[0-9]+){2,}", text):
                alerts.append("primary_parameter_money_format_anomaly")
                malformed_match = re.search(r"\$[0-9]+(?:\.[0-9]+){2,}", text)
                if malformed_match is not None:
                    facts.append(
                        {
                            "field": "commercial_linkage_fee_rate_usd_per_sqft",
                            "raw_value": malformed_match.group(0),
                            "normalized_value": None,
                            "unit": "usd_per_square_foot",
                            "denominator": "per_square_foot",
                            "category": "unknown",
                            "source_url": selected_url,
                            "source_excerpt": text[:600],
                            "source_locator": f"analysis_chunk:{chunk_index}",
                            "provenance_lane": "primary_scraped_document",
                            "source_hierarchy_status": "bill_or_reg_text",
                            "confidence": 0.35,
                            "ambiguity_flag": True,
                            "ambiguity_reason": "currency_format_anomaly",
                            "currency_sanity": "invalid",
                            "unit_sanity": "valid",
                            "effective_date": None,
                        }
                    )
            for match in re.finditer(r"\$([0-9]+(?:\.[0-9]{1,2})?)(?![\d.])", text):
                raw_token = match.group(0)
                value = float(match.group(1))
                category = "unknown"
                context_window = lowered[max(0, match.start() - 80) : match.end() + 80]
                if "office" in context_window:
                    category = "office"
                elif "retail" in context_window:
                    category = "retail"
                elif "hotel" in context_window:
                    category = "hotel"
                elif "industrial" in context_window:
                    category = "industrial"
                dedupe_key = (value, category)
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)
                effective_date = None
                date_match = re.search(
                    r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2},\s+\d{4}",
                    lowered,
                )
                if date_match:
                    effective_date = date_match.group(0)
                facts.append(
                    {
                        "field": "commercial_linkage_fee_rate_usd_per_sqft",
                        "raw_value": raw_token,
                        "value": value,
                        "normalized_value": value,
                        "unit": "usd_per_square_foot",
                        "denominator": "per_square_foot",
                        "category": category,
                        "source_url": selected_url,
                        "source_excerpt": text[:600],
                        "source_locator": f"analysis_chunk:{chunk_index}",
                        "provenance_lane": "primary_scraped_document",
                        "source_hierarchy_status": "bill_or_reg_text",
                        "confidence": 0.82,
                        "ambiguity_flag": False,
                        "ambiguity_reason": None,
                        "currency_sanity": "valid",
                        "unit_sanity": "valid",
                        "effective_date": effective_date,
                    }
                )
        return facts, sorted(set(alerts))

    @staticmethod
    def _detect_source_shape_drift(search_candidates: list[dict[str, Any]]) -> dict[str, Any]:
        missing_url = 0
        missing_snippet = 0
        for item in search_candidates:
            if not isinstance(item, dict):
                continue
            if not str(item.get("url") or item.get("link") or "").strip():
                missing_url += 1
            snippet = str(item.get("snippet") or item.get("content") or "").strip()
            if not snippet:
                missing_snippet += 1
        drift_detected = missing_url > 0 or missing_snippet > 0
        return {
            "drift_detected": drift_detected,
            "missing_url_count": missing_url,
            "missing_snippet_count": missing_snippet,
            "candidate_count": len(search_candidates),
        }

    @classmethod
    def _build_policy_lineage(
        cls,
        *,
        selected_url: str,
        source_family: str,
        candidate_audit: list[dict[str, Any]],
        structured_candidates: list[dict[str, Any]],
    ) -> dict[str, Any]:
        selected_family = cls._classify_selected_artifact_family(selected_url)
        expected_source_families = [
            "authoritative_policy_text",
            "meeting_context",
            "staff_fiscal_context",
            "related_attachments",
        ]
        has_authoritative_text = selected_family == "artifact"
        has_meeting_context = "meeting" in source_family.lower() or any(
            isinstance(item, dict)
            and (
                "meeting" in str(item.get("url") or "").lower()
                or "agenda" in str(item.get("url") or "").lower()
            )
            for item in candidate_audit
        )
        has_staff_fiscal_context = any(
            "fiscal" in str(item).lower() or "fee" in str(item).lower() or "budget" in str(item).lower()
            for item in structured_candidates
        )
        related_artifacts = [
            str(item.get("url") or "").strip()
            for item in candidate_audit
            if isinstance(item, dict)
            and str(item.get("url") or "").strip()
            and str(item.get("url") or "").strip() != selected_url
            and _is_concrete_artifact_url(str(item.get("url") or ""))
        ]
        has_related_artifacts = bool(related_artifacts)

        found_flags = {
            "authoritative_policy_text": has_authoritative_text,
            "meeting_context": has_meeting_context,
            "staff_fiscal_context": has_staff_fiscal_context,
            "related_attachments": has_related_artifacts,
        }
        negative_evidence = [
            {
                "source_family": family,
                "status": "not_found",
                "reason": "lineage_search_missing_in_current_package",
            }
            for family, found in found_flags.items()
            if not found
        ]
        return {
            "selected_artifact_family": selected_family,
            "expected_source_families": expected_source_families,
            "lineage_presence": found_flags,
            "related_artifacts": related_artifacts[:5],
            "negative_evidence": negative_evidence,
            "lineage_completeness_score": sum(1 for found in found_flags.values() if found) / len(found_flags),
        }

    @staticmethod
    def _collect_secondary_numeric_facts(structured_candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        collected: list[dict[str, Any]] = []
        for candidate in structured_candidates:
            if not isinstance(candidate, dict):
                continue
            source_family = str(candidate.get("source_family") or "").strip().lower()
            facts = candidate.get("structured_policy_facts")
            if not isinstance(facts, list):
                continue
            for fact in facts:
                if not isinstance(fact, dict):
                    continue
                value = fact.get("normalized_value", fact.get("value"))
                if isinstance(value, str):
                    try:
                        value = float(value.replace(",", "").strip())
                    except ValueError:
                        value = None
                if not isinstance(value, (int, float)):
                    continue
                collected.append(
                    {
                        "field": str(fact.get("field") or "unknown_parameter"),
                        "normalized_value": float(value),
                        "source_family": source_family or "unknown",
                        "source_url": str(fact.get("source_url") or candidate.get("artifact_url") or "").strip(),
                        "source_excerpt": str(fact.get("source_excerpt") or "").strip(),
                    }
                )
        return collected

    @staticmethod
    def _reconcile_parameter_sources(
        *,
        primary_facts: list[dict[str, Any]],
        secondary_facts: list[dict[str, Any]],
    ) -> dict[str, Any]:
        primary_index: dict[str, float] = {}
        for fact in primary_facts:
            field = str(fact.get("field") or "unknown_parameter")
            value = fact.get("normalized_value", fact.get("value"))
            if isinstance(value, (int, float)):
                primary_index[field] = float(value)
        reconciliation: list[dict[str, Any]] = []
        for secondary in secondary_facts:
            field = str(secondary.get("field") or "unknown_parameter")
            secondary_value = float(secondary.get("normalized_value"))
            if field in primary_index:
                primary_value = primary_index[field]
                if abs(primary_value - secondary_value) < 1e-6:
                    reconciliation.append(
                        {
                            "field": field,
                            "status": "confirmed",
                            "source_of_truth": "primary_scraped_document",
                            "primary_value": primary_value,
                            "secondary_value": secondary_value,
                        }
                    )
                else:
                    reconciliation.append(
                        {
                            "field": field,
                            "status": "source_of_truth_selected",
                            "source_of_truth": "primary_scraped_document",
                            "primary_value": primary_value,
                            "secondary_value": secondary_value,
                            "decision_reason": "primary_artifact_precedence_over_secondary",
                        }
                    )
            else:
                reconciliation.append(
                    {
                        "field": field,
                        "status": "source_of_truth_selected",
                        "source_of_truth": "secondary_search_derived",
                        "primary_value": None,
                        "secondary_value": secondary_value,
                        "decision_reason": "primary_value_missing_secondary_used_with_label",
                    }
                )
        unresolved = [
            item
            for item in reconciliation
            if str(item.get("status") or "") == "conflict_unresolved"
        ]
        return {
            "records": reconciliation,
            "unresolved_count": len(unresolved),
            "source_of_truth_policy": "primary_artifact_precedence_then_labeled_secondary",
            "secondary_override_blocked": all(
                str(item.get("source_of_truth") or "") != "secondary_search_derived"
                or item.get("primary_value") is None
                for item in reconciliation
            ),
        }

    @staticmethod
    def _infer_mechanism_hint(
        *,
        request: RunScopeRequest,
        selected_url: str,
    ) -> _EconomicMechanismHint:
        text = " ".join(
            [
                request.search_query.lower(),
                request.source_family.lower(),
                request.analysis_question.lower(),
                selected_url.lower(),
            ]
        )

        has_fee_or_tax = any(
            token in text
            for token in (
                "impact fee",
                "development fee",
                "developer fee",
                "linkage fee",
                "permit fee",
                "tax",
                "assessment",
            )
        )
        has_housing = any(
            token in text
            for token in ("housing", "multifamily", "condo", "rent", "residential", "developer")
        )
        if has_fee_or_tax and has_housing:
            return _EconomicMechanismHint(
                mechanism_family=MechanismFamily.FEE_OR_TAX_PASS_THROUGH.value,
                impact_mode=ImpactMode.PASS_THROUGH_INCIDENCE.value,
                secondary_research_needed=True,
                secondary_research_reason="pass_through_incidence_rate_missing",
            )

        if any(
            token in text
            for token in ("service fee", "utility fee", "city tax", "sales tax", "parcel tax")
        ):
            return _EconomicMechanismHint(
                mechanism_family=MechanismFamily.DIRECT_FISCAL.value,
                impact_mode=ImpactMode.DIRECT_FISCAL.value,
                secondary_research_needed=False,
            )

        if any(
            token in text
            for token in (
                "license",
                "licensing",
                "permit requirement",
                "training requirement",
                "compliance",
                "mandate",
            )
        ):
            return _EconomicMechanismHint(
                mechanism_family=MechanismFamily.COMPLIANCE_COST.value,
                impact_mode=ImpactMode.COMPLIANCE_COST.value,
                secondary_research_needed=False,
            )

        return _EconomicMechanismHint(
            mechanism_family=None,
            impact_mode=ImpactMode.QUALITATIVE_ONLY.value,
            secondary_research_needed=False,
        )

    async def _materialize_policy_evidence_package(
        self,
        *,
        request: RunScopeRequest,
        run_id: str,
        command_responses: list[CommandResponse],
    ) -> dict[str, Any]:
        search = self._response_by_command(command_responses, "search_materialize")
        read_fetch = self._response_by_command(command_responses, "read_fetch")
        index = self._response_by_command(command_responses, "index")
        analyze = self._response_by_command(command_responses, "analyze")

        raw_scrape_id = ""
        reader_artifact_uri = ""
        if read_fetch:
            raw_ids = read_fetch.refs.get("raw_scrape_ids", [])
            if isinstance(raw_ids, list) and raw_ids:
                raw_scrape_id = str(raw_ids[0])
            artifact_refs = read_fetch.refs.get("artifact_refs", [])
            if isinstance(artifact_refs, list) and artifact_refs:
                reader_artifact_uri = self._normalize_artifact_uri(str(artifact_refs[0]))
        document_id = str(index.refs.get("document_id", "")) if index else ""
        selected_url = self._selected_url_from_read_fetch(read_fetch)

        canonical_document_key = ""
        content_hash = ""
        if raw_scrape_id:
            raw_row = await self.db._fetchrow(
                """
                SELECT canonical_document_key, content_hash, storage_uri
                FROM raw_scrapes
                WHERE id = $1::uuid
                LIMIT 1
                """,
                raw_scrape_id,
            )
            if raw_row:
                canonical_document_key = str(raw_row["canonical_document_key"] or "")
                content_hash = str(raw_row["content_hash"] or "")
                if not reader_artifact_uri:
                    reader_artifact_uri = self._normalize_artifact_uri(
                        str(raw_row["storage_uri"] or "")
                    )
        if not reader_artifact_uri:
            reader_artifact_uri = self._normalize_artifact_uri("policy-evidence/unproven/pending")

        fail_closed_reasons: list[str] = []
        if read_fetch and read_fetch.status not in {"succeeded", "succeeded_with_alerts"}:
            fail_closed_reasons.append(f"read_fetch:{read_fetch.decision_reason}")
        if not raw_scrape_id:
            fail_closed_reasons.append("raw_scrape_missing")
        if not document_id:
            fail_closed_reasons.append("document_id_missing")
        analyze_sufficiency = ""
        if analyze:
            analysis_payload = analyze.details.get("analysis", {})
            if isinstance(analysis_payload, dict):
                analyze_sufficiency = str(analysis_payload.get("sufficiency_state") or "").strip()
            if analyze.status != "succeeded":
                fail_closed_reasons.append(f"analyze:{analyze.decision_reason}")
            elif analyze_sufficiency and analyze_sufficiency not in {"sufficient", "quantified"}:
                fail_closed_reasons.append(f"analysis_sufficiency:{analyze_sufficiency}")
        else:
            fail_closed_reasons.append("analysis_missing")

        package_id = f"pkg-{_hash(f'{_scope_idempotency_key(request)}|{canonical_document_key}|{selected_url}')[:24]}"
        mechanism_hint = self._infer_mechanism_hint(request=request, selected_url=selected_url)
        structured_enrichment = await self.structured_enricher.enrich(
            jurisdiction=request.jurisdiction,
            source_family=request.source_family,
            search_query=request.search_query,
            selected_url=selected_url,
        )
        search_snapshot_id = ""
        if search:
            search_snapshot_id = str(search.refs.get("search_snapshot_id") or "").strip()
        search_candidates: list[dict[str, Any]] = []
        if search_snapshot_id:
            snapshot_row = await self.db._fetchrow(
                "SELECT snapshot_payload FROM search_result_snapshots WHERE id = $1::uuid",
                search_snapshot_id,
            )
            if snapshot_row:
                payload = _db_json(snapshot_row["snapshot_payload"], [])
                if isinstance(payload, list):
                    search_candidates = [item for item in payload if isinstance(item, dict)]
        read_fetch_details = read_fetch.details if read_fetch else {}
        ranked_candidates = (
            list(read_fetch_details.get("ranked_candidates", []))
            if isinstance(read_fetch_details.get("ranked_candidates", []), list)
            else []
        )
        candidate_audit = (
            list(read_fetch_details.get("candidate_audit", []))
            if isinstance(read_fetch_details.get("candidate_audit", []), list)
            else []
        )
        reader_provider_errors = (
            list(read_fetch_details.get("reader_provider_errors", []))
            if isinstance(read_fetch_details.get("reader_provider_errors", []), list)
            else []
        )
        reader_quality_failures = (
            list(read_fetch_details.get("reader_quality_failures", []))
            if isinstance(read_fetch_details.get("reader_quality_failures", []), list)
            else []
        )
        search_provider_runtime = self._active_search_provider_provenance()
        search_provider = str(search_provider_runtime["provider"])
        source_shape_drift = self._detect_source_shape_drift(search_candidates)
        source_quality_metrics = self._build_source_quality_metrics(
            search_provider=search_provider,
            search_provider_runtime=search_provider_runtime,
            selected_url=selected_url,
            search_candidates=search_candidates,
            ranked_candidates=ranked_candidates,
            candidate_audit=candidate_audit,
            reader_provider_errors=reader_provider_errors,
            reader_quality_failures=reader_quality_failures,
            structured_candidates=structured_enrichment.candidates,
        )
        source_quality_metrics["source_shape_drift"] = source_shape_drift
        primary_fee_facts, primary_parameter_alerts = self._extract_primary_fee_facts_from_analysis(
            analyze=analyze,
            selected_url=selected_url,
        )
        secondary_numeric_facts = self._collect_secondary_numeric_facts(structured_enrichment.candidates)
        source_reconciliation = self._reconcile_parameter_sources(
            primary_facts=primary_fee_facts,
            secondary_facts=secondary_numeric_facts,
        )
        policy_lineage = self._build_policy_lineage(
            selected_url=selected_url,
            source_family=request.source_family,
            candidate_audit=candidate_audit,
            structured_candidates=structured_enrichment.candidates,
        )
        if (
            mechanism_hint.secondary_research_needed
            and mechanism_hint.secondary_research_reason
        ):
            fail_closed_reasons.append(
                f"secondary_research_needed:{mechanism_hint.secondary_research_reason}"
            )
        if source_shape_drift["drift_detected"]:
            fail_closed_reasons.append("search_source_shape_drift_detected")
        canonical_analysis_id = ""
        canonical_pipeline_run_id = ""
        canonical_pipeline_step_id = ""
        canonical_breakdown_ref = ""
        if analyze and analyze.status == "succeeded":
            analysis_id_value = str(analyze.refs.get("analysis_id") or "").strip()
            if analysis_id_value:
                canonical_analysis_id = analysis_id_value
                canonical_pipeline_run_id = run_id
                canonical_pipeline_step_id = analysis_id_value
                canonical_breakdown_ref = f"analysis:{analysis_id_value}"
        raw_scrape_retrieved_at = _utc_now().isoformat()
        raw_scrape_excerpt = ""
        if raw_scrape_id:
            raw_row_for_excerpt = await self.db._fetchrow(
                """
                SELECT created_at, data
                FROM raw_scrapes
                WHERE id = $1::uuid
                LIMIT 1
                """,
                raw_scrape_id,
            )
            if raw_row_for_excerpt:
                created_at_value = raw_row_for_excerpt["created_at"]
                if hasattr(created_at_value, "isoformat"):
                    raw_scrape_retrieved_at = created_at_value.isoformat()
                elif created_at_value:
                    raw_scrape_retrieved_at = str(created_at_value)
                raw_data = _db_json(raw_row_for_excerpt["data"], {})
                if isinstance(raw_data, dict):
                    raw_content = str(raw_data.get("content") or "").strip()
                    raw_scrape_excerpt = raw_content[:600]
        if not raw_scrape_excerpt:
            text_parts = self._analysis_text_parts(analyze)
            raw_scrape_excerpt = text_parts[0][:600] if text_parts else ""
        scraped_evidence_ready = bool(raw_scrape_id and reader_artifact_uri and selected_url)
        reader_substance_reason = ""
        if read_fetch and read_fetch.status not in {"succeeded", "succeeded_with_alerts"}:
            reader_substance_reason = "reader_output_insufficient_substance"
        elif not scraped_evidence_ready:
            reader_substance_reason = "empty_reader_output"
        package_artifact_uri = self._package_artifact_uri(package_id)
        package_payload = PolicyEvidencePackageBuilder().build(
            package_id=package_id,
            jurisdiction=request.jurisdiction,
            scraped_candidates=[
                {
                    "source_lane": "scrape_search",
                    "provider": search_provider,
                    "provider_run_id": request.windmill_run_id,
                    "source_family": request.source_family,
                    "jurisdiction": request.jurisdiction,
                    "query_text": request.search_query,
                    "search_snapshot_id": (
                        str(search.refs.get("search_snapshot_id", ""))
                        if search
                        else f"{package_id}-snapshot"
                    ),
                    "candidate_rank": 1,
                    "artifact_url": selected_url,
                    "artifact_type": request.source_family,
                    "content_hash": content_hash,
                    "canonical_document_key": canonical_document_key,
                    "reader_artifact_refs": [reader_artifact_uri] if reader_artifact_uri else [],
                    "reader_substance_reason": reader_substance_reason,
                    "evidence_readiness": "ready" if scraped_evidence_ready else "insufficient",
                    "retrieved_at": raw_scrape_retrieved_at,
                    "excerpt": raw_scrape_excerpt,
                    "evidence_source_type": "ordinance_text",
                    "source_tier": "tier_a",
                    "structured_policy_facts": primary_fee_facts,
                    "alerts": list(dict.fromkeys([*fail_closed_reasons, *primary_parameter_alerts])),
                    "selected_impact_mode": mechanism_hint.impact_mode,
                    "mechanism_family": mechanism_hint.mechanism_family,
                }
            ],
            structured_candidates=structured_enrichment.candidates,
            freshness_gate={"freshness_status": request.stale_status},
            economic_hints={
                "impact_mode": mechanism_hint.impact_mode,
                "mechanism_family": mechanism_hint.mechanism_family,
                "secondary_research_needed": mechanism_hint.secondary_research_needed,
                "secondary_research_reason": mechanism_hint.secondary_research_reason,
                "canonical_breakdown_ref": canonical_breakdown_ref,
                "canonical_pipeline_run_id": canonical_pipeline_run_id,
                "canonical_pipeline_step_id": canonical_pipeline_step_id,
            },
            storage_refs={
                "postgres_package_row": f"policy_evidence_packages:{package_id}",
                "reader_artifact": reader_artifact_uri or "minio://policy-evidence/unproven/pending",
                "pgvector_chunk_ref": f"document:{document_id or 'pending'}",
            },
        )
        package_storage_refs = package_payload.get("storage_refs")
        if isinstance(package_storage_refs, list):
            package_storage_refs.append(
                {
                    "storage_system": "minio",
                    "truth_role": "artifact_of_record",
                    "reference_id": package_artifact_uri,
                    "uri": package_artifact_uri,
                    "notes": "package artifact envelope",
                }
            )
        # Keep idempotent content-hash semantics stable for reruns of the same scope key.
        package_payload["created_at"] = "1970-01-01T00:00:00+00:00"
        package_payload["run_context"] = {
            "backend_run_id": run_id,
            "scope_idempotency_key": _scope_idempotency_key(request),
            "windmill_run_id": request.windmill_run_id,
            "windmill_job_id": request.windmill_job_id,
            "windmill_workspace": request.windmill_workspace,
            "windmill_flow_path": request.windmill_flow_path,
            "canonical_document_key": canonical_document_key,
            "selected_url": selected_url,
            "reader_artifact_uri": reader_artifact_uri,
            "raw_scrape_id": raw_scrape_id,
            "document_id": document_id,
            "structured_enrichment_status": structured_enrichment.status,
            "structured_sources": structured_enrichment.candidates,
            "structured_source_catalog": structured_enrichment.source_catalog,
            "structured_enrichment_alerts": structured_enrichment.alerts,
            "mechanism_family_hint": mechanism_hint.mechanism_family,
            "impact_mode_hint": mechanism_hint.impact_mode,
            "secondary_research_needed": mechanism_hint.secondary_research_needed,
            "secondary_research_reason": mechanism_hint.secondary_research_reason,
            "source_quality_metrics": source_quality_metrics,
            "policy_lineage": policy_lineage,
            "source_reconciliation": source_reconciliation,
            "search_provider_runtime": search_provider_runtime,
            "source_shape_drift": source_shape_drift,
            "primary_parameter_extraction": {
                "source": "analyze.evidence_selection.selected_chunks",
                "parameter_count": len(primary_fee_facts),
                "alerts": primary_parameter_alerts,
                "facts": primary_fee_facts,
            },
            "canonical_analysis_id": canonical_analysis_id,
            "canonical_pipeline_run_id": canonical_pipeline_run_id,
            "canonical_pipeline_step_id": canonical_pipeline_step_id,
            "canonical_breakdown_ref": canonical_breakdown_ref,
            "fail_closed_reasons": list(dict.fromkeys(fail_closed_reasons)),
            "package_identity": {
                "package_id": package_id,
                "canonical_document_key": canonical_document_key,
                "selected_url": selected_url,
                "idempotency_scope": _scope_idempotency_key(request),
            },
            "proof_modes": {
                "orchestration": "windmill_runtime_ids",
                "storage": "pending_storage_probe",
                "analysis_binding": (
                    "canonical_projection_bound"
                    if canonical_pipeline_run_id and canonical_pipeline_step_id
                    else "canonical_projection_missing"
                ),
            },
        }
        package_payload["structured_enrichment_status"] = structured_enrichment.status
        package_payload["source_quality_metrics"] = source_quality_metrics
        package_payload["policy_lineage"] = policy_lineage
        package_payload["source_reconciliation"] = source_reconciliation

        idempotency_key = f"{_scope_idempotency_key(request)}::policy_evidence_package"
        store = self._resolve_package_store()
        artifact_writer: ArtifactWriter | None = None
        artifact_probe: ArtifactProbe | None = None
        if getattr(self.storage, "client", None) is not None and getattr(
            self.storage, "bucket", None
        ):
            artifact_writer = _S3PolicyEvidenceArtifactWriter(storage=self.storage)
            artifact_probe = _S3PolicyEvidenceArtifactProbe(storage=self.storage)
        storage = PolicyEvidencePackageStorageService(
            store=store,
            artifact_writer=artifact_writer,
            artifact_probe=artifact_probe,
        )
        try:
            storage_result = storage.persist(
                package_payload=package_payload,
                idempotency_key=idempotency_key,
            )
        except RuntimeError as exc:
            if isinstance(store, PostgresPolicyEvidencePackageStore):
                fallback = PolicyEvidencePackageStorageService(
                    store=InMemoryPolicyEvidencePackageStore()
                )
                storage_result = fallback.persist(
                    package_payload=package_payload,
                    idempotency_key=idempotency_key,
                )
                fail_closed_reasons.append(f"postgres_store_unavailable:{exc}")
            else:
                raise
        storage_status = "stored" if storage_result.stored else "store_failed"
        if storage_result.idempotent_reuse:
            storage_status = "stored_reused"

        if storage_result.failure_class:
            fail_closed_reasons.append(storage_result.failure_class)
        fail_closed_reasons.extend(package_payload.get("insufficiency_reasons", []))
        refs = {
            "backend_run_id": run_id,
            "package_id": storage_result.package_id if storage_result.stored else None,
            "canonical_document_key": canonical_document_key,
            "selected_url": selected_url,
            "reader_artifact_uri": reader_artifact_uri,
            "package_artifact_uri": package_artifact_uri,
            "raw_scrape_id": raw_scrape_id,
            "document_id": document_id,
            "storage_status": storage_status,
            "storage_proof_mode": (
                "direct_live_probe"
                if storage_result.artifact_readback_status == "proven"
                else "indirect_or_unproven"
            ),
            "idempotent_replay": bool(storage_result.idempotent_reuse),
            "fail_closed_reasons": sorted(set(str(item) for item in fail_closed_reasons if str(item).strip())),
        }
        alerts = []
        if storage_result.failure_class:
            alerts.append(f"policy_evidence_storage:{storage_result.failure_class}")
        if storage_result.fail_closed:
            alerts.append("policy_evidence_fail_closed")
        return {
            "refs": refs,
            "alerts": alerts,
            "storage_result": {
                "stored": storage_result.stored,
                "idempotent_reuse": storage_result.idempotent_reuse,
                "fail_closed": storage_result.fail_closed,
                "failure_class": storage_result.failure_class,
                "artifact_write_status": storage_result.artifact_write_status,
                "artifact_readback_status": storage_result.artifact_readback_status,
                "pgvector_truth_role": storage_result.pgvector_truth_role,
            },
            "package_payload": package_payload,
        }

    async def _get_or_create_run_id(self, request: RunScopeRequest) -> str:
        existing = await self.db._fetchrow(
            """
            SELECT id
            FROM pipeline_runs
            WHERE windmill_run_id = $1
              AND source_family = $2
              AND jurisdiction = $3
            ORDER BY created_at DESC
            LIMIT 1
            """,
            request.windmill_run_id,
            request.source_family,
            request.jurisdiction,
        )
        if existing:
            return str(existing["id"])

        created = await self.db._fetchrow(
            """
            INSERT INTO pipeline_runs
              (bill_id, jurisdiction, models, trigger_source, started_at, status,
               orchestrator, windmill_workspace, windmill_run_id, windmill_job_id,
               source_family, contract_version, idempotency_key)
            VALUES
              ($1, $2, $3::jsonb, 'windmill', NOW(), 'running',
               'windmill_domain_bridge', $4, $5, $6, $7, $8, $9)
            RETURNING id
            """,
            request.idempotency_key,
            request.jurisdiction,
            _json({}),
            request.windmill_workspace,
            request.windmill_run_id,
            request.windmill_job_id,
            request.source_family,
            request.contract_version,
            _scope_idempotency_key(request),
        )
        if not created:
            raise RuntimeError("pipeline_run_create_failed")
        return str(created["id"])

    async def _reuse_if_idempotent(
        self, *, command: str, request: RunScopeRequest
    ) -> CommandResponse | None:
        idempotency_key = _scope_idempotency_key(request)
        row = await self.db._fetchrow(
            """
            SELECT status, decision_reason, retry_class, alerts, refs, counts, details, contract_version
            FROM pipeline_command_results
            WHERE command = $1 AND idempotency_key = $2
            LIMIT 1
            """,
            command,
            idempotency_key,
        )
        if not row:
            return None
        details = dict(_db_json(row["details"], {}) or {})
        details["idempotent_reuse"] = True
        return CommandResponse(
            command=command,  # type: ignore[arg-type]
            status=row["status"],
            decision_reason=row["decision_reason"] or "",
            retry_class=row["retry_class"] or "none",
            alerts=list(_db_json(row["alerts"], []) or []),
            refs=dict(_db_json(row["refs"], {}) or {}),
            counts={k: int(v) for k, v in dict(_db_json(row["counts"], {}) or {}).items()},
            details=details,
            contract_version=row["contract_version"] or CONTRACT_VERSION,
        )

    async def _enforce_reader_substance_on_reuse(
        self, *, reused: CommandResponse
    ) -> CommandResponse:
        if reused.status not in {"succeeded", "succeeded_with_alerts"}:
            return reused

        raw_scrape_ids = [str(raw_id).strip() for raw_id in reused.refs.get("raw_scrape_ids", [])]
        raw_scrape_ids = [raw_id for raw_id in raw_scrape_ids if raw_id]
        if not raw_scrape_ids:
            return reused

        failures: list[dict[str, Any]] = []
        for raw_scrape_id in raw_scrape_ids:
            row = await self.db._fetchrow(
                """
                SELECT id, url, COALESCE(data, '{}'::jsonb) AS data
                FROM raw_scrapes
                WHERE id = $1::uuid
                LIMIT 1
                """,
                raw_scrape_id,
            )
            if not row:
                continue
            raw_data = dict(_db_json(row["data"], {}) or {})
            markdown_body = str(raw_data.get("content", "")).strip()
            is_substantive, quality_details = assess_reader_substance(markdown_body)
            if is_substantive:
                continue
            url_value = ""
            try:
                url_value = str(row["url"] or "")
            except Exception:
                url_value = ""
            failures.append(
                {
                    "raw_scrape_id": str(row["id"]),
                    "url": url_value,
                    "reason": str(quality_details["reason"]),
                    "quality_details": quality_details,
                }
            )

        if not failures:
            return reused

        details = dict(reused.details)
        details["cached_reader_reuse_blocked"] = True
        details["reader_quality_failures"] = failures
        reason = str(failures[0]["reason"])
        alerts = list(reused.alerts)
        alerts.append(f"reader_output_insufficient_substance:{reason}")

        return CommandResponse(
            command="read_fetch",
            status="blocked",
            decision_reason="reader_output_insufficient_substance",
            retry_class="insufficient_evidence",
            alerts=list(dict.fromkeys(alerts)),
            refs=dict(reused.refs),
            counts=dict(reused.counts),
            details=details,
            contract_version=reused.contract_version,
        )

    async def _persist_response(
        self, *, run_id: str, request: RunScopeRequest, response: CommandResponse
    ) -> CommandResponse:
        await self.db._execute(
            """
            INSERT INTO pipeline_command_results
              (run_id, command, idempotency_key, status, decision_reason, retry_class, alerts,
               refs, counts, details, contract_version)
            VALUES
              ($1::uuid, $2, $3, $4, $5, $6, $7::jsonb, $8::jsonb, $9::jsonb, $10::jsonb, $11)
            ON CONFLICT (command, idempotency_key)
            DO UPDATE SET
              status = EXCLUDED.status,
              decision_reason = EXCLUDED.decision_reason,
              retry_class = EXCLUDED.retry_class,
              alerts = EXCLUDED.alerts,
              refs = EXCLUDED.refs,
              counts = EXCLUDED.counts,
              details = EXCLUDED.details,
              contract_version = EXCLUDED.contract_version
            """,
            run_id,
            response.command,
            _scope_idempotency_key(request),
            response.status,
            response.decision_reason,
            response.retry_class,
            _json(response.alerts),
            _json(response.refs),
            _json(response.counts),
            _json(response.details),
            response.contract_version,
        )
        await self.db._execute(
            """
            INSERT INTO pipeline_steps
              (run_id, step_number, step_name, status, input_context, output_result,
               duration_ms, command, retry_class, decision_reason, alerts, refs,
               windmill_job_id, idempotency_key)
            VALUES
              ($1::uuid, $2, $3, $4, $5::jsonb, $6::jsonb,
               0, $7, $8, $9, $10::jsonb, $11::jsonb, $12, $13)
            ON CONFLICT (run_id, step_number)
            DO UPDATE SET
              status = EXCLUDED.status,
              input_context = EXCLUDED.input_context,
              output_result = EXCLUDED.output_result,
              command = EXCLUDED.command,
              retry_class = EXCLUDED.retry_class,
              decision_reason = EXCLUDED.decision_reason,
              alerts = EXCLUDED.alerts,
              refs = EXCLUDED.refs,
              windmill_job_id = EXCLUDED.windmill_job_id,
              idempotency_key = EXCLUDED.idempotency_key
            """,
            run_id,
            STEP_NUMBER_BY_COMMAND[response.command],
            response.command,
            response.status,
            _json(
                {
                    "contract_version": request.contract_version,
                    "idempotency_key": request.idempotency_key,
                    "scope_idempotency_key": _scope_idempotency_key(request),
                    "jurisdiction": request.jurisdiction,
                    "source_family": request.source_family,
                }
            ),
            _json(response.to_dict()),
            response.command,
            response.retry_class,
            response.decision_reason,
            _json(response.alerts),
            _json(response.refs),
            request.windmill_job_id,
            _scope_idempotency_key(request),
        )
        return response

    async def _search_materialize(
        self, *, request: RunScopeRequest, run_id: str, meta: WindmillMetadata
    ) -> CommandResponse:
        reused = await self._reuse_if_idempotent(
            command="search_materialize",
            request=request,
        )
        if reused:
            return reused
        try:
            results = await self.search_client.search(query=request.search_query, count=10)
        except Exception as exc:
            response = CommandResponse(
                command="search_materialize",
                status="failed_retryable",
                decision_reason="search_transport_error",
                retry_class="transport",
                alerts=[f"search_provider_error:{exc}"],
                refs={"windmill_run_id": meta.run_id, "windmill_job_id": meta.job_id},
            )
            return await self._persist_response(run_id=run_id, request=request, response=response)

        normalized = [
            {
                "url": (item.get("url") or item.get("link") or "").strip(),
                "title": (item.get("title") or "").strip(),
                "snippet": (item.get("snippet") or item.get("content") or "").strip(),
            }
            for item in results
            if (item.get("url") or item.get("link"))
        ]
        results_hash = _hash(_json(normalized))
        query_hash = _hash(request.search_query.strip().lower())
        row = await self.db._fetchrow(
            """
            INSERT INTO search_result_snapshots
              (jurisdiction_id, source_family, query, query_hash, results_hash, result_count,
               snapshot_payload, contract_version, idempotency_key, captured_at)
            VALUES
              ($1, $2, $3, $4, $5, $6, $7::jsonb, $8, $9, NOW())
            ON CONFLICT (idempotency_key)
            DO UPDATE SET
              query = EXCLUDED.query,
              query_hash = EXCLUDED.query_hash,
              results_hash = EXCLUDED.results_hash,
              result_count = EXCLUDED.result_count,
              snapshot_payload = EXCLUDED.snapshot_payload,
              contract_version = EXCLUDED.contract_version,
              captured_at = NOW()
            RETURNING id, result_count
            """,
            request.jurisdiction,
            request.source_family,
            request.search_query,
            query_hash,
            results_hash,
            len(normalized),
            _json(normalized),
            request.contract_version,
            _scope_idempotency_key(request),
        )
        snapshot_id = str(row["id"]) if row else ""
        status = "succeeded" if normalized else "succeeded_with_alerts"
        reason = "fresh_snapshot_materialized" if normalized else "search_empty_result"
        alerts = [] if normalized else ["search_results_empty"]
        response = CommandResponse(
            command="search_materialize",
            status=status,
            decision_reason=reason,
            retry_class="none",
            alerts=alerts,
            counts={"search_results": len(normalized)},
            refs={
                "windmill_run_id": meta.run_id,
                "windmill_job_id": meta.job_id,
                "search_snapshot_id": snapshot_id,
            },
            details={"query": request.search_query},
        )
        return await self._persist_response(run_id=run_id, request=request, response=response)

    async def _freshness_gate(
        self,
        *,
        request: RunScopeRequest,
        run_id: str,
        meta: WindmillMetadata,
        snapshot_id: str,
        policy: FreshnessPolicy,
    ) -> CommandResponse:
        reused = await self._reuse_if_idempotent(
            command="freshness_gate",
            request=request,
        )
        if reused:
            return reused
        snapshot = await self.db._fetchrow(
            "SELECT result_count, captured_at FROM search_result_snapshots WHERE id = $1::uuid",
            snapshot_id,
        )
        if not snapshot:
            response = CommandResponse(
                command="freshness_gate",
                status="failed_terminal",
                decision_reason="missing_snapshot",
                retry_class="contract_violation",
                refs={"windmill_run_id": meta.run_id, "windmill_job_id": meta.job_id},
            )
            return await self._persist_response(run_id=run_id, request=request, response=response)

        captured_at = snapshot["captured_at"]
        now = _utc_now()
        snapshot_age_hours = int((now - captured_at).total_seconds() / 3600)
        result_count = int(snapshot["result_count"] or 0)

        freshness = request.stale_status
        status = "succeeded"
        alerts: list[str] = []
        if freshness in {"stale_but_usable", "empty_but_usable"}:
            status = "succeeded_with_alerts"
            alerts.append("source_search_failed_using_last_success")
        elif freshness in {"stale_blocked", "empty_blocked"}:
            status = "blocked"
            alerts.append(
                "stale_search_results_fail_closed"
                if freshness == "stale_blocked"
                else "empty_search_results_fail_closed"
            )
        elif freshness == "fresh" and result_count == 0:
            status = "succeeded_with_alerts"
            freshness = "empty_but_usable"
            alerts.append("search_results_empty")

        retry_class = "none" if status != "blocked" else "operator_required"
        response = CommandResponse(
            command="freshness_gate",
            status=status,  # type: ignore[arg-type]
            decision_reason=freshness,
            retry_class=retry_class,  # type: ignore[arg-type]
            alerts=alerts,
            counts={"search_results": result_count},
            refs={
                "windmill_run_id": meta.run_id,
                "windmill_job_id": meta.job_id,
                "search_snapshot_id": snapshot_id,
            },
            details={
                "freshness_status": freshness,
                "fresh_hours": policy.fresh_hours,
                "stale_usable_ceiling_hours": policy.stale_usable_ceiling_hours,
                "fail_closed_ceiling_hours": policy.fail_closed_ceiling_hours,
                "snapshot_age_hours": snapshot_age_hours,
            },
        )
        return await self._persist_response(run_id=run_id, request=request, response=response)

    async def _read_fetch(
        self, *, request: RunScopeRequest, run_id: str, meta: WindmillMetadata, snapshot_id: str
    ) -> CommandResponse:
        reused = await self._reuse_if_idempotent(
            command="read_fetch",
            request=request,
        )
        if reused:
            return await self._enforce_reader_substance_on_reuse(reused=reused)
        snapshot = await self.db._fetchrow(
            "SELECT snapshot_payload FROM search_result_snapshots WHERE id = $1::uuid",
            snapshot_id,
        )
        payload = list(_db_json(snapshot["snapshot_payload"], []) if snapshot else [])
        if not payload:
            response = CommandResponse(
                command="read_fetch",
                status="blocked",
                decision_reason="no_candidate_urls",
                retry_class="insufficient_evidence",
                refs={"windmill_run_id": meta.run_id, "windmill_job_id": meta.job_id},
            )
            return await self._persist_response(run_id=run_id, request=request, response=response)

        if not self.zai_api_key or self.reader_client is None:
            response = CommandResponse(
                command="read_fetch",
                status="failed_terminal",
                decision_reason="reader_provider_unavailable",
                retry_class="provider_unavailable",
                alerts=["reader_error:missing_reader_runtime"],
                refs={"windmill_run_id": meta.run_id, "windmill_job_id": meta.job_id},
            )
            return await self._persist_response(run_id=run_id, request=request, response=response)

        search_items = [
            SearchResultItem(
                url=str(item.get("url", item.get("link", ""))).strip(),
                title=str(item.get("title", "")).strip(),
                snippet=str(item.get("snippet", "")).strip(),
            )
            for item in payload
            if str(item.get("url", item.get("link", ""))).strip()
        ]
        ranked_candidates = rank_reader_candidates(
            search_items,
            max_candidates=READ_FETCH_MAX_CANDIDATES,
            query_context=request.search_query,
        )
        if not ranked_candidates:
            response = CommandResponse(
                command="read_fetch",
                status="blocked",
                decision_reason="no_candidate_urls",
                retry_class="insufficient_evidence",
                refs={"windmill_run_id": meta.run_id, "windmill_job_id": meta.job_id},
            )
            return await self._persist_response(run_id=run_id, request=request, response=response)

        reader_quality_failures: list[dict[str, Any]] = []
        reader_provider_errors: list[dict[str, Any]] = []
        candidate_audit: list[dict[str, Any]] = []

        def _quality_alerts() -> list[str]:
            alerts: list[str] = []
            for item in reader_quality_failures:
                reason = str(item.get("reason", "")).strip()
                if reason == "prefetch_skipped_low_value_portal":
                    alerts.append("reader_prefetch_skipped_low_value_portal")
                elif reason == "fallback_blocked_after_official_reader_errors":
                    alerts.append("reader_fallback_blocked_after_official_reader_errors")
                elif reason:
                    alerts.append(f"reader_output_insufficient_substance:{reason}")
            return alerts

        for candidate in ranked_candidates:
            url = str(candidate["url"])
            official_artifact_provider_error_seen = any(
                bool(item.get("candidate_is_official_artifact")) for item in reader_provider_errors
            )
            skip_reason = prefetch_skip_reason(url)
            if skip_reason:
                reader_quality_failures.append(
                    {
                        "url": url,
                        "rank": candidate["rank"],
                        "score": candidate["score"],
                        "reason": "prefetch_skipped_low_value_portal",
                        "quality_details": {"skip_signal": skip_reason},
                    }
                )
                candidate_audit.append(
                    {
                        "url": url,
                        "rank": candidate["rank"],
                        "score": candidate["score"],
                        "outcome": "reader_prefetch_skipped_low_value_portal",
                        "reason": skip_reason,
                    }
                )
                continue
            fallback_candidate = SearchResultItem(
                url=url,
                title=str(candidate.get("title", "")),
                snippet=str(candidate.get("snippet", "")),
            )
            if (
                request.source_family == "meeting_minutes"
                and official_artifact_provider_error_seen
                and _is_weak_reader_fallback_candidate(fallback_candidate)
            ):
                reader_quality_failures.append(
                    {
                        "url": url,
                        "rank": candidate["rank"],
                        "score": candidate["score"],
                        "reason": "fallback_blocked_after_official_reader_errors",
                        "quality_details": {
                            "source_family": request.source_family,
                            "official_artifact_provider_error_seen": True,
                        },
                    }
                )
                candidate_audit.append(
                    {
                        "url": url,
                        "rank": candidate["rank"],
                        "score": candidate["score"],
                        "outcome": "reader_fallback_blocked_after_official_reader_errors",
                    }
                )
                continue
            try:
                reader_payload = await self.reader_client.fetch_content(url, timeout=60)
            except Exception as exc:
                err = str(exc)
                candidate_is_official_artifact = _is_concrete_artifact_url(url)
                reader_provider_errors.append(
                    {
                        "url": url,
                        "rank": candidate["rank"],
                        "score": candidate["score"],
                        "error": err,
                        "candidate_is_official_artifact": candidate_is_official_artifact,
                    }
                )
                candidate_audit.append(
                    {
                        "url": url,
                        "rank": candidate["rank"],
                        "score": candidate["score"],
                        "outcome": "reader_provider_error",
                        "error": err,
                        "candidate_is_official_artifact": candidate_is_official_artifact,
                    }
                )
                continue

            data_block = reader_payload.get("reader_result", reader_payload)
            markdown_body = str(data_block.get("content", "")).strip()
            title = str(data_block.get("title", "")).strip() or "Untitled"
            canonical_url = str(data_block.get("url", url)).strip() or url

            is_substantive, quality_details = assess_reader_substance(markdown_body)
            if not is_substantive:
                reason = str(quality_details["reason"])
                reader_quality_failures.append(
                    {
                        "url": canonical_url,
                        "rank": candidate["rank"],
                        "score": candidate["score"],
                        "reason": reason,
                        "quality_details": quality_details,
                    }
                )
                candidate_audit.append(
                    {
                        "url": canonical_url,
                        "rank": candidate["rank"],
                        "score": candidate["score"],
                        "outcome": "reader_output_insufficient_substance",
                        "reason": reason,
                    }
                )
                continue

            canonical_key = build_v2_canonical_document_key(
                jurisdiction_id=request.jurisdiction,
                source_family=request.source_family,
                url=canonical_url,
                metadata={"document_type": "meeting_minutes", "title": title},
                data={},
            )
            content_hash = sha256_text(markdown_body)
            artifact_ref = await self._store_artifact(
                request=request,
                content_hash=content_hash,
                media_type="text/markdown",
                body=markdown_body,
            )
            source_id = await self.db.get_or_create_source(
                request.jurisdiction,
                name=f"{request.jurisdiction}-{request.source_family}",
                type=request.source_family,
                url=canonical_url,
            )
            if not source_id:
                raise RuntimeError("source_create_failed")

            raw_row = await self.db._fetchrow(
                """
                SELECT id, document_id, COALESCE(metadata, '{}'::jsonb) AS metadata
                FROM raw_scrapes
                WHERE canonical_document_key = $1 AND content_hash = $2
                ORDER BY created_at DESC
                LIMIT 1
                """,
                canonical_key,
                content_hash,
            )
            raw_scrape_id: str
            document_id: str
            if raw_row:
                raw_scrape_id = str(raw_row["id"])
                document_id = str(raw_row["document_id"]) if raw_row["document_id"] else _stable_uuid(
                    canonical_key, content_hash, "document"
                )
                await self.db._execute(
                    """
                    UPDATE raw_scrapes
                    SET document_id = $1::uuid,
                        storage_uri = $2,
                        processed = COALESCE(processed, false),
                        metadata = COALESCE(metadata, '{}'::jsonb) || $3::jsonb,
                        last_seen_at = NOW(),
                        seen_count = COALESCE(seen_count, 0) + 1
                    WHERE id = $4::uuid
                    """,
                    document_id,
                    artifact_ref,
                    _json({"bridge_kind": "reader_output", "title": title}),
                    raw_scrape_id,
                )
            else:
                raw_scrape_id = _stable_uuid(canonical_key, content_hash, "raw")
                document_id = _stable_uuid(canonical_key, content_hash, "document")
                await self.db._execute(
                    """
                    INSERT INTO raw_scrapes
                      (id, source_id, content_hash, content_type, data, url, metadata, storage_uri,
                       document_id, canonical_document_key, processed, created_at, last_seen_at, seen_count)
                    VALUES
                      ($1::uuid, $2::uuid, $3, $4, $5::jsonb, $6, $7::jsonb, $8,
                       $9::uuid, $10, false, NOW(), NOW(), 1)
                    """,
                    raw_scrape_id,
                    source_id,
                    content_hash,
                    "text/markdown",
                    _json({"content": markdown_body}),
                    canonical_url,
                    _json({"bridge_kind": "reader_output", "title": title}),
                    artifact_ref,
                    document_id,
                    canonical_key,
                )

            candidate_audit.append(
                {
                    "url": canonical_url,
                    "rank": candidate["rank"],
                    "score": candidate["score"],
                    "outcome": "materialized_raw_scrape",
                    "raw_scrape_id": raw_scrape_id,
                }
            )
            alerts = [
                *_quality_alerts(),
                *[f"reader_error:{item['error']}" for item in reader_provider_errors],
            ]
            response = CommandResponse(
                command="read_fetch",
                status="succeeded_with_alerts" if alerts else "succeeded",
                decision_reason=(
                    "raw_scrapes_materialized_with_reader_alerts" if alerts else "raw_scrapes_materialized"
                ),
                retry_class="none",
                alerts=list(dict.fromkeys(alerts)),
                counts={"raw_scrapes": 1, "artifacts": 1},
                refs={
                    "windmill_run_id": meta.run_id,
                    "windmill_job_id": meta.job_id,
                    "raw_scrape_ids": [raw_scrape_id],
                    "artifact_refs": [artifact_ref],
                    "document_id": document_id,
                },
                details={
                    "candidate_audit": candidate_audit,
                    "ranked_candidates": ranked_candidates,
                    "reader_provider_errors": reader_provider_errors,
                    "reader_quality_failures": reader_quality_failures,
                },
            )
            return await self._persist_response(run_id=run_id, request=request, response=response)

        alerts = [
            *_quality_alerts(),
            *[f"reader_error:{item['error']}" for item in reader_provider_errors],
        ]
        if reader_provider_errors:
            response = CommandResponse(
                command="read_fetch",
                status="failed_retryable",
                decision_reason="reader_provider_error",
                retry_class="provider_unavailable",
                alerts=list(dict.fromkeys(alerts)),
                refs={"windmill_run_id": meta.run_id, "windmill_job_id": meta.job_id},
                details={
                    "candidate_audit": candidate_audit,
                    "ranked_candidates": ranked_candidates,
                    "reader_provider_errors": reader_provider_errors,
                    "reader_quality_failures": reader_quality_failures,
                },
            )
            return await self._persist_response(run_id=run_id, request=request, response=response)

        response = CommandResponse(
            command="read_fetch",
            status="blocked",
            decision_reason="reader_output_insufficient_substance",
            retry_class="insufficient_evidence",
            alerts=list(dict.fromkeys(alerts)) or ["reader_output_insufficient_substance"],
            refs={"windmill_run_id": meta.run_id, "windmill_job_id": meta.job_id},
            details={
                "candidate_audit": candidate_audit,
                "ranked_candidates": ranked_candidates,
                "reader_quality_failures": reader_quality_failures,
            },
        )
        return await self._persist_response(run_id=run_id, request=request, response=response)

    async def _store_artifact(
        self,
        *,
        request: RunScopeRequest,
        content_hash: str,
        media_type: str,
        body: str,
    ) -> str:
        existing = await self.db._fetchrow(
            """
            SELECT storage_uri
            FROM content_artifacts
            WHERE jurisdiction_id = $1
              AND source_family = $2
              AND artifact_kind = 'reader_output'
              AND content_hash = $3
            LIMIT 1
            """,
            request.jurisdiction,
            request.source_family,
            content_hash,
        )
        if existing and existing["storage_uri"]:
            return str(existing["storage_uri"])

        object_key = build_artifact_object_key(
            contract_version=request.contract_version,
            jurisdiction_id=request.jurisdiction,
            source_family=request.source_family,
            artifact_kind="reader_output",
            content_hash=content_hash,
            media_type=media_type,
        )
        uri = await self.storage.upload(
            object_key,
            body.encode("utf-8"),
            content_type=media_type,
        )
        await self.db._execute(
            """
            INSERT INTO content_artifacts
              (jurisdiction_id, source_family, artifact_kind, content_hash, storage_uri,
               media_type, size_bytes, contract_version)
            VALUES
              ($1, $2, 'reader_output', $3, $4, $5, $6, $7)
            ON CONFLICT (jurisdiction_id, source_family, artifact_kind, content_hash)
            DO UPDATE SET
              storage_uri = EXCLUDED.storage_uri,
              media_type = EXCLUDED.media_type,
              size_bytes = EXCLUDED.size_bytes,
              contract_version = EXCLUDED.contract_version,
              last_seen_at = NOW(),
              seen_count = content_artifacts.seen_count + 1
            """,
            request.jurisdiction,
            request.source_family,
            content_hash,
            uri,
            media_type,
            len(body.encode("utf-8")),
            request.contract_version,
        )
        return uri

    async def _index(
        self,
        *,
        request: RunScopeRequest,
        run_id: str,
        meta: WindmillMetadata,
        raw_scrape_ids: list[str],
    ) -> CommandResponse:
        reused = await self._reuse_if_idempotent(command="index", request=request)
        if reused:
            return reused
        if not raw_scrape_ids:
            response = CommandResponse(
                command="index",
                status="blocked",
                decision_reason="no_raw_scrapes",
                retry_class="insufficient_evidence",
                refs={"windmill_run_id": meta.run_id, "windmill_job_id": meta.job_id},
            )
            return await self._persist_response(run_id=run_id, request=request, response=response)

        raw_row = await self.db._fetchrow(
            """
            SELECT id, document_id, content_hash, canonical_document_key,
                   COALESCE(data, '{}'::jsonb) AS data, storage_uri
            FROM raw_scrapes
            WHERE id = $1::uuid
            LIMIT 1
            """,
            raw_scrape_ids[0],
        )
        if not raw_row:
            response = CommandResponse(
                command="index",
                status="blocked",
                decision_reason="no_raw_scrapes",
                retry_class="insufficient_evidence",
                refs={"windmill_run_id": meta.run_id, "windmill_job_id": meta.job_id},
            )
            return await self._persist_response(run_id=run_id, request=request, response=response)

        raw_scrape_id = str(raw_row["id"])
        document_id = str(raw_row["document_id"])
        content_hash = str(raw_row["content_hash"])
        canonical_key = str(raw_row["canonical_document_key"])
        data = dict(_db_json(raw_row["data"], {}) or {})
        markdown_body = str(data.get("content", "")).strip()
        chunks = chunk_markdown_lines(markdown_body)
        embeddings: list[Any | None] = [None] * len(chunks)
        index_alerts: list[str] = []
        if chunks and self.embedding_service:
            try:
                generated_embeddings = await self.embedding_service.embed_documents(chunks)
                embeddings = list(generated_embeddings)
                if len(embeddings) != len(chunks):
                    index_alerts.append("embedding_count_mismatch")
                    embeddings = (embeddings + [None] * len(chunks))[: len(chunks)]
            except Exception as exc:  # noqa: BLE001
                index_alerts.append(f"embedding_generation_failed:{type(exc).__name__}")
                embeddings = [None] * len(chunks)
        elif chunks:
            index_alerts.append("embedding_provider_unavailable")

        chunk_count = 0
        for idx, text in enumerate(chunks):
            chunk_id = _stable_uuid(canonical_key, content_hash, str(idx), text)
            embedding = embeddings[idx] if idx < len(embeddings) else None
            embedding_value = str(embedding) if embedding is not None else None
            await self.db._execute(
                """
                INSERT INTO document_chunks (id, document_id, content, embedding, metadata, chunk_index, source)
                VALUES ($1::uuid, $2::uuid, $3, $4::vector, $5::jsonb, $6, $7)
                ON CONFLICT (id) DO UPDATE SET
                  content = EXCLUDED.content,
                  embedding = EXCLUDED.embedding,
                  metadata = EXCLUDED.metadata,
                  chunk_index = EXCLUDED.chunk_index,
                  source = EXCLUDED.source
                """,
                chunk_id,
                document_id,
                text,
                embedding_value,
                _json(
                    {
                        "canonical_document_key": canonical_key,
                        "raw_scrape_id": raw_scrape_id,
                        "content_hash": content_hash,
                        "artifact_ref": raw_row["storage_uri"],
                        "jurisdiction_id": request.jurisdiction,
                        "source_family": request.source_family,
                        "contract_version": request.contract_version,
                    }
                ),
                idx,
                "pipeline_domain_bridge",
            )
            chunk_count += 1

        await self.db._execute(
            """
            UPDATE raw_scrapes
            SET processed = true,
                metadata = COALESCE(metadata, '{}'::jsonb) || $1::jsonb
            WHERE id = $2::uuid
            """,
            _json({"chunk_count": chunk_count}),
            raw_scrape_id,
        )

        response = CommandResponse(
            command="index",
            status="succeeded_with_alerts" if index_alerts else "succeeded",
            decision_reason="chunks_indexed",
            retry_class="none",
            alerts=index_alerts,
            counts={"chunks": chunk_count},
            refs={
                "windmill_run_id": meta.run_id,
                "windmill_job_id": meta.job_id,
                "raw_scrape_ids": [raw_scrape_id],
                "document_id": document_id,
            },
            details={
                "embedding_provider": "openrouter:qwen/qwen3-embedding-8b" if self.embedding_service else None,
                "embedding_count": sum(1 for item in embeddings if item is not None),
            },
        )
        return await self._persist_response(run_id=run_id, request=request, response=response)

    async def _analyze(
        self,
        *,
        request: RunScopeRequest,
        run_id: str,
        meta: WindmillMetadata,
        document_id: str,
    ) -> CommandResponse:
        reused = await self._reuse_if_idempotent(command="analyze", request=request)
        if reused:
            return reused
        if not document_id:
            response = CommandResponse(
                command="analyze",
                status="blocked",
                decision_reason="no_evidence_chunks",
                retry_class="insufficient_evidence",
                counts={"evidence_chunks": 0},
                refs={"windmill_run_id": meta.run_id, "windmill_job_id": meta.job_id},
            )
            return await self._persist_response(run_id=run_id, request=request, response=response)

        rows = await self.db._fetch(
            """
            SELECT id, content, chunk_index
            FROM document_chunks
            WHERE document_id = $1::uuid
            ORDER BY chunk_index
            LIMIT $2
            """,
            document_id,
            ANALYZE_CANDIDATE_CHUNK_LIMIT,
        )
        candidate_chunks = [
            {
                "chunk_id": str(row["id"]) if row["id"] is not None else None,
                "chunk_index": int(row["chunk_index"]),
                "content": str(row["content"]),
                "document_id": str(document_id),
            }
            for row in rows
        ]
        selected_chunks, evidence_audit = rank_evidence_chunks(
            question=request.analysis_question,
            chunks=candidate_chunks,
            max_selected=ANALYZE_SELECTED_CHUNK_LIMIT,
        )
        evidence_chunks = [str(chunk.get("content", "")) for chunk in selected_chunks]
        if not evidence_chunks:
            response = CommandResponse(
                command="analyze",
                status="blocked",
                decision_reason="no_evidence_chunks",
                retry_class="insufficient_evidence",
                counts={"evidence_chunks": 0},
                refs={"windmill_run_id": meta.run_id, "windmill_job_id": meta.job_id},
            )
            return await self._persist_response(run_id=run_id, request=request, response=response)
        if not self._llm_client:
            fail_closed_analysis = self._provider_unavailable_analysis_payload(
                request=request,
                reason="analysis_provider_unavailable",
                evidence_audit=evidence_audit,
                evidence_chunk_count=len(evidence_chunks),
            )
            response = CommandResponse(
                command="analyze",
                status="succeeded_with_alerts",
                decision_reason="analysis_provider_unavailable",
                retry_class="provider_unavailable",
                alerts=[
                    "analysis_provider_unavailable",
                    "analysis_fail_closed_provider_unavailable",
                    "canonical_llm_narrative_not_proven",
                    "analysis_error:missing_zai_api_key",
                ],
                counts={"evidence_chunks": len(evidence_chunks)},
                refs={"windmill_run_id": meta.run_id, "windmill_job_id": meta.job_id},
                details={
                    "analysis": fail_closed_analysis,
                    "evidence_selection": {
                        "candidate_chunk_count": len(candidate_chunks),
                        "selected_chunk_count": len(evidence_chunks),
                        "selected_chunks": evidence_audit,
                    }
                },
            )
            return await self._persist_response(run_id=run_id, request=request, response=response)

        prompt = (
            "You are a policy analyst. Produce strict JSON with keys: "
            "summary, key_points (array of strings), sufficiency_state. "
            "Question:\n"
            f"{request.analysis_question}\n\n"
            "Evidence:\n"
            f"{chr(10).join(evidence_chunks[:10])}"
        )
        try:
            completion = await self._llm_client.chat.completions.create(
                model=self.zai_model,
                messages=[
                    {"role": "system", "content": "Return valid JSON only."},
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
            )
            content = completion.choices[0].message.content or "{}"
            parsed = json.loads(content)
            analysis_id = _stable_uuid(
                _scope_idempotency_key(request),
                request.jurisdiction,
                request.source_family,
                _hash(content),
            )
            response = CommandResponse(
                command="analyze",
                status="succeeded",
                decision_reason="analysis_completed",
                retry_class="none",
                counts={"analyses": 1, "evidence_chunks": len(evidence_chunks)},
                refs={
                    "windmill_run_id": meta.run_id,
                    "windmill_job_id": meta.job_id,
                    "analysis_id": analysis_id,
                },
                details={
                    "analysis": parsed,
                    "evidence_selection": {
                        "candidate_chunk_count": len(candidate_chunks),
                        "selected_chunk_count": len(evidence_chunks),
                        "selected_chunks": evidence_audit,
                    },
                },
            )
            return await self._persist_response(run_id=run_id, request=request, response=response)
        except Exception as exc:
            fail_closed_analysis = self._provider_unavailable_analysis_payload(
                request=request,
                reason="analysis_provider_unavailable",
                evidence_audit=evidence_audit,
                evidence_chunk_count=len(evidence_chunks),
            )
            response = CommandResponse(
                command="analyze",
                status="succeeded_with_alerts",
                decision_reason="analysis_provider_unavailable",
                retry_class="provider_unavailable",
                alerts=[
                    "analysis_provider_unavailable",
                    "analysis_fail_closed_provider_unavailable",
                    "canonical_llm_narrative_not_proven",
                    f"analysis_error:{exc}",
                ],
                counts={"evidence_chunks": len(evidence_chunks)},
                refs={"windmill_run_id": meta.run_id, "windmill_job_id": meta.job_id},
                details={
                    "analysis": fail_closed_analysis,
                    "evidence_selection": {
                        "candidate_chunk_count": len(candidate_chunks),
                        "selected_chunk_count": len(evidence_chunks),
                        "selected_chunks": evidence_audit,
                    }
                },
            )
            return await self._persist_response(run_id=run_id, request=request, response=response)

    @staticmethod
    def _provider_unavailable_analysis_payload(
        *,
        request: RunScopeRequest,
        reason: str,
        evidence_audit: list[dict[str, Any]],
        evidence_chunk_count: int,
    ) -> dict[str, Any]:
        return {
            "summary": "Economic analysis failed closed because the canonical LLM provider was unavailable.",
            "key_points": [
                "Evidence was ingested and selected for analysis, but no canonical model output was produced.",
                "This run is not decision-grade and requires a provider-healthy rerun before quantitative conclusions.",
            ],
            "sufficiency_state": "provider_unavailable",
            "analysis_mode": "fail_closed_provider_unavailable",
            "analysis_not_proven": True,
            "canonical_llm_narrative_proven": False,
            "decision_reason": reason,
            "requested_analysis_question": request.analysis_question,
            "evidence_chunk_count": evidence_chunk_count,
            "evidence_refs": [
                {
                    "chunk_id": chunk.get("chunk_id"),
                    "chunk_index": chunk.get("chunk_index"),
                    "score": chunk.get("score"),
                    "snippet": chunk.get("snippet"),
                }
                for chunk in evidence_audit
            ],
            "alerts": [
                "analysis_provider_unavailable",
                "analysis_fail_closed_provider_unavailable",
                "canonical_llm_narrative_not_proven",
            ],
        }

    async def _summarize(
        self,
        *,
        request: RunScopeRequest,
        run_id: str,
        meta: WindmillMetadata,
        command_responses: list[CommandResponse],
    ) -> CommandResponse:
        counts: dict[str, int] = {}
        refs: dict[str, Any] = {"windmill_run_id": meta.run_id, "windmill_job_id": meta.job_id}
        alerts: list[str] = []
        statuses: list[str] = []
        step_map: dict[str, str] = {}
        for result in command_responses:
            statuses.append(result.status)
            alerts.extend(result.alerts)
            for key, value in result.counts.items():
                counts[key] = counts.get(key, 0) + value
            step_map[result.command] = result.status
            refs[f"{result.command}_reason"] = result.decision_reason
            refs[f"{result.command}_retry_class"] = result.retry_class

        summary_status = "succeeded"
        if any(status == "failed_terminal" for status in statuses):
            summary_status = "failed_terminal"
        elif any(status == "failed_retryable" for status in statuses):
            summary_status = "failed_retryable"
        elif any(status == "blocked" for status in statuses):
            summary_status = "blocked"
        elif any(status == "succeeded_with_alerts" for status in statuses):
            summary_status = "succeeded_with_alerts"

        response = CommandResponse(
            command="summarize_run",
            status=summary_status,  # type: ignore[arg-type]
            decision_reason="run_summary_materialized",
            retry_class="none" if summary_status.startswith("succeeded") else "operator_required",
            alerts=list(dict.fromkeys(alerts)),
            counts=counts,
            refs=refs | {"run_id": run_id},
            details={"step_statuses": step_map},
        )
        return await self._persist_response(run_id=run_id, request=request, response=response)

    @staticmethod
    def _step_payload(response: CommandResponse, request: RunScopeRequest) -> dict[str, Any]:
        payload = response.to_dict()
        payload["envelope"] = {
            "contract_version": request.contract_version,
            "orchestrator": "windmill",
            "idempotency_key": request.idempotency_key,
            "scope_idempotency_key": _scope_idempotency_key(request),
            "jurisdiction": request.jurisdiction,
            "source_family": request.source_family,
            "stale_status": request.stale_status,
            "windmill_workspace": request.windmill_workspace,
            "windmill_flow_path": request.windmill_flow_path,
            "windmill_run_id": request.windmill_run_id,
            "windmill_job_id": request.windmill_job_id,
            "search_query": request.search_query,
            "analysis_question": request.analysis_question,
        }
        return payload


class PipelineDomainBridge:
    """Coarse backend command bridge used by internal orchestration callers."""

    def __init__(
        self,
        *,
        state: InMemoryDomainState | None = None,
        db: PostgresDB | None = None,
        storage: S3Storage | None = None,
    ) -> None:
        self._lock = Lock()
        self.state = state or InMemoryDomainState()
        self.db = db
        self.storage = storage
        self.runtime = None
        if self.db and self.storage:
            self.runtime = RailwayRuntimeBridge(db=self.db, storage=self.storage)

    async def run_scope_pipeline(self, request: RunScopeRequest) -> dict[str, Any]:
        self._validate_request(request)
        runtime_missing = self._missing_runtime_adapters()
        if not runtime_missing and self.runtime:
            return await self.runtime.run_scope_pipeline(request)
        return self._run_in_memory_pipeline(request=request, runtime_missing=runtime_missing)

    def _run_in_memory_pipeline(
        self, *, request: RunScopeRequest, runtime_missing: list[str]
    ) -> dict[str, Any]:
        with self._lock:
            self.state.now = _utc_now()
            service = self._build_service(
                jurisdiction=request.jurisdiction,
                source_family=request.source_family,
                search_query=request.search_query,
                stale_status=request.stale_status,
            )
            policy = FreshnessPolicy(
                fresh_hours=24,
                stale_usable_ceiling_hours=72,
                fail_closed_ceiling_hours=168,
            )
            meta = WindmillMetadata(
                run_id=request.windmill_run_id,
                job_id=request.windmill_job_id,
                workspace=request.windmill_workspace,
                flow_path=request.windmill_flow_path,
            )

            search = service.search_materialize(
                envelope=self._envelope("search_materialize", request, meta),
                query=request.search_query,
            )
            snapshot_id = str(search.refs.get("search_snapshot_id", ""))
            latest_success_at = self._apply_stale_status_overrides(
                request=request,
                snapshot_id=snapshot_id,
            )
            freshness = service.freshness_gate(
                envelope=self._envelope("freshness_gate", request, meta),
                snapshot_id=snapshot_id,
                policy=policy,
                latest_success_at=latest_success_at,
            )
            responses: list[CommandResponse] = [search, freshness]

            if freshness.decision_reason not in {"stale_blocked", "empty_blocked"}:
                read_fetch = service.read_fetch(
                    envelope=self._envelope("read_fetch", request, meta),
                    snapshot_id=snapshot_id,
                )
                responses.append(read_fetch)
                if read_fetch.status in {"succeeded", "succeeded_with_alerts", "skipped"}:
                    index = service.index(
                        envelope=self._envelope("index", request, meta),
                        raw_scrape_ids=list(read_fetch.refs.get("raw_scrape_ids", [])),
                    )
                    responses.append(index)
                    analyze = service.analyze(
                        envelope=self._envelope("analyze", request, meta),
                        question=request.analysis_question,
                        jurisdiction_id=request.jurisdiction,
                        source_family=request.source_family,
                    )
                    responses.append(analyze)

            summary = service.summarize_run(
                envelope=self._envelope("summarize_run", request, meta),
                command_responses=responses,
            )
            responses.append(summary)

            steps = {response.command: self._step_payload(response, request) for response in responses}
            return {
                "contract_version": CONTRACT_VERSION,
                "command": "run_scope_pipeline",
                "status": summary.status,
                "decision_reason": summary.decision_reason,
                "idempotency_key": request.idempotency_key,
                "jurisdiction": request.jurisdiction,
                "source_family": request.source_family,
                "stale_status": freshness.decision_reason,
                "stale_status_requested": request.stale_status,
                "windmill_workspace": request.windmill_workspace,
                "windmill_flow_path": request.windmill_flow_path,
                "windmill_run_id": request.windmill_run_id,
                "windmill_job_id": request.windmill_job_id,
                "search_query": request.search_query,
                "analysis_question": request.analysis_question,
                "alerts": summary.alerts,
                "counts": summary.counts,
                "refs": summary.refs,
                "steps": steps,
                "storage_mode": "in_memory_domain_ports",
                "missing_runtime_adapters": runtime_missing,
            }

    def _missing_runtime_adapters(self) -> list[str]:
        missing: list[str] = []
        if not self.db:
            missing.extend(
                [
                    "postgres_pipeline_state_store_adapter",
                    "pgvector_chunk_store_adapter",
                ]
            )
        if not self.storage:
            missing.append("minio_artifact_store_adapter")
        if not os.getenv("ZAI_API_KEY", "").strip():
            missing.extend(["zai_direct_reader_adapter", "zai_llm_analysis_adapter"])
        return missing

    def _build_service(
        self,
        *,
        jurisdiction: str,
        source_family: str,
        search_query: str,
        stale_status: str,
    ) -> PipelineDomainCommands:
        search_results: list[SearchResultItem] = []
        if stale_status not in {"empty_but_usable", "empty_blocked"}:
            doc_slug = f"{jurisdiction}/{source_family}".replace(" ", "-").lower()
            search_results = [
                SearchResultItem(
                    url=f"https://www.sanjoseca.gov/{doc_slug}/2026-04-10",
                    title="San Jose Meeting Minutes",
                    snippet=search_query,
                )
            ]

        return PipelineDomainCommands(
            state=self.state,
            search_provider=InMemorySearchProvider(results=search_results),
            reader_provider=InMemoryReaderProvider(),
            artifact_store=InMemoryArtifactStore(self.state),
            vector_store=InMemoryVectorStore(self.state),
            analyzer=InMemoryAnalyzer(),
        )

    def _apply_stale_status_overrides(
        self,
        *,
        request: RunScopeRequest,
        snapshot_id: str,
    ) -> datetime | None:
        if not snapshot_id or snapshot_id not in self.state.search_snapshots:
            return None

        snapshot = self.state.search_snapshots[snapshot_id]
        now = self.state.now
        if request.stale_status == "fresh":
            snapshot["captured_at"] = (now - timedelta(hours=1)).isoformat()
            return now - timedelta(hours=1)
        if request.stale_status == "stale_but_usable":
            snapshot["captured_at"] = (now - timedelta(hours=30)).isoformat()
            return now - timedelta(hours=10)
        if request.stale_status == "stale_blocked":
            snapshot["captured_at"] = (now - timedelta(hours=90)).isoformat()
            return now - timedelta(hours=10)
        if request.stale_status == "empty_but_usable":
            snapshot["captured_at"] = (now - timedelta(hours=1)).isoformat()
            snapshot["results"] = []
            return now - timedelta(hours=6)
        if request.stale_status == "empty_blocked":
            snapshot["captured_at"] = (now - timedelta(hours=1)).isoformat()
            snapshot["results"] = []
            return now - timedelta(hours=200)
        return None

    def _envelope(
        self,
        command: str,
        request: RunScopeRequest,
        windmill: WindmillMetadata,
    ) -> CommandEnvelope:
        return CommandEnvelope(
            command=command,  # type: ignore[arg-type]
            jurisdiction_id=request.jurisdiction,
            source_family=request.source_family,
            idempotency_key=_scope_idempotency_key(request),
            windmill=windmill,
            contract_version=request.contract_version,
        )

    def _step_payload(self, response: CommandResponse, request: RunScopeRequest) -> dict[str, Any]:
        payload = response.to_dict()
        payload["envelope"] = {
            "contract_version": request.contract_version,
            "orchestrator": "windmill",
            "idempotency_key": request.idempotency_key,
            "scope_idempotency_key": _scope_idempotency_key(request),
            "jurisdiction": request.jurisdiction,
            "source_family": request.source_family,
            "stale_status": request.stale_status,
            "windmill_workspace": request.windmill_workspace,
            "windmill_flow_path": request.windmill_flow_path,
            "windmill_run_id": request.windmill_run_id,
            "windmill_job_id": request.windmill_job_id,
            "search_query": request.search_query,
            "analysis_question": request.analysis_question,
        }
        return payload

    def _validate_request(self, request: RunScopeRequest) -> None:
        if request.contract_version != CONTRACT_VERSION:
            raise ValueError(
                f"contract_version mismatch: expected {CONTRACT_VERSION}, got {request.contract_version}"
            )
        if request.stale_status not in ALLOWED_STALE_STATUSES:
            raise ValueError(f"unsupported stale_status: {request.stale_status}")
