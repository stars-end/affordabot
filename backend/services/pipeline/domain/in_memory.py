"""Deterministic in-memory adapters and state for domain command tests."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from typing import Any

from services.pipeline.domain.ports import (
    Analyzer,
    ArtifactRecord,
    ArtifactStore,
    ReaderDocument,
    ReaderProvider,
    SearchProvider,
    SearchResultItem,
    VectorStore,
)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class InMemoryDomainState:
    command_results: dict[str, dict[str, Any]] = field(default_factory=dict)
    search_snapshots: dict[str, dict[str, Any]] = field(default_factory=dict)
    raw_scrapes: dict[str, dict[str, Any]] = field(default_factory=dict)
    artifacts: dict[str, ArtifactRecord] = field(default_factory=dict)
    chunks: dict[str, dict[str, Any]] = field(default_factory=dict)
    analyses: dict[str, dict[str, Any]] = field(default_factory=dict)
    run_summaries: dict[str, dict[str, Any]] = field(default_factory=dict)
    previous_success_by_scope: dict[str, datetime] = field(default_factory=dict)
    now: datetime = field(default_factory=utc_now)


class InMemorySearchProvider(SearchProvider):
    def __init__(
        self, *, results: list[SearchResultItem] | None = None, fail_mode: str | None = None
    ) -> None:
        self.results = results or []
        self.fail_mode = fail_mode

    def search(
        self, *, query: str, jurisdiction_id: str, source_family: str, max_results: int
    ) -> list[SearchResultItem]:
        _ = (query, jurisdiction_id, source_family)
        if self.fail_mode:
            raise RuntimeError(self.fail_mode)
        return self.results[:max_results]


class InMemoryReaderProvider(ReaderProvider):
    def __init__(self, *, fail_mode: str | None = None) -> None:
        self.fail_mode = fail_mode

    def fetch(self, *, url: str) -> ReaderDocument:
        if self.fail_mode:
            raise RuntimeError(self.fail_mode)
        return ReaderDocument(
            url=url,
            title="San Jose Meeting Minutes",
            text=(
                "# Minutes\n"
                "Housing permit processing timelines discussed.\n"
                "Fee schedule hearing moved.\n"
                "Public comments on affordable housing expansion."
            ),
            fetched_at=utc_now(),
            document_type="meeting_minutes",
            published_date="2026-04-10",
        )


class InMemoryArtifactStore(ArtifactStore):
    def __init__(self, state: InMemoryDomainState, *, fail_mode: str | None = None) -> None:
        self.state = state
        self.fail_mode = fail_mode

    def put(
        self,
        *,
        contract_version: str,
        jurisdiction_id: str,
        source_family: str,
        artifact_kind: str,
        body: str,
        media_type: str,
    ) -> ArtifactRecord:
        if self.fail_mode:
            raise RuntimeError(self.fail_mode)

        content_hash = sha256_text(body)
        ext = "json" if media_type == "application/json" else "md"
        artifact_ref = (
            f"artifacts/{contract_version}/{jurisdiction_id}/{source_family}/"
            f"{artifact_kind}/{content_hash}.{ext}"
        )
        existing = self.state.artifacts.get(artifact_ref)
        if existing:
            return existing

        record = ArtifactRecord(
            artifact_ref=artifact_ref,
            content_hash=content_hash,
            media_type=media_type,
            size_bytes=len(body.encode("utf-8")),
            kind=artifact_kind,
        )
        self.state.artifacts[artifact_ref] = record
        return record


class InMemoryVectorStore(VectorStore):
    def __init__(self, state: InMemoryDomainState, *, fail_mode: str | None = None) -> None:
        self.state = state
        self.fail_mode = fail_mode

    def upsert_chunks(self, chunks: list[dict[str, Any]]) -> int:
        if self.fail_mode:
            raise RuntimeError(self.fail_mode)
        for chunk in chunks:
            self.state.chunks[chunk["chunk_id"]] = dict(chunk)
        return len(chunks)


class InMemoryAnalyzer(Analyzer):
    def analyze(
        self, *, question: str, evidence_chunks: list[dict[str, Any]]
    ) -> dict[str, Any]:
        if not evidence_chunks:
            raise RuntimeError("insufficient_evidence")
        claims = [
            {
                "claim": "Housing-related agenda items were discussed.",
                "evidence_refs": [
                    {
                        "chunk_id": chunk["chunk_id"],
                        "canonical_document_key": chunk["canonical_document_key"],
                        "artifact_ref": chunk["artifact_ref"],
                    }
                    for chunk in evidence_chunks[:2]
                ],
            }
        ]
        return {
            "question": question,
            "summary": "Meeting minutes indicate active housing policy discussion.",
            "claims": claims,
            "sufficiency_state": "qualitative_only",
        }


def stable_json_hash(value: Any) -> str:
    return sha256_text(json.dumps(value, sort_keys=True, separators=(",", ":")))

