# ADR: Windmill / Affordabot Boundary For Data-Moat Pipeline

Date: 2026-04-12
Status: Accepted for implementation planning; production rollout still requires live Windmill validation.
Tracking: `bd-jxclm.15` while local Beads reconciliation is offline.

## Decision

Adopt a layered hybrid architecture:

- **Windmill** owns orchestration and operator control.
- **Affordabot domain code** owns product-data materialization and all product invariants.
- **Postgres** owns canonical relational product state.
- **pgvector** owns semantic retrieval indexes over canonical chunks.
- **MinIO** owns immutable large artifacts and raw/normalized payloads.
- **Affordabot backend APIs** own product read models and user/operator actions.
- **Frontend** owns visualization, review workflows, and product/operator UX through backend APIs.

Windmill must not become a second application backend. It may run affordabot domain commands, but it must not own canonical document identity, source truth, freshness semantics, provenance rules, analysis sufficiency, or direct canonical product writes.

The immediate implementation target is **Path B: Windmill orchestration plus affordabot domain boundary**, using a shared Python domain package first. Coarse HTTP endpoints are a later promotion path, not the starting point.

## Context

Affordabot differs from Prime Radiant AI. In Prime Radiant, Windmill can cleanly own ETL because ETL is support machinery. In affordabot, discovery, scraping, source ranking, canonicalization, freshness policy, evidence provenance, and analysis sufficiency are part of the product moat. Calling that whole surface "ETL" hides the core risk: moving it into Windmill would move product logic into the workflow control plane.

The Windmill storage-boundary bakeoff compared:

- **Path A: Windmill-heavy direct storage**
  - Windmill scripts directly manipulate search snapshots, artifacts, chunks, embeddings, and analyses.
  - The POC passed, but only by recreating product identity, freshness, dedupe, chunking, provenance, and idempotency inside a large script.

- **Path B: Windmill plus affordabot domain boundary**
  - Windmill owns DAG shape and calls coarse affordabot commands:
    `search_materialize`, `freshness_gate`, `read_fetch`, `index`, `analyze`, `summarize_run`.
  - Each command protects a product invariant and writes through affordabot-owned storage adapters.

Consultant reviews converged on the same direction:

- Path B is the correct boundary to lock directionally.
- Path A proves that direct storage tends to recreate an application backend inside Windmill.
- Before production implementation, three gaps must close:
  - jurisdiction-scoped canonical identity
  - write atomicity / crash-mid-step recovery
  - multi-jurisdiction fanout and concurrency model
- A live Windmill execution pass is required before final production lock.

## Layer Model

```text
Windmill
  orchestration/control plane

Affordabot domain package
  product materialization commands and invariants

Affordabot backend API
  product read models, user/operator actions, auth, frontend contract

Postgres
  canonical relational product state

pgvector
  semantic retrieval index over canonical chunks

MinIO
  immutable large artifacts and raw/normalized payloads

Frontend
  visualization, review queues, evidence display, operator UX
```

## Ownership Boundaries

| Layer | Owns | Must Not Own |
| --- | --- | --- |
| Windmill | schedules, manual triggers, webhooks, DAG shape, retries, branches, loops, failure handlers, approvals, run history, operator run links | canonical identity, freshness policy, provenance, direct canonical writes, analysis sufficiency |
| Affordabot domain package | product write commands, canonical IDs, idempotency, dedupe, freshness gates, artifact references, chunk provenance, evidence gates, analysis contract versions | schedule/runtime control, Windmill UI state |
| Affordabot backend API | product read models, frontend contracts, auth, operator actions, optional Windmill trigger facade | low-level direct storage bypasses, hidden orchestration policy |
| Postgres | canonical relational product truth and metadata | blob payload storage, orchestration decisions, vector ranking semantics |
| pgvector | embeddings and similarity search over canonical chunks | canonical truth, freshness policy, provenance authority |
| MinIO | immutable raw artifacts, reader outputs, large intermediate files, optional large LLM artifacts | product decisions, relational joins, vector search |
| Frontend | dashboards, review queues, citations, freshness/status visualization, operator actions through backend APIs | direct Windmill orchestration, direct storage access, direct pgvector/MinIO access |

## Storage Boundary Details

### Postgres

Postgres is the canonical source of relational product truth. It should store:

- jurisdictions
- source families and source configuration
- search snapshots
- canonical documents
- artifact metadata and MinIO object references
- document chunks metadata
- analysis records
- evidence links
- pipeline run summaries that are product-visible
- review/approval decisions
- contract versions and migration state

Postgres rows must contain enough identifiers and hashes to prove idempotency and provenance without reading MinIO.

### pgvector

pgvector is an access path, not product truth. Vector rows must point back to canonical chunk/document/artifact rows.

Rules:

- every embedding belongs to a canonical chunk row
- retrieval must be jurisdiction-scoped by metadata/filter, not by frontend convention
- vector hits are candidates; evidence is the chunk plus provenance chain
- rebuilding embeddings must not change canonical document identity

### MinIO

MinIO stores immutable heavy artifacts:

