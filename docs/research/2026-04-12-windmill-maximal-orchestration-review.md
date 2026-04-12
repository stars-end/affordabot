# Windmill-Maximal Orchestration Review

- BEADS_EPIC: bd-jxclm
- BEADS_SUBTASK: bd-jxclm.13
- Related: bd-jxclm.1 (spec PR #415), bd-jxclm.12 (POC PR #417)
- Author role: senior research/architecture
- Date: 2026-04-12

## Executive Verdict

VERDICT: `approve_with_changes`

The current spec (PR #415) and POC (PR #417) are on the right architectural
line: Windmill owns orchestration, affordabot backend owns domain logic and
writes. But three concrete biases in the spec are under-using Windmill and
quietly rebuilding orchestration features that Windmill already ships:

1. `pipeline_steps` duplicates a large fraction of Windmill's native job/step
   history (status, timings, retry metadata, operator-visible summary). We
   should keep a trimmed `pipeline_steps` focused on *domain* state, not
   orchestration state, and lean on Windmill's run history for everything
   operator-visible.
2. Retry metadata (`retryable`, `max_retries`, `retry_after_seconds`) is
   being invented inside the backend response contract. Windmill already has
   first-class per-step constant + exponential backoff retries, step
   timeouts, and `continue-on-error`. Backend should emit *status* and
   *error classification*; Windmill should decide retry behavior from the
   flow definition, not from advisory fields in the JSON body.
3. The spec treats Windmill flows as thin HTTP fan-in (`Windmill -> one
   backend endpoint -> next backend endpoint`) and passes on native flow
   features such as branches, error handlers, recovery handlers, and
   suspend/approval for operator overrides. This leaves us with a plausible
   path back to "one big backend script per run" with a thin schedule in
   front of it — exactly the shape bd-jxclm.1 says we are trying to escape.

Recommended changes are additive and do not break the four-table MVP or the
POC. See `Concrete Edits to PR #415` below.

Spec PR #415 should be updated in-place as part of bd-jxclm.13; POC PR #417
can remain as-is for now and its learnings roll forward into a new Windmill-
maximal follow-on POC (`bd-jxclm.14`, proposed).

## Scope and Method

Sources read (verbatim, via `git show` against fetched refs):

- `review-bd-jxclm-spec` (PR #415, SHA `8a00ea84`):
  `docs/specs/2026-04-11-windmill-driven-persisted-pipeline.md`
- `review-bd-jxclm-poc` (PR #417, SHA `eef408900d`):
  - `backend/services/persisted_pipeline_poc.py`
  - `backend/scripts/verification/poc_sanjose_persisted_pipeline.py`
  - `backend/artifacts/poc_sanjose_persisted_pipeline/report.md`
- `origin/master`:
  - `ops/windmill/README.md`
  - `ops/windmill/f/affordabot/trigger_cron_job.py`
  - `backend/tests/ops/test_windmill_contract.py`

External sources: official Windmill documentation at
`https://www.windmill.dev/docs/*`. Specific pages referenced below.

Non-goals for this review:

- Does not attempt to reimplement the spec.
- Does not re-validate the POC run evidence; that was already PASS-verified
  in bd-jxclm.12.
- Does not schedule Windmill infra changes. Any worker-pool or concurrency-
  related recommendation assumes we stay on our current Windmill deployment
  tier unless explicitly noted.

Tool routing exception: `llm-tldr` and `serena` MCP servers were available
in this session but not required — this task is a write-only research
artifact backed by direct `git show` reads and official doc fetches. No
symbol-aware edits to affordabot source were made.

## Windmill Capability Inventory

Each capability is called out with official-doc link and with whether it is
free/OSS-available vs tier-gated. "Tier-gated" means Cloud or Enterprise
Self-Hosted is required per Windmill docs as of April 2026.

### Orchestration primitives (free/OSS)

- **Flows (DAG)** — `https://www.windmill.dev/docs/flows/flow_editor`.
  Flow = ordered step graph. Steps can be scripts (TS/Python/Go/Bash), flow
  references, or subflows. Each step gets its own inputs, outputs, logs,
  retry policy, and timeout.
- **Branch one / Branch all** —
  `https://www.windmill.dev/docs/flows/flow_branches`. Conditional
  branching on JS expressions; parallel "branch all" with per-branch
  "skip on failure".
- **For loops and while loops** —
  `https://www.windmill.dev/docs/flows/flow_loops`. Parallel or sequential,
  with early-stop/break and early-return.
- **Per-step retries with constant + exponential backoff** —
  `https://www.windmill.dev/docs/flows/retries`. Both constant and
  exponential retries are per-step. Static attempts run before exponential
  attempts if both are configured. Retries are per-step only — flow-level
  retry needs to be modeled as either an outer flow or a `branch one` loop.
- **Continue on error** — same page. After retries are exhausted, a step
  can be configured to pass the error object downstream instead of
  failing the whole flow. This is the primary mechanism for "run partial
  on failure" without inventing a protocol in the JSON body.
- **Step timeouts** — `https://www.windmill.dev/docs/flows/flow_settings`.
  Per-step custom timeout in addition to the instance default.
- **Early stop / early return** — same page. First-class flow exit.
- **Flow-level error handler** —
  `https://www.windmill.dev/docs/flows/flow_error_handler`. A designated
  flow step runs when any step errors, receives the error object, and
  owns recovery/alerting logic.
- **Suspend / approval / prompts (human-in-the-loop)** —
  `https://www.windmill.dev/docs/flows/flow_approval`. Flow is paused until
  N approvers hit a resume URL, or optionally times out. Supports restricted
  approver groups, forms, and "continue on disapproval".
- **Caching** —
  `https://www.windmill.dev/docs/core_concepts/caching`. Per-step cache by
  input hash for a configurable TTL. This is the native idempotency story
  for "same inputs -> skip work".
- **Step mocking** — first-class for tests, per
  `https://www.windmill.dev/docs/flows/flow_editor`.
- **Run history, logs, labels, inputs/outputs, operator replay** —
  `https://www.windmill.dev/docs/core_concepts/jobs`. Every step run has an
  addressable job id, inputs, outputs, logs, and replay/rerun affordances.

### Scheduling (free/OSS)

- **Cron schedules** —
  `https://www.windmill.dev/docs/core_concepts/scheduling`. Uses croner;
  supports seconds field and advanced modifiers. Schedules can be attached
  to a script or flow. Each flow can have one "primary" schedule plus any
  number of "other" schedules via the Schedules menu.
- **Schedule-level error handler and recovery handler** — same page.
  Pre-packaged Slack and Teams handlers. "Recovery" handler specifically
  fires when a schedule resumes from an errored state — this is a built-in
  way to emit "pipeline is back" alerts we currently would hand-roll.
- **Dynamic skip validation** — conditional skip logic on each tick
  without editing the cron expression.

### Triggers beyond cron

- **Webhooks / HTTP routes** — `https://www.windmill.dev/docs/core_concepts/webhooks`
  and `https://www.windmill.dev/docs/core_concepts/http_routing`. Free/OSS.
- **Postgres triggers (logical replication)** —
  `https://www.windmill.dev/docs/core_concepts/postgres_triggers`.
  **Not available on Windmill Cloud** per docs; requires self-host with
  `wal_level=logical`, sufficient `max_wal_senders` / `max_replication_slots`,
  and publication config. Important constraint for any "fire flow when a
  row appears" pattern.
- **Kafka / NATS / MQTT / WebSocket / Email / Object store triggers** —
  `https://www.windmill.dev/docs/core_concepts/triggers`. Most are EE-
  gated; treat as not available until we verify our deployment tier.

### Resources, secrets, integrations (free/OSS)

- **Resources + Resource Types** —
  `https://www.windmill.dev/docs/core_concepts/resources_and_types`.
  Postgres and S3-compatible (MinIO, R2) resource types are preloaded.
  Resources are JSON Schema-typed, path-scoped, and passable as typed
  script parameters.
- **Variables and Secrets** — same page. `$var:<NAME>` substitution in
  resources, workspace-scoped, encrypted at rest.
- **Workspace Object Storage** —
  `https://www.windmill.dev/docs/core_concepts/persistent_storage/large_data_files`.
  Workspace-level S3 connection so scripts can read/write files without
  handling credentials. Free tier has UI limits (20 files per directory in
  the browser, 50 MB upload via UI). Direct API use is unconstrained. This
  matters when deciding if Windmill scripts should touch MinIO directly.
- **S3 streaming for large queries** and **instance object storage cache** —
  flagged as EE-only by docs.

### Concurrency and rate-limit control

- **Per-script / per-flow / per-step concurrency limits, per-key queuing** —
  `https://www.windmill.dev/docs/core_concepts/concurrency_limits`.
  **Enterprise/Cloud-gated per docs.** On OSS self-host this feature is
  not available; we must treat "one flow instance at a time" as a
  backend-owned invariant (or accept over-run), not as a Windmill-owned
  one. This is a blocking constraint on any plan that would remove the
  backend's own in-flight lock.

## Current Affordabot Usage Gap Analysis

### What we already use

From `ops/windmill/README.md` and `ops/windmill/f/affordabot/trigger_cron_job.py`:

- Windmill triggers shared-instance cron endpoints on the backend over
  HTTPS with `CRON_SECRET` auth and `X-PR-CRON-SOURCE`.
- `trigger_cron_job.py` is the single shim used by every cron flow,
  which means:
  - Slack alerting lives in that shim as Python code.
  - Retry/backoff is effectively zero at the Windmill layer — a single
    HTTP POST, and any 4xx/5xx bubbles up and the flow fails.
  - "Observability" is `print()` plus a Slack webhook.
- Flow wrappers exist as `f/affordabot/*__flow/flow.yaml` plus
  `*.schedule.yaml` pairs — one flow per cron endpoint.
- `backend/tests/ops/test_windmill_contract.py` enforces that these
  wrappers keep calling the shared trigger script and that the required
  variables remain declared.

This is fine as a migration shim out of Railway Cron. It is not "using
Windmill as an orchestrator." It's "using Windmill as a cron that also
posts to Slack."

### What we are rebuilding or planning to rebuild

Cross-referencing PR #415 against the capability inventory:

| Spec element | Windmill-native feature we are rebuilding |
| --- | --- |
| `pipeline_steps.status` / `started_at` / `finished_at` / `error_code` / `error_detail` / `alerts` columns | Windmill job/step history (every run, every step, every retry attempt already stores these) |
| `retryable`, `max_retries`, `retry_after_seconds` advisory fields in response | Windmill per-step retry policy (constant + exponential backoff), step timeouts |
| `status: partial` / `skipped` / `in_progress` plus "Windmill should poll" | Windmill `continue on error`, `suspend` / resume URL, and subflow polling patterns |
| `next_recommended_step` advisory field | Windmill flow graph is already the explicit step graph |
| `freshness_gate` as a dedicated backend step | Can stay backend-owned, but Windmill's `branch one` + `continue on error` already models "skip or alert" cleanly without a custom response protocol |
| Manual rerun as a separate Windmill flow `pipeline_retry_step` plus backend reconciliation | Native per-job **replay/rerun** from Windmill run history; flow-level early return |
| Backend-authored Slack alerts delivered through response `alerts[]` | Flow-level error handler + schedule-level recovery handler, both already Slack/Teams aware |
| Operator overrides baked into manifest JSON with named policies | Suspend/approval steps with forms for explicit overrides, audited per run |
| `stale_backed` flag in `pipeline_steps` to signal "degraded but succeeded" | Data still belongs in the backend (domain state), but degraded-but-succeeded is *also* a concept Windmill can express via continue-on-error + operator-visible labels |

None of these are wrong to store; the issue is that the spec is using
`pipeline_steps` as *both* the domain ledger *and* as an operator-visible
run log. The second job is Windmill's by construction. If we keep
`pipeline_steps` for domain state only, we shed about half the fields, and
operators get a better view of pipeline runs in the Windmill UI than they
would from a backend-owned table we'd have to build a UI for.

### What is not rebuilt, but is still under-used

- No current flow uses **branches**. All logic is linear HTTP POSTs.
- No current flow uses **retries** at the Windmill layer. We instead
  catch `requests.RequestException` and fail loudly, which means a
  single transient 502 from Railway kills a daily run.
- No current flow uses **approvals**. Manual substrate expansion uses a
  manifest JSON but no human-in-the-loop checkpoint; operators cannot
  gate "look at what we found, then promote."
- No current flow uses **caching**. Every re-run pays for the same
  search/fetch work unless the backend short-circuits via its own
  domain state.
- No current flow uses **Postgres triggers** (and we should not assume
  they are available without first confirming deployment tier).
- No current flow uses **workspace S3**. All MinIO reads/writes go
  through the backend, which the spec codifies ("Windmill should not
  delete objects directly"). This is the right call; see RACI below.

## Revised Architecture Recommendation

### One-sentence version

Keep the "Windmill calls backend endpoints, backend owns all domain
writes" rule from the spec, but rewrite the Windmill flow as a real
DAG — with branches, retries, error handlers, caching, and a suspend
checkpoint for operator promotion — and trim `pipeline_steps` down to
*domain* state so it does not duplicate Windmill's run history.

### Longer version

The spec's core invariant is correct and should stay:

> Windmill never writes `sources`, `raw_scrapes`, `document_chunks`,
> review tables, or pipeline domain tables. The backend owns auth,
> idempotency, policy, artifact writes, and final product state.

Inside that invariant there is still a lot of Windmill to use. The
revised split is:

- **Windmill flow** is the explicit step graph. Each step is one
  backend HTTP call. Steps are wired with retries (exponential backoff
  with small base, capped attempts), per-step timeouts, `continue on
  error` only where the downstream steps are safe to run on partial
  upstream state, and a flow-level error handler that emits a
  backend-authored alert. Schedules get a Windmill-native recovery
  handler so "pipeline is back after an outage" alerts are free.
- **Backend endpoints** stay small, idempotent, and synchronous.
  Every endpoint owns one domain decision and returns a *minimal*
  status: `succeeded`, `failed`, `skipped`, or `stale_backed`. It
  does not hand retry advice back to Windmill — retry is a Windmill
  flow concern. It does carry an error *classification* so the flow
  can branch between "transient, let Windmill retry" and "non-
  retryable, go straight to error handler". Operator summaries are
  still returned for Slack, but are authored in the backend because
  they reference domain evidence.
- **`pipeline_runs`** stays — it is the durable domain anchor that
  links Windmill run ids to jurisdiction/family coverage decisions
  and to artifact lineage.
- **`pipeline_steps`** shrinks. It loses orchestration-mirror columns
  (`started_at`, `finished_at`, `retryable`, `max_retries`,
  `retry_after_seconds`, most of `alerts` jsonb). It keeps *domain*
  columns (`run_id`, `step_key`, `idempotency_key`, `manifest_hash`,
  `status`, `freshness_policy`, `latest_success_at`, `max_stale_hours`,
  `stale_backed`, `decision_reason`, `error_code`, `artifact_manifest`).
  It gains `windmill_job_id` so the row can cheaply link out to the
  full run log in Windmill instead of mirroring it.
- **`search_result_snapshots`** stays — it is irreplaceable domain
  evidence. It gets a `windmill_run_id` FK-like pointer for the same
  reason.
- **`content_artifacts`** stays — MinIO lineage is the POC's core
  proof and is the right shape. See table-by-table section.

### Why not let Windmill write to Postgres directly

Three reasons, in order:

1. **Tier risk.** Concurrency limits, Postgres triggers, S3 streaming,
   and instance caches are all either Cloud or EE-gated. If we let
   Windmill scripts hold logic that depends on those features, we
   silently couple our orchestrator choice to a paid tier. Backend-
   owned writes keep the whole product runnable on a plain self-hosted
   Windmill.
2. **Blast radius.** If a Windmill script bug writes malformed rows
   into `sources` or `document_chunks`, we have no unit tests between
   it and the table. Keeping writes in the backend means the same
   SQLAlchemy models, constraints, and tests that every other code
   path exercises.
3. **Auth and audit.** The backend already has `CRON_SECRET`,
   `X-PR-CRON-SOURCE`, and request-level audit. Windmill has its own
   RBAC but no per-request domain audit. Dual paths mean dual audit.

### Why let Windmill do more orchestration

Three reasons, in order:

1. **Retries and backoff that actually work.** A single Railway
   restart today breaks a daily flow; exponential-backoff retries
   at the step level fix that without any backend change.
2. **Operator UX.** Windmill already renders a step graph, logs,
   inputs/outputs, and a re-run button per step. Every hour we spend
   building a `pipeline_runs/{id}/report` viewer is an hour rebuilding
   the Windmill run page. The report endpoint can stay (for cross-
   linking and for Slack summaries), but it does not need to become
   the primary operator surface.
3. **Human-in-the-loop.** Suspend/approval gives us a native
   "operator promotes this candidate set" step without writing a new
   UI. For MVP that covers the "promotion deferred" cutout the spec
   already called out.

## RACI Table

"R = responsible / executes, A = accountable / owns the boundary,
C = consulted, I = informed."

| Concern | Windmill | Affordabot backend | Postgres/MinIO | Operator |
| --- | --- | --- | --- | --- |
| Cron schedule + timezones | R/A | I | - | I |
| DAG shape / step ordering | R/A | C | - | I |
| Per-step retry + backoff + timeout | R/A | C | - | I |
| Step mocking in tests | R | C | - | - |
| Run history / step logs / re-run UI | R/A | I | - | R (read) |
| Schedule error + recovery handlers | R/A | C | - | I |
| Flow-level alerts (orchestration health) | R/A | C | - | I |
| Domain alerts (stale fallback, zero result) | C | R/A | - | I |
| Manifest parsing + contract version gate | C | R/A | - | - |
| Idempotency key enforcement | I | R/A | R | - |
| Freshness policy parameters + named policies | - | R/A | - | C |
| Source trust / promotion decisions | - | R/A | R | C |
| `sources` / `document_chunks` / review queue writes | - | R/A | R | - |
| `pipeline_runs` / `pipeline_steps` writes | - | R/A | R | - |
| `search_result_snapshots` writes | - | R/A | R | - |
| `content_artifacts` row writes | - | R/A | R | - |
| MinIO object writes (raw/fetch/extract/report) | - | R/A | R | - |
| MinIO object purge (retention) | R (trigger) | R/A (execute) | R | - |
| Suspend / approval gates for promotion | R/A | C (returns context) | - | R (acts) |
| Manual rerun a single step | R/A | R (execute) | R | R (decides) |
| Rollback to old cron path | R (disable schedule) | R (execute old cron) | - | R (decides) |

Key deltas from the spec's implicit RACI:

- Retry ownership moves from "backend declares retry metadata,
  Windmill obeys" to "Windmill owns retry from flow definition,
  backend classifies errors so Windmill can branch." Simpler contract,
  fewer new fields, and uses a Windmill feature that already exists.
- Operator rerun moves from "Windmill calls `pipeline_retry_step`"
  to "operator uses Windmill's native per-step replay." The
  `pipeline_retry_step` flow is deferred unless we hit a real gap.
- Approval gates are a Windmill concern with a backend data feed;
  the spec currently has no approval gate at all.

## Recommended Endpoint Contract Shape

Trim the spec's proposed request/response down to what the backend
genuinely owns. Drop any field that is a second-order copy of
Windmill's own state.

Request (every mutating step):

```json
{
  "contract_version": "1.0.0",
  "run_id": "uuid",
  "step_key": "search_materialize",
  "idempotency_key": "run_id:step_key:manifest_hash",
  "manifest_hash": "sha256:...",
  "trigger_source": "windmill:f/affordabot/pipeline_daily_refresh",
  "windmill_job_id": "01JABC...",
  "manifest": {}
}
```

Response (every mutating step):

```json
{
  "contract_version": "1.0.0",
  "status": "succeeded | skipped | stale_backed | failed",
  "error_class": "none | transient | policy_violation | contract_mismatch | upstream_missing",
  "run_id": "uuid",
  "step_key": "search_materialize",
  "counts": {
    "created": 0,
    "reused": 0,
    "failed": 0
  },
  "artifact_paths": [],
  "domain_alerts": [],
  "operator_summary": "plain English summary",
  "stale_backed": false,
  "decision_reason": "fresh | latest_good_within_policy | hard_stale_ceiling | zero_results"
}
```

Removed vs spec:

- `retryable`, `max_retries`, `retry_after_seconds`. Retries are a
  flow concern; backend tells the truth about whether the error is
  transient via `error_class`.
- `in_progress` status. Long-running work should either run
  synchronously inside the backend step or use a Windmill
  suspend/resume pattern, not a polling loop in JSON.
- `next_recommended_step`. The flow graph is the step graph. If the
  backend wants to signal "skip the next step", use
  `status: skipped` + `decision_reason`, branch in Windmill.
- `alerts[]` as orchestration-health messages. Keep `domain_alerts[]`
  for data-quality alerts authored by the backend (e.g., "3 consecutive
  stale fallbacks") — those still belong to the backend because they
  cite domain evidence. Orchestration-health alerts (HTTP errors,
  timeouts) belong in Windmill's flow-level error handler and
  schedule-level recovery handler.

Kept vs spec:

- `contract_version` gate. The spec's rationale here is sound and
  survives unchanged.
- `idempotency_key` + `manifest_hash`. This is the bit Windmill cannot
  own on our behalf without leaking domain logic. Keep.
- `operator_summary` and `counts`. These feed Slack and the
  report endpoint regardless of whether Windmill owns the run UI.

## Recommended Windmill Flow Shape

Pseudo-flow for `f/affordabot/pipeline_daily_refresh` under the revised
architecture:

```text
flow pipeline_daily_refresh
  step create_run
    POST /internal/pipeline/runs
    retry: constant 2 attempts / 30s
    timeout: 30s
    on_error: flow_error_handler
  step search_materialize
    POST /internal/pipeline/search-materialize
    retry: exponential base=30, multiplier=2, max=4
    timeout: 15m
    continue_on_error: false
  step freshness_gate
    POST /internal/pipeline/freshness-gate
    retry: constant 2 attempts / 30s
    timeout: 1m
  branch_one on results.freshness_gate.status
    when "skipped":
      early_return "nothing fresh to do"
    when "stale_backed":
      step record_stale_alert (backend-authored domain alert)
      continue to read_fetch
    default:
      continue to read_fetch
  step read_fetch
    POST /internal/pipeline/read-fetch
    retry: exponential base=60, multiplier=2, max=4
    timeout: 30m
    continue_on_error: true   # downstream can still extract partial results
  step extract
    POST /internal/pipeline/extract
    retry: exponential base=30, multiplier=2, max=3
    timeout: 20m
  step embed
    POST /internal/pipeline/embed
    retry: exponential base=30, multiplier=2, max=3
    timeout: 30m
  step report
    GET /internal/pipeline/runs/{run_id}/report
    retry: constant 2 / 30s
    timeout: 30s
  flow_error_handler
    POST /internal/pipeline/runs/{run_id}/mark-failed
    then Slack alert (workspace SLACK_WEBHOOK_URL, reuses existing pattern)
schedule:
  cron: "0 5 * * *"
  timezone: UTC
  recovery_handler: Slack "pipeline recovered"
```

Design notes:

- Every retry policy lives in the Windmill flow, not in the response
  body. We pick conservative values (small base, bounded attempts,
  per-step timeout) so a flaky network does not destroy a daily run
  and so a runaway step cannot hold a worker hostage.
- `freshness_gate` uses `branch_one` on a backend-owned `status`
  value. The branch itself is declared in flow code; the *decision*
  remains backend-owned. No business logic moves to the flow.
- `read_fetch` uses `continue_on_error: true`. Partial fetch is a
  known-safe state for `extract` and `embed` because artifacts are
  hashed and reusable. This replaces the spec's `status: partial`
  polling story with a native Windmill feature.
- `flow_error_handler` calls a backend endpoint so the domain state
  transitions to a "run failed at <step>" row. The Slack alert then
  happens in the error handler script, not in every step.
- The existing `trigger_cron_job.py` shim can remain as the HTTP
  primitive used by each step, so we do not have to rewrite the
  Slack normalization + auth logic. It just runs per step, not per
  run.

An additional manual flow `f/affordabot/pipeline_promote_candidates`
should use **suspend/approval** between "show me what the daily run
found" and "write to review queue / promote". This is where the
spec's deferred promotion boundary can land natively.

## Table-by-Table Recommendation

### `pipeline_runs`

Keep essentially as spec'd. Small additions:

- `windmill_flow_path` TEXT — which flow triggered this run
  (`f/affordabot/pipeline_daily_refresh`).
- `windmill_run_id` TEXT — the Windmill job id of the top-level flow
  run, for cross-linking from Slack/operator report back to the
  Windmill UI.
- Drop `summary` free-text (migrate to an `operator_summary`
  materialized in report artifact) only if storage budget matters;
  not strictly necessary for MVP.

### `pipeline_steps`

Shrink. Rationale: Windmill's run history is the authoritative
orchestration log; duplicating it is cost without benefit.

Keep:

- `id`, `run_id`, `contract_version`, `step_key`, `idempotency_key
  unique`, `manifest_hash`, `status`, `freshness_policy`,
  `latest_success_at`, `max_stale_hours`, `stale_backed default false`,
  `decision_reason`, `error_code`, `artifact_manifest jsonb`.

Drop or move:

- `started_at`, `finished_at`: covered by Windmill job history.
  Keep only if we need it for long-horizon analytics; if so, keep
  `finished_at` only.
- `retryable`, `max_retries`, `retry_after_seconds`: not a backend
  concern anymore.
- `error_detail`: move to `error_payload jsonb` only if we need
  structured parse; otherwise drop and link to Windmill job log via
  `windmill_job_id`.
- `alerts jsonb`: rename to `domain_alerts jsonb`, keep only
  backend-authored domain alerts (stale fallback, zero-result). Flow
  health alerts do not belong here.

Add:

- `windmill_job_id TEXT` — cheap link to the step's Windmill job log.

### `search_result_snapshots`

Keep exactly as spec'd. This is domain evidence that has no
Windmill analogue; the POC already validates this shape end-to-end.
No changes recommended for MVP.

### `content_artifacts`

Keep essentially as spec'd. Minor recommendations:

- Accept that workspace S3 on Windmill free tier has UI limits (20
  files per dir, 50 MB UI upload cap). Writes stay in the backend
  regardless, so the UI cap does not block us. However:
- MVP should keep object layout under `pipeline-runs/<run_id>/...`
  so that the operator browser (when used) hits *per-run* subdirs
  of size <20 most of the time. This is a cheap precaution that
  costs nothing.
- Add `windmill_job_id TEXT NULL` to artifact rows so an operator
  reading an artifact can jump back to the exact step run. Nullable
  because the purge job and backfill jobs also write artifacts.

No change to retention defaults; spec's retention table is
reasonable.

## Concrete Edits to PR #415

The following are the minimum changes to bring the spec in line with
this review without expanding scope.

1. **Replace the retry-advice response fields** (`retryable`,
   `max_retries`, `retry_after_seconds`) with `error_class`. Document
   that retries live in the Windmill flow definition. Remove
   `in_progress` as a backend-returned status.
2. **Remove `next_recommended_step`** from both the contract and the
   rationale. Add one sentence: "The Windmill flow graph is the step
   graph; backend returns `status` + `decision_reason` and the flow
   branches on it."
3. **Rename `alerts` to `domain_alerts`** in the response and in
   `pipeline_steps` to make it explicit that orchestration-health
   alerts do not live on the response.
4. **Trim `pipeline_steps` schema** per the table-by-table section:
   drop `retryable`, `max_retries`, `retry_after_seconds`, and the
   two timestamps if not needed; add `windmill_job_id`.
5. **Add `windmill_flow_path` and `windmill_run_id`** to
   `pipeline_runs`. Add `windmill_job_id` to `content_artifacts`
   (nullable).
6. **Add a Windmill Flow Shape section** to the spec that commits to
   at least:
   - per-step exponential retries (numbers can be placeholders)
   - per-step timeouts
   - a flow-level error handler
   - at least one `branch_one` on backend `status`
   - a schedule-level recovery handler
   - no `pipeline_retry_step` flow in MVP; native Windmill rerun
     is sufficient
7. **Add a "Windmill tier constraints" sub-section** to Risks. It
   should list: concurrency limits are tier-gated, Postgres triggers
   are not available on Cloud, workspace S3 has free-tier UI caps.
   It should explicitly say we do not depend on any of those for
   MVP. This closes the "what if our deployment tier changes"
   audit question.
8. **Update the execution phases**. Phase 7 (`Windmill Flow
   Orchestration`) should add: "use native Windmill retries, error
   handlers, branching, caching, and suspend/approval where they
   map cleanly; do not reimplement those features in backend
   scripts or response bodies."
9. **Replace the manual `pipeline_retry_step` bullet** in the Beads
   structure with either a deletion or a down-scoping note that
   Windmill's per-step rerun covers the MVP case. If we want a
   dedicated flow later for repair semantics, promote it to its
   own Beads subtask.
10. **Amend the completion-proof list** to include: "a Windmill run
    page link is embedded in the operator report" and "the daily
    schedule has a Slack recovery-handler firing after a simulated
    outage."

None of these edits changes the four-table MVP, breaks the POC, or
expands scope beyond what the consultant review at PR #416 already
accepted.

## Concrete New / Changed Beads Subtasks

Proposed:

- **bd-jxclm.1a (amendment)**: apply edits 1–10 above to the spec
  at `docs/specs/2026-04-11-windmill-driven-persisted-pipeline.md`.
  Owner: whoever picks up bd-jxclm.13 follow-up.
- **bd-jxclm.14 (new, follow-on POC)**: Windmill-maximal POC. Take
  the existing San Jose POC (bd-jxclm.12) and prove the native
  Windmill retries, branch_one, flow error handler, schedule
  recovery handler, and one suspend/approval gate against a small
  jurisdiction. Acceptance criteria below.
- **bd-jxclm.9 (scope tweak)**: Windmill orchestration flows task
  should explicitly include "use native retries / error handler /
  branch_one / caching" rather than "call backend endpoints". The
  current wording lets an implementer ship the thin-HTTP shape by
  accident.
- **bd-jxclm.2 (scope tweak)**: shrink `pipeline_steps` to the
  domain-only column set before the first migration lands. It is
  significantly cheaper to not add columns now than to drop them
  once backend code depends on them.
- **bd-jxclm.promotion (deferred)**: promote-candidates flow with a
  suspend/approval gate. Not MVP. Tracked separately so it does not
  quietly become MVP creep.

No existing Beads subtask needs to be deleted; this review recommends
scope trims, not scope deletions.

## Hands-On POC Plan (proposed `bd-jxclm.14`)

Goal: prove that a Windmill-maximal flow can drive the existing
San Jose vertical slice with native retries, branches, error handler,
and recovery handler, without moving any domain logic into Windmill
scripts.

Artifacts:

- a committed flow under `ops/windmill/f/affordabot/pipeline_sj_poc/flow.yaml`
- a schedule `pipeline_sj_poc.schedule.yaml`
- a contract test extension in
  `backend/tests/ops/test_windmill_contract.py` asserting that the
  new flow references the shared trigger script and declares the
  required retries / error handler
- a POC report at
  `backend/artifacts/poc_windmill_maximal_pipeline/report.md`

Scope:

- one jurisdiction (Saratoga CA or reuse the San Jose slice)
- one source family (meetings)
- five flow steps: create_run, search_materialize, freshness_gate,
  read_fetch, extract
- *no* ingestion to production pgvector from the POC flow
- backend endpoints from bd-jxclm.3 (or local stubs pointing at the
  bd-jxclm.12 POC service) so we do not block on full backend impl

Acceptance criteria:

1. Baseline run: flow completes successfully end to end with all
   five steps green in the Windmill UI.
2. Transient failure drill: inject a 503 from the backend on
   `read_fetch`; Windmill retries and the flow eventually succeeds.
   Windmill run history shows the retry attempts distinctly.
3. Non-retryable failure drill: inject a `contract_mismatch`
   `error_class`; flow does not retry and the flow-level error
   handler fires a Slack alert.
4. Freshness skip drill: force `freshness_gate` to return
   `skipped`; `branch_one` short-circuits the flow with
   `early_return` and no downstream writes happen.
5. Stale-backed drill: force `freshness_gate` to return
   `stale_backed`; flow proceeds, backend records the domain alert,
   and the operator report includes the stale-backed evidence.
6. Recovery handler drill: disable the schedule, re-enable after a
   simulated outage, and observe a Slack recovery message.
7. Re-run a single step from the Windmill UI; the backend idempotency
   key prevents duplicate artifact creation.
8. No flow step contains Python code beyond the existing
   `trigger_cron_job.py` shim and its error-handler counterpart.
9. No domain table write happens from Windmill code.

This POC is a direct successor to bd-jxclm.12 and should re-use its
POC tables / service layer to keep the blast radius small.

## Risks, Unknowns, and Plan-Tier Constraints

### Tier-gated Windmill features

Confirmed tier-gated in docs (April 2026):

- Concurrency limits (per-path / per-key queuing): **Cloud or EE
  only**. Mitigation: do not depend on Windmill concurrency limits
  in MVP. Continue to enforce "one pipeline run per jurisdiction" in
  the backend via `pipeline_runs` + `idempotency_key` uniqueness.
- Postgres triggers (logical replication → flow): **not on Cloud**.
  Self-host requires `wal_level=logical` and publication config.
  Mitigation: do not use Postgres triggers in MVP at all. Cron +
  webhook-triggered reruns cover every spec'd use case.
- S3 streaming for large queries and instance cache: **EE only**.
  Mitigation: backend streams MinIO via boto3, not Windmill.

### Workspace S3 free-tier limits

- Free tier caps: 20 files per directory in the UI browser, 50 MB
  per UI upload. Mitigation: keep MinIO writes in the backend
  (they already are per the spec), and keep object layout one
  run deep so the UI remains usable for operator debugging.

### Retries ≠ idempotency

- Windmill retries are per-step only; they fire on any error unless
  the flow also marks the step `continue_on_error`. Idempotency is
  entirely a backend responsibility. We already have
  `idempotency_key UNIQUE` in the spec; nothing more to do here.

### Flow-level retries

- Windmill does not have a built-in "retry the whole flow" knob.
  If we want run-level retries we model them as an outer flow that
  `for`-loops the inner one N times with `continue_on_error`.
  Decision: do not do this in MVP. Step-level retries cover
  transient failures. Run-level retries are an operator decision
  and should go through explicit rerun.

### Suspend/approval blocks flow slots

- Flows in suspended state occupy Windmill queue state. If we wire
  suspend/approval into the daily cron, operator inattention will
  leave flows hanging. Mitigation: put approval in the *manual*
  promote flow only, not in the daily pipeline. Use a default
  timeout on the approval step so forgotten approvals cancel
  cleanly.

### Failure mode: "Windmill becomes a second backend"

- Already called out in the spec. This review reinforces the
  mitigation: every Windmill step should remain a thin HTTP call.
  Any time a flow needs a conditional beyond `branch_one`/`for`, we
  write the conditional in the backend and return a status. The
  flow never sees a raw business rule.

### Unknowns this review did not resolve

- **Windmill deployment tier**. This review assumes OSS self-host
  with no EE features. If our deployment is actually Pro
  Self-Hosted / Cloud, we get concurrency limits and Postgres
  triggers for free and should reconsider a few decisions (e.g.,
  we could cheaply enforce "only one pipeline_daily_refresh in
  flight at a time" at Windmill level). Action: add a
  `bd-jxclm.13-followup` note asking an operator to confirm tier
  before bd-jxclm.9 is closed.
- **Long-step behavior under Railway restarts**. If a backend step
  runs for 30 minutes and Railway restarts mid-step, the POC did
  not test Windmill's response. Recommended to cover in the POC
  acceptance criteria above.
- **Contract-version rollout story**. The spec says fail closed on
  major mismatch, but does not specify how we roll the backend
  version forward while Windmill flows are still on the old one.
  Out of scope for this review, but worth calling out as a Phase 7
  followup.

## Sources

Windmill docs:

- `https://www.windmill.dev/docs/flows/flow_editor`
- `https://www.windmill.dev/docs/flows/flow_branches`
- `https://www.windmill.dev/docs/flows/flow_loops`
- `https://www.windmill.dev/docs/flows/retries`
- `https://www.windmill.dev/docs/flows/flow_settings`
- `https://www.windmill.dev/docs/flows/flow_error_handler`
- `https://www.windmill.dev/docs/flows/flow_approval`
- `https://www.windmill.dev/docs/core_concepts/scheduling`
- `https://www.windmill.dev/docs/core_concepts/jobs`
- `https://www.windmill.dev/docs/core_concepts/triggers`
- `https://www.windmill.dev/docs/core_concepts/webhooks`
- `https://www.windmill.dev/docs/core_concepts/http_routing`
- `https://www.windmill.dev/docs/core_concepts/postgres_triggers`
- `https://www.windmill.dev/docs/core_concepts/concurrency_limits`
- `https://www.windmill.dev/docs/core_concepts/caching`
- `https://www.windmill.dev/docs/core_concepts/resources_and_types`
- `https://www.windmill.dev/docs/core_concepts/persistent_storage/large_data_files`

Affordabot source:

- `docs/specs/2026-04-11-windmill-driven-persisted-pipeline.md` (PR #415)
- `backend/services/persisted_pipeline_poc.py` (PR #417)
- `backend/scripts/verification/poc_sanjose_persisted_pipeline.py` (PR #417)
- `backend/artifacts/poc_sanjose_persisted_pipeline/report.md` (PR #417)
- `ops/windmill/README.md` (master)
- `ops/windmill/f/affordabot/trigger_cron_job.py` (master)
- `backend/tests/ops/test_windmill_contract.py` (master)
