# Windmill Storage Boundary Bakeoff POC

Status: in progress
Tracking: offline-20260412-windmill-storage-bakeoff
Beads status: offline because local Beads mutations are broken; reconcile after infra repair.

## Decision Question

Can affordabot pre-MVP be primarily a Windmill DAG application with direct storage writes, or does it still need an affordabot-owned domain boundary for product data writes?

This POC compares two implementation paths against the same San Jose meeting-minutes slice.

## Fixed Slice

- Jurisdiction: `San Jose CA`
- Source family: `meeting_minutes`
- Discovery: SearXNG-compatible search endpoint
- Reader: Z.ai direct web reader when live secrets are available; deterministic local reader stub when secrets are unavailable
- Analysis: Z.ai LLM when live secrets are available; deterministic local analysis stub when secrets are unavailable
- Storage target: Postgres/pgvector/MinIO interfaces when live infra is available; deterministic local storage adapter when live infra is unavailable

The POC must separate live-infra blockers from architectural evidence. A local deterministic substitute is acceptable only when it preserves the same contract shape and records the live blocker.

## Path A: Windmill-Heavy Direct Storage

Windmill owns the DAG and calls storage/search/reader/LLM helpers directly.

Expected ownership:

- Windmill flow shape
- per-step retries/backoff
- branch on freshness status
- per-jurisdiction loop shape
- operational run summary
- direct writes through storage adapters for search snapshots, artifacts, chunks, and analysis rows

Affordabot should be minimally involved in Path A. If domain logic is needed, document exactly where it starts becoming more than storage glue.

## Path B: Windmill Plus Affordabot Domain Boundary

Windmill owns the DAG, but each step calls a coarse affordabot domain command.

Expected ownership:

- Windmill flow shape
- per-step retries/backoff
- branch on freshness status
- per-jurisdiction loop shape
- operational run summary
- affordabot commands for canonical document identity, idempotency, artifact persistence, chunk indexing, analysis sufficiency, and provenance

Affordabot commands must not be thin SQL wrappers. Each command must protect at least one domain invariant.

## Shared Run Envelope

Every step input/output should carry this envelope:

```json
{
  "contract_version": "2026-04-12.windmill-storage-bakeoff.v1",
  "architecture_path": "windmill_direct_storage | affordabot_domain_boundary",
  "orchestrator": "windmill",
  "windmill_workspace": "affordabot",
  "windmill_flow_path": "f/affordabot/pipeline_daily_refresh_bakeoff",
  "windmill_run_id": "local-or-live-run-id",
  "windmill_job_id": "local-or-live-job-id",
  "idempotency_key": "san-jose-ca:meeting_minutes:2026-04-12",
  "jurisdiction": "San Jose CA",
  "source_family": "meeting_minutes"
}
```

## Required Status Vocabulary

- `fresh`: current result is fresh enough to use.
- `stale_but_usable`: current result is stale but within fallback ceiling; analysis may continue and must emit an alert.
- `stale_blocked`: current result exceeds fallback ceiling; analysis must fail closed.
- `empty_result`: search completed but returned zero candidates; this is not a transport failure.
- `source_error`: search/source retrieval failed.
- `reader_error`: reader failed after URL selection.
- `storage_error`: Postgres/pgvector/MinIO persistence failed.
- `analysis_error`: LLM analysis failed.

## Required Evidence

Each path must produce:

- first-run result
- rerun/idempotency result
- SearXNG failure drill
- reader failure drill
- storage failure drill or documented blocker
- final analysis result
- provenance chain from final claim to chunk/document/artifact/search snapshot
- Windmill flow export or executable local Windmill-shaped flow surrogate
- storage snapshots before and after rerun
- implementation complexity notes

## Pass/Fail Criteria

Architecture evidence is sufficient only if both paths can be compared on:

- whether the code stayed understandable
- whether reruns avoided duplicate product records
- whether Windmill-native retries/branches/logs were enough
- whether storage writes were safe without spreading product invariants
- whether frontend/read-side consumption would be straightforward
- whether live infra blockers are operational rather than architectural

## Guardrails

- Do not run raw `op read`, `op item get`, `op item list`, or `op whoami`.
- Do not mutate Beads while local Beads is broken.
- Do not write secrets into repo files, logs, Windmill exports, or artifacts.
- Do not make irreversible live infrastructure changes.
- Prefer committed Windmill flow/script exports over live-only edits.
- Keep Path A and Path B write scopes separate.

