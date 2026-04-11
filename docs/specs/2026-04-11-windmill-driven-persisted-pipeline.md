# Windmill-Driven Persisted Discovery Pipeline

## Summary

Affordabot should move offline discovery, search refresh, page reading, extraction, ingestion, and QA reporting into a Windmill-orchestrated, backend-executed, persisted pipeline. Windmill should own scheduling, step orchestration, retries, run visibility, and operator entrypoints. The affordabot backend should own all business logic, domain validation, table writes, artifact writes, freshness policy, source promotion, and pgvector ingestion.

This revision incorporates the external consultant review from `bd-jxclm.11` / PR #416. The main changes are:

- collapse the search phase from three exposed endpoints into one backend-owned `search-materialize` step
- reduce the MVP state model to four core tables plus existing domain tables
- separate infrastructure work into its own Beads epic, `bd-ybyy7`
- make freshness policies backend-owned named policies instead of raw Windmill parameters
- add contract versioning, retry ownership, stale fallback ceilings, and concrete artifact retention defaults

## Problem

The current scheduled ingestion model is too script-shaped for broad source expansion. Several jobs run as large backend scripts behind Windmill trigger endpoints, which gives basic schedule visibility but weak step-level resumeability. If one late stage fails, earlier successful work is not always first-class reusable state.

The current web discovery and reader surfaces also blur provider responsibilities:

- Search/discovery can be served by an OSS SearXNG-compatible endpoint, but public SearXNG instances are not reliable production dependencies.
- The universal harvester currently asks Z.ai chat plus a web-search tool to read a URL and return markdown. That makes page reading opaque, quota-bound, and difficult to debug.
- Search results, fetched source content, extracted markdown, source promotion decisions, and vector ingestion are not consistently represented as durable intermediate artifacts with freshness gates.

The desired system needs to continue working when external search is temporarily down, avoid repeating successful upstream work, and preserve an audit trail for source truth.

## Goals

- Make Windmill the orchestrator for scheduled and manual offline data pipeline runs.
- Keep affordabot backend as the only owner of domain logic and writes to affordabot domain tables.
- Persist every meaningful intermediate state needed for resumeability and auditability.
- Use private SearXNG as the recurring search primitive for candidate generation once the infra epic ships.
- Support latest-good fallback when SearXNG fails and prior search snapshots are still within backend-owned freshness policy.
- Replace the opaque Z.ai chat-as-reader path for normal pages with backend-owned reader/extraction stages.
- Keep Z.ai or OCR/layout services as bounded fallbacks for hard documents, not as the default control plane.
- Make every mutating step idempotent and resumable by `run_id`, `step_key`, `manifest_hash`, and idempotency key.
- Provide enough persisted evidence for operator review, external consultant review, and rollback decisions.

## Non-Goals

- Do not move affordabot domain writes directly into Windmill scripts.
- Do not make Windmill workers mount the affordabot repo and run internal Python modules directly as the primary execution model.
- Do not use public SearXNG instances for production scheduled runs.
- Do not put private SearXNG provisioning on the product epic critical path.
- Do not treat search snapshots as accepted source truth.
- Do not rewrite user-facing advisor/chat flows around Windmill.
- Do not remove existing cron endpoints until the new pipeline proves parity and rollback is documented.

## Active Contract

After this epic, the canonical offline pipeline contract should be:

```text
Windmill flow
  -> authenticated backend pipeline endpoint
  -> backend creates/updates pipeline run state
  -> backend executes one domain step
  -> backend persists step output and artifacts
  -> backend returns explicit step status and advisory next-step metadata
  -> Windmill branches/retries/reports based on response
```

Windmill is allowed to:

- schedule daily and manual runs
- pass manifests, `run_id`, `step_key`, and operator inputs
- call authenticated backend endpoints
- branch on backend response status
- obey backend-declared retry metadata
- record orchestration logs
- send orchestration-health Slack/operator alerts

Windmill is not allowed to:

