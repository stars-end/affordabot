# Windmill & OSS Data-Quality / Data-Moat Audit

**Date:** 2026-04-27
**Reviewer role:** Senior data-platform / workflow-orchestration reviewer
**Epic:** `bd-n6h1c`
**Subtask:** `bd-n6h1c.8`
**Repo:** `stars-end/affordabot` (master @ `b850bd9`)
**PR context:** #440 (structured proof, `8b7d8d1`), #441 (search benchmark, `8ae7f3b`)

---

## Executive Summary

Affordabot's Windmill integration is **correctly scoped as an orchestration layer** but
**significantly underuses Windmill's first-party operational surfaces**. The current
architecture treats Windmill as a pure scheduler-of-record with HTTP trigger wrappers,
while building parallel observability (GlassBox, PipelineStatusPanel, admin read models)
in custom backend code. Several Windmill-native features — job labels, Flow Status
components, Windmill Apps, workspace S3/assets, audit logs — could reduce custom
admin-panel development for the operator-facing surfaces without compromising the correct
decision to keep product truth in Affordabot.

For data quality, **no OSS DQ framework is ready to adopt today**. The data moat's
quality requirements are overwhelmingly product-specific rubric logic (sufficiency gates,
freshness policies, evidence provenance chains) that commodity DQ tools cannot express.
The small fraction of generic checks (schema validation, null/duplicate detection on
ingestion) is better served by lightweight Pandera guards or inline pytest assertions
than by the infrastructure overhead of Great Expectations or Soda.

**Severity summary:**

| Finding | Severity | Risk |
|---------|----------|------|
| Windmill labels/assets not used | Medium | Wasted operator tooling; fragile custom run-matching |
| Windmill Apps/Flow Status not explored for ops view | Medium | Duplicated effort building PipelineStatusPanel |
| No Windmill→admin deep-link integration | Low | Operator context-switching friction |
| Domain-boundary flow still stub-backed | Info | Expected; tracked in `bd-9qjof` |
| OSS DQ tools not adopted | Low | Correct for now; revisit at 30+ source families |
| No lineage/catalog tooling | Low | Premature at current scale |

---

## 1. Current Usage Inventory

### 1.1 Committed Windmill Assets

| Asset | Type | Status | Notes |
|-------|------|--------|-------|
| `trigger_cron_job.py` | Shared script | **Active** | HTTP wrapper for all cron endpoints |
| `discovery_run__flow/flow.yaml` | Flow | **Scheduled** | `0 5 * * *` UTC |
| `daily_scrape__flow/flow.yaml` | Flow | **Scheduled** | `0 6 * * *` UTC |
| `rag_spiders__flow/flow.yaml` | Flow | **Scheduled** | `0 7 * * *` UTC |
| `universal_harvester__flow/flow.yaml` | Flow | **Scheduled** | `0 8 * * *` UTC |
| `manual_substrate_expansion__flow/flow.yaml` | Flow | **Manual trigger** | On-demand substrate capture |
| `pipeline_daily_refresh_domain_boundary.py` | Script | **Unscheduled** | Path B domain-boundary stub |
| `pipeline_daily_refresh_domain_boundary__flow/flow.yaml` | Flow | **Unscheduled** | Path B orchestration skeleton |
| `pipeline_daily_refresh_direct_storage.py` | Script | **Unscheduled** | Direct-storage path (deprecated) |
| `pipeline_daily_refresh_direct_storage__flow/flow.yaml` | Flow | **Unscheduled** | Direct-storage flow (deprecated) |
| `wmill.yaml` | Config | Active | Workspace sync config |

### 1.2 Windmill Feature Utilization Matrix

