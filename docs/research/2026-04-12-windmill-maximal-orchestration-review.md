# Windmill-Maximal Orchestration Review

BEADS_SUBTASK: bd-jxclm.13
DATE: 2026-04-12
SPEC_PR: #415 (SHA 8a00ea8)
POC_PR: #417 (SHA eef4089)
VERDICT: approve_with_changes

## Executive Verdict

PR #415's architecture is directionally correct: Windmill owns orchestration, backend owns domain logic. The spec already avoids the two worst failure modes (business logic in Windmill, Windmill writing domain tables directly).

However, the spec **under-uses Windmill's native orchestration primitives** in three areas where Windmill already provides first-class support that the spec reinvents or omits:

1. **Retries** — The spec puts retry policy (`retryable`, `max_retries`, `retry_after_seconds`) in backend responses, but never maps these to Windmill's native per-step retry configuration (constant + exponential backoff, "continue on error"). The backend should declare retry intent; Windmill should execute it.

2. **Branching** — The spec mentions Windmill "branches on backend response status" but never specifies the branch-one/branch-all structure. Windmill's branch-one with predicate expressions on `results.<step>.status` is the natural fit. The spec should define the concrete flow shape.

3. **Suspend/Approval** — The spec has no approval step, but the domain clearly needs one: stale-fallback ceiling exceeded, promotion review, operator rerun decisions. Windmill's native suspend/approval with Slack integration eliminates the need for any custom approval surface.