- raw HTML/PDF/source payloads
- Z.ai reader markdown/text output
- normalized JSON payloads
- screenshots or visual evidence when used
- large intermediate LLM artifacts if too large for Postgres

Rules:

- object keys are generated by affordabot domain code
- object records are referenced from Postgres by key, content hash, media type, and contract version
- MinIO never decides freshness, identity, canonicality, or evidence sufficiency

## Frontend Boundary

The frontend is a product visualization and review layer. It must consume affordabot backend read APIs. It must not call Windmill, Postgres, pgvector, or MinIO directly.

Frontend should display affordabot concepts:

- jurisdiction status
- last successful refresh
- fresh / stale-but-usable / stale-blocked state
- source coverage
- extraction/reader status
- evidence-backed analyses
- citation/provenance chain
- confidence/sufficiency state
- pipeline run summaries
- failure reasons and retry status
- manual rerun/review/approval actions

Backend APIs should present these concepts explicitly. The frontend should not infer stale state from raw timestamps, parse Windmill job payloads, construct MinIO keys, or know pgvector schema.

Example read model:

```json
{
  "jurisdiction_id": "san-jose-ca",
  "source_family": "meeting_minutes",
  "freshness": {
    "status": "stale_but_usable",
    "last_success_at": "2026-04-12T06:00:00Z",
    "max_stale_hours": 48,
    "fallback_ceiling_hours": 168,
    "alerts": ["source_search_failed_using_last_success"]
  },
  "latest_analysis": {
    "status": "ready",
    "contract_version": "2026-04-12.windmill-boundary.v1",
    "evidence_count": 8
  },
  "operator_links": {
    "windmill_run_url": "https://windmill.example/runs/..."
  }
}
```

Frontend actions should call backend APIs:

```text
Frontend action
  -> affordabot backend API
    -> validate auth/product state
    -> trigger Windmill or write product review decision
      -> Windmill calls affordabot domain commands when orchestration is needed
```

The frontend may show Windmill run URLs for operators, but Windmill is not the product UI.

## Domain Commands To Implement First

The first production-shaped boundary should be a shared Python package with coarse commands:

| Command | Windmill Role | Affordabot Invariants |
| --- | --- | --- |
| `search_materialize` | discover and persist scoped search snapshot | query scope, source family, jurisdiction, zero-result semantics, snapshot idempotency |
| `freshness_gate` | decide branch status | max stale hours, fallback ceiling, stale alerts, fail-closed semantics |
| `read_fetch` | fetch/read selected URLs | canonical document identity, artifact hashing, MinIO object key policy, document dedupe |
| `index` | embed and index content | chunk identity, jurisdiction-scoped metadata, pgvector upsert idempotency, provenance |
| `analyze` | produce evidence-gated output | sufficiency gate, contract version, claim-to-evidence links, no-analysis-without-evidence |
| `summarize_run` | report pipeline result | Windmill run linkage, product counts, operator-visible status |

These commands must not be thin SQL wrappers. Each command must enforce at least one product invariant.

## Windmill Flow Shape

Windmill should run a flow shaped like:

```text
pipeline_daily_refresh
  for each jurisdiction/source_family
    search_materialize
    freshness_gate
    branch:
      stale_blocked -> summarize_run(blocked) -> alert/fail closed
      fresh | stale_but_usable -> read_fetch -> index -> analyze -> summarize_run
```

Windmill owns:

- schedule and manual trigger
- per-step retries/backoff
- step timeouts
- branch conditions
- per-jurisdiction fanout
- concurrency controls
- failure handlers
- run history
- operator links

Windmill does not own:

- SQL statements for canonical product rows
- MinIO object naming
- chunking/provenance rules
- stale policy calculation
- analysis sufficiency
- frontend read models

## Shared Package First, HTTP Later

Start with a shared Python package imported by Windmill worker scripts and affordabot backend code.

Reasons:

- fewer moving parts for pre-MVP
- simpler local testing
- no premature service boundary
- one domain language shared by pipeline and backend
- avoids turning affordabot into middleware while keeping Windmill thin

Promote to coarse HTTP endpoints only when one of these triggers is met:

- Windmill workers cannot reliably carry the affordabot package dependencies
- multiple runtimes need the same domain commands
- independent deploy/rollback cadence is needed
- security or network policy requires a backend service boundary
- frontend/operator actions need the same command surface synchronously

If/when HTTP is introduced, endpoints must remain coarse:

```text
POST /pipeline/search-materialize
POST /pipeline/freshness-gate
POST /pipeline/read-fetch
POST /pipeline/index
POST /pipeline/analyze
POST /pipeline/summarize-run
```

Do not create low-level `insert_row`, `upload_object`, `embed_text`, or `write_chunk` endpoints.

## Required Spec Locks Before Implementation

Implementation must not proceed past skeleton/live POC until these are explicitly specified:

1. **Jurisdiction-scoped canonical identity**
   - final `canonical_document_key` format
   - URL normalization policy
   - treatment of same URL across jurisdictions
   - content drift/versioning policy

2. **Write atomicity and crash recovery**
   - per-command idempotency keys
   - partial MinIO upload handling
   - partial Postgres write handling
   - pgvector upsert retry behavior
   - rerun behavior after crash-mid-step