- write `sources`, `raw_scrapes`, `document_chunks`, source review tables, or pipeline domain tables directly
- implement SearXNG result scoring, source truth scoring, source promotion, content hashing, or vector ingestion
- own raw freshness policy parameters
- hold unversioned business rules that must stay aligned with backend code
- silently coerce failed backend steps into success

The backend is required to:

- own all Postgres, pgvector, and MinIO writes
- enforce auth and idempotency
- validate manifests and source-family policies
- own freshness policy parameters and stale fallback decisions
- persist raw and normalized artifacts
- return explicit status payloads suitable for Windmill branching
- declare retryability, retry delay, max retries, and backend-authored alert content
- fail loudly when durable state or artifact writes fail

## Architecture / Design

### Control Plane

Windmill remains the operational control plane. Existing affordabot Windmill assets already document the shared-instance pattern: Windmill calls authenticated backend cron endpoints and backend executes the job. The new design extends that pattern from monolithic cron endpoints to step-oriented pipeline endpoints.

New flows should live under the existing Windmill workspace namespace, for example:

```text
f/affordabot/pipeline_daily_refresh
f/affordabot/pipeline_manual_run
f/affordabot/pipeline_retry_step
```

The Windmill flow should pass an input manifest, not business logic. The manifest references named backend policies instead of embedding raw stale-hour or sample-size parameters:

```json
{
  "contract_version": "1.0.0",
  "run_label": "daily-discovery-refresh",
  "run_mode": "capture_and_ingest",
  "jurisdictions": ["Saratoga CA"],
  "families": ["meetings", "permits", "municipal_code"],
  "freshness_policy": "standard_daily_discovery",
  "processing_policy": "bounded_daily_default",
  "operator_notes": "bounded daily refresh"
}
```

The backend owns the definitions behind `standard_daily_discovery` and `bounded_daily_default`. Windmill may pass operator overrides only when the backend explicitly supports them and records the override in the persisted manifest.

### Contract Versioning

Every Windmill-to-backend request must include `contract_version`.

Rules:

- Start at `1.0.0`.
- Backend owns the supported version constant.
- Unsupported major versions fail closed with a non-retryable response.
- Minor version differences may be allowed only if the backend can safely ignore unknown fields.
- Every response echoes `contract_version` and may include `supported_contract_versions`.

### Backend Step API

Expose only steps that represent useful resume boundaries. Search planning, execution, normalization, and reranking share one failure domain, so they should be internal backend sub-steps of a single exposed `search-materialize` step.

MVP endpoints:

```text
POST /internal/pipeline/runs
POST /internal/pipeline/search-materialize
POST /internal/pipeline/freshness-gate
POST /internal/pipeline/read-fetch
POST /internal/pipeline/extract
POST /internal/pipeline/embed
GET  /internal/pipeline/runs/{run_id}/report
```

`promote` is deliberately deferred from MVP unless an implementation task proves it is needed for parity. Search snapshots and content artifacts can feed existing review/promotion surfaces before automatic promotion is added.

Every mutating request should include:

```json
{
  "contract_version": "1.0.0",
  "run_id": "uuid",
  "step_key": "search_materialize",
  "idempotency_key": "run_id:step_key:manifest_hash",
  "manifest_hash": "sha256:...",
  "trigger_source": "windmill:f/affordabot/pipeline_daily_refresh",
  "manifest": {}
}
```

Every mutating response should include:

```json
{
  "contract_version": "1.0.0",
  "status": "succeeded|failed|partial|skipped|in_progress",
  "run_id": "uuid",
  "step_key": "search_materialize",
  "retryable": true,
  "max_retries": 3,
  "retry_after_seconds": 300,
  "created_count": 0,
  "reused_count": 0,
  "failed_count": 0,
  "artifact_paths": [],
  "alerts": [],
  "next_recommended_step": "freshness_gate",
  "operator_summary": "plain English summary"
}
```

`next_recommended_step` is advisory only. Windmill must not treat it as hidden business logic. The Windmill flow definition remains the explicit step graph.

