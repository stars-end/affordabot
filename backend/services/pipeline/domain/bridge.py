"""Backend-owned command bridge for Windmill run_scope_pipeline calls."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Any

from services.pipeline.domain.commands import PipelineDomainCommands
from services.pipeline.domain.constants import CONTRACT_VERSION
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

ALLOWED_STALE_STATUSES = {
    "fresh",
    "stale_but_usable",
    "stale_blocked",
    "empty_but_usable",
    "empty_blocked",
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


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


class PipelineDomainBridge:
    """Coarse backend command bridge used by internal orchestration callers."""

    def __init__(self, *, state: InMemoryDomainState | None = None) -> None:
        self._lock = Lock()
        self.state = state or InMemoryDomainState()

    def run_scope_pipeline(self, request: RunScopeRequest) -> dict[str, Any]:
        with self._lock:
            self._validate_request(request)
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
                "missing_runtime_adapters": [
                    "postgres_pipeline_state_store_adapter",
                    "minio_artifact_store_adapter",
                    "pgvector_chunk_store_adapter",
                ],
            }

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
            idempotency_key=request.idempotency_key,
            windmill=windmill,
            contract_version=request.contract_version,
        )

    def _step_payload(self, response: CommandResponse, request: RunScopeRequest) -> dict[str, Any]:
        payload = response.to_dict()
        payload["envelope"] = {
            "contract_version": request.contract_version,
            "idempotency_key": request.idempotency_key,
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

