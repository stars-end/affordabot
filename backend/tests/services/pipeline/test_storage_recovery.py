from __future__ import annotations

import pytest

from services.pipeline.domain.storage import (
    InMemoryArtifactBlobStore,
    InMemoryChunkVectorStore,
    InMemoryPipelineStateStore,
    PipelineStorageCoordinator,
    build_artifact_object_key,
    sha256_text,
)


def _coordinator(
    *,
    state: InMemoryPipelineStateStore | None = None,
    blob: InMemoryArtifactBlobStore | None = None,
    vector: InMemoryChunkVectorStore | None = None,
) -> tuple[
    InMemoryPipelineStateStore,
    InMemoryArtifactBlobStore,
    InMemoryChunkVectorStore,
    PipelineStorageCoordinator,
]:
    local_state = state or InMemoryPipelineStateStore()
    local_blob = blob or InMemoryArtifactBlobStore()
    local_vector = vector or InMemoryChunkVectorStore()
    service = PipelineStorageCoordinator(
        state_store=local_state,
        blob_store=local_blob,
        vector_store=local_vector,
    )
    return local_state, local_blob, local_vector, service


def _index_once(service: PipelineStorageCoordinator, *, key: str):
    return service.index_reader_document(
        idempotency_key=key,
        jurisdiction_id="san-jose-ca",
        source_family="meeting_minutes",
        canonical_document_key=(
            "v2|jurisdiction=san-jose-ca|family=meeting_minutes|doctype=meeting_minutes|"
            "url=https://www.sanjoseca.gov/minutes/2026-04-10"
        ),
        markdown_body=(
            "# Meeting Minutes\n"
            "Housing permit processing timelines discussed.\n"
            "Fee schedule hearing moved.\n"
            "Public comments on affordable housing expansion.\n"
        ),
    )


def test_recover_when_blob_exists_but_artifact_row_missing() -> None:
    state, blob, _, service = _coordinator()
    state.fail_upsert_artifact_once = True

    with pytest.raises(RuntimeError, match="artifact_row_write_failed"):
        _index_once(service, key="k-artifact-first")

    expected_key = build_artifact_object_key(
        contract_version="2026-04-13.windmill-domain.v1",
        jurisdiction_id="san-jose-ca",
        source_family="meeting_minutes",
        artifact_kind="reader_output",
        content_hash=sha256_text(
            "# Meeting Minutes\n"
            "Housing permit processing timelines discussed.\n"
            "Fee schedule hearing moved.\n"
            "Public comments on affordable housing expansion.\n"
        ),
        media_type="text/markdown",
    )
    assert expected_key in blob.objects
    assert len(state.artifacts) == 0

    result = _index_once(service, key="k-artifact-retry")
    assert result.chunk_count == 4
    assert result.reused_artifact is False
    assert len(state.artifacts) == 1
    assert result.artifact_ref == expected_key


def test_recover_when_raw_exists_and_vector_write_failed() -> None:
    state, _, vector, service = _coordinator()
    vector.fail_upsert_once = True

    with pytest.raises(RuntimeError, match="vector_upsert_failed"):
        _index_once(service, key="k-vector-first")

    assert len(state.raw_scrapes) == 1
    raw_row = next(iter(state.raw_scrapes.values()))
    assert raw_row.processed is False
    assert raw_row.chunk_count == 0

    retry = _index_once(service, key="k-vector-retry")
    assert retry.reused_raw_scrape is True
    assert retry.chunk_count == 4
    assert len(vector.chunks_by_id) == 4


def test_recover_when_vectors_written_but_raw_not_marked_processed() -> None:
    state, _, vector, service = _coordinator()
    state.fail_mark_processed_once = True

    with pytest.raises(RuntimeError, match="mark_processed_failed"):
        _index_once(service, key="k-mark-first")

    assert len(vector.chunks_by_id) == 4
    raw_row = next(iter(state.raw_scrapes.values()))
    assert raw_row.processed is False

    retry = _index_once(service, key="k-mark-retry")
    assert retry.reused_raw_scrape is True
    raw_row_after = next(iter(state.raw_scrapes.values()))
    assert raw_row_after.processed is True
    assert raw_row_after.chunk_count == 4


def test_idempotent_rerun_returns_same_refs_without_duplication() -> None:
    state, blob, vector, service = _coordinator()

    first = _index_once(service, key="k-idempotent")
    second = _index_once(service, key="k-idempotent")

    assert second.idempotent_reuse is True
    assert second.raw_scrape_id == first.raw_scrape_id
    assert second.artifact_ref == first.artifact_ref
    assert second.chunk_ids == first.chunk_ids
    assert len(state.raw_scrapes) == 1
    assert len(state.artifacts) == 1
    assert len(vector.chunks_by_id) == 4
    assert len(blob.objects) == 1
