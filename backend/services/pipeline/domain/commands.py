"""Domain command service for Windmill/orchestrator integration."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import re
from typing import Any

from services.pipeline.domain.constants import CONTRACT_VERSION
from services.pipeline.domain.identity import build_v2_canonical_document_key
from services.pipeline.domain.in_memory import InMemoryDomainState, stable_json_hash
from services.pipeline.domain.models import CommandEnvelope, CommandResponse, FreshnessPolicy
from services.pipeline.domain.ports import (
    Analyzer,
    ArtifactStore,
    ReaderProvider,
    SearchProvider,
    SearchResultItem,
    VectorStore,
)

NAVIGATION_MARKERS = (
    "home",
    "contact",
    "sitemap",
    "menu",
    "navigation",
    "skip to content",
    "privacy",
    "accessibility",
    "subscribe",
    "sign up",
    "alerts",
    "departments",
)

SUBSTANTIVE_MARKERS = (
    "meeting",
    "minutes",
    "agenda",
    "council",
    "ordinance",
    "resolution",
    "vote",
    "hearing",
    "public comment",
    "housing",
    "budget",
    "policy",
)

ACTION_MARKERS = (
    "approved",
    "adopted",
    "motion",
    "vote",
    "voted",
    "resolution",
    "ordinance",
    "staff report",
    "recommendation",
    "recommended",
    "public hearing",
    "agenda item",
    "item 8",
    "item 10",
    "directed staff",
    "memorandum",
)


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _stable_chunk_id(
    *,
    canonical_document_key: str,
    content_hash: str,
    chunk_index: int,
    chunk_text: str,
) -> str:
    chunk_text_hash = _hash_text(chunk_text)
    material = (
        f"{CONTRACT_VERSION}|{canonical_document_key}|{content_hash}|{chunk_index}|{chunk_text_hash}"
    )
    return f"chunk_{_hash_text(material)}"


def _split_chunks(text: str) -> list[str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return []
    return lines


def assess_reader_substance(text: str) -> tuple[bool, dict[str, Any]]:
    normalized_lines = [line.strip().lower() for line in text.splitlines() if line.strip()]
    joined = " ".join(normalized_lines)
    word_count = len(re.findall(r"[a-z0-9$%.-]+", joined))
    nav_line_hits = sum(
        1 for line in normalized_lines if any(marker in line for marker in NAVIGATION_MARKERS)
    )
    nav_marker_hits = sum(1 for marker in NAVIGATION_MARKERS if marker in joined)
    substantive_hits = sum(1 for marker in SUBSTANTIVE_MARKERS if marker in joined)
    action_hits = sum(1 for marker in ACTION_MARKERS if marker in joined)
    markdown_image_count = joined.count("![image")
    bullet_line_count = sum(1 for line in normalized_lines if line.startswith("- "))
    line_count = len(normalized_lines)

    reason = "ok"
    is_substantive = True
    if not normalized_lines or word_count == 0:
        reason = "empty_reader_output"
        is_substantive = False
    elif nav_line_hits >= max(2, line_count // 2) and substantive_hits == 0:
        reason = "navigation_heavy"
        is_substantive = False
    elif nav_marker_hits >= 6 and substantive_hits <= 1:
        reason = "navigation_heavy"
        is_substantive = False
    elif markdown_image_count >= 8 and action_hits <= 1:
        reason = "navigation_heavy"
        is_substantive = False
    elif nav_marker_hits >= 8 and bullet_line_count >= 20 and action_hits <= 2:
        reason = "navigation_heavy"
        is_substantive = False
    elif (
        markdown_image_count >= 12
        and bullet_line_count >= 80
        and nav_marker_hits >= 4
        and bullet_line_count >= max(120, int(line_count * 0.6))
    ):
        reason = "navigation_heavy"
        is_substantive = False
    elif word_count < 25 and substantive_hits == 0:
        reason = "low_substantive_signal"
        is_substantive = False

    details = {
        "reason": reason,
        "word_count": word_count,
        "line_count": line_count,
        "navigation_line_hits": nav_line_hits,
        "navigation_marker_hits": nav_marker_hits,
        "substantive_marker_hits": substantive_hits,
        "action_marker_hits": action_hits,
        "markdown_image_count": markdown_image_count,
        "bullet_line_count": bullet_line_count,
    }
    return is_substantive, details


class PipelineDomainCommands:
    """Implements the six coarse commands with deterministic in-memory semantics."""

    def __init__(
        self,
        *,
        state: InMemoryDomainState,
        search_provider: SearchProvider,
        reader_provider: ReaderProvider,
        artifact_store: ArtifactStore,
        vector_store: VectorStore,
        analyzer: Analyzer,
    ) -> None:
        self.state = state
        self.search_provider = search_provider
        self.reader_provider = reader_provider
        self.artifact_store = artifact_store
        self.vector_store = vector_store
        self.analyzer = analyzer

    def _reuse_if_idempotent(self, envelope: CommandEnvelope) -> CommandResponse | None:
        cached = self.state.command_results.get(self._command_result_key(envelope))
        if not cached:
            return None
        response = CommandResponse(**cached)
        response.details = {
            **response.details,
            "idempotent_reuse": True,
        }
        return response

    def _store_result(self, envelope: CommandEnvelope, response: CommandResponse) -> CommandResponse:
        self.state.command_results[self._command_result_key(envelope)] = asdict(response)
        return response

    def _command_result_key(self, envelope: CommandEnvelope) -> str:
        return f"{envelope.command}:{envelope.idempotency_key}"

    def _windmill_refs(self, envelope: CommandEnvelope) -> dict[str, str]:
        return {
            "windmill_run_id": envelope.windmill.run_id,
            "windmill_job_id": envelope.windmill.job_id,
        }

    def search_materialize(
        self, *, envelope: CommandEnvelope, query: str, max_results: int = 10
    ) -> CommandResponse:
        envelope.validate()
        reused = self._reuse_if_idempotent(envelope)
        if reused:
            return reused

        try:
            results = self.search_provider.search(
                query=query,
                jurisdiction_id=envelope.jurisdiction_id,
                source_family=envelope.source_family,
                max_results=max_results,
            )
        except Exception as exc:
            return self._store_result(
                envelope,
                CommandResponse(
                    command="search_materialize",
                    status="failed_retryable",
                    decision_reason="search_transport_error",
                    retry_class="transport",
                    alerts=[f"search_provider_error:{exc}"],
                    refs=self._windmill_refs(envelope),
                ),
            )

        snapshot_hash = stable_json_hash(
            {
                "query": query,
                "jurisdiction_id": envelope.jurisdiction_id,
                "source_family": envelope.source_family,
                "results": [asdict(item) for item in results],
            }
        )
        snapshot_id = f"snapshot_{snapshot_hash[:16]}"
        self.state.search_snapshots[snapshot_id] = {
            "snapshot_id": snapshot_id,
            "query": query,
            "jurisdiction_id": envelope.jurisdiction_id,
            "source_family": envelope.source_family,
            "captured_at": self.state.now.isoformat(),
            "results": [asdict(item) for item in results],
        }

        status = "succeeded" if results else "succeeded_with_alerts"
        decision_reason = "fresh_snapshot_materialized" if results else "search_empty_result"
        alerts = [] if results else ["search_results_empty"]

        return self._store_result(
            envelope,
            CommandResponse(
                command="search_materialize",
                status=status,
                decision_reason=decision_reason,
                retry_class="none",
                alerts=alerts,
                counts={"search_results": len(results)},
                refs={**self._windmill_refs(envelope), "search_snapshot_id": snapshot_id},
                details={"query": query},
            ),
        )

    def freshness_gate(
        self,
        *,
        envelope: CommandEnvelope,
        snapshot_id: str,
        policy: FreshnessPolicy,
        latest_success_at: datetime | None,
    ) -> CommandResponse:
        envelope.validate()
        reused = self._reuse_if_idempotent(envelope)
        if reused:
            return reused

        snapshot = self.state.search_snapshots.get(snapshot_id)
        if not snapshot:
            return self._store_result(
                envelope,
                CommandResponse(
                    command="freshness_gate",
                    status="failed_terminal",
                    decision_reason="missing_snapshot",
                    retry_class="contract_violation",
                    refs=self._windmill_refs(envelope),
                ),
            )

        captured_at = datetime.fromisoformat(snapshot["captured_at"])
        snapshot_age_hours = int((_as_utc(self.state.now) - _as_utc(captured_at)).total_seconds() / 3600)
        result_count = len(snapshot["results"])

        fallback_age_hours = None
        if latest_success_at:
            fallback_age_hours = int(
                (_as_utc(self.state.now) - _as_utc(latest_success_at)).total_seconds() / 3600
            )

        freshness_status = "fresh"
        alerts: list[str] = []
        status = "succeeded"

        if result_count == 0:
            if fallback_age_hours is not None and fallback_age_hours <= policy.stale_usable_ceiling_hours:
                freshness_status = "empty_but_usable"
                status = "succeeded_with_alerts"
                alerts.append("source_search_failed_using_last_success")
            else:
                freshness_status = "empty_blocked"
                status = "blocked"
                alerts.append("empty_search_results_fail_closed")
        elif snapshot_age_hours <= policy.fresh_hours:
            freshness_status = "fresh"
        elif snapshot_age_hours <= policy.stale_usable_ceiling_hours:
            freshness_status = "stale_but_usable"
            status = "succeeded_with_alerts"
            alerts.append("source_search_failed_using_last_success")
        else:
            freshness_status = "stale_blocked"
            status = "blocked"
            alerts.append("stale_search_results_fail_closed")

        retry_class = "none" if status != "blocked" else "operator_required"
        return self._store_result(
            envelope,
            CommandResponse(
                command="freshness_gate",
                status=status,
                decision_reason=freshness_status,
                retry_class=retry_class,
                alerts=alerts,
                counts={"search_results": result_count},
                refs={**self._windmill_refs(envelope), "search_snapshot_id": snapshot_id},
                details={
                    "freshness_status": freshness_status,
                    "fresh_hours": policy.fresh_hours,
                    "stale_usable_ceiling_hours": policy.stale_usable_ceiling_hours,
                    "fail_closed_ceiling_hours": policy.fail_closed_ceiling_hours,
                    "snapshot_age_hours": snapshot_age_hours,
                    "fallback_age_hours": fallback_age_hours,
                },
            ),
        )

    def read_fetch(
        self, *, envelope: CommandEnvelope, snapshot_id: str, max_reads: int = 1
    ) -> CommandResponse:
        envelope.validate()
        reused = self._reuse_if_idempotent(envelope)
        if reused:
            return reused

        snapshot = self.state.search_snapshots.get(snapshot_id)
        if not snapshot:
            return self._store_result(
                envelope,
                CommandResponse(
                    command="read_fetch",
                    status="failed_terminal",
                    decision_reason="missing_snapshot",
                    retry_class="contract_violation",
                    refs=self._windmill_refs(envelope),
                ),
            )

        selected: list[SearchResultItem] = [
            SearchResultItem(
                url=item["url"],
                title=item.get("title", ""),
                snippet=item.get("snippet", ""),
            )
            for item in snapshot["results"][:max_reads]
        ]
        if not selected:
            return self._store_result(
                envelope,
                CommandResponse(
                    command="read_fetch",
                    status="blocked",
                    decision_reason="no_candidate_urls",
                    retry_class="insufficient_evidence",
                    refs=self._windmill_refs(envelope),
                ),
            )

        raw_scrape_ids: list[str] = []
        artifact_refs: list[str] = []
        quality_alerts: list[str] = []
        reader_quality_failures: list[dict[str, Any]] = []
        for candidate in selected:
            try:
                doc = self.reader_provider.fetch(url=candidate.url)
            except Exception as exc:
                return self._store_result(
                    envelope,
                    CommandResponse(
                        command="read_fetch",
                        status="failed_retryable",
                        decision_reason="reader_provider_error",
                        retry_class="provider_unavailable",
                        alerts=[f"reader_error:{exc}"],
                        refs=self._windmill_refs(envelope),
                    ),
                )

            is_substantive, quality_details = assess_reader_substance(doc.text)
            if not is_substantive:
                reason = str(quality_details["reason"])
                quality_alerts.append(f"reader_output_insufficient_substance:{reason}")
                reader_quality_failures.append(
                    {
                        "url": candidate.url,
                        "reason": reason,
                        "quality_details": quality_details,
                    }
                )
                continue

            canonical_key = build_v2_canonical_document_key(
                jurisdiction_id=envelope.jurisdiction_id,
                source_family=envelope.source_family,
                url=doc.url,
                metadata={"document_type": doc.document_type, "title": doc.title},
                data={"published_date": doc.published_date},
            )
            content_hash = _hash_text(doc.text)
            scrape_id = f"raw_{_hash_text(f'{canonical_key}|{content_hash}')[:16]}"
            existing = self.state.raw_scrapes.get(scrape_id)
            if existing:
                existing["seen_count"] += 1
                existing["last_seen_at"] = self.state.now.isoformat()
                raw_scrape_ids.append(scrape_id)
                artifact_refs.append(existing["artifact_ref"])
                continue

            try:
                artifact = self.artifact_store.put(
                    contract_version=CONTRACT_VERSION,
                    jurisdiction_id=envelope.jurisdiction_id,
                    source_family=envelope.source_family,
                    artifact_kind="reader_output",
                    body=doc.text,
                    media_type=doc.media_type,
                )
            except Exception as exc:
                return self._store_result(
                    envelope,
                    CommandResponse(
                        command="read_fetch",
                        status="failed_terminal",
                        decision_reason="reader_artifact_write_failed",
                        retry_class="transient_storage",
                        alerts=[f"artifact_store_error:{exc}"],
                        refs=self._windmill_refs(envelope),
                    ),
                )

            self.state.raw_scrapes[scrape_id] = {
                "raw_scrape_id": scrape_id,
                "canonical_document_key": canonical_key,
                "content_hash": content_hash,
                "artifact_ref": artifact.artifact_ref,
                "jurisdiction_id": envelope.jurisdiction_id,
                "source_family": envelope.source_family,
                "seen_count": 1,
                "last_seen_at": self.state.now.isoformat(),
                "title": doc.title,
                "text": doc.text,
            }
            raw_scrape_ids.append(scrape_id)
            artifact_refs.append(artifact.artifact_ref)

        if not raw_scrape_ids:
            alerts = list(dict.fromkeys(quality_alerts)) or ["reader_output_insufficient_substance"]
            return self._store_result(
                envelope,
                CommandResponse(
                    command="read_fetch",
                    status="blocked",
                    decision_reason="reader_output_insufficient_substance",
                    retry_class="insufficient_evidence",
                    alerts=alerts,
                    refs=self._windmill_refs(envelope),
                    details={"reader_quality_failures": reader_quality_failures},
                ),
            )

        status = "succeeded_with_alerts" if quality_alerts else "succeeded"
        decision_reason = (
            "raw_scrapes_materialized_with_reader_alerts"
            if quality_alerts
            else "raw_scrapes_materialized"
        )
        return self._store_result(
            envelope,
            CommandResponse(
                command="read_fetch",
                status=status,
                decision_reason=decision_reason,
                retry_class="none",
                alerts=list(dict.fromkeys(quality_alerts)),
                counts={"raw_scrapes": len(raw_scrape_ids), "artifacts": len(artifact_refs)},
                refs={
                    **self._windmill_refs(envelope),
                    "raw_scrape_ids": raw_scrape_ids,
                    "artifact_refs": artifact_refs,
                },
                details={"reader_quality_failures": reader_quality_failures},
            ),
        )

    def index(self, *, envelope: CommandEnvelope, raw_scrape_ids: list[str]) -> CommandResponse:
        envelope.validate()
        reused = self._reuse_if_idempotent(envelope)
        if reused:
            return reused

        rows = [self.state.raw_scrapes.get(raw_id) for raw_id in raw_scrape_ids]
        valid_rows = [row for row in rows if row]
        if not valid_rows:
            return self._store_result(
                envelope,
                CommandResponse(
                    command="index",
                    status="blocked",
                    decision_reason="no_raw_scrapes",
                    retry_class="insufficient_evidence",
                    refs=self._windmill_refs(envelope),
                ),
            )

        chunks: list[dict[str, Any]] = []
        for row in valid_rows:
            for idx, chunk_text in enumerate(_split_chunks(row["text"])):
                chunk_id = _stable_chunk_id(
                    canonical_document_key=row["canonical_document_key"],
                    content_hash=row["content_hash"],
                    chunk_index=idx,
                    chunk_text=chunk_text,
                )
                chunks.append(
                    {
                        "chunk_id": chunk_id,
                        "raw_scrape_id": row["raw_scrape_id"],
                        "canonical_document_key": row["canonical_document_key"],
                        "artifact_ref": row["artifact_ref"],
                        "jurisdiction_id": row["jurisdiction_id"],
                        "source_family": row["source_family"],
                        "contract_version": CONTRACT_VERSION,
                        "chunk_index": idx,
                        "text": chunk_text,
                    }
                )

        try:
            upserted = self.vector_store.upsert_chunks(chunks)
        except Exception as exc:
            return self._store_result(
                envelope,
                CommandResponse(
                    command="index",
                    status="failed_retryable",
                    decision_reason="vector_write_failed",
                    retry_class="transient_storage",
                    alerts=[f"vector_store_error:{exc}"],
                    refs=self._windmill_refs(envelope),
                ),
            )

        return self._store_result(
            envelope,
            CommandResponse(
                command="index",
                status="succeeded",
                decision_reason="chunks_indexed",
                retry_class="none",
                counts={"chunks": upserted},
                refs={**self._windmill_refs(envelope), "raw_scrape_ids": raw_scrape_ids},
            ),
        )

    def analyze(
        self,
        *,
        envelope: CommandEnvelope,
        question: str,
        jurisdiction_id: str,
        source_family: str,
    ) -> CommandResponse:
        envelope.validate()
        reused = self._reuse_if_idempotent(envelope)
        if reused:
            return reused

        evidence = [
            chunk
            for chunk in self.state.chunks.values()
            if chunk["jurisdiction_id"] == jurisdiction_id and chunk["source_family"] == source_family
        ]
        if not evidence:
            return self._store_result(
                envelope,
                CommandResponse(
                    command="analyze",
                    status="blocked",
                    decision_reason="no_evidence_chunks",
                    retry_class="insufficient_evidence",
                    refs=self._windmill_refs(envelope),
                    counts={"evidence_chunks": 0},
                ),
            )

        try:
            payload = self.analyzer.analyze(question=question, evidence_chunks=evidence)
        except Exception as exc:
            return self._store_result(
                envelope,
                CommandResponse(
                    command="analyze",
                    status="failed_terminal",
                    decision_reason="analysis_failed",
                    retry_class="contract_violation",
                    alerts=[f"analysis_error:{exc}"],
                    refs=self._windmill_refs(envelope),
                ),
            )

        analysis_id = f"analysis_{_hash_text(stable_json_hash(payload))[:16]}"
        self.state.analyses[analysis_id] = {
            "analysis_id": analysis_id,
            "question": question,
            "jurisdiction_id": jurisdiction_id,
            "source_family": source_family,
            "payload": payload,
            "contract_version": CONTRACT_VERSION,
        }
        self.state.previous_success_by_scope[f"{jurisdiction_id}|{source_family}"] = self.state.now
        return self._store_result(
            envelope,
            CommandResponse(
                command="analyze",
                status="succeeded",
                decision_reason="analysis_completed",
                retry_class="none",
                counts={"analyses": 1, "evidence_chunks": len(evidence)},
                refs={**self._windmill_refs(envelope), "analysis_id": analysis_id},
                details={"sufficiency_state": payload.get("sufficiency_state")},
            ),
        )

    def summarize_run(
        self,
        *,
        envelope: CommandEnvelope,
        command_responses: list[CommandResponse],
    ) -> CommandResponse:
        envelope.validate()
        reused = self._reuse_if_idempotent(envelope)
        if reused:
            return reused

        counts: dict[str, int] = {}
        refs: dict[str, Any] = self._windmill_refs(envelope)
        alerts: list[str] = []
        statuses: list[str] = []
        step_map: dict[str, str] = {}
        for result in command_responses:
            statuses.append(result.status)
            alerts.extend(result.alerts)
            for key, value in result.counts.items():
                counts[key] = counts.get(key, 0) + value
            step_map[result.command] = result.status
            refs.update({f"{result.command}_reason": result.decision_reason})
            refs.update({f"{result.command}_retry_class": result.retry_class})

        summary_status = "succeeded"
        if any(status == "failed_terminal" for status in statuses):
            summary_status = "failed_terminal"
        elif any(status == "failed_retryable" for status in statuses):
            summary_status = "failed_retryable"
        elif any(status == "blocked" for status in statuses):
            summary_status = "blocked"
        elif any(status == "succeeded_with_alerts" for status in statuses):
            summary_status = "succeeded_with_alerts"

        run_id = f"run_{envelope.windmill.run_id}"
        self.state.run_summaries[run_id] = {
            "run_id": run_id,
            "summary_status": summary_status,
            "step_statuses": step_map,
            "counts": counts,
            "alerts": list(dict.fromkeys(alerts)),
        }
        return self._store_result(
            envelope,
            CommandResponse(
                command="summarize_run",
                status=summary_status,
                decision_reason="run_summary_materialized",
                retry_class="none" if summary_status.startswith("succeeded") else "operator_required",
                alerts=list(dict.fromkeys(alerts)),
                counts=counts,
                refs=refs | {"run_id": run_id},
                details={"step_statuses": step_map},
            ),
        )

    def full_refresh(
        self,
        *,
        query: str,
        question: str,
        search_envelope: CommandEnvelope,
        freshness_envelope: CommandEnvelope,
        read_envelope: CommandEnvelope,
        index_envelope: CommandEnvelope,
        analyze_envelope: CommandEnvelope,
        summarize_envelope: CommandEnvelope,
        policy: FreshnessPolicy,
    ) -> list[CommandResponse]:
        search_result = self.search_materialize(envelope=search_envelope, query=query)
        snapshot_id = str(search_result.refs.get("search_snapshot_id", ""))
        latest_success = self.state.previous_success_by_scope.get(
            f"{search_envelope.jurisdiction_id}|{search_envelope.source_family}"
        )
        freshness_result = self.freshness_gate(
            envelope=freshness_envelope,
            snapshot_id=snapshot_id,
            policy=policy,
            latest_success_at=latest_success,
        )
        responses = [search_result, freshness_result]
        freshness_state = freshness_result.decision_reason

        if freshness_state in {"stale_blocked", "empty_blocked"}:
            responses.append(self.summarize_run(envelope=summarize_envelope, command_responses=responses))
            return responses

        read_result = self.read_fetch(envelope=read_envelope, snapshot_id=snapshot_id)
        responses.append(read_result)
        if read_result.status not in {"succeeded", "succeeded_with_alerts", "skipped"}:
            responses.append(self.summarize_run(envelope=summarize_envelope, command_responses=responses))
            return responses

        index_result = self.index(
            envelope=index_envelope,
            raw_scrape_ids=list(read_result.refs.get("raw_scrape_ids", [])),
        )
        responses.append(index_result)

        analyze_result = self.analyze(
            envelope=analyze_envelope,
            question=question,
            jurisdiction_id=search_envelope.jurisdiction_id,
            source_family=search_envelope.source_family,
        )
        responses.append(analyze_result)
        responses.append(self.summarize_run(envelope=summarize_envelope, command_responses=responses))
        return responses
