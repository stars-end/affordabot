# Windmill Domain Boundary Brownfield Spec Lock

Date: 2026-04-13
Status: Spec lock for implementation planning
Epic: `bd-9qjof`
First task: `bd-9qjof.1`
Related ADR: `docs/architecture/2026-04-12-windmill-affordabot-boundary-adr.md`
Related POC: `docs/poc/windmill-storage-bakeoff/ARCHITECTURE_RECOMMENDATION.md`
Cycle Review Spec: `docs/specs/2026-04-27-data-moat-cycle-review-architecture.md`

## Summary

Affordabot should replace the current monolithic cron-trigger pattern with a Windmill-native daily refresh flow, but Windmill must remain the orchestration layer. Product data logic stays in affordabot code.

The implementation target is a brownfield refactor:

- keep existing scraper, reader, ingestion, storage, retrieval, evidence, and admin surfaces where they already work
- extract a tested domain-command package around those existing services
- let Windmill call those coarse commands with native retries, branching, looping, schedules, failure handlers, and run history
- expose frontend/operator state through affordabot backend read APIs

This document locks the contracts needed before two implementation agents can safely work in parallel.

Cycle-review boundary update (2026-04-27): this spec remains the domain/orchestration boundary lock. The canonical 10-20 cycle review contract now lives in `docs/specs/2026-04-27-data-moat-cycle-review-architecture.md`, where Windmill run metadata is treated as runtime evidence and Affordabot admin/glassbox remains product truth.

## Problem

Affordabot's discovery and scraping pipeline is not commodity ETL. It is part of the product moat:

- canonical document identity
- source family coverage
- freshness and stale fallback behavior
- reader output preservation
- revision chains
- MinIO artifact provenance
- chunking and retrieval scope
- evidence sufficiency before analysis
- operator-visible trust and failure states

Moving this logic directly into Windmill would create a second backend in workflow scripts. Keeping everything in the existing backend cron endpoints underuses Windmill's DAG, retry, branch, schedule, and operator controls.

The correct implementation is a hybrid:

```text
Windmill flow
  orchestrates and records work
  calls coarse affordabot domain commands

Affordabot domain package
  enforces product invariants
  writes canonical product state

Affordabot backend API
  serves frontend/operator read models
  optionally triggers Windmill
```

## Goals

- Replace the current four-step cron chain with a Windmill-native flow for the new persisted discovery pipeline.
- Preserve affordabot-owned product invariants in normal backend/domain code.
- Reuse the existing brownfield stack instead of rebuilding scraping, ingestion, pgvector, MinIO, evidence, or admin systems.
- Make every domain command idempotent and safe under Windmill reruns.
- Produce operator-visible run summaries that the frontend can display without direct Windmill, Postgres, pgvector, or MinIO coupling.
- Validate the San Jose meeting-minutes slice end to end through live Windmill before production rollout.

## Non-Goals

- Do not migrate all existing cron jobs in one cutover.
- Do not move canonical product writes into Windmill scripts.
- Do not create low-level storage endpoints such as `insert_row`, `upload_object`, `embed_text`, or `write_chunk`.
- Do not make the frontend call Windmill, Postgres, pgvector, or MinIO directly.
- Do not make Z.ai web search primary. SearXNG-style OSS search is primary for search discovery.
- Do not remove Z.ai direct reader or Z.ai LLM analysis. Those remain canonical for reader extraction and analysis.
- Do not require coarse HTTP endpoints before the shared package path proves insufficient.

## Existing Stack Inventory

### Current Windmill Layer

Keep short-term as the rollback lane:

- `ops/windmill/README.md`
- `ops/windmill/f/affordabot/trigger_cron_job.py`
- `ops/windmill/f/affordabot/discovery_run__flow/flow.yaml`
- `ops/windmill/f/affordabot/daily_scrape__flow/flow.yaml`
- `ops/windmill/f/affordabot/rag_spiders__flow/flow.yaml`
- `ops/windmill/f/affordabot/universal_harvester__flow/flow.yaml`
- corresponding `*.schedule.yaml` files