### Idempotency and Concurrent Retries

Backend endpoints must tolerate duplicate calls from Windmill.

Rules:

- `pipeline_steps.idempotency_key` is unique.
- `pipeline_steps.manifest_hash` stores the hash separately from the derived idempotency key.
- If a duplicate key is received while the step is in progress, return the current step state instead of starting a second execution.
- If a duplicate `(run_id, step_key)` arrives with a different `manifest_hash`, reject it unless the request explicitly uses an approved rerun mode.
- Long-running steps may return `in_progress` and `retry_after_seconds`; Windmill should poll or retry according to backend-declared metadata.

### MVP Persistence Model

The MVP should use four core tables plus existing domain tables. This is intentionally slimmer than the first draft to reduce implementation risk while preserving auditability.

Pipeline runs:

```text
pipeline_runs
- id
- contract_version
- run_label
- run_mode
- manifest jsonb
- manifest_hash
- trigger_source
- status
- started_at
- finished_at
- created_by
- summary
- error_summary
```

Pipeline steps:

```text
pipeline_steps
- id
- run_id
- contract_version
- step_key
- idempotency_key unique
- manifest_hash
- status
- started_at
- finished_at
- created_count
- reused_count
- failed_count
- retryable
- max_retries
- retry_after_seconds
- freshness_policy
- latest_success_at
- max_stale_hours
- stale_backed not null default false
- decision_reason
- error_code
- error_detail
- alerts jsonb
- artifact_manifest jsonb
```

Search snapshots:

```text
search_result_snapshots
- id
- run_id
- query_key
- query_text
- provider
- provider_endpoint_hash
- observed_at
- validated_at
- rank
- title
- url
- snippet
- normalized_domain
- provider_score
- raw_artifact_path
- raw_payload_hash
```

Unified content artifacts:

```text
content_artifacts
- id
- run_id
- artifact_kind search_raw|fetch_raw|fetch_pdf|extract_markdown|debug_screenshot|report
- canonical_url
- source_snapshot_id
- parent_artifact_id
- status
- content_type
- content_hash
- markdown_hash
- extraction_method
- storage_path
- storage_hash
- retention_expires_at
- content_classification public|possibly_pii|sensitive
- http_status
- error_code
- error_detail
- created_at
- validated_at
```

Existing domain tables such as `sources`, `raw_scrapes`, source review queues, and `document_chunks` remain backend-owned. Pipeline tables can point at those domain records later, but Windmill must never write them directly. In MVP, pipeline stages should not write `raw_scrapes` until the backend has an explicit promotion/ingestion boundary.

### Backend-Owned Policy Tables or Config

The backend should own named policies. MVP may implement these in code/config, but the contract should be explicit enough to move to tables later.

Search query policy fields:

```text
query_key
jurisdiction_id
source_family
query_text
cadence
enabled
max_stale_hours
hard_stale_multiplier default 2
consecutive_stale_fallbacks
stale_alert_threshold default 3
```

Processing policy fields:

```text
policy_name
max_documents_per_source
sample_size_per_bucket
allow_playwright
allow_ocr_fallback
allow_live_search_on_miss
```

Latest-good fallback is safe only when:

- a prior successful snapshot exists
- `latest_success_at` is within `max_stale_hours`
- the hard ceiling `2 * max_stale_hours` has not been exceeded
- consecutive stale fallbacks have not exceeded the alert threshold without operator acknowledgement
- stale use is recorded as `stale_backed=true`
- backend emits an alert whenever stale fallback is used, even if the step succeeds

Zero-result search responses are not the same as provider failure. The backend must distinguish:

- provider unavailable
- provider returned zero results
- provider returned malformed payload
- provider returned results rejected by local validation

### Artifact Storage and Retention

MinIO should hold raw and intermediate artifacts that are too large or too operationally useful for normal relational rows:

```text
pipeline-runs/<run_id>/search/<query_key>/raw.json
pipeline-runs/<run_id>/fetch/<content_hash>/raw.html
pipeline-runs/<run_id>/fetch/<content_hash>/source.pdf
pipeline-runs/<run_id>/extract/<markdown_hash>/content.md
pipeline-runs/<run_id>/debug/<step_key>/screenshot.png
pipeline-runs/<run_id>/reports/summary.md
```

MVP retention defaults:

| Artifact kind | Default retention | Notes |
| --- | ---: | --- |
| `search_raw` | 30 days | Raw SearXNG payloads. |
| `fetch_raw` | 90 days | HTML or fetched text; classify as `possibly_pii` by default. |
| `fetch_pdf` | 90 days | Government PDFs may contain PII. |
| `extract_markdown` | 90 days | May be retained longer if linked to accepted source evidence. |
| `debug_screenshot` | 7 days | Debug-only. |
| `report` | 180 days | Operator reports can contain source-evaluation details. |

Artifact writes are part of the backend step contract. If the step cannot persist the required artifact, the step should fail or return `partial` only when the partial state is explicitly safe to resume.

A later cleanup job should be Windmill-scheduled but backend-executed:

```text
Windmill -> POST /internal/pipeline/artifacts/purge-expired
```

The backend deletes expired objects from MinIO and marks the artifact row purged. Windmill should not delete objects directly.

### Search Boundary

Private SearXNG is a search primitive, not a truth engine. It should return candidate URLs and snippets. The backend owns:

- query registry and query generation
- provider selection and endpoint config
- normalized URL extraction
- dedupe
- official-domain scoring
- source-family scoring
- freshness fallback
- promotion to review queue or source inventory

The recurring daily search job should materialize search snapshots for known query keys. Runtime consumers should prefer recent snapshots and only live-search on cache misses or explicitly allowed ad hoc work.

Private SearXNG provisioning and runtime configuration are tracked separately in infra epic `bd-ybyy7`. Product/backend work should keep the provider boundary injectable so the skeleton can ship before the private endpoint is fully hardened.

### Reader Boundary

The current Z.ai chat-as-reader behavior should be replaced for ordinary pages. The backend reader pipeline should use:

1. direct HTTP fetch
2. readability/trafilatura-style extraction
3. Playwright fallback for JavaScript-heavy pages, if policy allows
4. PDF extraction path for PDFs
5. Z.ai layout/OCR only for hard-document fallback after MVP, when local extraction fails or policy says OCR is allowed

The reader result is not source truth. It is persisted evidence for scoring, extraction, review, and ingestion.

### Source Promotion Boundary

Promotion to accepted source inventory should remain separate from search snapshots and extraction artifacts.

Search snapshots answer: "What did a provider return for this query?"

Fetch/extraction answers: "What content did this URL expose at this time?"

Promotion answers: "Should affordabot trust this URL/family as an accepted source?"

MVP can defer automatic promotion. If promotion is included, the backend should implement it as a policy-driven step:

- auto-promote only for explicitly allowed families and high-confidence first-party surfaces
- otherwise create candidate review items
- record rejection reasons and confidence signals
- preserve lineage back to search/fetch/extraction artifacts

## Execution Phases

### Phase 1: Specification and Review

- Commit this spec.
- Publish a draft PR so external reviewers can inspect it cross-VM.
- Run consultant review before implementation starts.
- Apply spec changes from consultant review before starting `bd-jxclm.2`.

### Phase 2: Pipeline State and Artifacts

- Add schema migrations and model/service layer for the four MVP tables.
- Implement idempotency keys, manifest hash checks, and state transitions.
- Define artifact retention defaults and content classification posture.

### Phase 3: Backend Step Contracts

- Add authenticated internal endpoints for the MVP step API.
- Ensure each endpoint can be called repeatedly with the same idempotency key.
- Ensure each endpoint returns Windmill-friendly status, retry, and alert payloads.

### Phase 4: Materialized Search

- Implement `search-materialize` with injectable provider selection.
- Use existing/mock provider in local tests and private SearXNG when infra is available.
- Persist normalized snapshots and raw search artifacts.
- Keep reranking internal to the backend step.

