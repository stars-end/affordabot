"""Storage adapters and recovery coordinator for pipeline domain writes."""

from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
from typing import Protocol

from services.pipeline.domain.constants import CONTRACT_VERSION


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _artifact_extension(media_type: str) -> str:
    if media_type == "application/json":
        return "json"
    if media_type == "text/html":
        return "html"
    if media_type == "application/pdf":
        return "pdf"
    return "md"


def build_artifact_object_key(
    *,
    contract_version: str,
    jurisdiction_id: str,
    source_family: str,
    artifact_kind: str,
    content_hash: str,
    media_type: str,
) -> str:
    ext = _artifact_extension(media_type)
    return (
        f"artifacts/{contract_version}/{jurisdiction_id}/{source_family}/"
        f"{artifact_kind}/{content_hash}.{ext}"
    )


def build_deterministic_chunk_id(
    *,
    canonical_document_key: str,
    content_hash: str,
    chunk_index: int,
    chunk_text: str,
) -> str:
    chunk_text_hash = sha256_text(chunk_text)
    material = (
        f"{CONTRACT_VERSION}|{canonical_document_key}|{content_hash}|{chunk_index}|{chunk_text_hash}"
    )
    return f"chunk_{sha256_text(material)}"


def chunk_markdown_lines(markdown_text: str) -> list[str]:
    return [line.strip() for line in markdown_text.splitlines() if line.strip()]


@dataclass(frozen=True)
class ArtifactRef:
    artifact_ref: str
    content_hash: str
    media_type: str
    size_bytes: int
    artifact_kind: str


@dataclass(frozen=True)
class RawScrapeRef:
    raw_scrape_id: str
    canonical_document_key: str
    content_hash: str
    artifact_ref: str
    processed: bool
    chunk_count: int


@dataclass(frozen=True)
class ChunkRecord:
    chunk_id: str
    raw_scrape_id: str
    canonical_document_key: str
    content_hash: str
    artifact_ref: str
    chunk_index: int
    text: str
    jurisdiction_id: str
    source_family: str


@dataclass(frozen=True)
class IndexMaterializationResult:
    idempotency_key: str
    raw_scrape_id: str
    artifact_ref: str
    chunk_ids: list[str]
    chunk_count: int
    reused_raw_scrape: bool
    reused_artifact: bool
    idempotent_reuse: bool = False


class PipelineStateStore(Protocol):
    def get_index_command_result(
        self, *, idempotency_key: str
    ) -> IndexMaterializationResult | None:
        ...

    def put_index_command_result(self, *, result: IndexMaterializationResult) -> None:
        ...

    def find_content_artifact(
        self,
        *,
        jurisdiction_id: str,
        source_family: str,
        artifact_kind: str,
        content_hash: str,
    ) -> ArtifactRef | None:
        ...

    def upsert_content_artifact(
        self,
        *,
        jurisdiction_id: str,
        source_family: str,
        artifact_kind: str,
        content_hash: str,
        artifact_ref: str,
        media_type: str,
        size_bytes: int,
        contract_version: str,
    ) -> ArtifactRef:
        ...

    def get_or_create_raw_scrape(
        self,
        *,
        canonical_document_key: str,
        content_hash: str,
        artifact_ref: str,
        jurisdiction_id: str,
        source_family: str,
        markdown_body: str,
    ) -> tuple[RawScrapeRef, bool]:
        ...

    def mark_raw_scrape_retrievable(self, *, raw_scrape_id: str, chunk_count: int) -> None:
        ...


class ArtifactBlobStore(Protocol):
    def put_if_absent(
        self, *, object_key: str, body: bytes, media_type: str
    ) -> str:
        ...


class ChunkVectorStore(Protocol):
    def upsert_chunks(self, *, chunks: list[ChunkRecord]) -> int:
        ...

    def count_chunks_for_raw_scrape(self, *, raw_scrape_id: str) -> int:
        ...