Current model: Windmill is the scheduler of record, but each Windmill job calls one authenticated backend cron endpoint. This is useful as a rollback path, but it is not the target flow shape.

### Backend Cron Entrypoints

Wrap first, then retire from the primary path after parity:

- `backend/main.py` routes under `/cron/*`
- `backend/scripts/cron/run_discovery.py`
- `backend/scripts/cron/run_daily_scrape.py`
- `backend/scripts/cron/run_rag_spiders.py`
- `backend/scripts/cron/run_universal_harvester.py`

These scripts are the current execution plane. The new domain package should reuse their service wiring where possible, but Windmill should call domain commands instead of calling one monolithic cron endpoint per phase.

### Discovery And Search

Reuse:

- `backend/services/auto_discovery_service.py`
- `backend/services/discovery/search_discovery.py`
- `backend/services/discovery/service.py`
- `backend/scripts/verification/poc_rag_pipeline_oss_swap.py`

Target: OSS SearXNG-style search is the primary discovery source. Z.ai direct web search is deprecated from the primary path and may exist only as a scheduled bakeoff/manual health check.

### Reader And Extraction

Reuse:

- `backend/clients/web_reader_client.py`
- `backend/services/extractors/zai.py`

Target: Z.ai direct reader remains canonical for web-reader extraction. Windmill should call an affordabot command that uses this reader; Windmill must not know the Z.ai response internals beyond command status.

### Scraping And Substrate Capture

Reuse:

- `backend/services/scraper/*`
- `backend/affordabot_scraper/*`
- `backend/scripts/substrate/manual_capture.py`
- `backend/scripts/substrate/manual_expansion_runner.py`
- `backend/services/substrate_promotion.py`

Target: keep source-specific capture logic in affordabot. Domain commands can call these services or factor shared helpers out of them.

### Ingestion, MinIO, pgvector

Reuse and tighten:

- `backend/services/ingestion_service.py`
- `backend/services/storage/s3_storage.py`
- `backend/contracts/storage.py`
- `backend/services/retrieval/local_pgvector.py`
- `backend/services/vector_backend_factory.py`

Current `IngestionService` already:

- loads `raw_scrapes`
- extracts text
- uploads blob payloads when configured
- chunks content
- embeds chunks
- upserts into `document_chunks`
- records `ingestion_truth`
- reuses an existing retrievable revision when `canonical_document_key` plus `content_hash` already exists

The new `index` command should wrap this behavior but must add a clearer idempotency and partial-write recovery contract.

### Identity And Revision Chain

Reuse but modify:

- `backend/services/revision_identity.py`
- `backend/migrations/007_add_revision_identity_columns.sql`

Current `build_canonical_document_key` is source-id-centric:

```text
v1|source=<source_id>|doctype=<document_type>|url=<canonical_url>
```

The new pipeline needs a jurisdiction/source-family scoped identity to avoid Path A versus Path B divergence and to support multi-jurisdiction document reuse intentionally.

### Evidence And Analysis

Reuse:

- `backend/services/llm/orchestrator.py`
- `backend/services/llm/evidence_adapter.py`
- `backend/services/llm/evidence_gates.py`
- `backend/schemas/analysis.py`

Target: Z.ai LLM analysis remains canonical. The `analyze` command must fail closed when evidence is insufficient.

### Admin And Frontend

Reuse and extend:

- `backend/routers/admin.py`
- `backend/scripts/substrate/substrate_inspection_report.py`
- `frontend/src/app/admin/page.tsx`
- `frontend/src/components/admin/*`
- `frontend/src/services/adminService.ts`

Target: frontend displays pipeline status through backend read models. It should not parse Windmill payloads or infer product state from raw storage.

## Active Contract

### Command Envelope

Every domain command accepts an envelope plus command-specific input:

```json
{
  "contract_version": "2026-04-13.windmill-domain.v1",
  "command": "search_materialize",
  "orchestrator": "windmill",
  "windmill_workspace": "affordabot",
  "windmill_flow_path": "f/affordabot/pipeline_daily_refresh_domain_boundary__flow",
  "windmill_run_id": "wm-run-id",
  "windmill_job_id": "wm-job-id",
  "idempotency_key": "sha256(scope+command+logical-input)",
  "jurisdiction_id": "san-jose-ca",
  "jurisdiction_name": "San Jose CA",
  "source_family": "meeting_minutes",
  "requested_at": "2026-04-13T00:00:00Z"
}
```

Every command returns:

```json
{
  "contract_version": "2026-04-13.windmill-domain.v1",
  "command": "search_materialize",
  "status": "succeeded",
  "decision_reason": "fresh_snapshot_materialized",
  "retry_class": "none",
  "alerts": [],
  "counts": {},
  "refs": {},
  "windmill": {
    "run_id": "wm-run-id",
    "job_id": "wm-job-id"
  }
}
```

Allowed `status` values:

- `succeeded`
- `succeeded_with_alerts`
- `skipped`
- `blocked`
- `failed_retryable`
- `failed_terminal`

Allowed `retry_class` values:

- `none`
- `transport`
- `rate_limited`
- `transient_storage`
- `provider_unavailable`
- `contract_violation`
- `insufficient_evidence`
- `operator_required`

Windmill owns retry policy. Affordabot returns `retry_class`, `decision_reason`, and machine-readable `alerts`; it does not return `max_retries`, `retry_after_seconds`, or `next_recommended_step` as control instructions.

### Domain Commands

#### `search_materialize`

Purpose: query OSS search and persist a normalized search snapshot.

Wrap or reuse:

- `backend/services/auto_discovery_service.py`
- `backend/services/discovery/search_discovery.py`
- `backend/services/discovery/service.py`
- `backend/scripts/verification/poc_rag_pipeline_oss_swap.py`

Inputs:

- jurisdiction
- source family
- query template or explicit query
- search backend configuration
- max result count

Writes:

- search snapshot rows
- raw normalized result payload artifact when large enough to justify MinIO
- pipeline step summary

Invariants:

- zero search results are not a transport failure
- every snapshot is scoped by jurisdiction and source family
- snapshot identity is idempotent for equivalent normalized results
- raw search payloads are retained or hash-addressed for auditability

Acceptance tests:

- same query and same results reuse the prior snapshot
- same URL in a different jurisdiction does not collide unless the identity policy explicitly says so
- empty results produce `succeeded_with_alerts` or `blocked` based on freshness state, not `failed_retryable`
- SearXNG transport failure returns `failed_retryable` with `retry_class=transport`

#### `freshness_gate`

Purpose: decide whether the pipeline can proceed using fresh or stale results.

Wrap or reuse:

- POC freshness behavior in `backend/scripts/verification/windmill_bakeoff_domain_boundary.py`
- existing admin/substrate run summary patterns

Inputs:

- latest search snapshot ref
- latest successful run summary
- source-family freshness policy

Outputs:

- `fresh`
- `stale_but_usable`
- `stale_blocked`
- `empty_but_usable`
- `empty_blocked`

Invariants:

- freshness policy is affordabot-owned business logic
- stale fallback has a hard ceiling
- stale fallback always emits an alert
- zero-result handling is separate from provider failure
- stale-blocked fails closed before reader/index/analyze

Initial policy defaults:

| Source Family | Fresh Hours | Stale Usable Ceiling | Fail-Closed Ceiling |
| --- | ---: | ---: | ---: |
| `meeting_minutes` | 24 | 72 | 168 |
| `agendas` | 24 | 72 | 168 |
| `legislation` | 24 | 48 | 120 |
| `general_web_reference` | 48 | 168 | 336 |