### Phase 5: Freshness Gate

- Implement named freshness policies.
- Implement latest-good fallback, consecutive stale counters, hard stale ceiling, and stale alerts.
- Prove zero-result, provider failure, stale-acceptable, and stale-rejected paths separately.

### Phase 6: Reader, Extraction, and Ingestion

- Implement fetch, extraction, content hash reuse, markdown artifact writes, and pgvector ingestion freshness.
- Replace normal-page dependence on Z.ai chat-as-reader.
- Defer Z.ai layout/OCR fallback unless required by a bounded hard-document validation.

### Phase 7: Windmill Flow Orchestration

- Add daily and manual Windmill flows that call backend step endpoints.
- Branch on backend status and retryability.
- Emit orchestration-health alerts while preserving backend-authored data-quality alerts.
- Keep Windmill scripts thin and free of domain writes.

### Phase 8: Validation and Rollout

- Run a bounded end-to-end flow for one jurisdiction and a small family set.
- Validate persisted intermediates, stale fallback, artifact retention, and resume-from-failed-step.
- Run an explicit parity window before retiring existing cron/script behavior.

## Beads Structure

Product/backend architecture epic:

- Epic: `bd-jxclm` - Design Windmill-driven persisted discovery pipeline
- First task: `bd-jxclm.1` - Write Windmill-driven pipeline implementation spec
- `bd-jxclm.2` - Add persisted pipeline state and artifact schema
- `bd-jxclm.3` - Implement backend pipeline step endpoints
- `bd-jxclm.4` - Materialize SearXNG search refresh with freshness gating
- `bd-jxclm.5` - Build reader, extraction, and artifact materialization stages
- `bd-jxclm.9` - Add Windmill orchestration flows and run controls
- `bd-jxclm.10` - Add pipeline validation, rollout, and operator runbooks
- `bd-jxclm.11` - External consultant review of Windmill pipeline spec

Separate infrastructure epic:

- Epic: `bd-ybyy7` - Provision infrastructure for affordabot persisted pipeline
- `bd-ybyy7.1` - Infra: provision private SearXNG search service
- `bd-jxclm.7` - Infra: wire Windmill and Railway runtime configuration
- `bd-jxclm.8` - Infra: define artifact storage retention and observability

Note: `bd-jxclm.7` and `bd-jxclm.8` are parented under `bd-ybyy7`; their IDs retain the original prefix because renaming them was not worth delaying the planning work.

Product dependency summary:

- Implementation tasks depend on `bd-jxclm.1`.
- Backend endpoints depend on schema.
- Materialized search depends on schema and endpoints, but not on infra provisioning.
- Reader/extraction depends on schema and endpoints.
- Windmill flows depend on backend endpoints, materialized search, and reader/extraction.
- Validation depends on Windmill flows.

Infra dependency summary:

- Infra work is parallel and tracked under `bd-ybyy7`.
- Product work should use injectable provider/config boundaries until infra is ready.
- A rollout gate, not a product implementation blocker, should verify private SearXNG, Railway/Windmill variables, and MinIO retention before broad production use.

## Validation

### Unit and Contract Tests

- Pipeline state transition tests.
- Idempotency tests for every backend endpoint.
- Auth tests for internal pipeline endpoints.
- Windmill contract tests for required variables, headers, and trigger source.
- Freshness policy tests for fresh, stale-acceptable, stale-rejected, hard-stale-ceiling, consecutive-stale-alert, zero-result, and no-prior-snapshot states.
- Artifact write/read tests for MinIO paths, retention metadata, content classification, and failure handling.
- Contract version tests for supported, unsupported major, and minor-version-tolerant payloads.

### Runtime Smokes

