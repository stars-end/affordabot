# Storage Snapshots

This file captures storage-state evidence from `artifacts/happy_rerun.json`.

## After First Run (`run-first`)

Storage counts:

- `search_snapshots`: 1
- `documents`: 1
- `artifacts`: 1
- `chunks`: 5
- `analyses`: 1

Representative keys:

- `snapshot_id`: `snapshot-579c45d51063aaef`
- `canonical_document_key`: `san-jose-ca::a653e7debe31e650`
- `artifact_ref`: `minio://affordabot-artifacts/San_Jose_CA/ecf092f9a92f34b1.md`
- `analysis_id`: `analysis-ebbbe7e0f3aeac41`

Provenance chain demonstrated:

`claim -> evidence chunk ids -> canonical_document_key + artifact_ref -> search snapshot`

## After Rerun (`run-second`)

Storage counts:

- `search_snapshots`: 1 (unchanged)
- `documents`: 1 (unchanged)
- `artifacts`: 1 (unchanged)
- `chunks`: 5 (unchanged)
- `analyses`: 1 (unchanged)

Idempotency signals:

- `search_materialize.snapshot_id` unchanged.
- `read_fetch.canonical_document_key` unchanged.
- `read_fetch.artifact_ref` unchanged.
- `index.chunks_created = 0`.
- `analyze.analysis_id` unchanged with `reused=true`.

## Interpretation

Path B can keep Windmill-style orchestration while preserving product write invariants in affordabot:
stable identity, deduplicated artifacts/chunks, and evidence-gated analysis.
