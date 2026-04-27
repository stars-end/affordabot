# Windmill & OSS Data-Quality Audit for Data-Moat Cycle Review

**Date**: 2026-04-26  
**Epic**: `bd-n6h1c`  
**Subtask**: `bd-n6h1c.8`  
**Reviewer**: opencode (qa_pass)  
**PR URLs for context**: [#440](https://github.com/stars-end/affordabot/pull/440), [#441](https://github.com/stars-end/affordabot/pull/441)

---

## Executive Summary

Affordabot is **not** severely underusing Windmill first-party capabilities — the current architecture makes a deliberate and defensible choice to keep product truth in affordabot code while Windmill owns orchestration and observability. However, there are **three low-effort, high-return gaps** worth acting on before implementation of the `bd-n6h1c` glassbox epic:

1. **Windmill Labels are unused but free**: Affordabot flows, scripts, schedules, and resources have zero labels today. Adding labels like `app:affordabot`, `moat:structured`, `moat:scraped`, `reviewed`, `blocked` would give HITL reviewers a one-click filter in the Windmill Runs page without any affordabot code changes.

2. **Windmill Runs page + label filtering could replace bespoke pipeline-status frontend for cycle review**: For reviewing 10-20 structured/unstructured improvement cycles, the Windmill Runs page with label filtering is a fully-built, zero-maintenance alternative to building custom admin dashboards. The current `PipelineStatusPanel` duplicates functionality Windmill already provides natively.

3. **No OSS data-quality tool is a net win at this scale**: For a tiny fintech startup reviewing 10-20 cycles, adding Great Expectations (52MB npm install, ~50-line expectation suites per source), Soda (Soda Cloud pricing starts at $500/mo), or OpenMetadata (requires Kafka + Elasticsearch) would **increase cognitive load more than it reduces it**. The existing affordabot `glass_box.py`, `AlertingService`, and substrate inspection reports already provide 80% of what these tools offer for the specific domain.

**Primary recommendation**: Invest in Windmill Labels + Runs filtering as the primary HITL review surface. Defer all OSS data-quality tools. Keep affordabot glassbox/admin for product-truth-specific views that Windmill cannot provide (canonical document identity, revision chains, economic handoff readiness).

---

## Findings

### Finding 1: Windmill Labels Are Available But Untapped

**Severity**: Low | **Risk**: Missed opportunity for zero-code HITL filtering

Windmill v1.682+ supports free-form labels on scripts, flows, apps, resources, variables, schedules, and triggers. Labels propagate to jobs at runtime. The Runs page supports label filtering with wildcards and comma-separated multi-label filtering.

From the committed workspace assets (`ops/windmill/f/affordabot/`), **zero labels** are defined on any item. From the live workspace (as of `ops/windmill/README.md`), the same is true — no labels appear in CLI commands like `job list` or `flow list`.

**What this costs to fix**: ~10 minutes of label assignment per workspace item, plus an optional batch CLI operation. No code changes.

**Evidence**:
- `ops/windmill/README.md:197-219` shows live CLI read patterns — labels are absent from output
- `ops/windmill/f/affordabot/pipeline_daily_refresh_domain_boundary__flow/flow.yaml` — no `labels` field
- `ops/windmill/f/affordabot/manual_substrate_expansion__flow/flow.yaml` — no labels field
- Windmill docs (windmill.dev/docs/core_concepts/labels) confirm label propagation to jobs

### Finding 2: Windmill Runs Page Partially Duplicates Affordabot PipelineStatusPanel

**Severity**: Medium | **Risk**: Maintenance burden for duplicated observability

The current `PipelineStatusPanel.tsx` frontend component (252 lines) displays:
- Jurisdiction/source-family pipeline freshness status
- Freshness policy (fresh hours, stale usable ceiling, fail-closed ceiling)
- Counts (search, raw scrapes, artifacts, chunks, analyses)
- Analysis readiness status
- Alerts
- Windmill run URL link

Windmill's Runs page natively provides:
- Per-job execution logs with full stdout/stderr, inputs, outputs, duration, status
- Time-series aggregation with success/failure dots
- Filtering by path, user, folder, worker, labels, concurrency key
- Flow execution visualization per step with retry/error drill-down
- Scheduled run previews
- Batch re-run capability with input override

**What Windmill cannot provide** that `PipelineStatusPanel` provides:
- Affordabot-specific freshness semantics (`fresh_hours`, `stale_usable_ceiling_hours`, `fail_closed_ceiling_hours`)
- Analysis sufficiency state (`qualitative_only`, `quantitative_ready`, `insufficient_evidence`)
- Product-truth counts derived from affordabot Postgres rows (search_results, chunks, analyses)
- Jurisdiction names (Windmill only knows run inputs, not product-level jurisdiction)

**Recommendation**: The `PipelineStatusPanel` should **embed link to Windmill run** and **augment** it with product-truth fields. It should not try to be a second run viewer. The existing code at `PipelineStatusPanel.tsx:199-216` already does this correctly — it links to Windmill run URL and affordabot audit trace. This pattern should be preserved and the panel should be slimmed to avoid duplicating what Windmill already displays.

### Finding 3: Windmill Assets Tracking Would Help But Requires Enterprise

**Severity**: Low | **Risk**: Dependency on Enterprise tier

Windmill's Assets feature tracks data flows (S3 objects, resources, volumes) with static code analysis and runtime detection. It provides column-level lineage for DuckDB and Data Tables. This would be useful for tracking which flows read/write to MinIO and Postgres resources.

However:
- Column-level tracking works for DuckDB/Data Tables only, not Postgres (which is Affordabot's canonical store)
- The feature requires setting up `res://` and `s3://` URI references in code
- Postgres is accessed via `PostgresDB` class, not through Windmill resources, so Windmill cannot introspect it

**Verdict**: Not worth pursuing for this use case. Affordabot's product-side lineage (canonical_document_key -> raw_scrape_id -> chunk_id -> analysis_id) is richer than what Windmill Assets would provide.

### Finding 4: Windmill Audit Logs Are Enterprise-Only

**Severity**: Informational | **Risk**: None (Enterprise not needed for this use case)

Windmill audit logs (Enterprise tier only) capture deployment, permission, resource modification, and login events. They do not capture job-level execution details beyond the Runs page. Since affordabot uses the shared dev instance (`server-dev-8d5b.up.railway.app`), Enterprise features are not available.

**Verdict**: Not a gap. Affordabot's own `pipeline_runs` table and `GlassBoxService` already provide equivalent or better auditability for the data moat workflow.

### Finding 5: Windmill Apps Could Host a Windmill-Native Review Dashboard

**Severity**: Low | **Risk**: Added maintenance surface

Windmill supports building full-code apps (React/Svelte) and low-code apps that run within Windmill itself, connected to backend runnables. In theory, a Windmill app could display the data-moat review grid, pulling from affordabot backend APIs.

**Why not**: This would create a second frontend surface. The existing affordabot admin dashboard (`/admin`) already has a working admin auth surface (Clerk), component library (shadcn), and established patterns (SubstrateExplorer, PipelineStatusPanel). Adding a Windmill app means maintaining a second auth, second deployment, and second UI framework.

**Verdict**: Defer. Keep the admin review surface in the affordabot frontend. Windmill's native UIs (Runs, Flows, Scripts) should be linked from affordabot, not duplicated.

### Finding 6: Windmill Data Tables Are Irrelevant for This Use Case

**Severity**: N/A | **Risk**: None

Windmill Data Tables are a persistent key-value/document store within Windmill workspaces. They are not a replacement for affordabot's Postgres schema (raw_scrapes, document_chunks, pipeline_runs, legislation). Product truth must remain in Postgres.

---

## Current Usage Inventory

### Committed Windmill Assets (from `ops/windmill/`)

| Asset | Type | Purpose | Labels | Schedule |
|---|---|---|---|---|
| `trigger_cron_job.py` | Script | Shared HTTP trigger wrapper for cron endpoints | None | N/A |
| `discovery_run__flow/` | Flow + Schedule | Discovery cron job (HTTP to `/cron/discovery`) | None | `0 5 * * *` |
| `daily_scrape__flow/` | Flow + Schedule | Daily scrape cron job (HTTP to `/cron/daily-scrape`) | None | `0 6 * * *` |
| `rag_spiders__flow/` | Flow + Schedule | RAG spiders cron job (HTTP to `/cron/rag-spiders`) | None | `0 7 * * *` |
| `universal_harvester__flow/` | Flow + Schedule | Universal harvester cron job (HTTP to `/cron/universal-harvester`) | None | `0 8 * * *` |
| `manual_substrate_expansion__flow/` | Flow (manual) | Manual substrate expansion trigger | None | Unscheduled |
| `pipeline_daily_refresh_domain_boundary__flow/` | Flow (POC) | Domain-boundary pipeline (stubs only) | None | Unscheduled |
| `pipeline_daily_refresh_domain_boundary.py` | Script (POC) | Domain-boundary pipeline script | None | N/A |

### Affordabot Admin Surfaces Mapping

| Affordabot Component | What It Provides | Windmill Equivalent |
|---|---|---|
| `PipelineStatusPanel.tsx` | Jurisdiction pipeline freshness + counts + alerts + Windmill link | Runs page + label filtering |
| `SubstrateExplorer.tsx` | Run-level raw scrape rows, failure buckets, row details | Flow execution details (step-level), but not per-row substrate data |
| `GlassBoxService` (`glass_box.py`) | Pipeline run heads, steps, mechanism traces | Flow step execution with input/output per step |
| `AlertingService` | Derived alerts from pipeline_runs result data | Windmill Critical Alerts (Enterprise) or Slack webhook |
| `admin.py` (`/admin/*`) | Full admin API for jurisdictions, scrapes, pipeline status, document health | Windmill REST API for jobs/flows/scripts/schedules |

### What Is a Stub vs. Real

| Component | Status | Evidence |
|---|---|---|
| `pipeline_daily_refresh_domain_boundary__flow` | **Stub/skeleton-backend only** | `ops/windmill/README.md:50-53`: "this flow shape calls coarse domain-command stubs only" |
| Domain commands (`search_materialize`, etc.) | **Skeleton in repo, not live** | `backend/services/pipeline/domain/commands.py` exists but uses in-memory adapters; `command_client` defaults to `stub` in the flow |
| `manual_substrate_expansion` | **Skeleton response** | `ops/windmill/README.md:146-149`: "Current backend behavior is a truthful skeleton response plus an immediate inspection artifact" |
| Live cron flows (discovery, daily_scrape, etc.) | **Live, auth-gated, HTTP-backed** | Confirmed by `admin.py` cron endpoints, `trigger_cron_job.py`, Windmill contract tests |

---

## Windmill Native Capability Fit Matrix

| Capability | Available in Dev Tier | Currently Used | Should Adopt? | Notes |
|---|---|---|---|---|
| **Labels** (flow/script/schedule/resource) | Yes (all tiers) | No | **Adopt (P0)** | Zero-code, ~10 min to add. Enables one-click HITL filtering. |
| **Runs page filtering by label** | Yes (all tiers) | No | **Adopt (P0)** | HITL can filter `moat:structured`, `moat:scraped`, `blocked`, `reviewed`. |
| **Runs page (general)** | Yes (all tiers) | Partially | **Already adequate** | Already linked from `PipelineStatusPanel`. |
| **Flow execution per-step detail** | Yes (all tiers) | Implicitly | **Already adequate** | Flow run detail shows per-step logs, IO, duration, status. |
| **Schedules** | Yes (all tiers) | Yes (4 flows) | **Already adequate** | `0 5/6/7/8 * * *` for the 4 cron flows. |
| **Retries (flow-level)** | Yes (all tiers) | Yes (2 flows) | **Already adequate** | `manual_substrate_expansion` has `attempts: 2`; `pipeline_daily_refresh` has `attempts: 2` per scope. |
| **Failure handlers** | Yes (all tiers) | Yes (1 flow) | **Already adequate** | `pipeline_daily_refresh_domain_boundary__flow` has `failure_module`. |
| **Branching (branchone)** | Yes (all tiers) | Yes (1 flow) | **Already adequate** | `pipeline_daily_refresh` uses `branchone` for outcome review. |
| **For-loop (parallel)** | Yes (all tiers) | Yes (1 flow) | **Already adequate** | `pipeline_daily_refresh` uses `forloopflow` with parallelism. |
| **Assets (data flow tracking)** | Yes (all tiers) | No | **Defer** | Only tracks S3/Resources/Volumes, not Postgres. Adds maintenance without postgres visibility. |
| **Resources** | Yes (all tiers) | Implicitly (vars) | **Already adequate** | Backend URL, CRON_SECRET, SLACK_WEBHOOK_URL via workspace vars. |
| **Variables & Secrets** | Yes (all tiers) | Yes (3 vars) | **Already adequate** | `BACKEND_PUBLIC_URL`, `CRON_SECRET`, `SLACK_WEBHOOK_URL`. |
| **Apps (full-code or low-code)** | Yes (Enterprise for full-code) | No | **Reject** | Would create a second frontend surface. Keep in affordabot admin. |
| **Data Tables** | Yes (all tiers) | No | **Reject** | Not a replacement for Postgres product truth. |
| **Object Storage (S3 workspace)** | Yes (all tiers) | No (MinIO is separate) | **Defer** | Affordabot uses MinIO, not Windmill S3. No benefit to switching. |
| **Audit Logs** | Enterprise only | No | **Reject** | Affordabot `pipeline_runs` table provides equivalent product-level audit. |
| **Critical Alerts** | Enterprise only | No | **Defer** | Slack webhook from `trigger_cron_job.py` already covers alerting. |
| **Webhooks (inbound)** | Yes (all tiers) | No | **Not needed** | Windmill calls affordabot over HTTP, not the other way. |
| **MCP** | Yes (all tiers) | No | **Not needed** | Not relevant to data-moat review. |

---

## OSS Data-Quality Tool Fit Matrix

### Evaluation Criteria

- **Setup cost**: Time to install, configure, and integrate with existing affordabot stack (Postgres + Python/FastAPI + Railway)
- **Local dev friction**: Does the tool require Docker, separate services, or heavy dependencies?
- **CI fit**: Can it run in GitHub Actions or a Railway build step without complex infrastructure?
- **Structured data fit**: How well does it handle Postgres-based structured sources (bill text, legislation, meeting minutes)?
- **Scraped/unstructured data fit**: Can it validate scraped HTML/PDF content quality?
- **Maintenance burden**: Ongoing cost to update expectations, manage configurations, debug failures.
- **Overlap with affordabot**: How much of what it does is already implemented in affordabot?

### Tool Comparison

| Tool | Setup Cost | Local Dev Friction | CI Fit | Structured Fit | Unstructured Fit | Maintenance | Overlap | Verdict |
|---|---|---|---|---|---|---|---|---|
| **Great Expectations (GX)** | Medium (pip install + CLI + configure) | High (needs DataContext, suite config, checkpoint YAML) | Medium (needs Postgres in CI) | **Good** (column-level expectations on Postgres) | **Poor** (designed for tabular data, not document content) | High (~50-line expectation suites per source; versioned YAML files) | High (glass_box, AlertingService cover similar alert patterns) | **Reject** |
| **Soda Core** | Low (pip install soda-core-postgres) | Low (YAML-based checks, no CLI-heavy setup) | Good (simple `soda scan` in CI) | **Good** (SQL-based checks, familiar to team) | **Poor** (no document-level checks) | Medium (YAML suites, but simpler than GX) | High (same alert overlap) | **Reject** |
| **Pandera** | Low (pip install pandera) | Very Low (decorator-based on DataFrames) | Good (runs in pytest) | **Good** (DataFrame schema validation) | **Poor** (DataFrame-only) | Very Low (decorators inline with code) | High (affordabot doesn't use DataFrames as primary pipeline surface) | **Reject** (wrong paradigm) |
| **OpenLineage + Marquez** | Very High (needs Marquez server + DB + lineage config) | Very High (Docker + Postgres + web UI) | Very High | **Good** (API-based lineage tracking) | **Poor** (no content-level checks) | Very High (infrastructure, API integration, debugging) | Medium (affordabot already has revision chain lineage) | **Reject** |
| **OpenMetadata / DataHub** | Very High (requires Kafka, Elasticsearch, MySQL/Postgres) | Extreme (complex stack, needs multiple services) | Extreme | **Excellent** (full data catalog + lineage + quality) | **Poor** (designed for data warehouse tables) | Extreme (requires dedicated infra person) | Low (affordabot has no data catalog) | **Reject** (scale mismatch) |
| **dbt tests** | High (needs dbt project, profiles, models) | High (separate toolchain from FastAPI) | Medium | **Good** (SQL-based tests) | **Poor** (no document testing) | High (separate project to maintain) | Medium | **Reject** (not a dbt shop) |
| **Evidently AI** | Low (pip install) | Low | Good | **Good** (data drift, distribution checks) | **Poor** (no document checks) | Low-Medium | Medium (affordabot has freshness gating already) | **Reject** (focused on ML model monitoring) |

### Why No OSS Tool Is a Net Win

1. **Scale mismatch**: Every listed tool is designed for teams managing 100+ tables/pipelines with dedicated data engineers. Affordabot is reviewing 10-20 cycles with one founder-operator.

2. **Document-centric domain**: GX, Soda, Pandera, and dbt tests all assume tabular data with numeric/string columns. Affordabot's domain is document-centric — raw HTML/PDF text, chunk quality, extraction fidelity, revision chains. These tools add no value for document-level quality.

3. **Existing overlap**: Affordabot already has:
   - `FreshnessPolicy` (in `admin.py:22-43`, mirroring `docs/specs/...spec-lock.md:331-338`)
   - `AlertingService` (in `admin.py:907-931`)
   - `GlassBoxService.get_pipeline_steps()` (in `glass_box.py:181-226`)
   - `build_substrate_inspection_report()` (in `admin.py:11-13`)
   - `validate_golden_bill_corpus_manifest.py` (committed verification script)
   - `evaluate_promotion_candidates.py` (substrate quality evaluation)

4. **Cognitive load budget**: The founder has explicitly asked for the "lowest-cognitive-load" architecture. Adding any OSS data-quality tool means:
   - Learning its DSL (GX expectations, SodaCL, Pandera schemas)
   - Maintaining configuration files alongside affordabot code
   - Debugging tool failures before debugging pipeline failures
   - Managing tool version upgrades and dependency conflicts

**Pandera is the closest to being useful** (lightest weight, lowest friction), but only if affordabot were to adopt DataFrame-based processing. It currently uses raw SQL + service classes, not pandas/polars DataFrames.

---

## Recommended Ownership Boundaries

```
┌─────────────────────────────────────────────────────────────┐
│                      WINDMILL (owns)                        │
│                                                             │
│  - Schedules: when discovery/scrape/ingest run              │
│  - Native retries with backoff                              │
│  - Flow branching (freshness gate outcome → skip/fail)     │
│  - Parallel fanout (multiple jurisdictions concurrently)    │
│  - Failure handlers                                          │
│  - Run history and per-step execution details               │
│  - Labels for HITL filtering (NEW: adopt)                   │
│  - Slack webhook notifications                              │
│  - Concurrency limits and admission control                 │
│                                                             │
│  Windmill MUST NOT own:                                     │
│  - Canonical document identity                              │
│  - Product Postgres/pgvector/MinIO writes                   │
│  - Freshness semantics                                      │
│  - Analysis sufficiency gates                               │
│  - Frontend read models                                     │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                    AFFORDABOT (owns)                        │
│                                                             │
│  - Canonical document key generation (v1, v2)              │
│  - Revision chain management                                │
│  - Product writes (raw_scrapes, document_chunks,            │
│    pipeline_runs, legislation)                              │
│  - MinIO artifact key policy                                │
│  - pgvector metadata policy                                 │
│  - Freshness policy and fail-closed gates                   │
│  - Analysis sufficiency gates                               │
│  - GlassBoxService (pipeline run/steps/alerts)              │
│  - AlertingService (derived product alerts)                 │
│  - Backend admin read APIs                                  │
│  - Admin frontend (PipelineStatusPanel, SubstrateExplorer)  │
│  - Data-moat review grid (bd-n6h1c.3)                       │
│  - Domain commands (search_materialize, freshness_gate,     │
│    read_fetch, index, analyze, summarize_run)               │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                OPTIONAL OSS DQ (none adopted)               │
│                                                             │
│  No OSS data-quality tool is recommended at this scale.     │
│  The existing affordabot glassbox/admin stack covers        │
│  80%+ of what these tools offer for the specific domain.    │
│                                                             │
│  If scale ever justifies it:                                │
│  - Pandera for DataFrame schema validation (lightest)       │
│  - Soda Core for SQL-based freshness checks (easiest CI fit)│
│  - Great Expectations if a dedicated data engineer joins    │
└─────────────────────────────────────────────────────────────┘
```

---

## Proposed Changes to Beads Epic/Tasks

### Modify `bd-n6h1c` (epic)

**Current scope**: Wire structured and scraped data-moat progress into admin/glassbox workflow.

**Recommended addition**: Add a subtask for Windmill labeling strategy and Runs-page HITL workflow documentation. The HITL review surface should default to Windmill Runs (label-filtered) + affordabot admin for product-truth drill-downs.

### New Subtasks Recommended

| Beads ID | Title | Priority | Description |
|---|---|---|---|
| `bd-n6h1c.9` | **Apply Windmill labels to all flows/scripts/schedules** | P0 | Add labels `app:affordabot`, `moat:structured`, `moat:scraped` to existing flows and scripts. Add context labels like `jd:SanJose`, `sf:meeting_minutes`. Document the label taxonomy in `ops/windmill/README.md`. |
| `bd-n6h1c.10` | **Document Windmill Runs HITL review workflow** | P1 | Add a `docs/reviews/windmill-hitl-review-workflow.md` describing how to: (1) open Windmill Runs page, (2) filter by `moat:structured` or `moat:scraped`, (3) drill into flow executions, (4) link to affordabot admin for product-truth views. This should be the primary review path, not the fallback. |
| `bd-n6h1c.11` | **Slim PipelineStatusPanel to Windmill-augmenting display** | P2 | Replace the counts/status duplication in `PipelineStatusPanel.tsx` with a prominent Windmill Runs link + affordabot-specific fields (freshness policy, analysis sufficiency). The panel should answer "what does affordabot know that Windmill doesn't?" not "what did the pipeline do?" |

### Do NOT Add

- **Do not add** OSS data-quality tool evaluation subtasks. This audit's recommendation is "reject" for all evaluated tools at current scale.
- **Do not add** Windmill App development subtasks. Keep the review UI in the existing affordabot admin dashboard.

---

## First Three Implementation Steps

1. **Apply Windmill labels** (30 min, no code change)
   - Assign `app:affordabot` label to all flows and scripts via Windmill CLI or UI
   - Assign `moat:structured` to discovery and daily_scrape flows
   - Assign `moat:scraped` to rag_spiders and universal_harvester flows
   - Assign `review:blocked`, `review:needs_hitl` as operational labels for jobs needing attention
   - Verify label propagation by triggering a manual run and checking the Runs page

2. **Document the HITL review workflow** (1 hour, docs-only)
   - Write `docs/reviews/windmill-hitl-review-workflow.md`
   - Include screenshots of Windmill Runs page with label filtering
   - Map each review question to the right tool (Windmill for run status, affordabot admin for product truth)
   - Define a checklist: "For each cycle, check Windmill Runs → if blocked/alerted, drill into affordabot admin for product truth → update labels to `reviewed` or `followup`"

3. **Slim PipelineStatusPanel** (2 hours, frontend change)
   - Remove duplicated counts/status that Windmill already shows
   - Keep affordabot-specific fields: freshness policy, analysis sufficiency state, economic handoff readiness
   - Make the Windmill Runs link more prominent (currently at `PipelineStatusPanel.tsx:199-208`)
   - Add a link to the doc from step 2

---

## Sources / Citations

### Repo Sources (affordabot master)

- `docs/CRON_ARCHITECTURE.md` (132 lines) — Windmill as scheduler of record, auth contract, job inventory
- `docs/specs/2026-04-13-windmill-domain-brownfield-spec-lock.md` (1005 lines) — Complete Windmill/Affordabot boundary spec including domain commands, identity, atomicity, storage contract, implementation phases
- `ops/windmill/README.md` (351 lines) — Live Windmill CLI patterns, shared-instance model, manual substrate expansion contract, deployment docs
- `ops/windmill/f/affordabot/pipeline_daily_refresh_domain_boundary__flow/flow.yaml` (297 lines) — Domain-boundary flow with matrix fanout, retries, branchone, failure handler, forloopflow
- `ops/windmill/f/affordabot/manual_substrate_expansion__flow/flow.yaml` (102 lines) — Manual substrate expansion flow
- `ops/windmill/f/affordabot/trigger_cron_job.py` (191 lines) — Shared HTTP trigger wrapper with Slack webhook alerting
- `backend/routers/admin.py` (1395+ lines) — Full admin API with GlassBox, substrate, pipeline, alerts, document health endpoints
- `backend/services/glass_box.py` (553 lines) — Pipeline run/steps/traces/alerts service
- `frontend/src/services/adminService.ts` (350 lines) — Admin API client with PipelineJurisdictionStatus, SubstrateExplorer interfaces
- `frontend/src/components/admin/SubstrateExplorer.tsx` (677 lines) — Run-first substrate debugging UI
- `frontend/src/components/admin/PipelineStatusPanel.tsx` (252 lines) — Pipeline status panel with freshness and counts display
- `docs/poc/round1-search-benchmark/README.md` (86 lines) — Round 1 search benchmark with SearXNG

### PR Context

- PR #440 (`8b7d8d1`) — Structured proof runtime overlay for cycle 53
- PR #441 (`8ae7f3b`) — Round 1 search benchmark (SearXNG vs baseline)

### Windmill Official Documentation (windmill.dev)

- `windmill.dev/docs/core_concepts` — Complete core concepts index
- `windmill.dev/docs/core_concepts/labels` — Labels on scripts, flows, apps, resources, schedules, triggers; propagation to jobs
- `windmill.dev/docs/core_concepts/assets` — Data flow tracking, static/runtime asset detection, column-level lineage
- `windmill.dev/platform/observability` — Runs page, flow execution, time-series, filtering, OpenTelemetry
- `windmill.dev/docs/core_concepts/monitor_past_and_future_runs` — Jobs runs page, filtering, labels, batch actions
- `windmill.dev/docs/core_concepts/audit_logs` — Audit logs (Enterprise only), retention policies
- `windmill.dev/docs/core_concepts/object_storage_in_windmill` — Workspace S3, secondary storage, S3 proxy

### OSS Data Quality Research

- "7 Open-Source Data Quality Tools to Use in 2025" — dqops.com
- "Great Expectations vs Soda vs OpenMetadata vs Pandera comparison" — multiple sources (Atlan, DataExpert.io, Medium, Substack)
- All evaluated tools confirmed to require significant infrastructure (GX: DataContext + checkpoint YAML; Soda: Soda Cloud pricing; OpenMetadata: Kafka + Elasticsearch; OpenLineage: Marquez server; Pandera: DataFrame paradigm)