| Windmill Feature | Available | Currently Used | Notes |
|-----------------|-----------|---------------|-------|
| Schedules | ✅ | ✅ | 4 scheduled cron flows |
| Manual triggers | ✅ | ✅ | Substrate expansion + domain-boundary POC |
| Flow DAG (branch/loop/retry) | ✅ | ✅ | Domain-boundary flow uses `forloopflow`, `branchone`, retry |
| Concurrency limits | ✅ | ✅ | `concurrency.limit: 2` on domain-boundary flow |
| Failure handlers | ✅ | ✅ | Domain-boundary flow has `failure_module` |
| Job labels | ✅ | ❌ | Not used on any flow or script |
| Flow labels | ✅ | ❌ | Not used |
| Dynamic labels (`wm_labels`) | ✅ | ❌ | Not returned from `trigger_cron_job.py` |
| Assets (S3 ref visualization) | ✅ | ❌ | MinIO refs not visible in Windmill |
| Windmill Apps | ✅ | ❌ | No operator apps built |
| Flow Status component | ✅ | ❌ | Not used; custom PipelineStatusPanel instead |
| Workspace S3/Object Storage | ✅ | ❌ | MinIO managed by Affordabot directly |
| Audit logs | ✅ | ❌ | Not consumed |
| OpenTelemetry integration | ✅ | ❌ | Not configured |
| Webhook triggers | ✅ | ❌ | All triggers are schedule or manual |
| Approval steps | ✅ | ❌ | No human-in-the-loop gates |

### 1.3 Domain-Boundary Flow Status

The `pipeline_daily_refresh_domain_boundary__flow` is **correctly shaped** with:
- Matrix fanout (`build_scope_matrix` → `forloopflow`)
- Per-scope pipeline execution with retries (2 attempts, exponential backoff)
- Outcome branching (blocked/failed vs successful summary)
- Failure handler module
- Flow-level concurrency limit (2)
- Schema-validated inputs (idempotency key, jurisdictions, source families)

**However, it remains stub-backed** (`command_client: stub` default). This is expected
and tracked in `bd-9qjof`. The backend endpoint mode (`command_client: backend_endpoint`)
is documented but gated on backend domain commands being ready.

### 1.4 Backend Observability Stack (Parallel to Windmill)

The backend has built significant custom observability that partially overlaps with what
Windmill provides natively:

| Backend Component | What It Does | Windmill Overlap |
|-------------------|-------------|-----------------|
| `GlassBoxService` | Pipeline run heads, steps, mechanism traces | Windmill run history, step logs |
| `PipelineStatusPanel` (frontend) | Jurisdiction status, freshness, counts | Windmill flow status, run dashboard |
| `SubstrateExplorer` (frontend) | Run list, detail, failure buckets, raw scrape viewer | Windmill run list + filtering |
| Admin pipeline endpoints | `/pipeline/jurisdictions/{id}/status`, `/runs/{id}`, `/runs/{id}/steps`, `/runs/{id}/evidence` | Windmill API |
| Pipeline run summaries in Postgres | `pipeline_runs`, `pipeline_steps` tables | Windmill job/run metadata |

**Key insight:** This overlap is **partially justified**. The backend read models serve
product-specific truth (freshness policy, evidence sufficiency, analysis status) that
Windmill cannot compute. But the *operational* surfaces (run list, step timing, failure
classification) are duplicated effort that Windmill handles natively.

---

## 2. Windmill Native Capability Fit Matrix

### 2.1 Can Windmill Satisfy These Glassbox/Admin Needs?