class PipelineStorageCoordinator:
    """Coordinates Postgres/MinIO/pgvector writes with rerun-safe behavior."""

    def __init__(
        self,
        *,
        state_store: PipelineStateStore,
        blob_store: ArtifactBlobStore,
        vector_store: ChunkVectorStore,
    ) -> None:
        self.state_store = state_store
        self.blob_store = blob_store
        self.vector_store = vector_store

    def index_reader_document(
        self,
        *,
        idempotency_key: str,
        jurisdiction_id: str,
        source_family: str,
        canonical_document_key: str,
        markdown_body: str,
        media_type: str = "text/markdown",
        artifact_kind: str = "reader_output",
    ) -> IndexMaterializationResult:
        cached = self.state_store.get_index_command_result(idempotency_key=idempotency_key)
        if cached:
            return replace(cached, idempotent_reuse=True)

        content_hash = sha256_text(markdown_body)
        size_bytes = len(markdown_body.encode("utf-8"))

        artifact = self.state_store.find_content_artifact(
            jurisdiction_id=jurisdiction_id,
            source_family=source_family,
            artifact_kind=artifact_kind,
            content_hash=content_hash,
        )
        reused_artifact = artifact is not None

        if artifact is None:
            object_key = build_artifact_object_key(
                contract_version=CONTRACT_VERSION,
                jurisdiction_id=jurisdiction_id,
                source_family=source_family,
                artifact_kind=artifact_kind,
                content_hash=content_hash,
                media_type=media_type,
            )
            artifact_ref = self.blob_store.put_if_absent(
                object_key=object_key,
                body=markdown_body.encode("utf-8"),
                media_type=media_type,
            )
            artifact = self.state_store.upsert_content_artifact(
                jurisdiction_id=jurisdiction_id,
                source_family=source_family,
                artifact_kind=artifact_kind,
                content_hash=content_hash,
                artifact_ref=artifact_ref,
                media_type=media_type,
                size_bytes=size_bytes,
                contract_version=CONTRACT_VERSION,
            )

        raw_scrape, reused_raw_scrape = self.state_store.get_or_create_raw_scrape(
            canonical_document_key=canonical_document_key,
            content_hash=content_hash,
            artifact_ref=artifact.artifact_ref,
            jurisdiction_id=jurisdiction_id,
            source_family=source_family,
            markdown_body=markdown_body,
        )

        chunks = [
            ChunkRecord(
                chunk_id=build_deterministic_chunk_id(
                    canonical_document_key=canonical_document_key,
                    content_hash=content_hash,
                    chunk_index=idx,
                    chunk_text=text,
                ),
                raw_scrape_id=raw_scrape.raw_scrape_id,
                canonical_document_key=canonical_document_key,
                content_hash=content_hash,
                artifact_ref=artifact.artifact_ref,
                chunk_index=idx,
                text=text,
                jurisdiction_id=jurisdiction_id,
                source_family=source_family,
            )
            for idx, text in enumerate(chunk_markdown_lines(markdown_body))
        ]

        if chunks:
            self.vector_store.upsert_chunks(chunks=chunks)

        chunk_count = self.vector_store.count_chunks_for_raw_scrape(
            raw_scrape_id=raw_scrape.raw_scrape_id
        )
        if not raw_scrape.processed and chunk_count > 0:
            self.state_store.mark_raw_scrape_retrievable(
                raw_scrape_id=raw_scrape.raw_scrape_id,
                chunk_count=chunk_count,
            )

        result = IndexMaterializationResult(
            idempotency_key=idempotency_key,
            raw_scrape_id=raw_scrape.raw_scrape_id,
            artifact_ref=artifact.artifact_ref,
            chunk_ids=[chunk.chunk_id for chunk in chunks],
            chunk_count=chunk_count,
            reused_raw_scrape=reused_raw_scrape,
            reused_artifact=reused_artifact,
        )
        self.state_store.put_index_command_result(result=result)
        return result