1. Backend can create a pipeline run and reject duplicate/different manifests correctly.
2. Search materialization writes snapshots and raw artifacts.
3. Freshness gate uses latest-good search snapshots if within policy.
4. A simulated provider outage emits alerts and increments consecutive stale fallback counters.
5. A hard stale ceiling fails closed.
6. A second run with unchanged content reuses prior fetch/extraction/embedding state.
7. A simulated artifact write failure marks the step failed or partial with visible operator summary.
8. Windmill manual flow triggers backend and backend records `X-PR-CRON-SOURCE`.
9. The final report links run id, step ids, artifact paths, stale decisions, and accepted/rejected candidate counts.

### Failure Drills

- Crash mid-step and replay with same idempotency key.
- Concurrent invocation of the same step by two Windmill attempts.
- Manifest drift on retry.
- Partial MinIO write.
- SearXNG total outage.
- Zero-result SearXNG response.
- Stale fallback threshold exceeded.
- Fetch success followed by extraction failure.
- Rollback to existing cron/script behavior.

### Completion Proof

The product epic is not complete until a bounded Windmill-triggered run produces:

- `pipeline_runs` row with terminal success or expected partial state
- `pipeline_steps` rows for the MVP steps
- persisted search snapshot rows
- at least one raw artifact in MinIO or explicit artifact skip reason
- at least one extracted markdown artifact or explicit extraction skip reason
- pgvector/document chunk reuse or ingestion evidence
- Slack/operator report
- rollback instructions

### Parity Window

Before retiring the existing cron/script path, run both old and new paths for a bounded parity window:

- duration: at least 7 calendar days or 5 successful scheduled runs, whichever is longer
- scope: one small jurisdiction set and one representative source family set
- pass metric: no unexplained data loss, no unhandled step failures, stale fallback alerts visible, and operator report generated for every run
- fail action: disable new pipeline schedules and continue existing cron/script path while preserving pipeline artifacts for diagnosis

## Risks / Rollback

### Windmill Becomes a Second Backend

Risk: business logic leaks into Windmill scripts.

Mitigation: keep Windmill flow code limited to HTTP calls, status branching, retries, and orchestration-health alerts. Backend endpoints own all writes and policy.

### Stale Search Results Hide Outages

Risk: latest-good fallback masks SearXNG failures.

Mitigation: allow stale fallback only inside backend-owned policy, always mark `stale_backed=true`, alert on every stale-backed success, increment consecutive stale counters, and fail closed beyond the hard stale ceiling.

### Search Snapshots Become Accepted Truth

Risk: search result rows are treated as trusted sources.

Mitigation: promotion remains separate with review/acceptance state and lineage. MVP may defer automatic promotion entirely.

### Artifact Growth or PII Exposure

Risk: raw search/fetch/extraction artifacts grow without bounds or expose sensitive resident information.

Mitigation: classify fetched artifacts as `possibly_pii` by default, keep pipeline artifacts private, write `retention_expires_at`, and purge expired artifacts through a backend-owned cleanup endpoint.

### Version Drift Between Windmill and Backend

Risk: a Windmill flow calls endpoint contracts from a different backend version.

Mitigation: include `contract_version` in manifests and backend responses. Fail closed on unsupported major versions.

### Rollback

Rollback should be additive:

1. Disable new Windmill pipeline schedules.
2. Keep manual flow disabled except for repair.
3. Re-enable or call existing cron endpoints/scripts while preserving newly written pipeline tables.
4. Do not delete pipeline artifacts until retention policy confirms they are not needed for diagnosis.

## Recommended First Task

Start with `bd-jxclm.2`, after this revised spec is accepted. The persisted state model is the foundation for every later step. The MVP schema should use the four-table model above, with idempotency and artifact references included from the first migration.

## External Consultant Review Prompt

Use PR #415 and review PR #416 as source material. Any follow-on review should focus on whether this revised spec correctly applies the review findings without overcorrecting.

Required follow-up questions:

1. Does the four-table MVP model preserve enough auditability?
2. Is `search-materialize` the right exposed boundary for search?
3. Are backend-owned named policies enough to keep business logic out of Windmill?
4. Are the stale fallback guardrails sufficient?
5. Is infra now separated cleanly from product/backend work?
6. What should still be cut before `bd-jxclm.2` starts?
