# Windmill / OSS Data-Quality / Data-Moat Architecture Audit

**Date:** 2026-04-26
**Auditor:** Senior data-platform / workflow-orchestration reviewer
**Scope:** Affordabot data-moat cycle review infrastructure
**Beads Epic:** `bd-n6h1c`
**Beads Subtask:** `bd-n6h1c.8`
**Feature-Key:** `bd-n6h1c.8`

---

## Executive Summary

Affordabot is **materially underusing first-party Windmill capabilities** for organizing and filtering its data-moat pipeline work, but Windmill **cannot replace** the product-specific glassbox/admin surfaces already under construction. The correct next architecture is a **tighter hybrid**: let Windmill own more of the orchestration metadata (labels, job links, asset tracking), keep Affordabot owning product truth (freshness, evidence sufficiency, jurisdiction scoping), and **pilot a lightweight OSS data-quality layer** only where it reduces custom code.

**Top-line verdict:**
- **Adopt** Windmill labels and `wm_labels` job tagging immediately.
- **Adopt** Windmill asset tracking for MinIO artifact references.
- **Pilot** Pandera for inline structured-data validation in domain commands.
- **Defer** Great Expectations, Soda, OpenMetadata, and heavy lineage investments.
- **Do not** move canonical product truth into Windmill scripts or apps.

---

## Findings

| ID | Finding | Severity | Risk |
|----|---------|----------|------|
| F1 | **Zero labels** are used on any committed Windmill flow or script. Labels are free, propagate to jobs, and would let operators filter runs by `structured`, `scraped`, or `jurisdiction:san-jose-ca` without custom backend code. | Medium | Operators rely solely on Affordabot backend read models for run discovery; Windmill runs page is unfiltered noise. |
| F2 | **Zero asset tracking** is used for MinIO artifacts. Windmill can detect `s3://` / `res://` references at static-analysis and runtime time, creating a visual data-flow graph. Current scripts pass artifact metadata opaquely in JSON payloads. | Medium | No first-party visualization of data lineage; operators must parse JSON in Affordabot admin. |
| F3 | The `pipeline_daily_refresh_domain_boundary__flow` is **still stub-backed** (`command_client` defaults to `stub`). PR #440 introduced a parallel `policy_evidence_package_orchestration__flow`, suggesting orchestration surface sprawl before the primary Path B flow is product-backed. | High | Two skeleton flows compete for operator attention; neither provides end-to-end product evidence. |
| F4 | **No OSS data-quality tool** is used. All validation (freshness gates, evidence sufficiency, content-hash verification) is custom Python. For a tiny team this is correct for product-rubric logic, but generic checks (schema conformance, null-rate bounds, URL-format validation) are being reimplemented. | Medium | Reinventing commodity checks increases maintenance load and error rates. |
| F5 | The backend `GlassBoxService` and `admin.py` pipeline read models **reimplement** run-history semantics that Windmill already provides (run lists, step statuses, timestamps, retry counts). The reimplementation is necessary because Affordabot enriches Windmill data with product truth (freshness policy, evidence sufficiency, jurisdiction scoping), but the seam is verbose and could be thinner. | Low | Maintenance burden on backend read models; every new pipeline step needs a GlassBox mapping. |
| F6 | **Beads memory lookup returned zero records** for Windmill data-moat, data quality, Windmill affordabot, and data moat glassbox. This means cross-agent knowledge about prior decisions is missing from the durable memory layer. | Medium | Risk of repeated rediscovery in future audits. |

---

## Current Usage Inventory

### Committed Windmill Assets (repo)