class InMemoryPipelineStateStore(PipelineStateStore):
    """Deterministic state store for unit tests."""

    def __init__(self) -> None:
        self.command_results: dict[str, IndexMaterializationResult] = {}
        self.artifacts: dict[tuple[str, str, str, str], ArtifactRef] = {}
        self.raw_scrapes: dict[tuple[str, str], RawScrapeRef] = {}
        self.raw_scrape_payloads: dict[str, str] = {}
        self.fail_upsert_artifact_once = False
        self.fail_mark_processed_once = False
        self._raw_counter = 0

    def get_index_command_result(
        self, *, idempotency_key: str
    ) -> IndexMaterializationResult | None:
        return self.command_results.get(idempotency_key)

    def put_index_command_result(self, *, result: IndexMaterializationResult) -> None:
        self.command_results[result.idempotency_key] = result

    def find_content_artifact(
        self,
        *,
        jurisdiction_id: str,
        source_family: str,
        artifact_kind: str,
        content_hash: str,
    ) -> ArtifactRef | None:
        key = (jurisdiction_id, source_family, artifact_kind, content_hash)
        return self.artifacts.get(key)

    def upsert_content_artifact(
        self,
        *,
        jurisdiction_id: str,
        source_family: str,
        artifact_kind: str,
        content_hash: str,
        artifact_ref: str,
        media_type: str,
        size_bytes: int,
        contract_version: str,
    ) -> ArtifactRef:
        _ = contract_version
        if self.fail_upsert_artifact_once:
            self.fail_upsert_artifact_once = False
            raise RuntimeError("artifact_row_write_failed")
        key = (jurisdiction_id, source_family, artifact_kind, content_hash)
        existing = self.artifacts.get(key)
        if existing:
            return existing
        row = ArtifactRef(
            artifact_ref=artifact_ref,
            content_hash=content_hash,
            media_type=media_type,
            size_bytes=size_bytes,
            artifact_kind=artifact_kind,
        )
        self.artifacts[key] = row
        return row

    def get_or_create_raw_scrape(
        self,
        *,
        canonical_document_key: str,
        content_hash: str,
        artifact_ref: str,
        jurisdiction_id: str,
        source_family: str,
        markdown_body: str,
    ) -> tuple[RawScrapeRef, bool]:
        key = (canonical_document_key, content_hash)
        existing = self.raw_scrapes.get(key)
        if existing:
            return existing, True

        _ = (jurisdiction_id, source_family)
        self._raw_counter += 1
        raw_id = f"raw_{self._raw_counter:04d}"
        row = RawScrapeRef(
            raw_scrape_id=raw_id,
            canonical_document_key=canonical_document_key,
            content_hash=content_hash,
            artifact_ref=artifact_ref,
            processed=False,
            chunk_count=0,
        )
        self.raw_scrapes[key] = row
        self.raw_scrape_payloads[raw_id] = markdown_body
        return row, False

    def mark_raw_scrape_retrievable(self, *, raw_scrape_id: str, chunk_count: int) -> None:
        if self.fail_mark_processed_once:
            self.fail_mark_processed_once = False
            raise RuntimeError("mark_processed_failed")
        for key, row in self.raw_scrapes.items():
            if row.raw_scrape_id == raw_scrape_id:
                self.raw_scrapes[key] = RawScrapeRef(
                    raw_scrape_id=row.raw_scrape_id,
                    canonical_document_key=row.canonical_document_key,
                    content_hash=row.content_hash,
                    artifact_ref=row.artifact_ref,
                    processed=True,
                    chunk_count=chunk_count,
                )
                return
        raise KeyError(f"raw scrape not found: {raw_scrape_id}")


class InMemoryArtifactBlobStore(ArtifactBlobStore):
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.put_calls = 0

    def put_if_absent(
        self, *, object_key: str, body: bytes, media_type: str
    ) -> str:
        _ = media_type
        self.put_calls += 1
        self.objects.setdefault(object_key, body)
        return object_key


class InMemoryChunkVectorStore(ChunkVectorStore):
    def __init__(self) -> None:
        self.chunks_by_id: dict[str, ChunkRecord] = {}
        self.fail_upsert_once = False

    def upsert_chunks(self, *, chunks: list[ChunkRecord]) -> int:
        if self.fail_upsert_once:
            self.fail_upsert_once = False
            raise RuntimeError("vector_upsert_failed")
        for chunk in chunks:
            self.chunks_by_id[chunk.chunk_id] = chunk
        return len(chunks)

    def count_chunks_for_raw_scrape(self, *, raw_scrape_id: str) -> int:
        return sum(
            1 for chunk in self.chunks_by_id.values() if chunk.raw_scrape_id == raw_scrape_id
        )