| Proposed Need | Windmill Can Satisfy? | Evidence | Recommendation |
|--------------|----------------------|----------|----------------|
| **Run history & filtering** | ✅ Yes | Native Runs dashboard with label/status/time filters | Use Windmill directly; link from admin panel |
| **Step-level execution logs** | ✅ Yes | Full stdout/stderr per step, typed I/O | Use Windmill directly for operator debugging |
| **Flow status visualization** | ✅ Yes | Flow Status component in Windmill Apps | Build a thin Windmill App or embed Flow Status |
| **Failure classification** | ⚠️ Partial | Windmill shows step errors; product-level retry_class requires Affordabot | Windmill shows ops failures; backend owns product failure taxonomy |
| **Freshness policy enforcement** | ❌ No | Product-specific business logic | Must remain in Affordabot |
| **Evidence sufficiency gates** | ❌ No | Product-specific rubric logic | Must remain in Affordabot |
| **Analysis status & provenance** | ❌ No | Product truth (LLM results, evidence chains) | Must remain in Affordabot |
| **Jurisdiction/source-family status** | ❌ No | Product-scoped aggregation over multiple runs | Must remain in Affordabot backend |
| **Canonical document identity** | ❌ No | Product-owned identity policy | Must remain in Affordabot |
| **Search result quality metrics** | ❌ No | Product benchmark data | Must remain in Affordabot |
| **Operator deep-links to flow runs** | ✅ Yes | `windmill_run_url` already in admin read model | Already partially implemented; expand |
| **Dynamic run labeling** | ✅ Yes | `wm_labels` in script return | Add to `trigger_cron_job.py` and domain-boundary script |
| **Asset lineage visualization** | ⚠️ Partial | Windmill Assets detect `s3://` refs in code | MinIO refs are in Affordabot code, not Windmill scripts; limited utility |
| **Alerting on run failures** | ✅ Yes | Slack webhook already implemented in trigger script; Windmill also supports native alerts | Already implemented; consider Windmill native alerts as backup |
| **Audit trail for operator actions** | ✅ Yes | Windmill audit logs track all mutations | Use Windmill audit logs for ops; keep Affordabot audit for product actions |

### 2.2 Recommended Windmill Adoption Items

| Action | Priority | Effort | Impact |
|--------|----------|--------|--------|
| **Add job labels** to `trigger_cron_job.py` returns (jurisdiction, source_family, run type) | High | 1-2h | Filterable run history without custom queries |
| **Add flow labels** to committed flow YAMLs (affordabot, cron, domain-boundary) | High | 30min | Instant workspace-level flow organization |
| **Return `wm_labels`** from domain-boundary script steps | Medium | 1h | Dynamic run-level labels visible in Windmill UI |
| **Build thin Windmill App** for operator run review | Medium | 4-8h | Replace need for much of SubstrateExplorer for ops use |
| **Embed Windmill deep-links** in admin panel more prominently | Low | 1h | Operator can jump to Windmill for step-level debug |
| **Explore Windmill workspace S3** for MinIO artifact browsing | Low | 2h investigation | May not be useful since MinIO is direct, not via Windmill |
| **Configure OpenTelemetry** for Windmill workers | Defer | 4h+ | Useful later at production scale |

---

## 3. OSS Data-Quality Tool Fit Matrix

### 3.1 Affordabot Data Quality Requirements

Before evaluating tools, the data quality requirements must be classified:

| Requirement Category | Examples | Generic DQ Tool? | Product-Specific? |
|---------------------|----------|-------------------|-------------------|
| **Schema validation** | Raw scrape has URL, content, metadata fields | ✅ Yes | No |
| **Null/empty detection** | Content not null/empty on ingestion | ✅ Yes | No |
| **Duplicate detection** | Same canonical_document_key + content_hash | ⚠️ Partial | Partially product-specific |
| **Freshness policy** | Source family staleness ceilings (24h/72h/168h) | ❌ No | Yes — product business logic |
| **Evidence sufficiency** | Min evidence count before analysis | ❌ No | Yes — product rubric |
| **Source trust scoring** | Official source detection, trust tier classification | ❌ No | Yes — product domain expertise |
| **Content quality** | Extractability, content class, OCR quality | ❌ No | Yes — product-specific classification |
| **Revision chain integrity** | Previous-scrape-id linkage, seen_count, last_seen_at | ❌ No | Yes — product identity model |
| **Chunk identity determinism** | Contract_version + canonical_key + content_hash + chunk_index | ❌ No | Yes — product identity model |
| **Search result quality** | Official source rate, useful URL yield, dedup rate | ❌ No | Yes — product benchmark |
| **LLM analysis provenance** | Claim-to-evidence linkage, sufficiency state | ❌ No | Yes — product truth |
| **Promotion state validity** | captured_candidate → durable_raw → promoted_substrate | ❌ No | Yes — product lifecycle |

