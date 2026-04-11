# Windmill-Driven Persisted Discovery Pipeline

## Summary

Affordabot should move offline discovery, search refresh, page reading, extraction, ingestion, and QA reporting into a Windmill-orchestrated, backend-executed, persisted pipeline. Windmill should own scheduling, step orchestration, retries, run visibility, and operator entrypoints. The affordabot backend should own all business logic, domain validation, table writes, artifact writes, freshness policy, source promotion, and pgvector ingestion.

This keeps Windmill useful without turning it into a second backend.

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
- Persist every meaningful intermediate state: search plan, search result snapshots, freshness decisions, fetched raw content, extracted markdown, ingestion jobs, vector chunks, and run reports.
- Use private SearXNG as the recurring search primitive for candidate generation.
- Support latest-good fallback when SearXNG fails and prior search snapshots are still within freshness policy.
- Replace the opaque Z.ai chat-as-reader path for normal pages with backend-owned reader/extraction stages.
- Keep Z.ai or OCR/layout services as bounded fallbacks for hard documents, not as the default control plane.
- Make every step idempotent and resumable by `run_id`, `step_key`, and idempotency key.
- Provide enough persisted evidence for operator review and external consultant review.

## Non-Goals

- Do not move affordabot domain writes directly into Windmill scripts.
- Do not make Windmill workers mount the affordabot repo and run internal Python modules directly as the primary execution model.
- Do not use public SearXNG instances for production scheduled runs.
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
  -> backend returns explicit step status and next-step metadata
  -> Windmill branches/retries/reports based on response
```

Windmill is allowed to:

- schedule daily and manual runs
- pass manifests, `run_id`, `step_key`, and operator inputs
- call authenticated backend endpoints
- branch on backend response status
- retry safe steps according to backend-declared retryability
- record orchestration logs
- send Slack/operator alerts

Windmill is not allowed to:

- write `sources`, `raw_scrapes`, `document_chunks`, source review tables, or pipeline domain tables directly
- implement SearXNG result scoring, source truth scoring, source promotion, content hashing, or vector ingestion
- hold unversioned business rules that must stay aligned with backend code
- silently coerce failed backend steps into success

The backend is required to:

- own all Postgres, pgvector, and MinIO writes
- enforce auth and idempotency
- validate manifests and source-family policies
- evaluate freshness and stale fallback
- persist raw and normalized artifacts
- return explicit status payloads suitable for Windmill branching
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

The Windmill flow should pass an input manifest, not business logic:

```json
{
  "run_label": "daily-discovery-refresh",
  "run_mode": "capture_and_ingest",
  "jurisdictions": ["Saratoga CA"],
  "families": ["meetings", "permits", "municipal_code"],
  "freshness_policy": "use_last_good_if_search_fails",
  "max_search_stale_hours": 168,
  "max_document_stale_hours": 720,
  "sample_size_per_bucket": 5,
  "operator_notes": "bounded daily refresh"
}
```

### Backend Step API

Prefer step endpoints that are coarse enough to be meaningful and fine enough to resume:

```text
POST /internal/pipeline/runs
POST /internal/pipeline/search-plan
POST /internal/pipeline/search-execute
POST /internal/pipeline/search-rerank
POST /internal/pipeline/freshness-gate
POST /internal/pipeline/read-fetch
POST /internal/pipeline/extract
POST /internal/pipeline/embed
POST /internal/pipeline/promote
POST /internal/pipeline/report
```

Every request should include:

```json
{
  "run_id": "uuid",
  "step_key": "search_execute",
  "idempotency_key": "run_id:step_key:manifest_hash",
  "trigger_source": "windmill:f/affordabot/pipeline_daily_refresh",
  "manifest": {}
}
```

Every response should include:

```json
{
  "status": "succeeded|failed|partial|skipped",
  "run_id": "uuid",
  "step_key": "search_execute",
  "retryable": true,
  "created_count": 0,
  "reused_count": 0,
  "failed_count": 0,
  "artifact_paths": [],
  "next_recommended_step": "search_rerank",
  "operator_summary": "plain English summary"
}
```

### Persistence Model

The schema should separate orchestration state from domain state.

Pipeline state:

```text
pipeline_runs
- id
- run_label
- run_mode
- manifest_hash
- trigger_source
- status
- started_at
- finished_at
- created_by
- summary
- error_summary

pipeline_steps
- id
- run_id
- step_key
- idempotency_key
- status
- started_at
- finished_at
- created_count
- reused_count
- failed_count
- retryable
- error_code
- error_detail
- artifact_manifest
```

Search state:

```text
search_queries
- id
- query_key
- jurisdiction_id
- source_family
- query_text
- cadence
- enabled
- max_stale_hours