| Path | Type | Schedule | Backed By |
|------|------|----------|-----------|
| `f/affordabot/discovery_run` | flow | `0 5 * * *` UTC | `trigger_cron_job.py` -> backend `/cron/discovery` |
| `f/affordabot/daily_scrape` | flow | `0 6 * * *` UTC | `trigger_cron_job.py` -> backend `/cron/daily-scrape` |
| `f/affordabot/rag_spiders` | flow | `0 7 * * *` UTC | `trigger_cron_job.py` -> backend `/cron/rag-spiders` |
| `f/affordabot/universal_harvester` | flow | `0 8 * * *` UTC | `trigger_cron_job.py` -> backend `/cron/universal-harvester` |
| `f/affordabot/manual_substrate_expansion` | flow | manual only | `trigger_cron_job.py` -> backend `/cron/manual-substrate-expansion` |
| `f/affordabot/pipeline_daily_refresh_domain_boundary__flow` | flow | **unscheduled** | stub (`command_client=stub` default) |
| `f/affordabot/policy_evidence_package_orchestration__flow` | flow | **unscheduled** | boundary-only script (added in PR #440) |
| `f/affordabot/trigger_cron_job.py` | script | n/a | shared trigger wrapper |
| `f/affordabot/pipeline_daily_refresh_domain_boundary.py` | script | n/a | orchestration skeleton step |
| `f/affordabot/policy_evidence_package_orchestration` | script | n/a | boundary step (added in PR #440) |

### Live Windmill Inventory (read-only CLI check, 2026-04-27)

- **Workspace:** `affordabot` on `https://server-dev-8d5b.up.railway.app`
- **Flows (7):** discovery_run, daily_scrape, rag_spiders, universal_harvester, manual_substrate_expansion, pipeline_daily_refresh_domain_boundary__flow, policy_evidence_package_orchestration__flow
- **Scripts (3):** trigger_cron_job, pipeline_daily_refresh_domain_boundary, policy_evidence_package_orchestration
- **Labels:** **none** on any flow or script.
- **Assets:** **none** detected (no `s3://` or `res://` references in code that Windmill tracks).
- **States / Resources:** standard workspace variables only (`BACKEND_PUBLIC_URL`, `CRON_SECRET`, `SLACK_WEBHOOK_URL`).
- **Queued jobs:** 3 scheduled flows waiting for next trigger (daily_scrape, rag_spiders, universal_harvester).

### Native Windmill Surfaces Used

| Surface | Used? | How |
|---------|-------|-----|
| Schedules | Yes | 4 cron schedules + 2 unscheduled flows |
| Flow DAG / branching | Partial | `pipeline_daily_refresh_domain_boundary__flow` has `branchone` and `forloopflow`; others are single-step wrappers |
| Retry / backoff | Yes | `pipeline_daily_refresh_domain_boundary__flow` step retries (2 attempts, exponential backoff); `manual_substrate_expansion` retries (2 attempts) |
| Concurrency limits | Yes | `limit: 2, key: affordabot-domain-boundary` on domain-boundary flow; `limit: 1` on manual expansion |
| Failure handlers | Yes | `failure_module` in domain-boundary flow |
| Run history / filtering | Implicit | Windmill runs page exists, but Affordabot does not link labels or filter by them |
| Labels | **No** | Not set on any asset |
| `wm_labels` job output | **No** | Not returned by any script |
| Assets / S3 tracking | **No** | MinIO artifact refs are passed as strings inside JSON payloads |
| Apps (low-code / full-code) | **No** | Not used, and correctly so per spec lock |
| Data tables / DuckDB | **No** | Not relevant to current pipeline shape |
| Audit logs | **No** | Enterprise feature; not available on shared dev instance |

---

## Windmill Native Capability Fit Matrix

| Proposed Glassbox Need | Windmill Can Satisfy? | Fit | Rationale |
|------------------------|----------------------|-----|-----------|
| Run history / status / timestamps | **Yes** | Adopt | Windmill runs page + CLI/API already provide this. Affordabot should embed deep links, not duplicate the list. |
| Step-level retry / backoff / failure branches | **Yes** | Adopt | Native flow features. Current `pipeline_daily_refresh_domain_boundary__flow` uses them correctly. |
| Job / run labeling and filtering | **Yes** | Adopt | Labels are free-form, propagate to jobs, and support `wm_labels` output. Ideal for tagging `jurisdiction:san-jose-ca`, `source_family:meeting_minutes`, `moat_cycle:53`. |
| Artifact / dataset lineage visualization | **Partial** | Pilot | Assets track `s3://` references and show flow nodes. Affordabot could return `s3object` typed results from Windmill scripts instead of plain strings. Limited to S3/MinIO-compatible URIs. |
| Operator-facing pipeline status (freshness, evidence count, sufficiency) | **No** | Reject | These are Affordabot product invariants. Windmill has no concept of "fresh_hours" or "evidence sufficiency." |
| Canonical document identity / revision chains | **No** | Reject | Product truth. Windmill states are for script-level persistence, not product entity identity. |
| Frontend admin dashboard | **No** | Reject | Windmill apps could theoretically build UIs, but moving product read models into Windmill violates the spec lock and creates a second backend. |
| Data-quality checks (null bounds, schema conformance, uniqueness) | **No** | Reject | Windmill is an orchestrator, not a DQ engine. No native expectations, suites, or anomaly detection. |
| Long-term audit / compliance logs | **No** | Defer | Audit logs are Enterprise/cloud-only. Shared dev instance does not have them. |

**Summary:** Windmill should own everything in the top 4 rows (orchestration metadata). Affordabot must own everything below (product truth).

---

## OSS Data-Quality / Lineage / Catalog Tool Fit Matrix

### Evaluation Criteria
- **Setup cost**: initial integration effort for a tiny team
- **Local dev friction**: can a developer run checks in `poetry run pytest` without Docker?
- **CI fit**: does it add value in GitHub Actions?
- **Structured data fit**: tabular Postgres / Parquet / CSV
- **Scraped / unstructured fit**: HTML, PDF, markdown, arbitrary JSON
- **Recommendation**: adopt / pilot / defer / reject

| Tool | Setup Cost | Local Dev Friction | CI Fit | Structured Fit | Scraped/Unstructured Fit | Recommendation |
|------|------------|-------------------|--------|---------------|--------------------------|----------------|
| **Pandera** | Very low | Zero (pip install, pytest) | Excellent | Excellent (DataFrame schemas) | Partial (can validate JSON/dict shapes) | **Pilot** |
| **Great Expectations (GX)** | High | High (context, datasources, checkpoints) | Moderate | Excellent | Poor (not designed for HTML/PDF) | **Defer** |
| **Soda Core** | Low-Medium | Low (SQL/YAML checks) | Good | Excellent | Poor (SQL-first; unstructured is out of scope) | **Defer** |
| **OpenLineage** | Low | Low (client library only) | Good | N/A (lineage, not DQ) | N/A | **Defer** |
| **OpenMetadata / DataHub** | Very high | High (needs deployed service) | Moderate | Excellent | Poor | **Reject** |
| **dbt tests** | Medium | Medium | Good | Excellent | Poor | **Reject** (no dbt in stack) |
| **Evidently / whylogs** | Medium | Low | Good | Good | Poor (ML drift focused) | **Reject** |

### Tool-by-Tool Rationale

**Pandera**
- Lightweight Python data-validation library. Define schemas as decorators or classes.
- Can validate Polars/Pandas DataFrames, or generic dictionaries (useful for MinIO artifact metadata, search snapshot rows).
- Example use: `@pa.check_types` on `IngestionService.chunk_and_embed()` to enforce `chunk_text` non-null, `embedding` length == 768, `metadata` has `jurisdiction_id`.
- **Verdict:** pilot inside domain commands for generic structural checks. Keep product-rubric logic (freshness, evidence sufficiency) custom.

**Great Expectations**
- Mature expectation suites, profiling, data docs. Integrates with OpenLineage.
- Requires a `DataContext`, datasource configuration, checkpoint definitions. Heavy for a 2-3 person team.
- Overkill for scraped HTML/PDF because it expects tabular datasources.
- **Verdict:** defer until structured-data volume justifies the maintenance tax.

**Soda Core**
- SQL-first checks in YAML. Good for Postgres table validation.
- Could validate `raw_scrapes` row counts, null rates, freshness windows directly in SQL.
- Less useful for MinIO artifact integrity or HTML content quality.
- **Verdict:** defer. Affordabot already has SQL freshness logic in `admin.py`; Soda adds a YAML layer without enough new value.

**OpenLineage + Marquez**
- Standard facet-based lineage metadata. Integrates with Airflow, Spark, dbt, GX.
- Affordabot pipeline is not in the OpenLineage ecosystem (no Spark, no dbt, no Airflow). Windmill has no native OpenLineage integration.
- Would require custom facet emission from backend scripts.
- **Verdict:** defer until the team needs cross-system lineage (e.g., if Prime Radiant EODHD pipelines join the same lineage graph).

**OpenMetadata / DataHub**
- Full data catalog with quality, lineage, profiling, dashboards.
- Requires a persistent metadata store, indexing, UI hosting.
- **Verdict:** reject. Far too heavy for current scale. Revisit if the team grows past 5 engineers.

---

## Recommended Ownership Boundary

```
┌─────────────────────────────────────────────────────────────────┐
│  WINDMILL                                                       │
│  - scheduling, triggers, retries, branching, loops              │
│  - run history, run URLs, job IDs                               │
│  - labels on flows/scripts (static + dynamic wm_labels)         │
│  - asset tracking for S3/MinIO references (s3object types)      │
│  - concurrency limits, failure handlers                         │
└─────────────────────────────────────────────────────────────────┘
                              ↕
┌─────────────────────────────────────────────────────────────────┐
│  AFFORDABOT                                                     │
│  - canonical document identity / revision chains                │
│  - freshness policy & evidence sufficiency gates                │
│  - jurisdiction / source-family scoping                         │
│  - Postgres / MinIO / pgvector write semantics                  │
│  - backend read models & frontend admin surfaces                │
│  - product-specific alerts (e.g., "stale_blocked")              │
│  - custom rubric logic (trust tier, promotion state)            │
└─────────────────────────────────────────────────────────────────┘
                              ↕
┌─────────────────────────────────────────────────────────────────┐
│  OPTIONAL OSS DQ (pilot only)                                   │
│  - Pandera: inline structural validation in domain commands     │
│  - OpenLineage: deferred until cross-system lineage needed      │
└─────────────────────────────────────────────────────────────────┘
```

---

## Proposed Changes to Beads Epics / Tasks

### Immediate additions to `bd-n6h1c` (this epic)

1. **`bd-n6h1c.9` — Windmill labels and job tagging for data-moat flows**
   - Add static labels to all committed flows and scripts: `data_moat`, `affordabot`, `env:dev`.
   - Add dynamic `wm_labels` output from `trigger_cron_job.py` and domain-boundary scripts including `jurisdiction_id`, `source_family`, `run_mode`.
   - Update `ops/windmill/README.md` with label conventions.
   - Acceptance: CLI `job list --label data_moat` returns Affordabot jobs only.

2. **`bd-n6h1c.10` — Asset tracking pilot for MinIO artifact refs**
   - Change domain-boundary scripts to return `s3object` typed results (or `dict` with `s3` key) for artifact references instead of plain strings.
   - Verify Windmill Assets page shows artifact nodes in the flow graph.
   - Acceptance: `windmill-cli` asset list or UI shows at least one `s3://` node linked to `f/affordabot/pipeline_daily_refresh_domain_boundary__flow`.

3. **`bd-n6h1c.11` — Pandera inline validation pilot in domain commands**
   - Add `pandera` dependency to `backend/pyproject.toml`.
   - Implement one Pandera schema each for:
     - `search_materialize` output (snapshot row shape)
     - `index` chunk metadata (required fields: `raw_scrape_id`, `jurisdiction_id`, `source_family`, `canonical_document_key`)
   - Run validation in command envelope post-processing, failing `failed_terminal` on schema violation.
   - Acceptance: unit test demonstrating schema failure produces correct `retry_class` and alert.

### Modifications to existing tasks

- **`bd-9qjof.3` (Windmill Flow Skeleton)**: Expand scope to include label conventions and `wm_labels` emission in the flow contract. This is low-cognitive-load and belongs in the same PR.
- **`bd-9qjof.5` (Backend Read Models / Frontend)**: Ensure `PipelineStatusPanel` displays Windmill run URL **and** a direct link to the Windmill runs page filtered by label (e.g., `?label=data_moat,jurisdiction:san-jose-ca`).

### Tasks to defer / reject

- Do **not** create a Beads task for Great Expectations, Soda, OpenMetadata, or DataHub.
- Do **not** create a Beads task for OpenLineage until at least one other system (Prime Radiant, dbt, Spark) is in the same lineage graph.
- Do **not** create a Beads task for Windmill Apps to replace the frontend admin dashboard.

---

## First Three Implementation Steps

1. **Labels (1-2 days)**
   - Edit all `ops/windmill/f/affordabot/*__flow/flow.yaml` and `*.script.yaml` files to add `labels: [data_moat, affordabot]`.
   - Modify `trigger_cron_job.py` to return `{"wm_labels": ["data_moat", f"jurisdiction:{jurisdiction_id}", f"source_family:{source_family}"]}` when jurisdiction/source_family are known.
   - Deploy to `affordabot` workspace and verify filtering in Windmill UI.

2. **Asset tracking pilot (2-3 days)**
   - In the domain-boundary script (`pipeline_daily_refresh_domain_boundary.py`), change artifact ref returns from `{"artifact_uri": "artifacts/..."}` to `{"s3": "artifacts/..."}` (Windmill `s3object` shape).
   - Run a manual stub flow and confirm the Assets tab shows the node.
   - Document the pattern in `ops/windmill/README.md`.

3. **Pandera pilot (2-3 days)**
   - Add `pandera = "^0.20.0"` to `backend/pyproject.toml`.
   - Write `backend/services/pipeline/domain/validators.py` with schemas for `SearchSnapshotRow`, `ChunkMetadata`.
   - Integrate into `index` command post-write verification: validate a sample of chunk metadata before returning `succeeded`.
   - Add pytest cases for happy path and schema violation.

---

## Sources / Citations

### Repository Evidence
- `docs/CRON_ARCHITECTURE.md` — Windmill scheduler of record, shared-instance model, auth contract.
- `docs/specs/2026-04-13-windmill-domain-brownfield-spec-lock.md` — Command envelope, domain commands, Windmill must-not-own list.
- `ops/windmill/README.md` — Live CLI patterns, safe auth, deployment notes.
- `ops/windmill/f/affordabot/pipeline_daily_refresh_domain_boundary__flow/flow.yaml` — Stub-backed flow shape, retry/concurrency/failure handler config.
- `ops/windmill/f/affordabot/manual_substrate_expansion__flow/flow.yaml` — Retry config, concurrency limit.
- `ops/windmill/f/affordabot/trigger_cron_job.py` — Shared trigger wrapper, Slack alerting.
- `backend/routers/admin.py` — Pipeline read models, freshness policy, substrate explorer, policy evidence package overlays (PR #440 delta).
- `backend/services/glass_box.py` — Pipeline run/step retrieval, mechanism trace normalization.
- `frontend/src/services/adminService.ts` — API client for pipeline status, substrate runs.
- `frontend/src/components/admin/PipelineStatusPanel.tsx` — Frontend pipeline status display.
- `frontend/src/components/admin/SubstrateExplorer.tsx` — Run-first substrate debugging UI.
- `docs/poc/round1-search-benchmark/README.md` — Round 1 SearXNG benchmark evidence (PR #441).

### PR Context Deltas
- **PR #440** (`8b7d8d1526673aff7440e8b880a95c3d1d2d972c`): Added structured-source runtime proof overlay, policy evidence package storage, quality spine economics, and a second Windmill orchestration flow (`policy_evidence_package_orchestration__flow`). This confirms the team is building parallel orchestration skeletons rather than hardening one.
- **PR #441** (`8ae7f3b470b82b89e271b194bc978ab6b5d46b5b`): Added Round 1 search benchmark harness and live SearXNG evidence. Validated OSS search as primary discovery path.

### Live Windmill Inventory
- **CLI check executed 2026-04-27** via `windmill-cli@1.682.0` against `https://server-dev-8d5b.up.railway.app` workspace `affordabot`.
- Confirmed 7 flows, 3 scripts, 0 labels, 0 assets, 3 queued scheduled jobs.

### External Documentation
- Windmill Labels: https://www.windmill.dev/docs/core_concepts/labels (labels propagate to jobs; support `wm_labels` output; filterable via API/UI)
- Windmill Assets: https://www.windmill.dev/docs/core_concepts/assets (static + runtime detection of `s3://`, `res://`, `volume://`; column-level tracking for DuckDB; asset nodes in flows)
- Windmill Jobs / Runs: https://www.windmill.dev/docs/core_concepts/jobs and https://www.windmill.dev/docs/core_concepts/monitor_past_and_future_runs (run history, filtering by labels/tags/status, batch re-run, SSE streaming)
- Windmill Data Pipelines: https://www.windmill.dev/docs/core_concepts/data_pipelines (S3 integration, Polars/DuckDB helpers, restart-from-step)
- OpenLineage: https://openlineage.io/docs/ (open lineage standard, facets, integrations with Airflow/Spark/dbt/GX; Marquez as reference UI)
- Great Expectations + OpenLineage: https://openlineage.io/docs/integrations/great-expectations/
- OpenMetadata Data Quality: https://blog.open-metadata.org/simple-easy-and-efficient-data-quality-with-openmetadata-1c4e7d329364 (contrasts with GX/Soda; no need for yet another tool)
- Soda Core vs Great Expectations comparisons: DataExpert.io, The Data Letter, Medium Nexumo_ (Soda = lower barrier SQL/YAML; GX = higher complexity Python suites)

### Beads Memory
- `bdx memories "Windmill data moat"` — `{}`
- `bdx memories "data quality"` — `{}`
- `bdx search "Windmill affordabot" --label memory --status all` — `[]`
- `bdx search "data moat glassbox" --label memory --status all` — `[]`

---

## Appendices

### A. Windmill Label Convention Proposal

Static labels (committed in YAML):
```yaml
labels:
  - data_moat
  - affordabot
  - env:dev
```

Dynamic labels (emitted at runtime via `wm_labels`):
```python
return {
    "wm_labels": [
        f"jurisdiction:{jurisdiction_id}",
        f"source_family:{source_family}",
        f"mode:{mode}",
    ]
}
```

Filter URL pattern:
```
https://server-dev-8d5b.up.railway.app/runs?label=data_moat,jurisdiction:san-jose-ca
```

### B. Pandera Schema Sketch

```python
import pandera as pa
from pandera.typing import Series

class ChunkMetadataSchema(pa.DataFrameModel):
    raw_scrape_id: Series[str] = pa.Field(nullable=False)
    jurisdiction_id: Series[str] = pa.Field(nullable=False)
    source_family: Series[str] = pa.Field(nullable=False)
    canonical_document_key: Series[str] = pa.Field(nullable=False)
    chunk_index: Series[int] = pa.Field(ge=0)
    chunk_text: Series[str] = pa.Field(nullable=False, str_min_length=1)
    embedding: Series[list] = pa.Field(nullable=True)
```

### C. Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Adding labels/assets diverts attention from making the domain-boundary flow product-backed | Medium | High | Scope labels/assets as `bd-n6h1c.9/10` with explicit 1-2 day budgets; do not expand. |
| Pandera adds dependency fragility | Low | Low | Pin minor version; schema failures are `failed_terminal`, not silent. |
| Windmill label proliferation creates noise | Low | Medium | Enforce label vocabulary in `ops/windmill/README.md`; use `jurisdiction:` and `source_family:` prefixes. |
| Second flow (`policy_evidence_package_orchestration__flow`) becomes permanent parallel surface | High | High | Merge or retire it before `bd-9qjof.6` live gate. This audit recommends consolidating on `pipeline_daily_refresh_domain_boundary__flow`. |