**Conclusion: ~15-20% of checks are generic DQ; ~80-85% are product-specific rubric logic.**

### 3.2 Tool-by-Tool Assessment

#### Great Expectations (GX)

| Criterion | Assessment |
|-----------|-----------|
| **Fit for Affordabot** | Poor |
| **Setup overhead** | High — Data Context, Batch Requests, Expectation Suites |
| **Unstructured data** | Weak — designed for tabular/warehouse data |
| **CI integration** | Good — pytest plugin, CLI runner |
| **Scraped content validation** | Not designed for HTML/PDF/markdown quality scoring |
| **Team bandwidth** | Significant learning curve for 1-person team |
| **Verdict** | **Reject** — overhead disproportionate to the 15% of checks it could serve |

#### Soda (SodaCL)

| Criterion | Assessment |
|-----------|-----------|
| **Fit for Affordabot** | Marginal |
| **Setup overhead** | Low — YAML checks, quick start |
| **Unstructured data** | Weak — SQL/YAML first, no content quality scoring |
| **CI integration** | Good — CLI runner, CI-friendly |
| **Scraped content validation** | Cannot express content_class, trust_tier, or extractability rules |
| **Team bandwidth** | Low learning curve but still a new dependency |
| **Verdict** | **Defer** — potentially useful at 30+ source families for basic schema/freshness checks on Postgres tables; premature now |

#### Pandera

| Criterion | Assessment |
|-----------|-----------|
| **Fit for Affordabot** | Moderate for ingestion validation |
| **Setup overhead** | Very low — Python decorators, no infrastructure |
| **Unstructured data** | Applies to DataFrames from scrape results |
| **CI integration** | Excellent — inline pytest, zero infrastructure |
| **Scraped content validation** | Can validate DataFrame schemas; cannot express domain rubric |
| **Team bandwidth** | Minimal — "Pydantic for DataFrames" |
| **Verdict** | **Pilot** — useful as inline guard on ingestion DataFrames; can replace ad hoc null/schema checks with declarative schemas |

#### OpenLineage / Marquez

| Criterion | Assessment |
|-----------|-----------|
| **Fit for Affordabot** | Poor at current scale |
| **Setup overhead** | Medium — requires Marquez service, event emission |
| **Value at current scale** | Low — <10 pipeline steps, lineage is obvious from flow YAML |
| **Team bandwidth** | Moderate infra burden for minimal insight |
| **Verdict** | **Reject** — lineage is trivially visible in Windmill flow DAG and domain-boundary spec; revisit only if pipeline grows to 50+ steps across multiple flows |

#### OpenMetadata / DataHub

| Criterion | Assessment |
|-----------|-----------|
| **Fit for Affordabot** | Poor at current scale |
| **Setup overhead** | High (DataHub) / Medium (OpenMetadata) |
| **Value at current scale** | Very low — 4 tables, 1 MinIO bucket, 1 vector store |
| **Catalog need** | Nonexistent — entire data model fits in existing spec-lock doc |
| **Team bandwidth** | Unsustainable for 1-person ops |
| **Verdict** | **Reject** — data estate is too small; spec-lock document is the effective catalog |

#### dbt Tests

| Criterion | Assessment |
|-----------|-----------|
| **Fit for Affordabot** | Poor — no warehouse-centric pipeline |
| **Setup overhead** | Medium — requires dbt project structure, adapter |
| **Affordabot stack** | Python + Postgres + MinIO + pgvector; not warehouse-oriented |
| **Verdict** | **Reject** — Affordabot is not a warehouse pipeline; dbt tests require materialization context |

#### Evidently / whylogs

| Criterion | Assessment |
|-----------|-----------|
| **Fit for Affordabot** | Poor for current use case |
| **Primary design** | ML model monitoring, data drift detection |
| **Scraped content** | No built-in support for document quality scoring |
| **Verdict** | **Reject** — designed for ML feature monitoring, not document ingestion quality |