Acceptance tests:

- fresh proceeds
- stale-but-usable proceeds with alert
- stale-blocked stops the flow before reads
- repeated stale fallbacks hit the fail-closed ceiling

#### `read_fetch`

Purpose: fetch selected documents through the canonical reader path and create raw substrate records.

Wrap or reuse:

- `backend/clients/web_reader_client.py`
- `backend/services/extractors/zai.py`
- `backend/db/postgres_client.py:create_raw_scrape`
- `backend/services/revision_identity.py`

Inputs:

- selected search result refs
- reader backend selection
- canonical identity policy

Writes:

- raw reader artifact in MinIO where configured
- `raw_scrapes` row or updated revision chain
- artifact metadata and content hash
- pipeline step summary

Invariants:

- Z.ai direct reader remains canonical for reader extraction
- Windmill does not parse reader payload internals
- canonical document identity is generated by affordabot code
- same content hash under the same canonical key reuses the existing retrievable revision
- reader failures stop before index/analyze

Acceptance tests:

- reader success stores artifact ref and raw scrape ref
- reader failure returns `failed_retryable` or `failed_terminal` based on provider error class
- same content hash and same canonical key do not create duplicate chunks on rerun
- MinIO artifact hash mismatch returns `failed_terminal`

#### `index`

Purpose: turn raw reader/substrate records into retrievable chunks.

Wrap or reuse:

- `backend/services/ingestion_service.py`
- `backend/services/retrieval/local_pgvector.py`
- `backend/services/vector_backend_factory.py`
- `backend/services/storage/s3_storage.py`

Inputs:

- raw scrape refs
- chunking/embedding configuration
- retrieval scope

Writes:

- `raw_scrapes.ingestion_truth`
- `raw_scrapes.document_id`
- `document_chunks`
- MinIO artifact refs when the raw payload was not already stored
- pipeline step summary

Invariants:

- every chunk links to `raw_scrape_id`, `canonical_document_key`, `jurisdiction_id`, `source_family`, and artifact ref
- pgvector is an index, not canonical truth
- reruns reuse existing retrievable revisions where possible
- vector writes are idempotent by deterministic chunk identity
- no analysis is allowed if retrievable chunk count is zero

Required refactor:

Current `IngestionService` creates random document and chunk IDs for new processed rows. The new command must make chunk identity deterministic from:

```text
contract_version
canonical_document_key
content_hash
chunk_index
chunk_text_hash
```

Acceptance tests:

- rerun does not duplicate chunks
- partial MinIO success followed by Postgres failure recovers by hash/ref
- partial Postgres success followed by vector failure recovers by deterministic chunk ids
- `LocalPgVectorBackend.query` filters by jurisdiction/source family in metadata

#### `analyze`

Purpose: produce Z.ai LLM analysis only from sufficient evidence.

Wrap or reuse:

- `backend/services/llm/orchestrator.py`
- `backend/services/llm/evidence_adapter.py`
- `backend/services/llm/evidence_gates.py`
- `backend/schemas/analysis.py`

Inputs:

- jurisdiction
- source family
- analysis question/template
- evidence refs from indexed chunks

Writes:

- analysis record
- evidence links
- large LLM artifacts in MinIO if needed
- pipeline step summary

Invariants:

- Z.ai LLM analysis remains canonical
- no quantified/impact output without evidence sufficiency
- every claim links to chunk/document/artifact provenance
- analysis output includes contract version

Acceptance tests:

- no chunks produces `blocked` with `retry_class=insufficient_evidence`
- insufficient evidence fails closed
- successful analysis includes claim-to-evidence refs
- contract version mismatch fails terminally

#### `summarize_run`

Purpose: produce product-visible pipeline state for operators and frontend.

Wrap or reuse:

- `backend/routers/admin.py`
- `backend/scripts/substrate/substrate_inspection_report.py`
- `backend/services/glass_box.py` where applicable

Inputs:

- Windmill run/job IDs
- domain command outputs
- product row refs

Writes:

- pipeline run summary rows
- pipeline step summary rows
- operator-visible alerts

Invariants:

- summary is backend-authored product state
- Windmill run URL is an operator link, not product truth
- frontend consumes this summary through backend API

Acceptance tests:

- happy run summary includes all step statuses and counts
- stale fallback summary includes alert
- blocked run summary exposes fail-closed reason
- rerun summary links old/new attempt ids without duplicating product rows

## Canonical Identity Spec

### Target Format

Use a new `v2` canonical document key for this pipeline:

```text
v2|jurisdiction=<jurisdiction_slug>|family=<source_family>|doctype=<document_type>|url=<normalized_url>
```

Fallback when no durable URL exists:

```text
v2|jurisdiction=<jurisdiction_slug>|family=<source_family>|doctype=<document_type>|title=<normalized_title>|date=<yyyy-mm-dd-or-unknown>
```

The jurisdiction slug is required even when the same URL appears in multiple jurisdictions. Cross-jurisdiction dedupe can be introduced later through a separate global content identity, not by weakening product-scoped canonical identity.

### URL Normalization

Start from `normalize_canonical_url` in `backend/services/revision_identity.py` and preserve:

- lowercase scheme and host
- default port removal
- repeated slash normalization
- trailing slash removal except root
- tracking query removal for `utm_*`, `fbclid`, `gclid`, `mc_cid`, `mc_eid`, `ref`, `source`
- sorted remaining query parameters
- fragment removal

Do not strip query parameters globally. Municipal agenda/minute systems sometimes encode document identity in query parameters.

### Revision Behavior

- `canonical_document_key` identifies a logical document within jurisdiction/source family.
- `content_hash` identifies a concrete payload revision.
- Same `canonical_document_key` plus same `content_hash` means the command should reuse the existing retrievable revision if one exists.
- Same `canonical_document_key` plus different `content_hash` creates a new revision and points `previous_raw_scrape_id` at the latest prior revision.
- `seen_count` increments when the same canonical/content identity is observed again.
- `last_seen_at` updates on each observation.

### Migration Position

Do not rewrite all historical `v1` keys in the first implementation. Instead:

- add `v2` key generation to the new domain package
- keep old rows readable
- write new rows with `v2` keys
- add a later migration task only if historical chain continuity becomes necessary for launch

## Storage Contract

### Postgres

Postgres is canonical relational product state.

Existing tables to reuse:

- `raw_scrapes`
- `document_chunks`
- `pipeline_runs`
- `pipeline_steps`
- admin/substrate read surfaces

Additive tables or columns likely needed:

- `search_result_snapshots`
- `content_artifacts` or a similarly named artifact metadata table
- `pipeline_runs` columns for `orchestrator`, `windmill_workspace`, `windmill_run_id`, `source_family`, `contract_version`, and `idempotency_key`
- `pipeline_steps` columns for `command`, `retry_class`, `decision_reason`, `alerts`, `refs`, and Windmill job id

Do not make Windmill write canonical product rows directly.

### MinIO

MinIO stores immutable large artifacts:

- raw SearXNG JSON payloads when retained
- Z.ai reader markdown/text output
- raw HTML/PDF/source payloads
- large LLM request/response artifacts if too large for Postgres

Object keys are generated by affordabot domain code:

```text
artifacts/<contract_version>/<jurisdiction_slug>/<source_family>/<artifact_kind>/<sha256>.<ext>
```

Postgres stores:

- object key/URI
- content hash
- media type
- byte length where available
- artifact kind
- contract version
- canonical document key where applicable
- creating command and idempotency key

### pgvector

pgvector stores retrieval indexes derived from canonical chunks.

Rules:

- every vector row must include metadata for `jurisdiction_id`, `source_family`, `canonical_document_key`, `raw_scrape_id`, `artifact_ref`, and `contract_version`
- every vector row points back to a canonical Postgres document/chunk context
- similarity hits are candidates; evidence is the chunk plus provenance chain
- rebuilding embeddings must not alter canonical document identity

## Atomicity And Idempotency

Windmill can rerun an entire flow. It does not provide resume-from-step semantics that should be trusted as the product recovery mechanism. Affordabot commands must make whole-flow reruns safe.

### Idempotency Keys

Each command computes an idempotency key from:

```text
contract_version
command
jurisdiction_id
source_family
logical input refs
normalized provider payload hash where applicable
```

Database writes should use uniqueness constraints around command idempotency where possible.

### Command Write Pattern

Each command follows this pattern:

1. validate contract version and input refs
2. acquire a scoped advisory lock or insert an in-progress operation row
3. detect prior completed command result by idempotency key
4. write immutable artifacts first when the artifact hash is known
5. write or upsert canonical Postgres rows in a transaction
6. write pgvector rows using deterministic ids where applicable
7. verify postconditions
8. write pipeline step summary
9. return refs and counts

### Partial-Write Recovery

Required behavior:

| Failure Point | Rerun Behavior |
| --- | --- |
| provider failed before storage | retry provider or use freshness fallback |
| MinIO object uploaded, Postgres row missing | find by content hash/object key and attach row |
| Postgres raw row inserted, MinIO ref missing | retry artifact write or mark `storage_uri` absent with alert if non-blocking |
| Postgres raw row inserted, vector write failed | rerun `index` reuses raw row and deterministic chunk ids |
| vector rows written, raw row not marked processed | rerun verifies chunk count and marks retrievable |
| analysis artifact written, analysis row missing | attach by content hash/idempotency key or rewrite deterministically |

Storage upload failure should be blocking for reader artifacts in the new pipeline unless explicitly configured as non-blocking for a source family. The current ingestion path treats blob upload as non-blocking; the domain command must make that policy explicit.

## Concurrency And Admission Control

Windmill owns loops and concurrency settings. Affordabot owns product-level admission safety.

Initial limits:

- max Windmill fanout: 2 jurisdictions concurrently in dev
- max source families per jurisdiction: 1 at a time
- max SearXNG calls: 2 concurrent
- max Z.ai reader calls: 1 concurrent in dev
- max Z.ai LLM analysis calls: 1 concurrent in dev
- max `index` commands touching the same jurisdiction/source family: 1

Affordabot must enforce:

- one active command per `jurisdiction_id + source_family + command + logical_input_hash`
- one active full refresh per `jurisdiction_id + source_family`
- deterministic rerun behavior if duplicate Windmill runs start

Implementation options:

- Postgres advisory locks for active command scopes
- unique rows with `status in ('running')` guarded by transactions
- provider-specific semaphores if commands run inside one worker process

Duplicate Windmill run policy:

- if an identical command is already completed, return the completed refs
- if an identical command is running, return `skipped` or `blocked` with `retry_class=operator_required` depending on call context
- if a conflicting command is running for the same jurisdiction/source family, fail closed before writes

## Windmill Flow Contract

Target flow:

```text
pipeline_daily_refresh
  input: jurisdictions[], source_families[], mode
  for each jurisdiction/source_family with concurrency limit
    search_materialize
    freshness_gate
    branch:
      stale_blocked | empty_blocked
        summarize_run(blocked)
        fail/alert
      fresh | stale_but_usable | empty_but_usable
        read_fetch
        index
        analyze
        summarize_run
```

Windmill owns:

- schedules
- manual/webhook triggers
- native step retries/backoff
- branch conditions
- per-jurisdiction/source-family loop
- failure handler
- run history and run URLs
- operator approvals if needed later

Windmill must not own:

- canonical document key generation
- SQL for canonical product records
- MinIO object key policy
- pgvector metadata policy
- freshness semantics
- analysis sufficiency gates
- frontend read models

Current cron flows remain enabled as rollback until the parity window passes.