search_result_snapshots
- id
- run_id
- query_key
- query_text
- provider
- provider_endpoint_hash
- observed_at
- rank
- title
- url
- snippet
- normalized_domain
- provider_score
- local_score
- raw_artifact_path
- raw_payload_hash
```

Freshness decisions:

```text
pipeline_freshness_decisions
- id
- run_id
- decision_key
- input_kind
- input_ref
- status
- freshness_policy
- latest_success_at
- max_stale_hours
- stale_backed
- decision_reason
```

Reader and extraction state:

```text
fetch_artifacts
- id
- run_id
- canonical_url
- fetched_at
- status
- http_status
- content_type
- content_hash
- raw_artifact_path
- screenshot_artifact_path
- error_code

extraction_artifacts
- id
- run_id
- fetch_artifact_id
- extraction_method
- status
- markdown_hash
- markdown_artifact_path
- metadata_artifact_path
- error_code
```

Ingestion state:

```text
ingestion_jobs
- id
- run_id
- extraction_artifact_id
- content_hash
- embedding_model
- status
- chunk_count
- reused_existing_chunks
- error_code
```

Existing domain tables such as `sources`, `raw_scrapes`, source review queues, and `document_chunks` remain backend-owned. Pipeline tables can point at those domain records, but Windmill must never write them directly.

### Artifact Storage

MinIO should hold raw and intermediate artifacts that are too large or too operationally useful for normal relational rows:

```text
pipeline-runs/<run_id>/search/<query_key>/raw.json
pipeline-runs/<run_id>/fetch/<content_hash>/raw.html
pipeline-runs/<run_id>/fetch/<content_hash>/source.pdf
pipeline-runs/<run_id>/extract/<markdown_hash>/content.md
pipeline-runs/<run_id>/debug/<step_key>/screenshot.png
pipeline-runs/<run_id>/reports/summary.md
```

Artifact writes are part of the backend step contract. If the step cannot persist the required artifact, the step should fail or return `partial` only when the partial state is explicitly safe to resume.

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

### Reader Boundary

The current Z.ai chat-as-reader behavior should be replaced for ordinary pages. The backend reader pipeline should use:

1. direct HTTP fetch
2. readability/trafilatura-style extraction
3. Playwright fallback for JavaScript-heavy pages
4. PDF extraction path for PDFs
5. Z.ai layout/OCR only for hard-document fallback when local extraction fails or policy says OCR is allowed

The reader result is not source truth. It is persisted evidence for scoring, extraction, review, and ingestion.

### Source Promotion Boundary

Promotion to accepted source inventory should remain separate from search snapshots and extraction artifacts.

Search snapshots answer: "What did a provider return for this query?"

Fetch/extraction answers: "What content did this URL expose at this time?"

Promotion answers: "Should affordabot trust this URL/family as an accepted source?"

The backend should implement promotion as a policy-driven step:

- auto-promote only for explicitly allowed families and high-confidence first-party surfaces
- otherwise create candidate review items
- record rejection reasons and confidence signals
- preserve lineage back to search/fetch/extraction artifacts

## Execution Phases

### Phase 1: Specification and Review

- Commit this spec.
- Publish a draft PR so external reviewers can inspect it cross-VM.
- Run consultant review before implementation starts.

### Phase 2: Pipeline State and Artifacts

- Add schema migrations and model/service layer for pipeline runs, steps, snapshots, decisions, fetch artifacts, extraction artifacts, and ingestion jobs.
- Define MinIO prefixes and retention policy.
- Add idempotency and status transition tests.

### Phase 3: Backend Step Contracts

- Add authenticated internal endpoints for each step.
- Ensure each endpoint can be called repeatedly with the same idempotency key.
- Ensure each endpoint returns Windmill-friendly status payloads.

### Phase 4: Materialized SearXNG Search

- Provision and configure private SearXNG.
- Implement search plan, execute, normalize, rerank, snapshot, and latest-good fallback.
- Prove failure behavior by disabling SearXNG and continuing from an acceptable prior snapshot.

### Phase 5: Reader, Extraction, and Ingestion

- Implement fetch, extraction, content hash reuse, markdown artifact writes, and pgvector ingestion freshness.
- Replace normal-page dependence on Z.ai chat-as-reader.
- Preserve Z.ai layout/OCR as a bounded hard-document fallback.

### Phase 6: Windmill Flow Orchestration

- Add daily and manual Windmill flows that call backend step endpoints.
- Branch on backend status and retryability.
- Emit Slack/operator summaries.
- Keep Windmill scripts thin and free of domain writes.

### Phase 7: Validation and Rollout

- Run a bounded end-to-end flow for one jurisdiction and a small family set.
- Validate persisted intermediates, stale fallback, artifact retention, and resume-from-failed-step.
- Document rollback to existing cron/script behavior until replacement is proven.

## Beads Structure

- Epic: `bd-jxclm` - Design Windmill-driven persisted discovery pipeline
- First task: `bd-jxclm.1` - Write Windmill-driven pipeline implementation spec
- `bd-jxclm.2` - Add persisted pipeline state and artifact schema
- `bd-jxclm.3` - Implement backend pipeline step endpoints
- `bd-jxclm.4` - Materialize SearXNG search refresh with freshness gating
- `bd-jxclm.5` - Build reader, extraction, and artifact materialization stages
- `bd-jxclm.6` - Infra: provision private SearXNG search service
- `bd-jxclm.7` - Infra: wire Windmill and Railway runtime configuration
- `bd-jxclm.8` - Infra: define artifact storage retention and observability
- `bd-jxclm.9` - Add Windmill orchestration flows and run controls
- `bd-jxclm.10` - Add pipeline validation, rollout, and operator runbooks

Dependency summary:

- All implementation and infra tasks depend on `bd-jxclm.1`.
- Backend endpoints depend on schema.
- Materialized SearXNG search depends on schema, endpoints, and private SearXNG provisioning.
- Reader/extraction depends on schema, endpoints, and artifact retention policy.
- Windmill flows depend on backend endpoints, materialized search, reader/extraction, and Windmill/Railway config.
- Validation depends on Windmill flows, SearXNG provisioning, and artifact observability.

## Validation

### Unit and Contract Tests

- Pipeline state transition tests.
- Idempotency tests for every backend endpoint.
- Auth tests for internal pipeline endpoints.
- Windmill contract tests for required variables, headers, and trigger source.
- Freshness policy tests for fresh, stale-acceptable, stale-rejected, and no-prior-snapshot states.
- Artifact write/read tests for MinIO paths and failure handling.

### Runtime Smokes

1. Private SearXNG endpoint returns JSON from backend runtime.
2. Windmill manual flow triggers backend and backend records `X-PR-CRON-SOURCE`.
3. A bounded run for one jurisdiction writes search snapshots.
4. A second run with unchanged content reuses prior fetch/extraction/embedding state.
5. A simulated SearXNG outage uses latest-good search snapshots if within policy.
6. A simulated artifact write failure marks the step failed or partial with visible operator summary.
7. The final report links run id, step ids, artifact paths, and accepted/rejected candidate counts.

### Completion Proof

The epic is not complete until a bounded Windmill-triggered run produces:

- `pipeline_runs` row with terminal success or expected partial state
- step rows for search, freshness, read/fetch, extraction, embedding, promotion/reporting
- persisted search snapshot rows
- at least one raw artifact in MinIO
- at least one extracted markdown artifact or explicit extraction skip reason
- pgvector/document chunk reuse or ingestion evidence
- Slack/operator report
- rollback instructions

## Risks / Rollback

### Windmill Becomes a Second Backend

Risk: business logic leaks into Windmill scripts.

Mitigation: keep Windmill flow code limited to HTTP calls, status branching, retries, and alerts. Backend endpoints own all writes and policy.

### Stale Search Results Hide Outages

Risk: latest-good fallback masks SearXNG failures.

Mitigation: allow stale fallback only inside explicit policy and always mark `stale_backed=true`. Windmill should still alert on refresh failure.

### Search Snapshots Become Accepted Truth

Risk: search result rows are treated as trusted sources.

Mitigation: promotion remains a separate backend step with review/acceptance state and lineage.

### Artifact Growth

Risk: raw search/fetch/extraction artifacts grow without bounds.

Mitigation: implement retention windows, size budgets, and MinIO lifecycle cleanup before broad rollout.

### Version Drift Between Windmill and Backend

Risk: a Windmill flow calls endpoint contracts from a different backend version.

Mitigation: include pipeline contract version in manifests and backend responses. Fail closed on unsupported versions.

### Rollback

Rollback should be additive:

1. Disable new Windmill pipeline schedules.
2. Keep manual flow disabled except for repair.
3. Re-enable or call existing cron endpoints/scripts while preserving newly written pipeline tables.
4. Do not delete pipeline artifacts until retention policy confirms they are not needed for diagnosis.

## Recommended First Task

Start with `bd-jxclm.2`, after this spec is reviewed. The persisted state model is the foundation for every later step. Without schema, idempotency, and artifact references, the system cannot safely resume, reuse latest-good results, or prove what happened during a Windmill run.

## External Consultant Review Prompt

Use the pushed PR for this spec as the source of truth. The consultant should review the design before implementation and focus on business logic boundaries, failure modes, and operational simplicity.

Required review questions:

1. Does the Windmill/backend boundary keep domain logic in affordabot while still making Windmill useful as an orchestrator?
2. Are the proposed step boundaries too fine, too coarse, or appropriately resumable?
3. Is the schema sufficient for auditability without overbuilding?
4. Is latest-good fallback safe, and what metadata is missing to prevent silent stale behavior?
5. Are SearXNG, reader, MinIO, and pgvector responsibilities separated cleanly?
6. What parts should be cut from the MVP to reduce delivery risk?
7. What failure drills are missing before rollout?