3. **Concurrency model**
   - per-jurisdiction fanout limit
   - per-source-family rate limits
   - SearXNG reader/LLM concurrency ceilings
   - Postgres advisory lock or uniqueness strategy
   - duplicate Windmill run admission policy

4. **Contract versioning**
   - command request/response envelope version
   - artifact schema version
   - analysis output version
   - backwards-compatible read model policy

5. **Frontend read model contract**
   - status vocabulary
   - freshness payload
   - evidence/provenance payload
   - operator action payloads
   - Windmill run-link exposure policy

## Live Validation Gate

Before production implementation is considered locked, run one bounded live Windmill pass for a San Jose meeting-minutes slice:

- Windmill flow executes in the shared affordabot workspace
- private/dev SearXNG endpoint is called
- Z.ai direct reader is called
- Z.ai LLM analysis is called
- Postgres writes occur through affordabot domain code
- pgvector chunk index is written and queried
- MinIO artifact is written and referenced from Postgres
- rerun proves idempotency
- stale-but-usable and stale-blocked drills are captured
- failure handler produces operator-visible evidence
- no 1Password GUI prompts occur
- frontend/backend read model can display the resulting status and evidence

## Implementation Strategy

### Phase 0: Spec Closure

Deliverables:

- final canonical document key spec
- command envelope and status vocabulary
- write atomicity/idempotency spec
- concurrency/admission-control spec
- frontend read model draft

Validation:

- architecture review accepts the boundary and spec locks
- tests can be written from the spec without hidden assumptions

### Phase 1: Domain Package Skeleton

Deliverables:

- `affordabot_pipeline` or equivalent backend package
- command interfaces and typed request/response models
- storage ports for Postgres, pgvector, and MinIO
- deterministic in-memory adapters for tests
- scenario tests ported from the bakeoff

Validation:

- happy path
- rerun idempotency
- stale-but-usable
- stale-blocked
- source/reader/storage failures
- crash-mid-step partial-state drills

### Phase 2: Real Storage Adapters

Deliverables:

- Postgres schema/migration prototype
- pgvector chunk index integration
- MinIO artifact adapter
- transaction/idempotency behavior around all writes

Validation:

- local/CI integration tests with real Postgres-compatible DB if available
- MinIO/object-store contract tests
- partial-write recovery tests

### Phase 3: Windmill Flow Integration

Deliverables:

- Windmill scripts import/call the domain package
- flow export with native retries, branch conditions, failure handler, and per-jurisdiction loop shape
- `dx-review`/consultant review of flow shape

Validation:

- local flow-shaped test
- live Windmill run evidence
- rerun evidence
- failure handler evidence

### Phase 4: Backend Read Models And Frontend Display

Deliverables:

- backend status/evidence/read APIs
- frontend jurisdiction pipeline status view
- evidence/provenance display
- operator action entry points for rerun/review

Validation:

- frontend reads only backend APIs
- no direct Windmill/MinIO/pgvector frontend dependency
- manual browser or Playwright evidence for key pages

### Phase 5: Rollout And Parity Window

Deliverables:

- run new Windmill pipeline beside existing cron path where applicable
- compare outputs for a fixed jurisdiction/source-family set
- alerting and rollback runbook

Validation:

- parity window has explicit duration and pass/fail metrics
- rollback path is one command/config switch

## Beads Structure To Reconcile

Beads mutations were avoided during this session because local Beads was under infra repair. When Beads is healthy, reconcile this plan as:

```text
Epic: Lock and implement affordabot Windmill/domain-boundary pipeline

Children:
1. Spec locks: identity, atomicity, concurrency, contracts, frontend read model
2. Domain package skeleton with deterministic adapters
3. Real Postgres/pgvector/MinIO adapters
4. Windmill live-flow integration and validation
5. Backend read models and frontend display
6. Rollout/parity/rollback

Blocking edges:
1 blocks 2
2 blocks 3 and 4
3 blocks 4
4 blocks 5
5 blocks 6
```

Recommended first executable task:

```text
Write the spec-lock document for canonical identity, write atomicity, concurrency, command envelope, and frontend read model.
```

This task is first because it prevents the implementation from baking in ambiguous product identity or unsafe retry semantics.

## Consequences

Positive:

- avoids a split-brain backend across Windmill and affordabot
- keeps product moat logic testable in normal code
- uses Windmill for the workflow features it is good at
- gives frontend stable product read models
- allows future HTTP extraction without changing domain concepts

Costs:

- Windmill scripts are thinner but depend on affordabot package deployment hygiene
- domain package needs careful dependency management in Windmill workers
- live validation remains mandatory because local POC evidence does not prove Windmill runtime semantics

Rejected alternatives:

- **Windmill direct storage as product backend**: rejected because Path A recreated product logic inside scripts and would scatter invariants as the DAG grows.
- **Backend-only cron pipeline**: rejected because it underuses Windmill for retries, branches, operator controls, and run history.
- **Frontend reading storage/Windmill directly**: rejected because it leaks implementation details and bypasses product semantics.