## Backend Read Model Contract

Add backend read APIs under the admin router or a new pipeline admin router. Suggested paths:

```text
GET  /api/admin/pipeline/jurisdictions/{jurisdiction_id}/status
GET  /api/admin/pipeline/runs/{run_id}
GET  /api/admin/pipeline/runs/{run_id}/steps
GET  /api/admin/pipeline/runs/{run_id}/evidence
POST /api/admin/pipeline/jurisdictions/{jurisdiction_id}/refresh
```

The frontend-facing status payload should look like:

```json
{
  "contract_version": "2026-04-13.windmill-domain.v1",
  "jurisdiction_id": "san-jose-ca",
  "jurisdiction_name": "San Jose CA",
  "source_family": "meeting_minutes",
  "pipeline_status": "stale_but_usable",
  "last_success_at": "2026-04-13T00:00:00Z",
  "freshness": {
    "status": "stale_but_usable",
    "fresh_hours": 24,
    "stale_usable_ceiling_hours": 72,
    "fail_closed_ceiling_hours": 168,
    "alerts": ["source_search_failed_using_last_success"]
  },
  "counts": {
    "search_results": 2,
    "raw_scrapes": 1,
    "artifacts": 1,
    "chunks": 4,
    "analyses": 1
  },
  "latest_analysis": {
    "status": "ready",
    "sufficiency_state": "qualitative_only",
    "evidence_count": 4
  },
  "operator_links": {
    "windmill_run_url": "https://windmill.example/runs/..."
  }
}
```

Frontend rules:

- use `frontend/src/services/adminService.ts` as the API boundary
- extend existing admin/substrate views before inventing a parallel admin app
- display backend statuses and alerts directly
- never infer freshness from raw timestamps in the browser
- never construct MinIO keys in the browser
- never call Windmill from the browser except through a backend-mediated operator action

## Implementation Phases

### Phase 0: Spec Lock

Task: `bd-9qjof.1`

Deliverables:

- this spec
- brownfield mapping in Beads
- reviewer acceptance that identity, atomicity, concurrency, command envelope, and frontend read model are sufficiently locked

Validation:

- `git diff --check`
- architecture review using `dx-review` or equivalent reviewer quorum

### Phase 1: Domain Package Skeleton

Task: `bd-9qjof.2`

Deliverables:

- package such as `backend/services/pipeline/domain/`
- command request/response models
- command envelope validator
- deterministic in-memory adapters
- tests ported from `backend/scripts/verification/windmill_bakeoff_domain_boundary.py`

Validation:

- happy run
- rerun idempotency
- source failure
- reader failure
- storage failure
- stale-but-usable
- stale-blocked
- no-analysis-without-evidence

### Phase 2: Windmill Flow Skeleton

Task: `bd-9qjof.3`

Deliverables:

- Windmill flow export for `pipeline_daily_refresh_domain_boundary__flow`
- thin Windmill scripts that invoke the domain package
- native retries, branch predicates, failure handler, loop/fanout shape
- no direct canonical storage writes in Windmill scripts

Validation:

- local flow-shaped test or script harness
- static scan showing no direct SQL/MinIO/pgvector product writes in Windmill layer

### Phase 3: Real Storage Adapters

Task: `bd-9qjof.4`

Deliverables:

- Postgres schema/migration prototype
- MinIO artifact adapter integration
- pgvector deterministic chunk id integration
- partial-write recovery tests

Validation:

- real or test Postgres-compatible integration test where available
- MinIO/object-store contract test
- crash-mid-step drills
- rerun after partial failure

### Phase 4: Backend Read Models And Frontend

Task: `bd-9qjof.5`

Deliverables:

- backend admin pipeline status/read APIs
- `adminService.ts` client methods and types
- frontend admin status/evidence display
- backend-mediated manual refresh action

Validation:

- backend API tests
- frontend build/typecheck
- browser or Playwright evidence for the admin route if UI files change

