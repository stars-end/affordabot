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
from services.revision_identity import normalize_canonical_url
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
_ECONOMIC_SELECTION_QUERY_SIGNALS = (
    "commercial linkage",
    "impact fee",
    "fee schedule",
    "fees",
    "rates",
    "per square foot",
    "per sq ft",
    "nexus",
)
_SAN_JOSE_OFFICIAL_HOST_SIGNALS = (
    "sanjoseca.gov",
    "sanjose.legistar.com",
    "webapi.legistar.com",
)
_POLICY_IDENTITY_SIGNALS = (
    "commercial linkage fee",
    "commercial linkage",
    " matter 7526",
    "matter/7526",
    "matter=7526",
    "matters/7526",
    "clf",
    "nexus study",
    "fee schedule",
)
_POLICY_LINEAGE_SIGNALS = (
    "ordinance",
    "resolution",
    "fee schedule",
    "nexus study",
    "attachment",
)

_IDENTITY_LINKED_ATTACHMENT_FAMILIES = {
    "ordinance",
    "resolution",
    "memorandum",
    "staff_report",
    "fee_study",
    "nexus_study",
    "feasibility_study",
    "fee_schedule",
}
_JURISDICTION_BLOCKLIST_SIGNALS = ("los altos",)


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
        selected_candidate_context: str = "",
    ) -> StructuredEnrichmentResult:
        _ = (jurisdiction, source_family, search_query, selected_url, selected_candidate_context)
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

    @staticmethod
    def _structured_candidate_context(
        *,
        search_query: str,
        selected_url: str,
        ranked_candidates: list[dict[str, Any]],
    ) -> str:
        parts: list[str] = [search_query.strip()]
        selected: dict[str, Any] | None = None
        for candidate in ranked_candidates:
            if not isinstance(candidate, dict):
                continue
            if str(candidate.get("url") or "").strip() == selected_url:
                selected = candidate
                break
        if selected is None and ranked_candidates and isinstance(ranked_candidates[0], dict):
            selected = ranked_candidates[0]
        if selected:
            for key in ("title", "snippet", "query_context"):
                value = str(selected.get(key) or "").strip()
                if value:
                    parts.append(value)
        parts.append(selected_url.strip())
        return " ".join(part for part in parts if part)

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
    def _selected_candidate_audit_entry(
        *,
        candidate_audit: list[dict[str, Any]],
        selected_url: str,
    ) -> dict[str, Any] | None:
        for item in candidate_audit:
            if str(item.get("url") or "").strip() == selected_url:
                return item
        return None

    @staticmethod
    def _is_economic_selection_query(query_text: str) -> bool:
        lowered = str(query_text or "").strip().lower()
        if not lowered:
            return False
        return any(signal in lowered for signal in _ECONOMIC_SELECTION_QUERY_SIGNALS)

    @staticmethod
    def _normalize_identity_url(url: str) -> str:
        normalized = normalize_canonical_url(str(url or "").strip())
        if normalized:
            return normalized
        return str(url or "").strip().lower()

    @classmethod
    def _candidate_identity_hint_score(
        cls,
        *,
        query_text: str,
        candidate: dict[str, Any],
    ) -> int:
        del query_text
        combined = " ".join(
            [
                str(candidate.get("url") or "").strip(),
                str(candidate.get("title") or "").strip(),
                str(candidate.get("snippet") or "").strip(),
            ]
        ).lower()
        score = 0
        if re.search(r"\bsan[\s\-]?jose\b", combined) or "sanjose" in combined:
            score += 2
        if any(signal in combined for signal in _POLICY_IDENTITY_SIGNALS):
            score += 2
        if any(signal in combined for signal in _POLICY_LINEAGE_SIGNALS):
            score += 1
        if any(signal in combined for signal in _JURISDICTION_BLOCKLIST_SIGNALS):
            score -= 3
        return score

    @classmethod
    def _prioritize_artifact_candidates_for_fetch(
        cls,
        *,
        ranked_candidates: list[dict[str, Any]],
        query_text: str,
    ) -> list[dict[str, Any]]:
        if not ranked_candidates:
            return ranked_candidates
        if not cls._is_economic_selection_query(query_text):
            return ranked_candidates
        has_artifact = any(
            _is_concrete_artifact_url(str(item.get("url") or ""))
            for item in ranked_candidates
        )
        has_official_page = any(
            cls._is_official_domain_url(str(item.get("url") or ""))
            and not _is_concrete_artifact_url(str(item.get("url") or ""))
            for item in ranked_candidates
        )
        if not has_artifact or not has_official_page:
            return ranked_candidates

        artifact_candidates = [
            item for item in ranked_candidates if _is_concrete_artifact_url(str(item.get("url") or ""))
        ]
        non_artifact_candidates = [
            item for item in ranked_candidates if not _is_concrete_artifact_url(str(item.get("url") or ""))
        ]
        artifact_candidates = sorted(
            artifact_candidates,
            key=lambda item: (
                cls._candidate_identity_hint_score(query_text=query_text, candidate=item),
                float(item.get("score") or 0.0),
            ),
            reverse=True,
        )
        non_artifact_candidates = sorted(
            non_artifact_candidates,
            key=lambda item: (
                cls._candidate_identity_hint_score(query_text=query_text, candidate=item),
                float(item.get("score") or 0.0),
            ),
            reverse=True,
        )
        best_artifact_score = (
            cls._candidate_identity_hint_score(query_text=query_text, candidate=artifact_candidates[0])
            if artifact_candidates
            else -99
        )
        best_non_artifact_score = (
            cls._candidate_identity_hint_score(query_text=query_text, candidate=non_artifact_candidates[0])
            if non_artifact_candidates
            else -99
        )
        # Fail-closed preference: if artifact candidates do not match identity signals but an
        # official non-artifact candidate does, read the identity-matching source first.
        if best_non_artifact_score > best_artifact_score and best_artifact_score <= 0:
            return [*non_artifact_candidates, *artifact_candidates]
        return [*artifact_candidates, *non_artifact_candidates]

    @classmethod
    def _evaluate_maintained_fee_schedule_gate(
        cls,
        *,
        url: str,
        title: str,
        snippet: str,
        markdown_body: str,
    ) -> dict[str, Any]:
        normalized_url = str(url or "").strip()
        if not normalized_url:
            return {
                "classified_as_maintained_fee_schedule": False,
                "passed": False,
                "reason": "missing_url",
                "authoritative_policy_text_ok": False,
            }
        if _is_concrete_artifact_url(normalized_url):
            return {
                "classified_as_maintained_fee_schedule": False,
                "passed": False,
                "reason": "concrete_artifact_url",
                "authoritative_policy_text_ok": False,
            }
        if not cls._is_official_domain_url(normalized_url):
            return {
                "classified_as_maintained_fee_schedule": False,
                "passed": False,
                "reason": "non_official_domain",
                "authoritative_policy_text_ok": False,
            }

        combined = " ".join(
            part.strip().lower()
            for part in (normalized_url, title, snippet, markdown_body[:3000])
            if part and part.strip()
        )
        classification_signals = (
            "commercial linkage fee",
            "impact fee",
            "fee schedule",
            "fees and rates",
            "per square foot",
            "per sq ft",
            "nexus study",
        )
        classified = any(signal in combined for signal in classification_signals)
        if not classified:
            return {
                "classified_as_maintained_fee_schedule": False,
                "passed": False,
                "reason": "missing_fee_schedule_signals",
                "authoritative_policy_text_ok": False,
            }

        currency_values = re.findall(r"\$[0-9]+(?:\.[0-9]{1,2})?", markdown_body)
        has_unit_signal = any(
            signal in combined for signal in ("per square foot", "per sq ft", "sq.ft", "sq ft")
        )
        has_current_context = bool(
            re.search(r"\b(20[2-4][0-9])\b", markdown_body)
            and re.search(r"\b(effective|updated|as of|adopted|current)\b", combined)
        )
        has_fee_table_substance = len(currency_values) >= 2 and has_unit_signal
        passed = has_fee_table_substance and has_current_context
        return {
            "classified_as_maintained_fee_schedule": True,
            "passed": passed,
            "reason": "passed" if passed else "insufficient_fee_table_substance_or_freshness",
            "currency_value_count": len(currency_values),
            "has_unit_signal": has_unit_signal,
            "has_current_context": has_current_context,
            # Fail-closed default: this page class does not imply authoritative policy text.
            "authoritative_policy_text_ok": False,
        }

    @classmethod
    def _candidate_artifact_family_from_audit_entry(
        cls,
        *,
        url: str,
        audit_entry: dict[str, Any] | None,
    ) -> str:
        normalized = str(url or "").strip()
        if not normalized:
            return "missing"
        if _is_concrete_artifact_url(normalized):
            return "artifact"
        if prefetch_skip_reason(normalized):
            return "portal"
        if cls._is_official_domain_url(normalized):
            if isinstance(audit_entry, dict):
                fee_schedule_gate = audit_entry.get("fee_schedule_gate")
                if (
                    isinstance(fee_schedule_gate, dict)
                    and bool(fee_schedule_gate.get("classified_as_maintained_fee_schedule"))
                    and bool(fee_schedule_gate.get("passed"))
                ):
                    return "maintained_fee_schedule"
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
    def _build_lineage_identity_context(
        cls,
        *,
        structured_candidates: list[dict[str, Any]],
    ) -> dict[str, Any]:
        linked_urls: set[str] = set()
        jurisdiction_signal_hits: set[str] = set()
        policy_signal_hits: set[str] = set()
        for candidate in structured_candidates:
            if not isinstance(candidate, dict):
                continue
            lineage_metadata = candidate.get("lineage_metadata")
            lineage_metadata = lineage_metadata if isinstance(lineage_metadata, dict) else {}
            matter_id = str(lineage_metadata.get("matter_id") or "").strip()
            artifact_url = str(candidate.get("artifact_url") or "").strip()
            candidate_text = " ".join(
                [
                    artifact_url,
                    str(candidate.get("source_family") or ""),
                    str(candidate.get("policy_match_key") or ""),
                    matter_id,
                    str(lineage_metadata.get("event_body_id") or ""),
                ]
            ).lower()
            if re.search(r"\bsan[\s\-]?jose\b", candidate_text) or "sanjose" in candidate_text:
                jurisdiction_signal_hits.add("lineage_san_jose_signal")
            if (
                matter_id == "7526"
                or any(signal in candidate_text for signal in _POLICY_IDENTITY_SIGNALS)
                or any(signal in candidate_text for signal in _POLICY_LINEAGE_SIGNALS)
            ):
                policy_signal_hits.add("lineage_policy_signal")
            if artifact_url:
                linked_urls.add(cls._normalize_identity_url(artifact_url))

            ref_groups: list[list[Any]] = []
            related = candidate.get("related_attachment_refs")
            if isinstance(related, list):
                ref_groups.append(related)
            linked = candidate.get("linked_artifact_refs")
            if isinstance(linked, list):
                ref_groups.append(linked)
            lineage_related = lineage_metadata.get("related_attachment_refs")
            if isinstance(lineage_related, list):
                ref_groups.append(lineage_related)

            for group in ref_groups:
                for raw_ref in group:
                    url = ""
                    source_family = ""
                    if isinstance(raw_ref, dict):
                        url = str(
                            raw_ref.get("url")
                            or raw_ref.get("attachment_url")
                            or raw_ref.get("source_url")
                            or ""
                        ).strip()
                        source_family = str(
                            raw_ref.get("source_family")
                            or raw_ref.get("attachment_family")
                            or ""
                        ).strip().lower()
                    elif isinstance(raw_ref, str):
                        url = raw_ref.strip()
                    if not url:
                        continue
                    linked_urls.add(cls._normalize_identity_url(url))
                    url_text = url.lower()
                    if re.search(r"\bsan[\s\-]?jose\b", url_text) or "sanjose" in url_text:
                        jurisdiction_signal_hits.add("lineage_ref_san_jose_signal")
                    if source_family in _IDENTITY_LINKED_ATTACHMENT_FAMILIES:
                        policy_signal_hits.add("lineage_ref_attachment_family_signal")
                        if "legistar.com" in url_text and "view.ashx" in url_text:
                            policy_signal_hits.add("lineage_ref_view_attachment_signal")
                    if any(signal in url_text for signal in _POLICY_LINEAGE_SIGNALS):
                        policy_signal_hits.add("lineage_ref_policy_signal")

        return {
            "linked_urls": sorted(linked_urls),
            "jurisdiction_signal_hits": sorted(jurisdiction_signal_hits),
            "policy_signal_hits": sorted(policy_signal_hits),
            "has_jurisdiction_context": bool(jurisdiction_signal_hits),
            "has_policy_context": bool(policy_signal_hits),
        }

    @classmethod
    def _evaluate_identity_quality(
        cls,
        *,
        jurisdiction: str,
        search_query: str,
        selected_url: str,
        selected_title: str,
        selected_snippet: str,
        structured_candidates: list[dict[str, Any]],
    ) -> dict[str, Any]:
        identity_required = cls._is_economic_selection_query(search_query)
        if not identity_required:
            return {
                "identity_required": False,
                "jurisdiction_identity_status": "not_applicable",
                "policy_identity_status": "not_applicable",
                "identity_quality_status": "not_applicable",
                "identity_failure_codes": [],
                "identity_failure_reasons": [],
                "jurisdiction_signal_hits": [],
                "policy_signal_hits": [],
                "explicit_lineage_linked": False,
                "jurisdiction_identity_ready": True,
                "policy_identity_ready": True,
                "identity_quality_ready": True,
                "identity_blocker_code": "",
                "identity_blocker_reason": "",
            }

        selected_url_value = str(selected_url or "").strip()
        selected_text = " ".join(
            [
                selected_url_value,
                str(selected_title or "").strip(),
                str(selected_snippet or "").strip(),
            ]
        ).lower()
        normalized_selected_url = cls._normalize_identity_url(selected_url_value)
        selected_parts = urlsplit(selected_url_value)
        selected_host = selected_parts.netloc.lower()
        selected_path = selected_parts.path.lower()
        selected_query = selected_parts.query.lower()

        lineage_context = cls._build_lineage_identity_context(
            structured_candidates=structured_candidates
        )
        linked_urls = set(lineage_context["linked_urls"])
        explicit_lineage_linked = (
            normalized_selected_url in linked_urls
            and bool(lineage_context["has_jurisdiction_context"])
            and bool(lineage_context["has_policy_context"])
        )

        jurisdiction_signal_hits: set[str] = set()
        policy_signal_hits: set[str] = set()
        identity_failure_codes: list[str] = []
        identity_failure_reasons: list[str] = []

        target_jurisdiction = str(jurisdiction or "").strip().lower()
        target_is_san_jose = bool(re.search(r"\bsan[\s\-]?jose\b", target_jurisdiction)) or (
            "sanjose" in target_jurisdiction
        )

        if target_is_san_jose:
            if any(host in selected_host for host in _SAN_JOSE_OFFICIAL_HOST_SIGNALS):
                jurisdiction_signal_hits.add("same_official_host")
            if "sanjose" in selected_host or "sanjose" in selected_path or "sanjose" in selected_query:
                jurisdiction_signal_hits.add("sanjose_slug")
            if selected_host.endswith("legistar.com") and (
                "sanjose" in selected_host or "/sanjose/" in selected_path or "sanjose" in selected_query
            ):
                jurisdiction_signal_hits.add("sanjose_legistar_host")
            if re.search(r"\bsan[\s\-]?jose\b", selected_text) or "sanjose" in selected_text:
                jurisdiction_signal_hits.add("sanjose_text_signal")
            if explicit_lineage_linked:
                jurisdiction_signal_hits.add("explicit_policy_lineage_link")

        if "sanjoseca.gov" in selected_host and "commercial-linkage-fee" in selected_path:
            policy_signal_hits.add("san_jose_clf_page")
        if any(signal in selected_text for signal in _POLICY_IDENTITY_SIGNALS):
            policy_signal_hits.add("policy_keyword_match")
        if any(signal in selected_text for signal in _POLICY_LINEAGE_SIGNALS):
            policy_signal_hits.add("policy_lineage_keyword_match")
        if "7526" in selected_text:
            policy_signal_hits.add("matter_7526_match")
        if explicit_lineage_linked:
            policy_signal_hits.add("explicit_policy_lineage_link")

        if any(signal in selected_text for signal in _JURISDICTION_BLOCKLIST_SIGNALS) and not explicit_lineage_linked:
            identity_failure_codes.append("jurisdiction_identity_mismatch")
            identity_failure_reasons.append(
                "selected source contains explicit wrong-jurisdiction signal for requested jurisdiction"
            )
        elif target_is_san_jose and not jurisdiction_signal_hits:
            identity_failure_codes.append("jurisdiction_identity_unproven")
            identity_failure_reasons.append(
                "selected source is missing requested jurisdiction identity signals"
            )

        if not policy_signal_hits:
            identity_failure_codes.append("policy_identity_mismatch")
            identity_failure_reasons.append(
                "selected source is missing requested policy identity signals"
            )

        jurisdiction_identity_ready = all(
            code not in {"jurisdiction_identity_mismatch", "jurisdiction_identity_unproven"}
            for code in identity_failure_codes
        )
        policy_identity_ready = "policy_identity_mismatch" not in identity_failure_codes
        identity_quality_ready = jurisdiction_identity_ready and policy_identity_ready
        identity_blocker_code = identity_failure_codes[0] if identity_failure_codes else ""
        identity_blocker_reason = identity_failure_reasons[0] if identity_failure_reasons else ""

        return {
            "identity_required": True,
            "jurisdiction_identity_status": "pass" if jurisdiction_identity_ready else "fail",
            "policy_identity_status": "pass" if policy_identity_ready else "fail",
            "identity_quality_status": "pass" if identity_quality_ready else "fail",
            "identity_failure_codes": identity_failure_codes,
            "identity_failure_reasons": identity_failure_reasons,
            "jurisdiction_signal_hits": sorted(
                set(jurisdiction_signal_hits).union(lineage_context["jurisdiction_signal_hits"])
            ),
            "policy_signal_hits": sorted(
                set(policy_signal_hits).union(lineage_context["policy_signal_hits"])
            ),
            "explicit_lineage_linked": explicit_lineage_linked,
            "jurisdiction_identity_ready": jurisdiction_identity_ready,
            "policy_identity_ready": policy_identity_ready,
            "identity_quality_ready": identity_quality_ready,
            "identity_blocker_code": identity_blocker_code,
            "identity_blocker_reason": identity_blocker_reason,
        }

    @classmethod
    def _build_source_quality_metrics(
        cls,
        *,
        jurisdiction: str,
        search_query: str,
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
        selected_candidate_detail: dict[str, Any] = {}
        for item in ranked_candidates:
            if str(item.get("url") or "").strip() == selected_url:
                selected_candidate_detail = item
                break
        if not selected_candidate_detail:
            for item in search_candidates:
                if str(item.get("url") or "").strip() == selected_url:
                    selected_candidate_detail = item
                    break
        selected_title = str(selected_candidate_detail.get("title") or "").strip()
        selected_snippet = str(
            selected_candidate_detail.get("snippet") or selected_candidate_detail.get("content") or ""
        ).strip()
        selected_audit_entry = cls._selected_candidate_audit_entry(
            candidate_audit=candidate_audit,
            selected_url=selected_url,
        )
        selected_artifact_family = cls._candidate_artifact_family_from_audit_entry(
            url=selected_url,
            audit_entry=selected_audit_entry,
        )
        artifact_candidates = [
            item for item in candidate_pool if _is_concrete_artifact_url(str(item.get("url") or ""))
        ]
        substantive_artifact_urls = sorted(
            {
                str(item.get("url") or "").strip()
                for item in candidate_audit
                if str(item.get("outcome") or "").strip() in {"materialized_raw_scrape", "reused_existing_raw_scrape"}
                and _is_concrete_artifact_url(str(item.get("url") or ""))
            }
        )
        fee_schedule_gate = (
            selected_audit_entry.get("fee_schedule_gate")
            if isinstance(selected_audit_entry, dict)
            and isinstance(selected_audit_entry.get("fee_schedule_gate"), dict)
            else {}
        )
        identity_quality = cls._evaluate_identity_quality(
            jurisdiction=jurisdiction,
            search_query=search_query,
            selected_url=selected_url,
            selected_title=selected_title,
            selected_snippet=selected_snippet,
            structured_candidates=structured_candidates,
        )
        shape_quality_gate_passed = selected_artifact_family == "artifact" or (
            selected_artifact_family == "maintained_fee_schedule" and bool(fee_schedule_gate.get("passed"))
        )
        selected_quality_gate_passed = shape_quality_gate_passed and bool(
            identity_quality.get("identity_quality_ready")
        )
        if not bool(identity_quality.get("identity_quality_ready")):
            artifact_quality_gate_status = "fail"
            artifact_quality_gate_reason = str(
                identity_quality.get("identity_blocker_code") or "identity_quality_failed"
            )
        elif selected_artifact_family != "artifact" and substantive_artifact_urls:
            artifact_quality_gate_status = "fail"
            artifact_quality_gate_reason = "artifact_candidates_present_but_non_artifact_selected"
        elif selected_artifact_family == "maintained_fee_schedule" and bool(fee_schedule_gate.get("passed")):
            artifact_quality_gate_status = "pass"
            artifact_quality_gate_reason = "maintained_fee_schedule_exception_no_artifact_quality_pass"
        elif substantive_artifact_urls:
            artifact_quality_gate_status = "pass"
            artifact_quality_gate_reason = "artifact_candidate_passed_quality_gate"
        else:
            artifact_quality_gate_status = "pass"
            artifact_quality_gate_reason = "no_artifact_candidate_passed_quality_gate"
        selected_candidate = {
            "url": selected_url,
            "provider": search_provider,
            "rank": selected_rank,
            "selection_reason": cls._selection_reason_from_audit(candidate_audit, selected_url),
            "artifact_grade": selected_artifact_family == "artifact",
            "official_domain": cls._is_official_domain_url(selected_url),
            "artifact_family": selected_artifact_family,
            "artifact_quality_gate_passed": selected_quality_gate_passed,
            "shape_quality_gate_passed": shape_quality_gate_passed,
            "fee_schedule_gate": fee_schedule_gate,
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
        selection_quality_status = (
            "pass" if selected_quality_gate_passed else "fail"
        )
        selection_quality_reason = (
            "selected_candidate_passed_identity_and_artifact_quality"
            if selected_quality_gate_passed
            else artifact_quality_gate_reason
        )
        return {
            "top_n_window": top_n_window,
            "top_n_official_recall_count": official_recall,
            "top_n_artifact_recall_count": artifact_recall,
            "selected_candidate": selected_candidate,
            "selected_artifact_family": selected_artifact_family,
            "artifact_quality_gate_status": artifact_quality_gate_status,
            "artifact_quality_gate_reason": artifact_quality_gate_reason,
            "artifact_quality_gate": {
                "artifact_candidate_count": len(artifact_candidates),
                "artifact_candidate_substantive_count": len(substantive_artifact_urls),
                "substantive_artifact_urls": substantive_artifact_urls,
            },
            "reader_substance_observed": reader_substance_observed,
            "reader_substance_selection_outcome": selected_outcome,
            "secondary_numeric_rescue_detected": secondary_lane_used
            and secondary_numeric_parameter_count > 0,
            "secondary_numeric_parameter_count": secondary_numeric_parameter_count,
            "selection_quality_status": selection_quality_status,
            "selection_quality_reason": selection_quality_reason,
            "jurisdiction_identity_status": identity_quality["jurisdiction_identity_status"],
            "policy_identity_status": identity_quality["policy_identity_status"],
            "identity_quality_status": identity_quality["identity_quality_status"],
            "identity_failure_codes": identity_quality["identity_failure_codes"],
            "identity_failure_reasons": identity_quality["identity_failure_reasons"],
            "jurisdiction_identity_signals": identity_quality["jurisdiction_signal_hits"],
            "policy_identity_signals": identity_quality["policy_signal_hits"],
            "identity_required": identity_quality["identity_required"],
            "explicit_lineage_linked": identity_quality["explicit_lineage_linked"],
            "jurisdiction_identity_ready": identity_quality["jurisdiction_identity_ready"],
            "policy_identity_ready": identity_quality["policy_identity_ready"],
            "identity_quality_ready": identity_quality["identity_quality_ready"],
            "identity_blocker_code": identity_quality["identity_blocker_code"],
            "identity_blocker_reason": identity_quality["identity_blocker_reason"],
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
    def _extract_primary_fee_facts_from_text_parts(
        cls,
        *,
        text_parts: list[str],
        selected_url: str,
        source_locator_prefix: str,
    ) -> tuple[list[dict[str, Any]], list[str]]:
        def _normalize_land_use(raw_category: str) -> tuple[str, str | None, str | None]:
            category_text = " ".join(raw_category.lower().split())
            subarea: str | None = None
            if "downtown" in category_text:
                subarea = "downtown"
            elif "rest of city" in category_text:
                subarea = "rest_of_city"
            if "industrial" in category_text:
                return ("industrial", subarea, subarea)
            if "residential care" in category_text:
                return ("residential_care", subarea, subarea)
            if "office" in category_text:
                return ("office", subarea, subarea)
            if "retail" in category_text:
                return ("retail", subarea, subarea)
            if "hotel" in category_text:
                return ("hotel", subarea, subarea)
            if "warehouse" in category_text:
                return ("warehouse", subarea, subarea)
            return ("unknown", subarea, subarea)

        def _infer_final_status(text: str) -> str:
            lowered = text.lower()
            if any(token in lowered for token in ("adopted", "approved", "enacted", "final")):
                return "adopted"
            if any(token in lowered for token in ("proposed", "draft", "recommend")):
                return "proposed"
            return "unknown"

        def _extract_dates(text: str) -> tuple[str | None, str | None]:
            month_date_pattern = re.compile(
                r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2},\s+\d{4}",
                flags=re.IGNORECASE,
            )
            matches = list(month_date_pattern.finditer(text))
            effective_date: str | None = None
            adoption_date: str | None = None
            lowered = text.lower()
            for match in matches:
                value = match.group(0)
                window_start = max(0, match.start() - 40)
                window_end = min(len(lowered), match.end() + 40)
                window = lowered[window_start:window_end]
                if effective_date is None and any(
                    token in window for token in ("effective", "beginning", "commencing")
                ):
                    effective_date = value
                if adoption_date is None and any(
                    token in window for token in ("adopted", "approved", "final", "passed")
                ):
                    adoption_date = value
            if matches and adoption_date is None and any(
                token in lowered for token in ("adopted", "approved", "final", "passed")
            ):
                adoption_date = matches[0].group(0)
            if matches and effective_date is None and "effective" in lowered:
                effective_date = matches[0].group(0)
            return effective_date, adoption_date

        def _extract_payment_context(
            *,
            raw_token: str,
            threshold: str | None,
            context_excerpt: str,
        ) -> tuple[str | None, str | None, float | None, str | None]:
            lowered = context_excerpt.lower()
            payment_timing: str | None = None
            if "prior to the building permit issuance" in lowered or "prior to building permit issuance" in lowered:
                payment_timing = "paid_before_building_permit_issuance"
            elif "scheduling of final building inspection" in lowered or "final building inspection" in lowered:
                payment_timing = "paid_at_final_building_inspection"
            elif "paid in full" in lowered:
                payment_timing = "paid_in_full_timing_unspecified"

            payment_reduction_percent: float | None = None
            payment_reduction_context: str | None = None
            reduction_match = re.search(
                r"(?P<pct>[0-9]{1,3}(?:\.[0-9]+)?)\s*%\s*reduction",
                context_excerpt,
                flags=re.IGNORECASE,
            )
            if reduction_match:
                payment_reduction_percent = float(reduction_match.group("pct"))
                sentence_start = max(
                    context_excerpt.rfind(".", 0, reduction_match.start()),
                    context_excerpt.rfind("\n", 0, reduction_match.start()),
                )
                sentence_end_candidates = [
                    pos
                    for pos in (
                        context_excerpt.find(".", reduction_match.end()),
                        context_excerpt.find("\n", reduction_match.end()),
                    )
                    if pos != -1
                ]
                sentence_start = sentence_start + 1 if sentence_start != -1 else 0
                sentence_end = min(sentence_end_candidates) if sentence_end_candidates else len(context_excerpt)
                payment_reduction_context = " ".join(context_excerpt[sentence_start:sentence_end].split()) or None

            exemption_context: str | None = None
            if re.match(r"no\s+fee", raw_token, flags=re.IGNORECASE):
                if threshold:
                    exemption_context = f"no_fee_for_threshold:{threshold}"
                else:
                    exemption_match = re.search(
                        r"no\s+fee[^.;\n]*",
                        context_excerpt,
                        flags=re.IGNORECASE,
                    )
                    if exemption_match:
                        exemption_context = " ".join(exemption_match.group(0).split()) or None
                    else:
                        exemption_context = "no_fee"

            return (
                payment_timing,
                payment_reduction_context,
                payment_reduction_percent,
                exemption_context,
            )

        facts: list[dict[str, Any]] = []
        alerts: list[str] = []
        seen: set[tuple[str, str, str, str, str, str, str]] = set()
        fee_row_pattern = re.compile(
            r"(?P<category>Downtown\s+Office|Rest\s+of\s+City\s+Office|Office|Retail|Hotel|"
            r"Industrial/Research\s+and\s+Development|Warehouse|Residential\s+Care)"
            r"(?:\s*\((?P<threshold>[^)]*?(?:sq\.?\s*ft|sq\.?ft|square\s+foot)[^)]*)\))?"
            r"\s*(?P<raw>No\s+fee\s*\(\$0\)|\$[0-9]+(?:\.[0-9]+){2,}|\$[0-9]+(?:\.[0-9]{1,2})?)",
            re.IGNORECASE,
        )

        for chunk_index, text in enumerate(text_parts, start=1):
            lowered = text.lower()
            if not any(signal in lowered for signal in ("fee", "fees", "per sq", "square foot", "sq. ft")):
                continue
            effective_date_hint, adoption_date_hint = _extract_dates(text)
            final_status = _infer_final_status(text)
            row_match_found = False
            for row_match in fee_row_pattern.finditer(text):
                row_match_found = True
                raw_token = row_match.group("raw")
                raw_category = " ".join(row_match.group("category").split())
                land_use, subarea, geography = _normalize_land_use(raw_category)
                threshold = " ".join((row_match.group("threshold") or "").split()) or None
                context_start = max(0, row_match.start() - 120)
                context_end = min(len(text), row_match.end() + 120)
                context_excerpt = " ".join(text[context_start:context_end].split())
                (
                    payment_timing,
                    payment_reduction_context,
                    payment_reduction_percent,
                    exemption_context,
                ) = _extract_payment_context(
                    raw_token=raw_token,
                    threshold=threshold,
                    context_excerpt=context_excerpt,
                )
                if re.match(r"no\s+fee", raw_token, flags=re.IGNORECASE):
                    value: float | None = 0.0
                    normalized_raw = "$0"
                    ambiguity = False
                    ambiguity_reason = None
                    confidence = 0.86
                elif re.fullmatch(r"\$[0-9]+(?:\.[0-9]+){2,}", raw_token):
                    alerts.append("primary_parameter_money_format_anomaly")
                    value = None
                    normalized_raw = raw_token
                    ambiguity = True
                    ambiguity_reason = "currency_format_anomaly"
                    confidence = 0.35
                else:
                    value = float(raw_token.replace("$", ""))
                    normalized_raw = raw_token
                    ambiguity = False
                    ambiguity_reason = None
                    confidence = 0.86
                dedupe_value = f"{value:.6f}" if value is not None else normalized_raw
                dedupe_key = (
                    "commercial_linkage_fee_rate_usd_per_sqft",
                    dedupe_value,
                    land_use,
                    threshold or "",
                    payment_timing or "",
                    payment_reduction_context or "",
                    exemption_context or "",
                )
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)
                facts.append(
                    {
                        "field": "commercial_linkage_fee_rate_usd_per_sqft",
                        "raw_value": normalized_raw,
                        "value": value,
                        "normalized_value": value,
                        "unit": "usd_per_square_foot",
                        "denominator": "per_square_foot",
                        "category": land_use,
                        "land_use": land_use,
                        "raw_land_use_label": raw_category,
                        "subarea": subarea,
                        "geography": geography,
                        "threshold": threshold,
                        "payment_timing": payment_timing,
                        "payment_reduction_context": payment_reduction_context,
                        "payment_reduction_percent": payment_reduction_percent,
                        "exemption_context": exemption_context,
                        "source_url": selected_url,
                        "source_ref": selected_url,
                        "source_excerpt": context_excerpt[:600],
                        "source_locator": f"{source_locator_prefix}:{chunk_index}:fee_table_row",
                        "chunk_locator": f"{source_locator_prefix}:{chunk_index}",
                        "table_locator": "commercial_linkage_fee_table",
                        "page_locator": None,
                        "locator_quality": "table_row_chunk_locator",
                        "provenance_lane": "primary_scraped_document",
                        "source_hierarchy_status": "bill_or_reg_text",
                        "confidence": confidence,
                        "ambiguity_flag": ambiguity,
                        "ambiguity_reason": ambiguity_reason,
                        "currency_sanity": "invalid" if ambiguity else "valid",
                        "unit_sanity": "valid",
                        "effective_date": effective_date_hint,
                        "adoption_date": adoption_date_hint,
                        "final_status": final_status,
                    }
                )
                tail_window = text[row_match.end() : min(len(text), row_match.end() + 180)]
                for extra_match in re.finditer(
                    r"(?P<raw>\$[0-9]+(?:\.[0-9]+){2,}|\$[0-9]+(?:\.[0-9]{1,2})?)\s*(?P<context>when\s+paid[^.;\n]*)",
                    tail_window,
                    flags=re.IGNORECASE,
                ):
                    extra_raw = extra_match.group("raw")
                    extra_excerpt = " ".join(f"{raw_category} {extra_match.group(0)}".split())
                    (
                        extra_payment_timing,
                        extra_reduction_context,
                        extra_reduction_percent,
                        extra_exemption_context,
                    ) = _extract_payment_context(
                        raw_token=extra_raw,
                        threshold=threshold,
                        context_excerpt=extra_excerpt,
                    )
                    if re.fullmatch(r"\$[0-9]+(?:\.[0-9]+){2,}", extra_raw):
                        alerts.append("primary_parameter_money_format_anomaly")
                        extra_value: float | None = None
                        extra_ambiguity = True
                        extra_ambiguity_reason = "currency_format_anomaly"
                        extra_confidence = 0.35
                    else:
                        extra_value = float(extra_raw.replace("$", ""))
                        extra_ambiguity = False
                        extra_ambiguity_reason = None
                        extra_confidence = 0.86
                    extra_value_token = (
                        f"{extra_value:.6f}" if extra_value is not None else extra_raw
                    )
                    extra_key = (
                        "commercial_linkage_fee_rate_usd_per_sqft",
                        extra_value_token,
                        land_use,
                        threshold or "",
                        extra_payment_timing or "",
                        extra_reduction_context or "",
                        extra_exemption_context or "",
                    )
                    if extra_key in seen:
                        continue
                    seen.add(extra_key)
                    facts.append(
                        {
                            "field": "commercial_linkage_fee_rate_usd_per_sqft",
                            "raw_value": extra_raw,
                            "value": extra_value,
                            "normalized_value": extra_value,
                            "unit": "usd_per_square_foot",
                            "denominator": "per_square_foot",
                            "category": land_use,
                            "land_use": land_use,
                            "raw_land_use_label": raw_category,
                            "subarea": subarea,
                            "geography": geography,
                            "threshold": threshold,
                            "payment_timing": extra_payment_timing,
                            "payment_reduction_context": extra_reduction_context,
                            "payment_reduction_percent": extra_reduction_percent,
                            "exemption_context": extra_exemption_context,
                            "source_url": selected_url,
                            "source_ref": selected_url,
                            "source_excerpt": extra_excerpt[:600],
                            "source_locator": f"{source_locator_prefix}:{chunk_index}:fee_table_row",
                            "chunk_locator": f"{source_locator_prefix}:{chunk_index}",
                            "table_locator": "commercial_linkage_fee_table",
                            "page_locator": None,
                            "locator_quality": "table_row_chunk_locator",
                            "provenance_lane": "primary_scraped_document",
                            "source_hierarchy_status": "bill_or_reg_text",
                            "confidence": extra_confidence,
                            "ambiguity_flag": extra_ambiguity,
                            "ambiguity_reason": extra_ambiguity_reason,
                            "currency_sanity": "invalid" if extra_ambiguity else "valid",
                            "unit_sanity": "valid",
                            "effective_date": effective_date_hint,
                            "adoption_date": adoption_date_hint,
                            "final_status": final_status,
                        }
                    )
            if row_match_found:
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
                            "land_use": "unknown",
                            "raw_land_use_label": "unknown",
                            "subarea": None,
                            "geography": None,
                            "threshold": None,
                            "payment_timing": None,
                            "payment_reduction_context": None,
                            "payment_reduction_percent": None,
                            "exemption_context": None,
                            "source_url": selected_url,
                            "source_ref": selected_url,
                            "source_excerpt": text[:600],
                            "source_locator": f"{source_locator_prefix}:{chunk_index}",
                            "chunk_locator": f"{source_locator_prefix}:{chunk_index}",
                            "table_locator": None,
                            "page_locator": None,
                            "locator_quality": "chunk_locator_only",
                            "provenance_lane": "primary_scraped_document",
                            "source_hierarchy_status": "bill_or_reg_text",
                            "confidence": 0.35,
                            "ambiguity_flag": True,
                            "ambiguity_reason": "currency_format_anomaly",
                            "currency_sanity": "invalid",
                            "unit_sanity": "valid",
                            "effective_date": effective_date_hint,
                            "adoption_date": adoption_date_hint,
                            "final_status": final_status,
                        }
                    )
            for match in re.finditer(r"\$([0-9]+(?:\.[0-9]{1,2})?)(?![\d.])", text):
                raw_token = match.group(0)
                value = float(match.group(1))
                category = "unknown"
                context_start = max(0, match.start() - 160)
                context_end = min(len(text), match.end() + 160)
                context_excerpt = " ".join(text[context_start:context_end].split())
                context_window = context_excerpt.lower()
                unit_signals = (
                    "per square foot",
                    "per sq",
                    "sq. ft",
                    "sq.ft",
                    "square foot",
                    "gross floor area",
                )
                post_value_window = lowered[match.end() : min(len(lowered), match.end() + 60)]
                if any(
                    signal in post_value_window
                    for signal in ("million", "annually", "annual revenue", "generate")
                ):
                    continue
                if not any(signal in context_window for signal in unit_signals):
                    continue
                sentence_start = max(text.rfind("\n", 0, match.start()), text.rfind(".", 0, match.start()))
                sentence_end_candidates = [
                    pos for pos in (text.find("\n", match.end()), text.find(".", match.end())) if pos != -1
                ]
                sentence_start = sentence_start + 1 if sentence_start != -1 else context_start
                sentence_end = min(sentence_end_candidates) if sentence_end_candidates else context_end
                local_excerpt = " ".join(text[sentence_start:sentence_end].split())
                if not local_excerpt:
                    local_excerpt = context_excerpt
                if "office" in context_window:
                    category = "office"
                elif "retail" in context_window:
                    category = "retail"
                elif "hotel" in context_window:
                    category = "hotel"
                elif "industrial" in context_window:
                    category = "industrial"
                (
                    payment_timing,
                    payment_reduction_context,
                    payment_reduction_percent,
                    exemption_context,
                ) = _extract_payment_context(
                    raw_token=raw_token,
                    threshold=None,
                    context_excerpt=local_excerpt or context_excerpt,
                )
                dedupe_key = (
                    "commercial_linkage_fee_rate_usd_per_sqft",
                    f"{value:.6f}",
                    category,
                    "",
                    payment_timing or "",
                    payment_reduction_context or "",
                    exemption_context or "",
                )
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)
                facts.append(
                    {
                        "field": "commercial_linkage_fee_rate_usd_per_sqft",
                        "raw_value": raw_token,
                        "value": value,
                        "normalized_value": value,
                        "unit": "usd_per_square_foot",
                        "denominator": "per_square_foot",
                        "category": category,
                        "land_use": category,
                        "raw_land_use_label": category,
                        "subarea": None,
                        "geography": None,
                        "threshold": None,
                        "payment_timing": payment_timing,
                        "payment_reduction_context": payment_reduction_context,
                        "payment_reduction_percent": payment_reduction_percent,
                        "exemption_context": exemption_context,
                        "source_url": selected_url,
                        "source_ref": selected_url,
                        "source_excerpt": (local_excerpt or context_excerpt)[:600],
                        "source_locator": f"{source_locator_prefix}:{chunk_index}",
                        "chunk_locator": f"{source_locator_prefix}:{chunk_index}",
                        "table_locator": None,
                        "page_locator": None,
                        "locator_quality": "chunk_locator_only",
                        "provenance_lane": "primary_scraped_document",
                        "source_hierarchy_status": "bill_or_reg_text",
                        "confidence": 0.82,
                        "ambiguity_flag": False,
                        "ambiguity_reason": None,
                        "currency_sanity": "valid",
                        "unit_sanity": "valid",
                        "effective_date": effective_date_hint,
                        "adoption_date": adoption_date_hint,
                        "final_status": final_status,
                    }
                )
        return facts, sorted(set(alerts))

    @classmethod
    def _extract_primary_fee_facts_from_analysis(
        cls,
        *,
        analyze: CommandResponse | None,
        selected_url: str,
    ) -> tuple[list[dict[str, Any]], list[str]]:
        return cls._extract_primary_fee_facts_from_text_parts(
            text_parts=cls._analysis_text_parts(analyze),
            selected_url=selected_url,
            source_locator_prefix="analysis_chunk",
        )

    @classmethod
    def _merge_primary_fee_facts(
        cls,
        *fact_groups: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        merged: list[dict[str, Any]] = []
        seen: set[tuple[str, str, str, str, str, str, str, str, str]] = set()
        categorized_ambiguous_raws = {
            (
                str(fact.get("field") or ""),
                str(fact.get("raw_value") or ""),
                str(fact.get("source_url") or ""),
            )
            for facts in fact_groups
            for fact in facts
            if fact.get("ambiguity_flag")
            and str(fact.get("raw_value") or "")
            and str(fact.get("land_use") or fact.get("category") or "unknown") != "unknown"
        }
        for facts in fact_groups:
            for fact in facts:
                raw_value = str(fact.get("raw_value") or "")
                if (
                    fact.get("ambiguity_flag")
                    and str(fact.get("land_use") or fact.get("category") or "unknown") == "unknown"
                    and (str(fact.get("field") or ""), raw_value, str(fact.get("source_url") or ""))
                    in categorized_ambiguous_raws
                ):
                    continue
                normalized_value = fact.get("normalized_value")
                value_key = str(normalized_value if normalized_value is not None else raw_value)
                key = (
                    str(fact.get("field") or ""),
                    value_key,
                    str(fact.get("land_use") or fact.get("category") or ""),
                    str(fact.get("subarea") or ""),
                    str(fact.get("threshold") or ""),
                    str(fact.get("payment_timing") or ""),
                    str(fact.get("payment_reduction_context") or ""),
                    str(fact.get("exemption_context") or ""),
                    str(fact.get("source_url") or ""),
                )
                if key in seen:
                    continue
                seen.add(key)
                merged.append(fact)
        return merged

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
        selected_audit_entry = cls._selected_candidate_audit_entry(
            candidate_audit=candidate_audit,
            selected_url=selected_url,
        )
        selected_family = cls._candidate_artifact_family_from_audit_entry(
            url=selected_url,
            audit_entry=selected_audit_entry,
        )
        expected_source_families = [
            "authoritative_policy_text",
            "meeting_context",
            "staff_fiscal_context",
            "related_attachments",
            "attachment_content_ingested",
            "attachment_economic_rows",
        ]
        fee_schedule_authoritative_policy_text = False
        if isinstance(selected_audit_entry, dict):
            fee_schedule_gate = selected_audit_entry.get("fee_schedule_gate")
            if isinstance(fee_schedule_gate, dict):
                fee_schedule_authoritative_policy_text = bool(
                    fee_schedule_gate.get("authoritative_policy_text_ok")
                )
        has_authoritative_text = selected_family == "artifact" or fee_schedule_authoritative_policy_text
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
        related_artifacts: list[str] = []
        seen_related_artifacts: set[str] = set()
        for item in candidate_audit:
            if not isinstance(item, dict):
                continue
            url = str(item.get("url") or "").strip()
            if (
                not url
                or url == selected_url
                or not _is_concrete_artifact_url(url)
                or url in seen_related_artifacts
            ):
                continue
            seen_related_artifacts.add(url)
            related_artifacts.append(url)

        related_attachment_refs: list[dict[str, Any]] = []
        seen_attachment_refs: set[tuple[str, str, str]] = set()
        attachment_content_probes: list[dict[str, Any]] = []
        seen_probe_keys: set[tuple[str, str, str]] = set()
        for candidate in structured_candidates:
            if not isinstance(candidate, dict):
                continue
            attachment_groups: list[list[Any]] = []
            direct_refs = candidate.get("related_attachment_refs")
            if isinstance(direct_refs, list):
                attachment_groups.append(direct_refs)
            lineage_metadata = candidate.get("lineage_metadata")
            if isinstance(lineage_metadata, dict):
                lineage_refs = lineage_metadata.get("related_attachment_refs")
                if isinstance(lineage_refs, list):
                    attachment_groups.append(lineage_refs)
            if not attachment_groups:
                fallback_refs = candidate.get("linked_artifact_refs")
                if isinstance(fallback_refs, list):
                    attachment_groups.append(fallback_refs)

            for group in attachment_groups:
                for raw_ref in group:
                    attachment_id = ""
                    attachment_title = ""
                    attachment_url = ""
                    attachment_family = "unknown"

                    if isinstance(raw_ref, dict):
                        attachment_id = str(raw_ref.get("attachment_id") or raw_ref.get("id") or "").strip()
                        attachment_title = str(raw_ref.get("title") or raw_ref.get("name") or "").strip()
                        attachment_url = str(raw_ref.get("url") or raw_ref.get("attachment_url") or "").strip()
                        attachment_family = str(
                            raw_ref.get("source_family") or raw_ref.get("attachment_family") or "unknown"
                        ).strip() or "unknown"
                    elif isinstance(raw_ref, str):
                        attachment_url = raw_ref.strip()
                    else:
                        continue

                    if not attachment_id and not attachment_title and not attachment_url:
                        continue
                    dedupe_key = (attachment_id, attachment_title.lower(), attachment_url)
                    if dedupe_key in seen_attachment_refs:
                        continue
                    seen_attachment_refs.add(dedupe_key)

                    if (
                        attachment_url
                        and attachment_url != selected_url
                        and _is_concrete_artifact_url(attachment_url)
                        and attachment_url not in seen_related_artifacts
                    ):
                        seen_related_artifacts.add(attachment_url)
                        related_artifacts.append(attachment_url)

                    related_attachment_refs.append(
                        {
                            "attachment_id": attachment_id or None,
                            "title": attachment_title or None,
                            "url": attachment_url or None,
                            "source_family": attachment_family,
                        }
                    )

            raw_probes = candidate.get("attachment_content_probes")
            if isinstance(raw_probes, list):
                for probe in raw_probes:
                    if not isinstance(probe, dict):
                        continue
                    probe_id = str(probe.get("attachment_id") or "").strip()
                    probe_title = str(probe.get("title") or "").strip()
                    probe_url = str(probe.get("url") or "").strip()
                    probe_key = (probe_id, probe_title.lower(), probe_url)
                    if probe_key in seen_probe_keys:
                        continue
                    seen_probe_keys.add(probe_key)
                    attachment_content_probes.append(
                        {
                            "attachment_id": probe_id or None,
                            "title": probe_title or None,
                            "source_title": str(probe.get("source_title") or probe_title).strip() or None,
                            "url": probe_url or None,
                            "source_url": str(probe.get("source_url") or probe_url).strip() or None,
                            "source_family": str(probe.get("source_family") or "unknown").strip() or "unknown",
                            "status": str(probe.get("status") or "").strip() or "unknown",
                            "read_status": str(probe.get("read_status") or "").strip() or "unknown",
                            "failure_class": str(probe.get("failure_class") or "").strip() or None,
                            "content_ingested": bool(probe.get("content_ingested")),
                            "economic_row_count": int(probe.get("economic_row_count") or 0),
                            "excerpt": str(probe.get("excerpt") or "").strip()[:400],
                            "content_hash": str(probe.get("content_hash") or "").strip() or None,
                        }
                    )

        has_related_artifacts = bool(related_artifacts) or bool(related_attachment_refs)
        attachment_refs_present = bool(related_attachment_refs)
        attachment_content_ingested = any(
            bool(item.get("content_ingested")) for item in attachment_content_probes
        )
        attachment_economic_rows_available = any(
            int(item.get("economic_row_count") or 0) > 0 for item in attachment_content_probes
        )

        found_flags = {
            "authoritative_policy_text": has_authoritative_text,
            "meeting_context": has_meeting_context,
            "staff_fiscal_context": has_staff_fiscal_context,
            "related_attachments": has_related_artifacts,
            "attachment_content_ingested": attachment_content_ingested,
            "attachment_economic_rows": attachment_economic_rows_available,
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
            "related_artifacts": related_artifacts[:10],
            "related_attachment_refs": related_attachment_refs[:25],
            "related_attachment_source_families": sorted(
                {
                    str(ref.get("source_family") or "unknown")
                    for ref in related_attachment_refs
                }
            ),
            "attachment_state": {
                "refs_present": attachment_refs_present,
                "content_ingested": attachment_content_ingested,
                "economic_rows_available": attachment_economic_rows_available,
                "attachment_ref_count": len(related_attachment_refs),
                "attachment_probe_count": len(attachment_content_probes),
                "attachment_ingested_count": sum(
                    1 for item in attachment_content_probes if bool(item.get("content_ingested"))
                ),
                "attachment_economic_row_count": sum(
                    int(item.get("economic_row_count") or 0) for item in attachment_content_probes
                ),
            },
            "attachment_content_probes": attachment_content_probes[:25],
            "negative_evidence": negative_evidence,
            "lineage_completeness_score": sum(1 for found in found_flags.values() if found) / len(found_flags),
        }

    @staticmethod
    def _attachment_hierarchy_status(source_family: str) -> str:
        normalized = str(source_family or "").strip().lower()
        if normalized in {"resolution", "ordinance", "ordinance_text", "municipal_code", "legislation_text"}:
            return "bill_or_reg_text"
        return "fiscal_or_reg_impact_analysis"

    @classmethod
    def _extract_official_attachment_probe_facts(
        cls,
        *,
        candidate: dict[str, Any],
    ) -> list[dict[str, Any]]:
        probes = candidate.get("attachment_content_probes")
        if not isinstance(probes, list):
            return []
        lineage_metadata = candidate.get("lineage_metadata")
        matter_id = ""
        if isinstance(lineage_metadata, dict):
            matter_id = str(lineage_metadata.get("matter_id") or "").strip()
        extracted: list[dict[str, Any]] = []
        for probe_index, probe in enumerate(probes, start=1):
            if not isinstance(probe, dict):
                continue
            if not bool(probe.get("content_ingested")):
                continue
            excerpt = str(probe.get("excerpt") or "").strip()
            if not excerpt:
                continue
            source_url = str(probe.get("url") or "").strip()
            if not source_url:
                continue
            attachment_id = str(probe.get("attachment_id") or "").strip()
            attachment_title = str(probe.get("title") or "").strip()
            attachment_family = str(probe.get("source_family") or "official_attachment").strip() or "official_attachment"
            source_ref = source_url
            if matter_id and attachment_id:
                source_ref = f"legistar::matter::{matter_id}::attachment::{attachment_id}"
            parsed_rows, _ = cls._extract_primary_fee_facts_from_text_parts(
                text_parts=[excerpt],
                selected_url=source_url,
                source_locator_prefix=f"attachment_probe:{attachment_id or probe_index}",
            )
            for row in parsed_rows:
                normalized_row = dict(row)
                normalized_row["source_family"] = attachment_family
                normalized_row["source_ref"] = source_ref
                normalized_row["attachment_id"] = attachment_id or None
                normalized_row["attachment_title"] = attachment_title or None
                normalized_row["source_hierarchy_status"] = cls._attachment_hierarchy_status(attachment_family)
                normalized_row["provenance_lane"] = "structured_attachment_probe"
                extracted.append(normalized_row)
        return extracted

    @classmethod
    def _collect_secondary_numeric_facts(cls, structured_candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        collected: list[dict[str, Any]] = []
        seen: set[tuple[str, ...]] = set()
        secondary_source_families = {"tavily_secondary_search", "exa_secondary_search"}
        for candidate in structured_candidates:
            if not isinstance(candidate, dict):
                continue
            source_family = str(candidate.get("source_family") or "").strip().lower()
            is_true_structured = bool(candidate.get("true_structured", True))
            if source_family in secondary_source_families:
                is_true_structured = False

            raw_facts = candidate.get("structured_policy_facts")
            facts: list[dict[str, Any]] = [fact for fact in raw_facts if isinstance(fact, dict)] if isinstance(raw_facts, list) else []
            synthesized_attachment_facts = cls._extract_official_attachment_probe_facts(candidate=candidate)
            synthesized_attachment_urls = {
                str(fact.get("source_url") or "").strip()
                for fact in synthesized_attachment_facts
                if str(fact.get("source_url") or "").strip()
            }
            facts.extend(synthesized_attachment_facts)

            for fact in facts:
                field = str(fact.get("field") or "unknown_parameter")
                if not any(
                    token in field.lower()
                    for token in (
                        "fee",
                        "rate",
                        "cost",
                        "tax",
                        "assessment",
                        "charge",
                        "usd",
                    )
                ):
                    continue

                source_url = str(fact.get("source_url") or candidate.get("artifact_url") or "").strip()
                source_locator = str(fact.get("source_locator") or "").strip()
                locator_quality = str(fact.get("locator_quality") or "").strip()
                if (
                    source_url in synthesized_attachment_urls
                    and (source_locator == "attachment_probe:excerpt" or locator_quality == "attachment_probe_excerpt")
                ):
                    # Drop low-fidelity probe rows when richer parsed attachment rows exist.
                    continue

                value = fact.get("normalized_value", fact.get("value"))
                if isinstance(value, str):
                    try:
                        value = float(value.replace(",", "").strip())
                    except ValueError:
                        value = None
                if not isinstance(value, (int, float)):
                    continue

                lane_classification = str(fact.get("source_lane_classification") or "").strip()
                if lane_classification != "secondary_search_derived":
                    lane_classification = "true_structured_source" if is_true_structured else "secondary_search_derived"

                resolved_source_family = str(fact.get("source_family") or source_family or "unknown").strip().lower() or "unknown"
                row_payload = {
                    "field": field,
                    "normalized_value": float(value),
                    "raw_value": str(fact.get("raw_value") or "").strip() or None,
                    "value": float(value),
                    "source_family": resolved_source_family,
                    "source_url": source_url,
                    "source_ref": str(fact.get("source_ref") or source_url).strip() or source_url,
                    "attachment_id": str(fact.get("attachment_id") or "").strip() or None,
                    "attachment_title": str(fact.get("attachment_title") or "").strip() or None,
                    "source_excerpt": str(fact.get("source_excerpt") or "").strip(),
                    "source_locator": source_locator or None,
                    "chunk_locator": str(fact.get("chunk_locator") or "").strip() or None,
                    "table_locator": str(fact.get("table_locator") or "").strip() or None,
                    "page_locator": str(fact.get("page_locator") or "").strip() or None,
                    "locator_quality": locator_quality or "locator_not_available",
                    "unit": str(fact.get("unit") or "").strip() or None,
                    "denominator": str(fact.get("denominator") or "").strip() or None,
                    "land_use": str(fact.get("land_use") or fact.get("category") or "").strip() or "unknown",
                    "subarea": str(fact.get("subarea") or "").strip() or None,
                    "geography": str(fact.get("geography") or "").strip() or None,
                    "threshold": str(fact.get("threshold") or "").strip() or None,
                    "payment_timing": str(fact.get("payment_timing") or "").strip() or None,
                    "payment_reduction_context": str(fact.get("payment_reduction_context") or "").strip() or None,
                    "payment_reduction_percent": float(fact.get("payment_reduction_percent"))
                    if isinstance(fact.get("payment_reduction_percent"), (int, float))
                    else None,
                    "exemption_context": str(fact.get("exemption_context") or "").strip() or None,
                    "raw_land_use_label": str(fact.get("raw_land_use_label") or "").strip() or None,
                    "effective_date": str(fact.get("effective_date") or "").strip() or None,
                    "adoption_date": str(fact.get("adoption_date") or "").strip() or None,
                    "final_status": str(fact.get("final_status") or "").strip() or "unknown",
                    "source_hierarchy_status": str(fact.get("source_hierarchy_status") or "").strip()
                    or cls._attachment_hierarchy_status(resolved_source_family),
                    "confidence": float(fact.get("confidence"))
                    if isinstance(fact.get("confidence"), (int, float))
                    else 0.5,
                    "ambiguity_flag": bool(fact.get("ambiguity_flag")),
                    "ambiguity_reason": str(fact.get("ambiguity_reason") or "").strip() or None,
                    "currency_sanity": str(fact.get("currency_sanity") or "").strip().lower() or "valid",
                    "unit_sanity": str(fact.get("unit_sanity") or "").strip().lower() or "valid",
                    "policy_match_key": str(
                        fact.get("policy_match_key")
                        or candidate.get("policy_match_key")
                        or ""
                    ).strip()
                    or None,
                    "policy_match_confidence": float(candidate.get("policy_match_confidence"))
                    if isinstance(candidate.get("policy_match_confidence"), (int, float))
                    else None,
                    "reconciliation_status": str(
                        fact.get("reconciliation_status")
                        or candidate.get("reconciliation_status")
                        or ""
                    ).strip()
                    or None,
                    "source_lane_classification": lane_classification,
                }
                row_identity = (
                    str(row_payload["field"]),
                    cls._value_token_for_row(row_payload),
                    str(row_payload.get("land_use") or ""),
                    str(row_payload.get("subarea") or ""),
                    str(row_payload.get("threshold") or ""),
                    str(row_payload.get("payment_timing") or ""),
                    str(row_payload.get("payment_reduction_context") or ""),
                    str(row_payload.get("exemption_context") or ""),
                    str(row_payload.get("source_locator") or ""),
                    str(row_payload.get("source_family") or ""),
                    str(row_payload.get("source_url") or ""),
                    str(row_payload.get("source_lane_classification") or ""),
                )
                if row_identity in seen:
                    continue
                seen.add(row_identity)
                collected.append(row_payload)
        return collected

    @staticmethod
    def _to_float(value: Any) -> float | None:
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            cleaned = value.replace(",", "").strip()
            try:
                return float(cleaned)
            except ValueError:
                return None
        return None

    @staticmethod
    def _value_token_for_row(fact: dict[str, Any]) -> str:
        normalized_value = RailwayRuntimeBridge._to_float(fact.get("normalized_value", fact.get("value")))
        if normalized_value is not None:
            return f"{normalized_value:.6f}"
        return str(fact.get("raw_value") or "").strip()

    @classmethod
    def _economic_row_key(
        cls,
        fact: dict[str, Any],
    ) -> tuple[str, str, str, str, str, str, str, str, str, str]:
        return (
            str(fact.get("field") or "unknown_parameter").strip(),
            str(fact.get("land_use") or fact.get("category") or "unknown").strip(),
            str(fact.get("subarea") or "").strip(),
            str(fact.get("threshold") or "").strip(),
            str(fact.get("payment_timing") or "").strip(),
            str(fact.get("payment_reduction_context") or "").strip(),
            str(fact.get("exemption_context") or "").strip(),
            str(fact.get("raw_land_use_label") or "").strip(),
            str(fact.get("source_locator") or "").strip(),
            cls._value_token_for_row(fact),
        )

    @staticmethod
    def _economic_row_identity(fact: dict[str, Any]) -> tuple[str, ...]:
        row_key = RailwayRuntimeBridge._economic_row_key(fact)
        return (
            *row_key,
            str(fact.get("source_locator") or "").strip(),
            str(fact.get("source_family") or "").strip(),
            str(fact.get("source_url") or "").strip(),
            str(fact.get("source_lane_classification") or "").strip(),
        )

    @staticmethod
    def _locator_fail_closed_signals(fact: dict[str, Any]) -> list[str]:
        locator_quality = str(fact.get("locator_quality") or "").strip() or "locator_not_available"
        has_table_locator = bool(str(fact.get("table_locator") or "").strip())
        has_chunk_locator = bool(str(fact.get("chunk_locator") or "").strip())
        has_page_locator = bool(str(fact.get("page_locator") or "").strip())
        signals: list[str] = []
        if locator_quality in {"chunk_locator_only", "page_locator_only", "locator_not_available"}:
            signals.append("locator_precision_insufficient_for_artifact_grade")
        if locator_quality == "chunk_locator_only" and not has_table_locator:
            signals.append("chunk_locator_only_requires_table_or_artifact_locator")
        if has_page_locator and not has_table_locator:
            signals.append("page_locator_only_requires_table_or_artifact_locator")
        if not has_chunk_locator and not has_table_locator and not has_page_locator:
            signals.append("missing_source_locator_requires_manual_trace")
        return signals

    @staticmethod
    def _sort_row_key(fact: dict[str, Any]) -> tuple[str, ...]:
        return (
            str(fact.get("field") or "").strip(),
            str(fact.get("land_use") or fact.get("category") or "").strip(),
            str(fact.get("subarea") or "").strip(),
            str(fact.get("threshold") or "").strip(),
            str(fact.get("payment_timing") or "").strip(),
            str(fact.get("payment_reduction_context") or "").strip(),
            str(fact.get("exemption_context") or "").strip(),
            RailwayRuntimeBridge._value_token_for_row(fact),
            str(fact.get("source_locator") or "").strip(),
            str(fact.get("source_family") or "").strip(),
            str(fact.get("source_url") or "").strip(),
        )

    @classmethod
    def _is_authoritative_official_attachment_row(cls, fact: dict[str, Any]) -> bool:
        lane = str(fact.get("source_lane_classification") or "").strip().lower()
        if lane == "secondary_search_derived":
            return False
        source_family = str(fact.get("source_family") or "").strip().lower()
        if source_family in {"tavily_secondary_search", "exa_secondary_search"}:
            return False
        attachment_id = str(fact.get("attachment_id") or "").strip()
        attachment_title = str(fact.get("attachment_title") or "").strip()
        if attachment_id or attachment_title:
            return True
        locator = str(fact.get("source_locator") or "").strip().lower()
        if locator.startswith("attachment_probe:"):
            return True
        source_url = str(fact.get("source_url") or "").strip().lower()
        if "legistar" in source_url and source_family in {
            "legistar_web_api",
            "resolution",
            "ordinance",
            "memorandum",
            "nexus_study",
            "staff_report",
            "official_attachment",
        }:
            return True
        return False

    @classmethod
    def _build_normalized_economic_rows(
        cls,
        *,
        canonical_document_key: str,
        selected_url: str,
        primary_facts: list[dict[str, Any]],
        structured_facts: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        lane_rank = {
            "primary_official": 0,
            "true_structured_source": 1,
            "secondary_search_derived": 2,
        }
        locator_rank = {
            "table_row_chunk_locator": 0,
            "chunk_locator_only": 1,
            "locator_not_available": 2,
        }

        def _row_priority(row: dict[str, Any]) -> tuple[int, int, int, float]:
            lane = str(row.get("source_lane_classification") or "secondary_search_derived")
            ambiguity = 1 if bool(row.get("ambiguity_flag")) else 0
            locator = str(row.get("locator_quality") or "locator_not_available")
            confidence = float(row.get("confidence") or 0.0)
            return (
                lane_rank.get(lane, 3),
                ambiguity,
                locator_rank.get(locator, 3),
                -confidence,
            )

        rows_by_key: dict[tuple[str, str, str, str, str, str, str, str, str, str, str], dict[str, Any]] = {}

        def _ingest_fact(fact: dict[str, Any], *, default_lane: str) -> None:
            source_url = str(fact.get("source_url") or selected_url).strip() or selected_url
            source_lane = str(fact.get("source_lane_classification") or default_lane).strip() or default_lane
            policy_key = (
                str(fact.get("policy_match_key") or "").strip()
                or canonical_document_key
                or source_url
            )
            normalized_value = cls._to_float(fact.get("normalized_value", fact.get("value")))
            raw_value = str(fact.get("raw_value") or "").strip() or None
            land_use = str(fact.get("land_use") or fact.get("category") or "unknown").strip() or "unknown"
            subarea = str(fact.get("subarea") or "").strip() or None
            threshold = str(fact.get("threshold") or "").strip() or None
            ambiguity_flag = bool(fact.get("ambiguity_flag")) or normalized_value is None
            ambiguity_reason = str(fact.get("ambiguity_reason") or "").strip() or None
            currency_sanity = str(fact.get("currency_sanity") or "").strip().lower() or "valid"
            unit_sanity = str(fact.get("unit_sanity") or "").strip().lower() or "valid"
            arithmetic_eligible = (
                normalized_value is not None
                and not ambiguity_flag
                and currency_sanity != "invalid"
                and unit_sanity != "invalid"
            )
            row_payload = {
                "policy_key": policy_key,
                "field": str(fact.get("field") or "unknown_parameter").strip(),
                "source_url": source_url,
                "source_ref": str(fact.get("source_ref") or source_url).strip() or source_url,
                "attachment_id": str(fact.get("attachment_id") or "").strip() or None,
                "attachment_title": str(fact.get("attachment_title") or "").strip() or None,
                "source_locator": str(fact.get("source_locator") or "").strip() or None,
                "chunk_locator": str(fact.get("chunk_locator") or "").strip() or None,
                "table_locator": str(fact.get("table_locator") or "").strip() or None,
                "page_locator": str(fact.get("page_locator") or "").strip() or None,
                "locator_quality": str(fact.get("locator_quality") or "").strip() or "locator_not_available",
                "land_use": land_use,
                "category": land_use,
                "subarea": subarea,
                "geography": str(fact.get("geography") or "").strip() or None,
                "threshold": threshold,
                "payment_timing": str(fact.get("payment_timing") or "").strip() or None,
                "payment_reduction_context": str(fact.get("payment_reduction_context") or "").strip() or None,
                "payment_reduction_percent": float(fact.get("payment_reduction_percent"))
                if isinstance(fact.get("payment_reduction_percent"), (int, float))
                else None,
                "exemption_context": str(fact.get("exemption_context") or "").strip() or None,
                "raw_land_use_label": str(fact.get("raw_land_use_label") or "").strip() or None,
                "raw_value": raw_value,
                "normalized_value": normalized_value,
                "unit": str(fact.get("unit") or "").strip() or None,
                "denominator": str(fact.get("denominator") or "").strip() or None,
                "effective_date": str(fact.get("effective_date") or "").strip() or None,
                "adoption_date": str(fact.get("adoption_date") or "").strip() or None,
                "final_status": str(fact.get("final_status") or "").strip() or "unknown",
                "source_hierarchy_status": str(
                    fact.get("source_hierarchy_status") or "bill_or_reg_text"
                ).strip(),
                "confidence": float(fact.get("confidence"))
                if isinstance(fact.get("confidence"), (int, float))
                else 0.5,
                "ambiguity_flag": ambiguity_flag,
                "ambiguity_reason": ambiguity_reason,
                "currency_sanity": currency_sanity,
                "unit_sanity": unit_sanity,
                "sanity_checks": {
                    "currency": currency_sanity,
                    "unit": unit_sanity,
                    "arithmetic_eligible": arithmetic_eligible,
                },
                "source_lane_classification": source_lane,
                "source_family": str(fact.get("source_family") or "").strip() or None,
            }
            row_payload["fail_closed_signals"] = cls._locator_fail_closed_signals(row_payload)
            value_token = (
                f"{normalized_value:.6f}"
                if normalized_value is not None
                else str(raw_value or "")
            )
            dedupe_key = (
                policy_key,
                row_payload["field"],
                land_use,
                str(subarea or ""),
                str(threshold or ""),
                str(row_payload.get("payment_timing") or ""),
                str(row_payload.get("payment_reduction_context") or ""),
                str(row_payload.get("exemption_context") or ""),
                str(row_payload.get("raw_land_use_label") or ""),
                str(row_payload.get("source_locator") or ""),
                value_token,
            )
            existing = rows_by_key.get(dedupe_key)
            if existing is None or _row_priority(row_payload) < _row_priority(existing):
                row_hash_input = "|".join(dedupe_key + (source_url,))
                row_payload["row_id"] = f"econ-row-{_hash(row_hash_input)[:16]}"
                rows_by_key[dedupe_key] = row_payload

        for primary in primary_facts:
            _ingest_fact(primary, default_lane="primary_official")
        for structured in structured_facts:
            _ingest_fact(
                structured,
                default_lane=str(
                    structured.get("source_lane_classification") or "true_structured_source"
                ).strip()
                or "true_structured_source",
            )

        rows = list(rows_by_key.values())
        return sorted(
            rows,
            key=lambda row: (
                lane_rank.get(str(row.get("source_lane_classification") or ""), 3),
                str(row.get("land_use") or ""),
                str(row.get("subarea") or ""),
                str(row.get("threshold") or ""),
                str(row.get("payment_timing") or ""),
                str(row.get("payment_reduction_context") or ""),
                str(row.get("exemption_context") or ""),
                str(row.get("raw_land_use_label") or ""),
                cls._value_token_for_row(row),
                str(row.get("source_url") or ""),
            ),
        )

    @classmethod
    def _reconcile_parameter_sources(
        cls,
        *,
        primary_facts: list[dict[str, Any]],
        secondary_facts: list[dict[str, Any]],
    ) -> dict[str, Any]:
        def _dedupe_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
            deduped: list[dict[str, Any]] = []
            seen_identity: set[tuple[str, ...]] = set()
            for row in rows:
                identity = cls._economic_row_identity(row)
                if identity in seen_identity:
                    continue
                seen_identity.add(identity)
                deduped.append(row)
            return deduped

        primary_rows = _dedupe_rows(primary_facts)
        true_structured_rows: list[dict[str, Any]] = []
        secondary_snippet_rows: list[dict[str, Any]] = []
        for fact in secondary_facts:
            lane = str(fact.get("source_lane_classification") or "").strip()
            if lane == "secondary_search_derived":
                secondary_snippet_rows.append(fact)
            else:
                true_structured_rows.append(fact)
        true_structured_rows = _dedupe_rows(true_structured_rows)
        secondary_snippet_rows = _dedupe_rows(secondary_snippet_rows)
        official_attachment_row_count = sum(
            1 for row in true_structured_rows if cls._is_authoritative_official_attachment_row(row)
        )

        true_structured_by_key: dict[tuple[str, str, str, str, str, str, str, str, str, str], list[dict[str, Any]]] = {}
        secondary_snippet_by_key: dict[tuple[str, str, str, str, str, str, str, str, str, str], list[dict[str, Any]]] = {}
        for row in true_structured_rows:
            true_structured_by_key.setdefault(cls._economic_row_key(row), []).append(row)
        for row in secondary_snippet_rows:
            secondary_snippet_by_key.setdefault(cls._economic_row_key(row), []).append(row)

        records: list[dict[str, Any]] = []
        used_true: set[tuple[str, ...]] = set()
        used_secondary: set[tuple[str, ...]] = set()

        for primary in sorted(primary_rows, key=cls._sort_row_key):
            row_key = cls._economic_row_key(primary)
            primary_identity = cls._economic_row_identity(primary)
            primary_value = cls._to_float(primary.get("normalized_value", primary.get("value")))
            true_matches = true_structured_by_key.get(row_key, [])
            secondary_matches = secondary_snippet_by_key.get(row_key, [])
            true_values = [
                cls._to_float(item.get("normalized_value", item.get("value")))
                for item in true_matches
            ]
            true_values = [value for value in true_values if value is not None]
            for item in true_matches:
                used_true.add(cls._economic_row_identity(item))
            for item in secondary_matches:
                used_secondary.add(cls._economic_row_identity(item))

            status = "missing_structured_corroboration"
            source_of_truth = "primary_scraped_document"
            decision_reason = "primary_official_row_missing_true_structured_corroboration"
            if primary_value is None:
                status = "conflict_unresolved"
                source_of_truth = "none"
                decision_reason = "primary_value_ambiguous_manual_review_required"
            elif true_values:
                if any(abs(primary_value - value) < 1e-6 for value in true_values):
                    status = "confirmed"
                    decision_reason = "primary_official_confirmed_by_true_structured_source"
                else:
                    status = "source_of_truth_selected"
                    decision_reason = "primary_artifact_precedence_over_true_structured_conflict"
            elif secondary_matches:
                status = "missing_structured_corroboration"
                decision_reason = (
                    "primary_artifact_precedence_over_secondary_search;"
                    "true_structured_corroboration_missing"
                )

            locator_signals = cls._locator_fail_closed_signals(primary)
            if locator_signals and status != "confirmed":
                decision_reason = f"{decision_reason};locator_precision_insufficient"

            records.append(
                {
                    "field": row_key[0],
                    "land_use": row_key[1],
                    "subarea": row_key[2] or None,
                    "threshold": row_key[3] or None,
                    "payment_timing": row_key[4] or None,
                    "payment_reduction_context": row_key[5] or None,
                    "exemption_context": row_key[6] or None,
                    "raw_land_use_label": row_key[7] or None,
                    "status": status,
                    "source_of_truth": source_of_truth,
                    "primary_value": primary_value,
                    "secondary_value": true_values[0]
                    if true_values
                    else (
                        cls._to_float(
                            secondary_matches[0].get(
                                "normalized_value",
                                secondary_matches[0].get("value"),
                            )
                        )
                        if secondary_matches
                        else None
                    ),
                    "decision_reason": decision_reason,
                    "source_url": str(primary.get("source_url") or "").strip() or None,
                    "source_locator": str(primary.get("source_locator") or "").strip() or None,
                    "source_locator_quality": str(primary.get("locator_quality") or "").strip()
                    or "locator_not_available",
                    "source_family": str(primary.get("source_family") or "").strip() or None,
                    "true_structured_source_families": sorted(
                        {
                            str(item.get("source_family") or "").strip()
                            for item in true_matches
                            if str(item.get("source_family") or "").strip()
                        }
                    ),
                    "secondary_source_families": sorted(
                        {
                            str(item.get("source_family") or "").strip()
                            for item in secondary_matches
                            if str(item.get("source_family") or "").strip()
                        }
                    ),
                    "fail_closed_signals": locator_signals,
                    "row_identity": "|".join(primary_identity),
                }
            )

        for row_key, matches in true_structured_by_key.items():
            for item in matches:
                identity = cls._economic_row_identity(item)
                if identity in used_true:
                    continue
                value = cls._to_float(item.get("normalized_value", item.get("value")))
                is_authoritative_attachment = cls._is_authoritative_official_attachment_row(item)
                records.append(
                    {
                        "field": row_key[0],
                        "land_use": row_key[1],
                        "subarea": row_key[2] or None,
                        "threshold": row_key[3] or None,
                        "payment_timing": row_key[4] or None,
                        "payment_reduction_context": row_key[5] or None,
                        "exemption_context": row_key[6] or None,
                        "raw_land_use_label": row_key[7] or None,
                        "status": (
                            "authoritative_structured_attachment"
                            if is_authoritative_attachment
                            else "conflict_unresolved"
                        ),
                        "source_of_truth": "true_structured_source" if is_authoritative_attachment else "none",
                        "primary_value": None,
                        "secondary_value": value,
                        "decision_reason": (
                            "official_attachment_true_structured_row_available"
                            if is_authoritative_attachment
                            else "true_structured_row_without_primary_official_match"
                        ),
                        "source_url": str(item.get("source_url") or "").strip() or None,
                        "source_locator": str(item.get("source_locator") or "").strip() or None,
                        "source_locator_quality": str(item.get("locator_quality") or "").strip()
                        or "locator_not_available",
                        "source_family": str(item.get("source_family") or "").strip() or "unknown",
                        "true_structured_source_families": [
                            str(item.get("source_family") or "unknown")
                        ],
                        "secondary_source_families": [],
                        "fail_closed_signals": cls._locator_fail_closed_signals(item),
                        "row_identity": "|".join(identity),
                    }
                )

        for row_key, matches in secondary_snippet_by_key.items():
            for item in matches:
                identity = cls._economic_row_identity(item)
                if identity in used_secondary:
                    continue
                value = cls._to_float(item.get("normalized_value", item.get("value")))
                records.append(
                    {
                        "field": row_key[0],
                        "land_use": row_key[1],
                        "subarea": row_key[2] or None,
                        "threshold": row_key[3] or None,
                        "payment_timing": row_key[4] or None,
                        "payment_reduction_context": row_key[5] or None,
                        "exemption_context": row_key[6] or None,
                        "raw_land_use_label": row_key[7] or None,
                        "status": "secondary_only_not_authoritative",
                        "source_of_truth": "none",
                        "primary_value": None,
                        "secondary_value": value,
                        "decision_reason": "secondary_search_row_without_primary_official_match",
                        "source_url": str(item.get("source_url") or "").strip() or None,
                        "source_locator": str(item.get("source_locator") or "").strip() or None,
                        "source_locator_quality": str(item.get("locator_quality") or "").strip()
                        or "locator_not_available",
                        "source_family": str(item.get("source_family") or "").strip() or "unknown",
                        "true_structured_source_families": [],
                        "secondary_source_families": [
                            str(item.get("source_family") or "unknown")
                        ],
                        "fail_closed_signals": cls._locator_fail_closed_signals(item),
                        "row_identity": "|".join(identity),
                    }
                )

        sorted_records = sorted(
            records,
            key=lambda item: (
                str(item.get("field") or ""),
                str(item.get("land_use") or ""),
                str(item.get("subarea") or ""),
                str(item.get("threshold") or ""),
                str(item.get("payment_timing") or ""),
                str(item.get("payment_reduction_context") or ""),
                str(item.get("exemption_context") or ""),
                str(item.get("raw_land_use_label") or ""),
                str(
                    item.get("primary_value")
                    if item.get("primary_value") is not None
                    else item.get("secondary_value")
                ),
                str(item.get("source_locator") or ""),
                str(item.get("source_family") or ""),
            ),
        )
        unresolved = [
            item
            for item in sorted_records
            if str(item.get("status") or "") in {"conflict_unresolved", "missing_structured_corroboration"}
        ]
        return {
            "records": sorted_records,
            "unresolved_count": len(unresolved),
            "source_of_truth_policy": "primary_artifact_precedence_then_labeled_secondary",
            "secondary_override_blocked": all(
                str(item.get("source_of_truth") or "") != "secondary_search_derived"
                for item in sorted_records
            ),
            "primary_official_row_count": len(primary_rows),
            "true_structured_row_count": len(true_structured_rows),
            "secondary_snippet_row_count": len(secondary_snippet_rows),
            "official_attachment_row_count": official_attachment_row_count,
            "official_attachment_authoritative_row_count": official_attachment_row_count,
            "missing_true_structured_corroboration_count": sum(
                1
                for item in sorted_records
                if str(item.get("status") or "") == "missing_structured_corroboration"
            ),
            "fail_closed_locator_signal_count": sum(
                1 for item in sorted_records if item.get("fail_closed_signals")
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
        raw_content = ""
        if raw_scrape_id:
            raw_row = await self.db._fetchrow(
                """
                SELECT canonical_document_key, content_hash, storage_uri, data->>'content' AS raw_content
                FROM raw_scrapes
                WHERE id = $1::uuid
                LIMIT 1
                """,
                raw_scrape_id,
            )
            if raw_row:
                canonical_document_key = str(raw_row["canonical_document_key"] or "")
                content_hash = str(raw_row["content_hash"] or "")
                try:
                    raw_content = str(raw_row["raw_content"] or "")
                except KeyError:
                    row_data = getattr(raw_row, "data", {})
                    raw_data = row_data.get("data") if isinstance(row_data, dict) else {}
                    raw_content = str(raw_data.get("content") or "") if isinstance(raw_data, dict) else ""
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
        read_fetch_details = read_fetch.details if read_fetch else {}
        ranked_candidates = (
            list(read_fetch_details.get("ranked_candidates", []))
            if isinstance(read_fetch_details.get("ranked_candidates", []), list)
            else []
        )
        selected_candidate_context = self._structured_candidate_context(
            search_query=request.search_query,
            selected_url=selected_url,
            ranked_candidates=ranked_candidates,
        )
        structured_enrichment = await self.structured_enricher.enrich(
            jurisdiction=request.jurisdiction,
            source_family=request.source_family,
            search_query=request.search_query,
            selected_url=selected_url,
            selected_candidate_context=selected_candidate_context,
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
            jurisdiction=request.jurisdiction,
            search_query=request.search_query,
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
        analysis_fee_facts, primary_parameter_alerts = self._extract_primary_fee_facts_from_analysis(
            analyze=analyze,
            selected_url=selected_url,
        )
        raw_fee_facts, raw_parameter_alerts = self._extract_primary_fee_facts_from_text_parts(
            text_parts=[raw_content] if raw_content else [],
            selected_url=selected_url,
            source_locator_prefix="reader_content",
        )
        primary_fee_facts = self._merge_primary_fee_facts(analysis_fee_facts, raw_fee_facts)
        primary_parameter_alerts = sorted(set(primary_parameter_alerts + raw_parameter_alerts))
        structured_numeric_facts = self._collect_secondary_numeric_facts(structured_enrichment.candidates)
        normalized_economic_rows = self._build_normalized_economic_rows(
            canonical_document_key=canonical_document_key,
            selected_url=selected_url,
            primary_facts=primary_fee_facts,
            structured_facts=structured_numeric_facts,
        )
        source_reconciliation = self._reconcile_parameter_sources(
            primary_facts=primary_fee_facts,
            secondary_facts=structured_numeric_facts,
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
            "normalized_official_economic_rows": normalized_economic_rows,
            "search_provider_runtime": search_provider_runtime,
            "source_shape_drift": source_shape_drift,
            "primary_parameter_extraction": {
                "source": "analyze.evidence_selection.selected_chunks",
                "parameter_count": len(primary_fee_facts),
                "normalized_row_count": len(normalized_economic_rows),
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
        package_payload["normalized_official_economic_rows"] = normalized_economic_rows

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
        ranked_candidates = self._prioritize_artifact_candidates_for_fetch(
            ranked_candidates=ranked_candidates,
            query_text=request.search_query,
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
            fee_schedule_gate = self._evaluate_maintained_fee_schedule_gate(
                url=canonical_url,
                title=title,
                snippet=str(candidate.get("snippet") or ""),
                markdown_body=markdown_body,
            )
            candidate_artifact_family = self._candidate_artifact_family_from_audit_entry(
                url=canonical_url,
                audit_entry={"fee_schedule_gate": fee_schedule_gate},
            )

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
                    "candidate_artifact_family": candidate_artifact_family,
                    "fee_schedule_gate": fee_schedule_gate,
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