The POC (PR #417) validates the persistence model correctly but runs the entire pipeline as a monolithic Python function. The next POC must prove **Windmill as the actual orchestrator** calling backend step endpoints, not just a scheduler calling a monolith.

---

## Windmill Capability Inventory

| Capability | Windmill Feature | Doc Link | Tier |
|---|---|---|---|
| Flow/DAG architecture | Flow editor with DAG steps | https://www.windmill.dev/docs/flows/flow_editor | Free |
| Branching (conditional) | Branch one (if/else) and branch all (parallel) | https://www.windmill.dev/docs/flows/flow_branches | Free |
| For loops | For-each with parallelism control, skip failure, squash | https://www.windmill.dev/docs/flows/flow_loops | Free |
| While loops | While loop with early stop | https://www.windmill.dev/docs/flows/while_loops | Free |
| Retries (constant) | Per-step constant retry with delay | https://www.windmill.dev/docs/flows/retries | Free |
| Retries (exponential) | Per-step exponential backoff | https://www.windmill.dev/docs/flows/retries | Free |
| Continue on error | Step-level toggle; error passed as result to downstream branch | https://www.windmill.dev/docs/flows/retries | Free |
| Step timeout | Custom timeout per step | https://www.windmill.dev/docs/flows/custom_timeout | Free |
| Error handler | Flow-level error handler step | https://www.windmill.dev/docs/flows/flow_error_handler | Free |
| Early stop/break | Predicate-based early termination | https://www.windmill.dev/docs/flows/early_stop | Free |
| Early return | Sync return + async continuation | https://www.windmill.dev/docs/flows/early_return | Free |
| Schedules/cron | Schedule triggers on scripts and flows | https://www.windmill.dev/docs/core_concepts/scheduling | Free |
| Webhooks | Webhook triggers | https://www.windmill.dev/docs/core_concepts/webhooks | Free |
| HTTP routes | Custom HTTP endpoints | https://www.windmill.dev/docs/core_concepts/http_routing | Free |
| Postgres triggers | LISTEN/NOTIFY-based Postgres event triggers | https://www.windmill.dev/docs/core_concepts/postgres_triggers | Free |
| Suspend/Approval | Suspend flow until approval/cancel, Slack integration, forms | https://www.windmill.dev/docs/flows/flow_approval | Free (forms: EE) |
| Sleep/delays | Per-step sleep before scheduling next | https://www.windmill.dev/docs/flows/sleep | Free |
| Concurrency limits | Per-script and per-flow rate limits | https://www.windmill.dev/docs/flows/concurrency_limit | EE/Cloud |
| Job debouncing | Cancel pending jobs with identical characteristics | https://www.windmill.dev/docs/core_concepts/job_debouncing | EE/Cloud |
| Worker groups | Dedicated workers by tag | https://www.windmill.dev/docs/core_concepts/worker_groups | Free |
| Resources and secrets | Workspace-level typed resources and encrypted variables | https://www.windmill.dev/docs/core_concepts/resources_and_types | Free |
| Variables/secrets | Workspace variables with secret encryption | https://www.windmill.dev/docs/core_concepts/variables_and_secrets | Free |
| Object storage (S3) | Workspace and instance S3 integration | https://www.windmill.dev/docs/core_concepts/object_storage_in_windmill | EE |
| Custom instance DB | Windmill's own Postgres for internal queries | https://www.windmill.dev/docs/core_concepts/custom_instance_database | Free |
| Data pipelines | SQL-based ETL pipelines | https://www.windmill.dev/docs/core_concepts/data_pipelines | Free |
| Run history/observability | Job logs, inputs/outputs, labels, run page | https://www.windmill.dev/docs/core_concepts/monitor_past_and_future_runs | Free |
| Caching | Per-step result caching | https://www.windmill.dev/docs/flows/cache | Free |
| Labels | Key-value labels on runs for filtering | https://www.windmill.dev/docs/core_concepts/labels | Free |
| Step mocking/pin | Pin a step result for testing | https://www.windmill.dev/docs/flows/step_mocking | Free |
| Trigger scripts | Poll-based incremental data fetch | https://www.windmill.dev/docs/flows/flow_trigger | Free |
| Workflows as code | Python/TS programs that define DAGs | https://www.windmill.dev/docs/core_concepts/workflows_as_code | Free |
| Git sync | Bidirectional sync with Git repo | https://www.windmill.dev/docs/advanced/git_sync | EE |
| Critical alerts | Configurable alert on job failure patterns | https://www.windmill.dev/docs/core_concepts/critical_alerts | EE/Cloud |
| Audit logs | Detailed audit trail | https://www.windmill.dev/docs/core_concepts/audit_logs | EE/Cloud |
| Autoscaling | Worker autoscaling | https://www.windmill.dev/docs/core_concepts/autoscaling | EE/Cloud |

### Tier Gating Summary

Most flow orchestration features (branches, loops, retries, error handlers, approval, sleep, caching) are **free/self-host**. The key features that require **Enterprise or Cloud**:

- Concurrency limits (rate-limit protection)
- Job debouncing
- S3/object storage integration
- Git sync
- Critical alerts
- Audit logs
- Approval forms (basic suspend is free; adding a form schema is EE)

**Risk**: If affordabot runs on the free self-hosted tier, it lacks concurrency limits and job debouncing. The spec's `retry_after_seconds` and backend-side rate awareness partially compensates, but a proper concurrency guard would require either EE or an external semaphore (e.g., backend-side admission control).

---

## Current Affordabot Usage Gap Analysis

### What Affordabot Currently Uses

From `ops/windmill/README.md` and `trigger_cron_job.py`:

- **Schedules**: 4 cron jobs (discovery, daily-scrape, rag-spiders, universal-harvester) + 1 manual flow
- **Execution model**: Shared-instance — Windmill calls authenticated backend cron endpoints over HTTP
- **Observability**: Slack webhook success/failure alerts from `trigger_cron_job`
- **No flows**: Each job is a single-script wrapper that calls one monolithic backend endpoint
- **No branching**: Success/failure is the only branching (via Slack alert)
- **No retries**: If the backend endpoint fails, the job fails. No retry at the Windmill level.
- **No step-level visibility**: One job = one HTTP call. No intermediate step tracking in Windmill.
- **No concurrency control**: Multiple jobs could hit the backend simultaneously without coordination.
- **No approval/suspend**: All jobs run to completion or fail. No human-in-the-loop.
- **No caching**: Each run starts from scratch.
- **No for-loops**: Multi-jurisdiction expansion is handled inside the backend monolith, not in the flow graph.

### What the Spec Proposes (PR #415)

- Step-oriented pipeline endpoints (search-materialize, freshness-gate, read-fetch, extract, embed)
- Backend returns `status`, `retryable`, `max_retries`, `retry_after_seconds`
- Windmill "branches on backend response status"
- Pipeline state persisted in 4 tables
- Artifact storage in MinIO
- Named freshness policies owned by backend

### Gap: What Windmill Already Provides That the Spec Rebuilds or Omits

| Capability | Spec approach | Windmill already provides | Gap severity |
|---|---|---|---|
| Retry execution | Backend declares retry params in response; spec says Windmill "obeys" but doesn't wire it | Native per-step retry: constant delay, exponential backoff, max attempts, "continue on error" | High — spec should map backend retry intent to Windmill retry config |
| Conditional branching | "Windmill branches on backend response" (unspecified) | Branch-one with JS predicates on `results.<step>.status`, `results.<step>.retryable` | High — spec should define the branch predicates |
| Stale-fallback escalation | Backend increments counters, alerts, hard ceiling | Could use Windmill early-stop + approval for ceiling escalation | Medium — backend logic is correct, but approval at ceiling should use Windmill suspend |
| Per-step timeout | Not specified in spec | Native custom timeout per step | Medium — each backend endpoint call should have a Windmill timeout |
| Concurrency/rate limiting | Not addressed | Windmill concurrency limits (EE) or backend admission control | Medium — needed when scaling to multiple jurisdictions |
| Human approval | Not in spec | Native suspend/approval with Slack integration and forms | Medium — needed for promotion review and stale-ceiling override |
| For-loop over jurisdictions | Spec mentions jurisdiction list in manifest | Native for-loop with parallelism control, skip-failure, squash | High — should iterate jurisdictions in Windmill, not inside backend |
| Run labels | Not in spec | Native labels on runs for filtering | Low — nice-to-have for observability |
| Step-level caching | Backend reuses via content hash | Native step result caching | Low — backend content-hash reuse is more domain-specific |
| Error handler | Not specified | Native flow-level error handler step | Medium — should define what Windmill does on unrecoverable failure |

---

## Core Questions

### Q1: What orchestration features are we currently rebuilding or planning to rebuild that Windmill already provides?

**Retry execution**: The spec puts `retryable`, `max_retries`, `retry_after_seconds` in the backend response, expecting Windmill to "obey" them. But the spec never specifies how Windmill implements this. Windmill's native per-step retry (constant + exponential backoff) is the right mechanism. The backend should declare retry intent declaratively; Windmill should configure its native retry from those declarations.

**Conditional branching**: The spec says Windmill "branches on backend response status" but never defines the branch structure. Windmill's branch-one with predicate expressions is the natural mechanism.

**Jurisdiction iteration**: The spec's manifest includes a `jurisdictions` array, but doesn't specify whether the backend or Windmill iterates over it. Windmill's for-loop with parallelism control is the right mechanism — it gives per-jurisdiction step visibility, skip-failure isolation, and parallelism tuning.

**Step timeout**: Not mentioned in the spec, but every backend HTTP call needs a Windmill-side timeout to prevent stuck flows.

### Q2: What should move from affordabot backend code into Windmill flow configuration?

- **Retry policy wiring**: Move from "backend declares, Windmill somehow obeys" to "backend declares, Windmill configures native retry"
- **Step graph structure**: The sequence (search-materialize -> freshness-gate -> read-fetch -> extract -> embed) should be explicit Windmill flow steps, not backend-internal routing
- **Jurisdiction iteration**: Windmill for-loop over jurisdictions
- **Branch predicates**: `results.search_materialize.status === "failed" && results.search_materialize.retryable` etc.
- **Step timeouts**: Windmill per-step timeout
- **Error handler**: Windmill flow-level error handler that sends Slack alert + marks run failed
- **Approval at stale ceiling**: Windmill suspend/approval step

### Q3: What should stay in affordabot backend no matter how powerful Windmill is?

- All Postgres writes (pipeline_runs, pipeline_steps, domain tables)
- All MinIO artifact writes
- Freshness policy evaluation and stale-fallback logic
- Idempotency key enforcement and manifest hash validation
- Search provider selection, query generation, URL normalization, dedupe, scoring
- Content hashing, content classification (PII detection), retention policy
- Source trust scoring and promotion decisions
- pgvector ingestion
- Contract version validation
- Alert content generation (backend authors the alert; Windmill delivers it)

### Q4: Should Windmill write directly to affordabot Postgres/MinIO, or only call backend endpoints?

**Recommendation: Only call backend endpoints.**

Tradeoffs:

| Approach | Pros | Cons |
|---|---|---|
| Windmill writes directly | Fewer network hops, simpler for trivial writes | Breaks auth boundary; Windmill must hold DB credentials; business logic leaks into Windmill scripts; no idempotency/manifest-hash enforcement; no content classification; version drift risk |
| Windmill calls backend endpoints | Clean auth boundary; backend enforces all invariants; idempotency guaranteed; single source of truth for writes | Extra network hop; backend must be available; requires careful timeout/retry config |

The spec's current position is correct. Windmill should never hold affordabot DB credentials or write domain rows directly. The network hop cost is negligible compared to the correctness benefit.

### Q5: Should pipeline_steps remain an affordabot table if Windmill already has job/step history?

**Yes, pipeline_steps must remain.**

Windmill's job history is orchestration-level: it tracks which Windmill step ran, when, with what inputs/outputs, and whether it succeeded. It does not know about:

- Idempotency keys and manifest hashes
- Freshness policy names and stale-backing decisions
- Content hash reuse and artifact manifests
- Domain-specific counters (created_count, reused_count, failed_count)
- Backend-authored alert content
- Business-logic error codes

These are domain concepts that belong in affordabot's schema. pipeline_steps should reference Windmill's job/step IDs (add a `windmill_job_id` column) for cross-referencing, but the table itself must persist domain state.

### Q6: What is the cleanest backend response contract for Windmill to branch/retry/alert on?

The current spec response shape is good but needs two adjustments:

**Add `windmill_retry_hint`** to allow Windmill to configure native retries from backend declarations:

```json
{
  "contract_version": "1.0.0",
  "status": "succeeded|failed|partial|skipped|in_progress",
  "run_id": "uuid",
  "step_key": "search_materialize",
  "retryable": true,
  "windmill_retry_hint": {
    "constant_delay_seconds": 300,
    "max_attempts": 3,
    "exponential_base": 2,
    "exponential_multiplier": 60
  },
  "alerts": [],
  "next_recommended_step": "freshness_gate",
  "operator_summary": "plain English summary"
}
```

The `windmill_retry_hint` is advisory — the Windmill flow definition is the authoritative retry config. But it allows the flow YAML to reference backend-declared values instead of hardcoding them.

**Add `windmill_suspend_hint`** for stale-ceiling and promotion scenarios:

```json
{
  "status": "failed",
  "retryable": false,
  "windmill_suspend_hint": {
    "reason": "stale_ceiling_exceeded",
    "approval_message": "Stale fallback ceiling exceeded for San Jose minutes. Approve to continue with expired data.",
    "timeout_seconds": 86400
  }
}
```

### Q7: What should the next Windmill-maximal POC prove?

1. A Windmill flow (not a single script) calls backend step endpoints in sequence
2. Each step is a separate Windmill flow node with native retry configuration
3. Branch-one on `results.<step>.status` routes "failed + retryable" to retry, "failed + non-retryable" to error handler, "succeeded" to next step
4. For-loop over 2+ jurisdictions with parallelism=1 (serial) and skip-failure=true
5. Flow-level error handler sends a Slack alert with run_id and failed step summary
6. One step times out via Windmill native timeout (not backend timeout)
7. Suspend/approval step triggered when backend returns `windmill_suspend_hint`
8. Run the same pipeline twice with unchanged content; prove the second run reuses prior artifacts via backend idempotency (Windmill does NOT cache; backend content-hash reuse works)

### Q8: What specific changes should be made to PR #415 and the bd-jxclm task graph?

See "Concrete Edits Recommended for PR #415" and "Concrete New/Changed Beads Subtasks" below.

---

## Revised Architecture Recommendation

### RACI Table

| Responsibility | Windmill | Backend | Postgres/MinIO | Human/Operator |
|---|---|---|---|---|
| Scheduling (cron, manual trigger) | **R** | I | - | A (enable/disable) |
| Flow graph definition | **R** | C | - | I |
| Per-step retry execution | **R** | C (declares intent) | - | I |
| Per-step timeout | **R** | I (declares expected duration) | - | - |
| Branch predicates | **R** | C (response shape enables it) | - | - |
| Jurisdiction iteration | **R** | I (manifest provides list) | - | - |
| Error handler / Slack alert delivery | **R** | C (authors alert content) | - | I |
| Approval/suspend at stale ceiling | **R** | C (declares suspend hint) | - | **A** |
| Approval/suspend for promotion | **R** | C (declares suspend hint) | - | **A** |
| All Postgres writes | I | **R** | **R** (storage) | - |
| All MinIO artifact writes | I | **R** | **R** (storage) | - |
| Freshness policy evaluation | I | **R** | - | - |
| Idempotency enforcement | I | **R** | - | - |
| Manifest hash validation | I | **R** | - | - |
| Search provider selection + scoring | I | **R** | - | - |
| Content hashing + classification | I | **R** | - | - |
| Source trust + promotion decisions | I | **R** | - | **A** (review) |
| pgvector ingestion | I | **R** | - | - |
| Contract version validation | I | **R** | - | - |
| Artifact retention + purge | I | **R** (backend endpoint) | **R** (storage) | - |
| Run labels + observability metadata | **R** | I | - | I |
| Step-level observability (Windmill UI) | **R** | - | - | I |
| Run-level observability (pipeline_runs) | I | **R** | - | I |

R = Responsible, A = Accountable/Approver, C = Consulted, I = Informed

### Recommended Endpoint Contract Shape

```text
POST /internal/pipeline/runs
  Request:  { contract_version, run_label, run_mode, manifest, manifest_hash, trigger_source }
  Response: { contract_version, status, run_id, windmill_retry_hint? }

POST /internal/pipeline/search-materialize
  Request:  { contract_version, run_id, step_key, idempotency_key, manifest_hash, manifest, trigger_source }
  Response: { contract_version, status, run_id, step_key, retryable, windmill_retry_hint?, windmill_suspend_hint?, created_count, reused_count, failed_count, artifact_paths, alerts, next_recommended_step, operator_summary }

POST /internal/pipeline/freshness-gate
  Request:  (same shape)
  Response: { ...status, freshness_policy_name, stale_backed, latest_success_at, max_stale_hours, windmill_suspend_hint? }

POST /internal/pipeline/read-fetch
  Request:  (same shape)
  Response: { ...status, artifact_paths }

POST /internal/pipeline/extract
  Request:  (same shape)
  Response: { ...status, artifact_paths, extraction_method }

POST /internal/pipeline/embed
  Request:  (same shape)
  Response: { ...status, embedded_count, reused_count }

GET /internal/pipeline/runs/{run_id}/report
  Response: { contract_version, run_id, status, steps[], artifacts[], alerts[], operator_summary }
```

### Recommended Windmill Flow Shape

```yaml
# f/affordabot/pipeline_daily_refresh__flow/flow.yaml
summary: "Daily persisted discovery pipeline"
schema:
  type: object
  properties:
    contract_version:
      type: string
      default: "1.0.0"
    jurisdictions:
      type: array
      items: { type: string }
      default: ["San Jose CA"]
    families:
      type: array
      items: { type: string }
      default: ["meetings", "permits"]
    freshness_policy:
      type: string
      default: "standard_daily_discovery"
    processing_policy:
      type: string
      default: "bounded_daily_default"
modules:
  - id: create_run
    value:
      type: script
      path: f/affordabot/trigger_pipeline_step
      input_transforms:
        endpoint: { value: "runs" }
        payload:
          type: javascript
          expr: |
            JSON.stringify({
              contract_version: flow_input.contract_version,
              run_label: "daily-discovery-refresh",
              run_mode: "capture_and_ingest",
              jurisdictions: flow_input.jurisdictions,
              families: flow_input.families,
              freshness_policy: flow_input.freshness_policy,
              processing_policy: flow_input.processing_policy,
              trigger_source: "windmill:f/affordabot/pipeline_daily_refresh"
            })

  - id: per_jurisdiction
    value:
      type: forloop
      iterator:
        type: javascript
        expr: "flow_input.jurisdictions"
      parallelism: 1
      skip_failure: true
      modules:
        - id: search_materialize
          value:
            type: script
            path: f/affordabot/trigger_pipeline_step
            input_transforms:
              endpoint: { value: "search-materialize" }
              payload:
                type: javascript
                expr: |
                  JSON.stringify({
                    contract_version: flow_input.contract_version,
                    run_id: results.create_run.run_id,
                    step_key: "search_materialize",
                    idempotency_key: `${results.create_run.run_id}:search_materialize:${flow_input.families.join(',')}`,
                    manifest_hash: results.create_run.manifest_hash,
                    manifest: { jurisdiction: iter.value, families: flow_input.families },
                    trigger_source: "windmill:f/affordabot/pipeline_daily_refresh"
                  })
            retry: &default_retry
              constant_delay: 300
              max_constant_attempts: 3
              exponential_base: 2
              exponential_multiplier: 60
              max_exponential_attempts: 2
            timeout: 600

        - id: branch_on_search
          value:
            type: branchone
            branches:
              - summary: "Search succeeded"
                predicate: "results.search_materialize.status === 'succeeded'"
              - summary: "Search failed, suspend for approval"
                predicate: "results.search_materialize.windmill_suspend_hint != null"
            default:
              summary: "Search failed, not retryable"

        - id: freshness_gate
          value:
            type: script
            path: f/affordabot/trigger_pipeline_step
            input_transforms:
              endpoint: { value: "freshness-gate" }
            retry: *default_retry
            timeout: 120

        - id: read_fetch
          value:
            type: script
            path: f/affordabot/trigger_pipeline_step
            input_transforms:
              endpoint: { value: "read-fetch" }
            retry: *default_retry
            timeout: 1200

        - id: extract
          value:
            type: script
            path: f/affordabot/trigger_pipeline_step
            input_transforms:
              endpoint: { value: "extract" }
            retry: *default_retry
            timeout: 600

        - id: embed
          value:
            type: script
            path: f/affordabot/trigger_pipeline_step
            input_transforms:
              endpoint: { value: "embed" }
            retry: *default_retry
            timeout: 600

  - id: stale_ceiling_approval
    value:
      type: script
      path: f/affordabot/request_approval
      suspend:
        required_events: 1
        timeout: 86400
      input_transforms:
        message:
          type: javascript
          expr: "results.search_materialize.windmill_suspend_hint.approval_message"

  - id: error_handler
    value:
      type: script
      path: f/affordabot/send_error_alert
      input_transforms:
        run_id:
          type: javascript
          expr: "results.create_run.run_id"
        error_detail:
          type: javascript
          expr: "JSON.stringify(error)"
```

### Table-by-Table Recommendation

#### pipeline_runs

**Keep.** Windmill has flow-run history, but pipeline_runs holds domain concepts: contract_version, manifest, manifest_hash, run_label, run_mode, trigger_source, summary, error_summary. Add `windmill_flow_run_id` column for cross-reference.

Do NOT replace with Windmill's run history. Windmill doesn't know about contract versions, manifests, or business-logic summaries.

#### pipeline_steps

**Keep.** Same reasoning. Windmill's step history tracks orchestration; pipeline_steps tracks domain state: idempotency_key, manifest_hash, freshness_policy, stale_backed, decision_reason, alerts, artifact_manifest. Add `windmill_job_id` column.

Do NOT replace with Windmill's step history. The idempotency key, freshness policy, and stale-backing decisions are business logic that Windmill must not own.

#### search_result_snapshots

**Keep.** This is pure domain data — search provider results, normalized URLs, scoring, freshness. Windmill has no equivalent concept.

#### content_artifacts

**Keep.** Artifact lineage, content classification, retention, and hash-based reuse are business logic. Windmill's S3/object storage is an infrastructure concern (where bytes live), not a lineage concern (what bytes mean). The backend should write to MinIO directly and record the storage path in this table.

---

## Concrete Edits Recommended for PR #415

### 1. Add Windmill Flow Shape Section

After the "Backend Step API" section, add a new section "Windmill Flow Definition" that specifies:

- The flow is a multi-step Windmill flow, not a single-script wrapper
- Each backend endpoint is a separate flow step calling `f/affordabot/trigger_pipeline_step`
- For-loop over jurisdictions with configurable parallelism
- Branch-one on `results.<step>.status` and `results.<step>.windmill_suspend_hint`
- Per-step native retry configuration derived from backend `windmill_retry_hint`
- Per-step timeout (search: 600s, freshness-gate: 120s, read-fetch: 1200s, extract: 600s, embed: 600s)
- Flow-level error handler that sends Slack alert with run_id
- Suspend/approval step for stale-ceiling and promotion

### 2. Add `windmill_retry_hint` to Response Contract

Add to the response shape:

```json
"windmill_retry_hint": {
  "constant_delay_seconds": 300,
  "max_constant_attempts": 3,
  "exponential_base": 2,
  "exponential_multiplier": 60,
  "max_exponential_attempts": 2
}
```

And `windmill_suspend_hint`:

```json
"windmill_suspend_hint": {
  "reason": "stale_ceiling_exceeded|promotion_review|operator_rerun",
  "approval_message": "plain English for approval page",
  "timeout_seconds": 86400
}
```

### 3. Add `windmill_flow_run_id` and `windmill_job_id` to Tables

Add to `pipeline_runs`:
- `windmill_flow_run_id text`

Add to `pipeline_steps`:
- `windmill_job_id text`

These allow cross-referencing between affordabot persistence and Windmill's observability UI.

### 4. Add "Windmill Retry vs Backend Retry" Clarification

Add a subsection under "Idempotency and Concurrent Retries":

> Windmill native retry is the retry execution mechanism. Backend `windmill_retry_hint` declares the desired policy. The Windmill flow YAML is the authoritative retry config. If Windmill retries a step, the backend idempotency key ensures the step is not re-executed if it already succeeded.

### 5. Add Approval/Suspend Boundary

Add to the "Active Contract" section:

> Windmill is allowed to suspend a flow pending operator approval when the backend returns `windmill_suspend_hint`. The approval mechanism is Windmill's native suspend/approval with Slack notification. The backend does not implement its own approval queue.

### 6. Add a Thin Trigger Script

The current `trigger_cron_job.py` is designed for monolithic cron endpoints. Add a new `trigger_pipeline_step.py` that:

- Takes endpoint, payload, backend_url, cron_secret, timeout_seconds
- POSTs to `/internal/pipeline/{endpoint}`
- Returns the parsed JSON response (for branch predicates)
- Does NOT send its own Slack alert (let the flow error handler do that)

### 7. Specify Concurrency Strategy

Add a section:

> When affordabot runs on Windmill EE, use native concurrency limits on the pipeline flow (max 1 concurrent run per jurisdiction-family pair) and on individual steps (max N concurrent search-materialize calls to avoid SearXNG overload). When on free self-host, implement backend-side admission control via a `pipeline_locks` table.

---

## Concrete New/Changed Beads Subtasks

| Beads ID | Title | Change | Rationale |
|---|---|---|---|
| bd-jxclm.9 | Add Windmill orchestration flows and run controls | **Expand**: change from "add flows that call existing cron endpoints" to "add multi-step Windmill flow with native retry, branching, for-loop, timeout, error handler, and approval steps" | Current description is too vague; must specify the flow shape |
| bd-jxclm.2 | Add persisted pipeline state and artifact schema | **Minor expand**: add `windmill_flow_run_id` to pipeline_runs, `windmill_job_id` to pipeline_steps | Cross-reference with Windmill observability |
| bd-jxclm.3 | Implement backend pipeline step endpoints | **Minor expand**: add `windmill_retry_hint` and `windmill_suspend_hint` to response shapes | Enable Windmill-native retry and approval |
| (new) bd-jxclm.14 | Add thin `trigger_pipeline_step` Windmill script | **New**: separate from `trigger_cron_job.py`; returns parsed response for branching; no inline Slack alerting | Current trigger script is monolith-oriented |
| (new) bd-jxclm.15 | Windmill-maximal POC: multi-step flow calling backend step endpoints | **New**: prove the flow shape works with native retry, branching, for-loop, timeout, error handler | POC #417 proved persistence, not Windmill orchestration |
| (new) bd-jxclm.16 | Add concurrency strategy: EE concurrency limits or backend admission control | **New**: prevents SearXNG overload and concurrent-run conflicts | Currently unaddressed |

---

## Hands-On POC Plan

### Objective

Prove that a Windmill flow (not a monolithic script) can orchestrate backend step endpoints with native retry, branching, for-loop, and approval.

### Scope

- 2 jurisdictions (San Jose CA, Saratoga CA)
- 1 family (meetings)
- Backend endpoints: create-run, search-materialize, freshness-gate, read-fetch, extract
- No embed (defer to later work)

### Acceptance Criteria

1. Windmill flow has 5+ separate steps (create-run, for-loop with search-materialize + freshness-gate + read-fetch + extract per jurisdiction)
2. Each step has native retry configured (constant: 2 attempts, 60s delay)
3. Each step has a timeout (search: 600s, freshness: 120s, fetch: 1200s, extract: 600s)
4. Branch-one on search-materialize status: succeeded -> freshness-gate, failed+retryable -> retry (via Windmill native), failed+non-retryable -> error handler
5. For-loop over jurisdictions with parallelism=1, skip-failure=true
6. Flow-level error handler sends Slack alert with run_id and failed step
7. One simulated failure (search provider outage) triggers Windmill retry, then error handler
8. One simulated suspend scenario (stale ceiling) triggers approval step
9. Second run with unchanged content reuses prior artifacts (verified by pipeline_steps.reused_count > 0)
10. All 4 pipeline tables populated with correct domain state
11. At least 1 artifact in MinIO (or fixture-backed object store)
12. No business logic in Windmill scripts (all scripts are thin HTTP wrappers)

### Prerequisites

- bd-jxclm.2 (schema) complete
- bd-jxclm.3 (step endpoints) at least search-materialize, freshness-gate, read-fetch, extract implemented
- bd-jxclm.14 (trigger_pipeline_step script) implemented
- Backend deployed with internal pipeline endpoints

### Estimated Duration

2-3 implementation sessions after prerequisites are met.

---

## Risks, Unknowns, and Plan-Tier/Self-Hosting Constraints

### Tier-Gated Features

| Feature | Tier | Impact if Unavailable | Mitigation |
|---|---|---|---|
| Concurrency limits | EE/Cloud | Cannot rate-limit search-materialize calls at the Windmill level | Backend-side admission control via pipeline_locks table |
| Job debouncing | EE/Cloud | Concurrent manual + scheduled runs could conflict | Backend idempotency keys already prevent double-execution |
| Approval forms | EE | Cannot add structured form to approval page (basic suspend is free) | Approval message in suspend hint; operator reviews in Windmill UI |
| S3/object storage | EE | Cannot use Windmill's S3 integration for artifacts | Backend writes to MinIO directly (already planned) |
| Git sync | EE | Windmill assets must be synced manually via `wmill sync push` | Already using CLI sync |
| Critical alerts | EE/Cloud | No built-in failure-pattern alerting | Custom Slack alerting in flow error handler |
| Audit logs | EE/Cloud | No Windmill audit trail | Backend pipeline_steps table serves as domain audit trail |

### Key Unknown

**Affordabot's Windmill tier is not documented in the spec or README.** The concurrency limits and approval forms are the most impactful EE-gated features for this pipeline. If affordabot is on the free self-hosted tier, the POC must prove that backend-side admission control is a viable fallback for concurrency, and that basic suspend (without forms) is sufficient for approvals.

### Risk: Windmill Retry vs Backend Idempotency Interaction

If Windmill retries a step and the backend had already completed it, the idempotency key must return the existing step state (not re-execute). The spec already requires this. The POC must prove it with a concrete test: simulate a Windmill retry after a step has succeeded, verify the backend returns the existing result.

### Risk: For-Loop Scale

If the jurisdiction list grows to 50+, the for-loop with parallelism=1 becomes very slow. With parallelism=5, it risks overloading SearXNG or the backend. The concurrency strategy (bd-jxclm.16) must be resolved before scaling.

### Risk: Approval Timeout

If an operator doesn't respond to a stale-ceiling approval, the flow hangs. The suspend/approval timeout (default 86400s = 24h) must be configured, and the error handler must mark the run as "approval timed out" in pipeline_runs.

---

## Tool Routing Exception

No exceptions. Used webfetch for Windmill official documentation, llm-tldr for semantic discovery, and bash for file operations.