### 3.3 Summary Recommendation Matrix

| Tool | Verdict | When to Revisit |
|------|---------|-----------------|
| Great Expectations | **Reject** | If Affordabot becomes a multi-team platform with shared data contracts |
| Soda | **Defer** | At 30+ source families, if basic schema/freshness checks become repetitive |
| Pandera | **Pilot** | Now — inline ingestion DataFrame validation |
| OpenLineage/Marquez | **Reject** | At 50+ pipeline steps across multiple flows |
| OpenMetadata/DataHub | **Reject** | At 20+ data assets with multi-team discovery needs |
| dbt Tests | **Reject** | If warehouse replaces direct Postgres for analytics |
| Evidently/whylogs | **Reject** | If ML model drift monitoring becomes a need |

---

## 4. Recommended Ownership Boundaries

### 4.1 Canonical Ownership Model

```
┌─────────────────────────────────────────────────────┐
│                    WINDMILL OWNS                     │
│                                                     │
│  • Schedule execution (cron triggers)               │
│  • Manual/webhook trigger dispatch                  │
│  • Flow DAG: loop, branch, retry, failure handler   │
│  • Per-step retry policy and backoff                │
│  • Concurrency limits (flow-level and step-level)   │
│  • Run history, step logs, execution timing          │
│  • Job/flow labels for operator filtering           │
│  • Operator approval gates (future)                 │
│  • Workspace-level audit logs                       │
│  • Native alerting (backup to custom Slack)         │
│  • Optional: thin operator app for run review       │
│                                                     │
│  Windmill MUST NOT:                                 │
│  • Generate canonical document keys                 │
│  • Write to Postgres product tables                 │
│  • Write to MinIO with product key policies         │
│  • Write to pgvector with product metadata          │
│  • Evaluate freshness or evidence sufficiency       │
│  • Parse LLM response internals                     │
│  • Serve frontend read models                       │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│                  AFFORDABOT OWNS                     │
│                                                     │
│  • Domain command package (search_materialize,      │
│    freshness_gate, read_fetch, index, analyze,      │
│    summarize_run)                                   │
│  • Canonical document identity (v2 keys)            │
│  • Freshness policy (per-source-family ceilings)    │
│  • Evidence sufficiency gates                       │
│  • LLM analysis orchestration and provenance        │
│  • Product-state read models (pipeline status,      │
│    jurisdiction status, evidence views)              │
│  • Admin panel (SubstrateExplorer,                  │
│    PipelineStatusPanel)                             │
│  • MinIO artifact key policy                        │
│  • pgvector metadata policy                         │
│  • Data-moat quality gates (trust tier, content     │
│    class, promotion state, search quality metrics)  │
│  • Command idempotency and partial-write recovery   │
│  • Contract version enforcement                     │
│                                                     │
│  Frontend MUST NOT:                                 │
│  • Call Windmill API directly                       │
│  • Infer freshness from raw timestamps              │
│  • Construct MinIO keys                             │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│             OPTIONAL OSS DQ (Future)                 │
│                                                     │
│  • Pandera: inline DataFrame schema guards on       │
│    ingestion input/output (pilot now)               │
│  • Soda: basic Postgres table health checks if      │
│    source families grow past 30 (defer)             │
│                                                     │
│  OSS DQ MUST NOT:                                   │
│  • Replace product-specific rubric logic            │
│  • Add infrastructure dependencies (services,      │
│    databases) beyond pip packages                   │
│  • Require operator training beyond existing        │
│    pytest/CI patterns                               │
└─────────────────────────────────────────────────────┘
```

### 4.2 Decision: Where Should Operators Review Data-Moat Cycles?

**Both surfaces, with clear routing:**

