# Path B: Windmill + Affordabot Domain Boundary

This POC implements a Windmill-shaped flow where orchestration is step-based, but product
storage writes are performed only by coarse affordabot domain commands.

Implementation entrypoint:
- `backend/scripts/verification/windmill_bakeoff_domain_boundary.py`

Committed Windmill export (reviewable orchestration shape):
- `ops/windmill/f/affordabot/pipeline_daily_refresh_domain_boundary.py`
- `ops/windmill/f/affordabot/pipeline_daily_refresh_domain_boundary.script.yaml`
- `ops/windmill/f/affordabot/pipeline_daily_refresh_domain_boundary__flow/flow.yaml`

Runner flow steps (Windmill-shaped):
1. `search_materialize`
2. `freshness_gate`
3. `read_fetch`
4. `index`
5. `analyze`
6. `summarize_run`

## Domain Boundary Contract

Each domain command owns explicit invariants and is intentionally not a thin SQL wrapper:

- `search_materialize`: idempotent search snapshot persistence for the scope `(jurisdiction, source_family, query, normalized_results)`.
- `freshness_gate`: explicit freshness state (`fresh`, `empty_result`, `stale_blocked`) with zero-result treated as non-transport state.
- `read_fetch`: canonical document identity (`canonical_document_key`) and deduplicated artifact reference.
- `index`: chunk upsert idempotency and provenance links (`chunk -> canonical_document_key + artifact_ref`).
- `analyze`: fail closed when evidence is missing (`analysis_error` if no chunks).
- `summarize_run`: ties orchestration IDs to domain state counts and per-step statuses.

## Local Adapters Used

This run uses deterministic local substitutes with production-compatible contract shape:

- Search: SearXNG-compatible JSON response model.
- Reader: Z.ai reader contract shape (`reader_result` envelope).
- Artifacts: MinIO-style refs (`minio://affordabot-artifacts/...`).
- Vector index: pgvector-compatible embedding adapter.
- Analysis: deterministic analysis adapter that emits explicit evidence refs.

Live infra was intentionally not used because secret access is currently restricted in this task.

## Artifacts

- `artifacts/happy_rerun.json`
- `artifacts/source_failure.json`
- `artifacts/reader_failure.json`
- `artifacts/storage_failure.json`
- `artifacts/stale_usable.json`
- `artifacts/stale_blocked.json`

## Architectural Finding (Path B)

Path B is viable. The backend boundary clearly pays for itself at canonical identity,
idempotency, provenance, and sufficiency gating. It starts to look like middleware only if
commands are decomposed into low-level storage primitives instead of domain commands.