### Phase 5: Live Windmill San Jose Gate

Task: `bd-9qjof.6`

Deliverables:

- live Windmill run in shared `affordabot` workspace
- private/dev SearXNG call evidence
- Z.ai direct reader call evidence
- Z.ai LLM analysis call evidence
- Postgres + pgvector + MinIO write/read evidence
- rerun idempotency evidence
- stale/failure drill evidence
- no 1Password GUI prompt evidence

Validation:

- run artifact committed under `docs/poc/` or `backend/artifacts/`
- backend read model displays the run summary

### Phase 6: Rollout And Final Review

Task: `bd-9qjof.7`

Deliverables:

- parity window plan
- rollback runbook
- final architecture review package
- decision record for promoting the new pipeline as primary

Validation:

- explicit parity duration and pass/fail metrics
- rollback path proven or rehearsed
- final review accepts the production path

## Two-Agent Dispatch Plan

After `bd-9qjof.1` is accepted:

### Wave 1

Worker A: `bd-9qjof.2`

- owns domain package skeleton
- owns envelope, command models, in-memory adapters, deterministic tests
- must not edit Windmill flow assets except test fixtures

Worker B: `bd-9qjof.3`

- owns Windmill flow/script skeleton
- owns flow-shaped harness and branch/retry/failure handler documentation
- must not implement product storage logic inside Windmill scripts

### Wave 2

Worker A: `bd-9qjof.4`

- owns Postgres/MinIO/pgvector adapters and partial-write recovery
- owns deterministic chunk identity and storage tests

Worker B: `bd-9qjof.5`

- owns backend read APIs and frontend admin visualization
- owns frontend evidence if UI changes

### Wave 3

Single integration owner: `bd-9qjof.6`

- runs the live San Jose Windmill gate
- gathers evidence
- files defects discovered during live execution

### Wave 4

Single rollout owner: `bd-9qjof.7`

- writes final review package
- locks parity and rollback
- prepares final architecture discussion

## Validation Gates

Minimum checks before implementation PRs can merge:

- unit tests for command envelope and status vocabulary
- unit tests for all six commands with deterministic adapters
- idempotency tests for rerun and duplicate Windmill run admission
- partial-write recovery tests for MinIO, Postgres, and pgvector
- source failure, reader failure, storage failure, stale-but-usable, stale-blocked tests
- backend API tests for pipeline read models
- frontend build/typecheck and browser evidence if frontend changes
- live Windmill San Jose run before production rollout lock

## Risks And Mitigations

| Risk | Mitigation |
| --- | --- |
| Windmill scripts become a second backend | Scripts may call only coarse domain commands; static review rejects direct canonical writes |
| Identity divergence creates duplicate or orphaned data | Adopt `v2` jurisdiction/source-family scoped key; keep `v1` readable |
| Whole-flow rerun duplicates rows | Idempotency keys, deterministic chunk ids, uniqueness constraints, and postcondition checks |
| Partial writes across Postgres/MinIO/pgvector leave inconsistent state | Explicit recovery matrix and crash-mid-step tests |
| Frontend couples to orchestration internals | Backend read model contract only; Windmill URLs are operator links |
| Shared Windmill workspace affects Prime Radiant or other flows | Keep workspace path scoped to `f/affordabot/*`; do not mutate shared resources outside affordabot paths |
| Z.ai search remains broken | Remove from primary path; schedule separate manual/weekly health check only |
| Z.ai reader or LLM provider failure blocks launch | Commands classify provider failure and stale fallback behavior; reader/analysis remain canonical but fail closed where evidence is insufficient |

## Recommended First Executable Task

Start `bd-9qjof.2` and `bd-9qjof.3` in parallel only after reviewers accept this spec lock.

The implementation should not start by editing storage schemas or frontend views. It should start by making the domain command contract executable with deterministic tests, while Windmill flow assets are shaped around that same contract.