| Review Task | Primary Surface | Why |
|------------|----------------|-----|
| "Did the pipeline run succeed?" | **Windmill** (run list, step logs) | Native observability, no custom code needed |
| "Is the jurisdiction data fresh enough?" | **Affordabot admin panel** | Freshness is product-owned business logic |
| "What's the evidence quality?" | **Affordabot admin panel** | Evidence sufficiency is product truth |
| "Why did step X fail?" | **Windmill** (step detail, stderr) | Windmill has full execution context |
| "What documents were captured?" | **Affordabot SubstrateExplorer** | Product-scoped substrate viewer |
| "Is the analysis reliable?" | **Affordabot admin panel** | Analysis provenance is product truth |
| "Which runs should I rerun?" | **Windmill** (run list + labels) | Windmill native rerun support |

**Implementation:** Affordabot admin panel should include prominent deep-links to
Windmill run detail pages (already partially done via `windmill_run_url` in operator
links). Add labels to make Windmill-side filtering effective.

---

## 5. Proposed Changes to Beads Epics/Tasks

### 5.1 Modify Epic `bd-n6h1c` Before Implementation?

**No.** The epic's scope (data-moat quality gates) is correctly scoped to
product-specific rubric logic. The Windmill utilization improvements and optional
OSS DQ pilot are orthogonal concerns that should be tracked separately.

### 5.2 Recommended New Beads Tasks

| Proposed Task | Epic | Priority | Effort | Dependencies |
|--------------|------|----------|--------|-------------|
| Add Windmill job/flow labels to all committed flows and `trigger_cron_job.py` | `bd-9qjof` (or new) | P2 | 2-3h | None |
| Return `wm_labels` from domain-boundary script (jurisdiction, source_family, status) | `bd-9qjof.3` or `.6` | P2 | 1h | Domain-boundary script active |
| Add prominent Windmill deep-links to PipelineStatusPanel | `bd-n6h1c` (or new) | P3 | 1h | None |
| Pandera pilot: add DataFrame schema guards to `IngestionService.process_raw()` | New task | P3 | 3-4h | None |
| Evaluate Windmill App builder for thin operator run-review dashboard | New task | P3 | 4-8h investigation | Windmill instance access |

### 5.3 Tasks NOT Recommended

| Not Recommended | Reason |
|----------------|--------|
| OSS DQ framework adoption (GX/Soda) | Overhead exceeds value at current scale |
| Data catalog deployment (OpenMetadata/DataHub) | Data estate too small; spec-lock is effective catalog |
| Lineage tooling (OpenLineage/Marquez) | Pipeline DAG trivially visible in flow YAML |
| Migrate custom admin read models to Windmill | Product truth must stay in Affordabot |
| Build Windmill S3 integration for MinIO | MinIO is direct-access; Windmill layer adds complexity |

---

## 6. First Three Implementation Steps

### Step 1: Add Windmill Labels (2-3 hours)

1. Add static `labels` to all committed `*__flow/flow.yaml` files:
   ```yaml
   labels:
     - affordabot
     - cron
     - production
   ```
2. Return `wm_labels` from `trigger_cron_job.py`:
   ```python
   result["wm_labels"] = [f"endpoint:{endpoint}", f"env:{env}"]
   ```
3. Sync to Windmill workspace and verify labels appear in run list.

### Step 2: Enrich Admin Panel Deep-Links (1 hour)

1. Ensure `_build_windmill_run_url` in `admin.py` resolves from `WINDMILL_BASE_URL`
   env var at runtime (already partially done).
2. Add `windmill_run_url` to `PipelineStatusPanel` as a clickable external link.
3. Verify link navigates to correct Windmill run detail page.

### Step 3: Pandera Pilot on Ingestion (3-4 hours)

1. `pip install pandera` (add to `pyproject.toml`).
2. Define a `RawScrapeInputSchema` for the DataFrame entering `IngestionService`:
   ```python
   import pandera as pa
   raw_scrape_schema = pa.DataFrameSchema({
       "url": pa.Column(str, nullable=False),
       "content": pa.Column(str, nullable=False, checks=pa.Check.str_length(min_value=1)),
       "source_id": pa.Column(str, nullable=False),
   })
   ```
