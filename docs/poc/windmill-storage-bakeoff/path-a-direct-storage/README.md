# Path A Direct Storage (Windmill-Heavy)

This implementation captures the Path A bakeoff for the San Jose meeting-minutes slice with a Windmill-shaped DAG that performs direct storage interactions without affordabot backend domain endpoints.

## Scope

- Orchestration model: Windmill-owned step graph (`search_materialize`, `freshness_gate`, `read_fetch`, `index_chunks`, `analyze`) plus failure drills.
- Storage model: direct writes through local deterministic adapters that mirror:
  - MinIO object refs (`minio://...`)
  - pgvector-like chunk storage/query
  - Postgres-like relational rows for snapshots/documents/analysis/runs
- Search/reader/analysis:
  - SearXNG-compatible payload shape
  - Z.ai reader and LLM contract shapes
  - deterministic local fallbacks when live infra/secrets are unavailable

## Files

- Runner: `backend/scripts/verification/windmill_bakeoff_direct_storage.py`
- Windmill script export: `ops/windmill/f/affordabot/pipeline_daily_refresh_direct_storage.py`
- Windmill script schema: `ops/windmill/f/affordabot/pipeline_daily_refresh_direct_storage.script.yaml`
- Windmill flow export: `ops/windmill/f/affordabot/pipeline_daily_refresh_direct_storage__flow/flow.yaml`
- Evidence:
  - `run-evidence.md`
  - `storage-snapshots.md`
  - `failure-drills.md`
  - `suite-results.json`

## Architectural Finding (Path A)

Path A is viable for a thin pre-MVP slice, but direct-storage logic quickly starts re-creating product invariants in the flow layer:

- canonical document identity (`canonical_document_key`)
- idempotent artifact keys (content-hash/idempotency scoped refs)
- chunk deduplication and upsert semantics
- analysis upsert semantics by idempotency key
- status vocabulary enforcement for failure/freshness outcomes

In short: Windmill can own orchestration well, but pure direct storage writes force orchestration code to absorb domain responsibilities unless those invariants are moved into reusable domain commands/libraries.

## Live Infra Blockers in This Run

- `SEARX_ENDPOINT` not configured in this environment, so deterministic SearX fixture used.
- `ZAI_API_KEY` not available for this run, so reader/analysis used deterministic contract-shape substitutes.

Both blockers are operational. The flow and storage-boundary behavior were still exercised with stable deterministic fixtures.
