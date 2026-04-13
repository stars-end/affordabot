"""Ports for domain command dependencies."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol


@dataclass(frozen=True)
class SearchResultItem:
    url: str
    title: str
    snippet: str


class SearchProvider(Protocol):
    def search(
        self, *, query: str, jurisdiction_id: str, source_family: str, max_results: int
    ) -> list[SearchResultItem]:
        ...


@dataclass(frozen=True)
class ReaderDocument:
    url: str
    title: str
    text: str
    fetched_at: datetime
    media_type: str = "text/markdown"
    document_type: str = "meeting_minutes"
    published_date: str | None = None


class ReaderProvider(Protocol):
    def fetch(self, *, url: str) -> ReaderDocument:
        ...


@dataclass(frozen=True)
class ArtifactRecord:
    artifact_ref: str
    content_hash: str
    media_type: str
    size_bytes: int
    kind: str


class ArtifactStore(Protocol):
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
        ...


class VectorStore(Protocol):
    def upsert_chunks(self, chunks: list[dict[str, Any]]) -> int:
        ...


class Analyzer(Protocol):
    def analyze(
        self, *, question: str, evidence_chunks: list[dict[str, Any]]
    ) -> dict[str, Any]:
        ...