3. Validate at ingestion entry point; raise on schema violation.
4. Add pytest coverage for schema guard.

---

## 7. Lowest-Cognitive-Load Architecture for 10-20 Cycle Reviews

For reviewing 10-20 structured/unstructured data-moat improvement cycles, the
recommended architecture is:

```
Cycle Review Workflow:
  1. Windmill → run list filtered by labels (jurisdiction, source_family, cycle_number)
     → quick pass/fail triage
  2. Affordabot admin → PipelineStatusPanel → freshness + evidence status
     → product-truth validation
  3. Affordabot admin → SubstrateExplorer → drill into specific run captures
     → document-level inspection
  4. Windmill → step detail for any failed steps → root cause
  5. Affordabot admin → evidence view → claim-to-evidence audit

Key enablers:
  - Windmill labels make step 1 instant (no SQL, no grep)
  - Admin deep-links make step 4 one-click
  - Existing PipelineStatusPanel handles steps 2-3 already
  - Existing evidence endpoints handle step 5 already
```

**The bottleneck is step 1** — without Windmill labels, the operator must manually
match Windmill run IDs to jurisdiction/source_family context. Adding labels eliminates
this friction.

---

## 8. Sources & Citations

### Internal Sources
- `docs/CRON_ARCHITECTURE.md` — Windmill scheduler-of-record documentation
- `docs/specs/2026-04-13-windmill-domain-brownfield-spec-lock.md` — Domain-boundary spec
- `ops/windmill/README.md` — Windmill orchestration README
- `ops/windmill/f/affordabot/pipeline_daily_refresh_domain_boundary__flow/flow.yaml` — Flow definition
- `ops/windmill/f/affordabot/trigger_cron_job.py` — Shared trigger script
- `backend/routers/admin.py` — Admin API endpoints
- `backend/services/glass_box.py` — GlassBox observability service
- `frontend/src/services/adminService.ts` — Frontend admin service
- `frontend/src/components/admin/PipelineStatusPanel.tsx` — Pipeline status panel
- `frontend/src/components/admin/SubstrateExplorer.tsx` — Substrate explorer
- `docs/poc/round1-search-benchmark/README.md` — Search benchmark evidence
- PR #440 (`8b7d8d1`) — Structured proof overlay
- PR #441 (`8ae7f3b`) — Search benchmark evidence

### External Sources
- [Windmill docs: Labels](https://www.windmill.dev/docs/core_concepts/labels) — Job/flow labels, dynamic `wm_labels`
- [Windmill docs: Apps](https://www.windmill.dev/docs/apps/getting_started) — Low-code and full-code app builder
- [Windmill docs: Flow Status](https://www.windmill.dev/docs/apps/app_configuration_settings/app_component_library#flow-status) — Flow Status component
- [Windmill docs: Workspace S3](https://www.windmill.dev/docs/core_concepts/persistent_storage/large_data_files) — Workspace object storage
- [Windmill docs: Assets](https://www.windmill.dev/docs/core_concepts/assets) — Asset lineage visualization
- [Windmill docs: Audit Logs](https://www.windmill.dev/docs/core_concepts/audit_logs) — Audit log retention and access
- [Windmill docs: Embedding](https://www.windmill.dev/docs/misc/embed) — Iframe embedding and whitelabeling
- [Great Expectations docs](https://docs.greatexpectations.io/) — GX framework
- [Soda docs](https://docs.soda.io/) — SodaCL
- [Pandera docs](https://pandera.readthedocs.io/) — DataFrame validation
- [OpenLineage docs](https://openlineage.io/docs/) — Lineage standard
- [OpenMetadata docs](https://docs.open-metadata.org/) — Data catalog
- [DataHub docs](https://datahubproject.io/docs/) — Metadata platform

### Beads Memory Lookups (Attempted)
- `bdx memories "Windmill data moat"` — No results
- `bdx memories "data quality"` — No results
- `bdx search "Windmill affordabot" --label memory --status all` — No results
- `bdx search "data moat glassbox" --label memory --status all` — No results
