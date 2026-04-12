# Windmill Maximal Orchestration Review

## Executive Verdict

**VERDICT: REVISE_PLAN** (Move to `ALL_IN_NOW` on Windmill)

Affordabot is currently under-utilizing Windmill's capabilities, leading to the NIH (Not Invented Here) re-implementation of a DAG orchestrator in the backend Postgres schema. We must lean fully into Windmill for control-plane orchestration (retry loops, flow states, history) while strictly reserving the backend for data-plane execution (auth, domain tables, freshness policies, source of truth).

## Windmill Capability Inventory

| Capability | Windmill Native | Official Documentation |
| --- | --- | --- |
| Flow / DAG Graph | Yes (Flows, YAML/JSON graphs) | [Windmill Flows](https://www.windmill.dev/docs/flows) |
| Branching & Loops | Yes (Conditional edges, for-loops, map-reduce) | [Control Flow](https://www.windmill.dev/docs/flows/control_flow) |
| Retries & Backoff | Yes (Step-level retries natively supported) | [Retries](https://www.windmill.dev/docs/flows/retry) |
| Error Handlers | Yes (Flow-level and step-level catch blocks) | [Error Handlers](https://www.windmill.dev/docs/flows/error_handlers) |
| Suspend & Approve | Yes (Approvals, sleep, Wait for Webhook) | [Approvals & Suspend](https://www.windmill.dev/docs/flows/suspend) |
| Step Timeouts | Yes (Timeouts defined per step) | [Step Settings](https://www.windmill.dev/docs/flows) |
| Run History & Logs | Yes (Granular execution history per step) | [Observability](https://www.windmill.dev/docs/observability) |
| Concurrency / Queues | Yes (Worker tags, concurrency limits per script) | [Concurrency](https://www.windmill.dev/docs/workers) |
| Schedule & Cron | Yes (Schedules with timezone support) | [Schedules](https://www.windmill.dev/docs/schedules) |
| Resumability | Yes (Resume from any failed step) | [Flow State](https://www.windmill.dev/docs/flows/state) |

## Current Affordabot Usage Gap Analysis

In PR #415 and PR #417, the proposed MVP model defines the `pipeline_steps` table with fields like:
`started_at`, `finished_at`, `status`, `retryable`, `max_retries`, `retry_after_seconds`.

This is a direct duplication of Windmill’s native orchestration abilities. Because Windmill inherently tracks when a step starts, finishes, fails, and handles retry executions transparently, tracking these at the backend schema level introduces race conditions between Windmill's DB and Affordabot's DB.

## Revised Architecture Recommendation

### RACI Table

| Responsibility | Windmill Owns | Affordabot Backend Owns | Postgres/MinIO Owns | Human/Operator Owns |
| --- | --- | --- | --- | --- |
| Job Schedule & Triggers | **A/R** | C | I | I |
| Retries, Backoffs, Timeouts | **A/R** | C | I | I |
| Concurrency & Worker Queues | **A/R** | I | I | I |
| Flow Graph & Branching Logic | **A/R** | C | I | I |
| Step & Run Execution Logs | **A/R** | I | I | I |
| Domain Auth & Validation | I | **A/R** | I | I |
| Idempotency against Duplicate Data | I | **A/R** | C | I |
| Freshness Policy & Stale Logic | I | **A/R** | C | I |
| Artifact Lineage & Persistence | I | **A/R** | **A/R** | I |
| Final Product / Domain State | I | **A/R** | **A/R** | I |
| Approvals / Rerun Decisions | C | I | I | **A/R** |

*(A/R = Accountable/Responsible, C = Consulted, I = Informed)*

### Core Questions Addressed

**1. What orchestration features are we currently rebuilding or planning to rebuild that Windmill already provides?**
`pipeline_steps` tracks execution times, retry status, `retry_after_seconds` and general state-machine status (`in_progress`, `failed`, `succeeded`). Windmill natively provides granular logs, retry behavior, and terminal status execution.

**2. What should move from affordabot backend code into Windmill flow configuration?**
All logic dictating "if step fails, wait 300s and retry 3 times". The backend should merely throw a 429 or 500 error, and the Windmill step itself should be configured natively in YAML to handle the retry. The flow should natively branch between "search", "read", and "promote" steps in its DAG rather than a monolithic backend script coordinating sub-steps.

**3. What should stay in affordabot backend no matter how powerful Windmill is?**
Auth, data normalization, freshness enforcement (evaluating cache hits), artifact MinIO uploads, idempotency hashing to prevent destructive duplicate runs, and semantic reasoning (domain logic).

**4. Should Windmill write directly to affordabot Postgres/MinIO, or only call backend endpoints? Explain tradeoffs.**
**Only call backend endpoints.**
*Tradeoff:* Direct writes from Windmill save HTTP overhead, but completely couple our schema, data validation, and logic to Windmill scripts. It prevents code re-use (e.g., using the same ingestion pipeline from a standalone script). Endpoints create a strict contract boundary, allowing schema migrations to occur safely behind an API.

**5. Should pipeline_steps remain an affordabot table if Windmill already has job/step history?**
**No.** `pipeline_steps` should be removed entirely. Windmill logs store step history. If an audit-level "Run ID" is needed for lineage, it can be passed natively to `search_result_snapshots` or `content_artifacts` directly using Windmill's intrinsic `run_id`.

**6. What is the cleanest backend response contract for Windmill to branch/retry/alert on?**
A well-structured HTTP response code alongside a minimal JSON payload:
```json
{
  "status": "succeeded",
  "action_taken": "stale_fallback",
  "artifacts_produced": ["artifact_123"],
  "next_recommended_action": "read_fetch"
}
```
Windmill can branch logic via Javascript transitions based on `response.action_taken` or `response.status`, and rely on native HTTP error codes (e.g., 429 Too Many Requests, 503 HTTP) for backoffs.

**7. What should the next Windmill-maximal POC prove?**
It must prove a full `wmill.yaml` Flow definition consisting of three separate steps (Search -> Fetch -> Report), where Windmill natively handles a forced step failure/timeout and seamlessly resumes/retries without the backend managing `pipeline_steps` state tables.

**8. What specific changes should be made to PR #415 and the bd-jxclm task graph?**
- Delete the `pipeline_steps` table.
- Simplify `pipeline_runs` to only store domain-level metadata unsuited for default Windmill logs (e.g., operator notes), or remove it and use Windmill `run_id` as the FK directly on domain tables.
- Remove `retryable`, `max_retries`, and `retry_after_seconds` from the backend contract schema entirely.
- Add tasks to define the YAML graph definition for Windmill rather than python orchestrators.

### Table-by-Table Recommendation

*   **`pipeline_runs`**: Delete. Use Windmill's intrinsic Run tracking for orchestration logs. For domain linkage, just append Windmill's `$run_id` as a string to your domain artifacts.
*   **`pipeline_steps`**: Delete. Fully duplicative of Windmill's step execution engine.
*   **`search_result_snapshots`**: Keep. This holds product-domain caching, not orchestration execution state.
*   **`content_artifacts`**: Keep. Domain-specific storage representation.

### Concrete Edits Recommended for PR #415
*   Remove the "Pipeline steps" schema definition.
*   Update the "Backend Step API" response definition to remove `retryable`, `max_retries`, `retry_after_seconds`.
*   Establish that the Windmill Flow natively handles `wait` and `retry` constraints based on HTTP generic status codes.

### Concrete New/Changed Beads Subtasks

*   **Modify `bd-jxclm.2`**: Remove `pipeline_steps` and `pipeline_runs` from schema migration.
*   **Modify `bd-jxclm.3`**: Implement backend endpoints to be purely stateless functional nodes mapped by `idempotency_key`, lacking internal retry evaluation.
*   **NEW `bd-jxclm.6`**: "Define native Windmill Flow YAML with Step-Level Branches & Retries"

### Hands-on POC Plan with Acceptance Criteria

**Goal**: Build a Windmill YAML flow that drives the `poc_sanjose` backend.
**Steps**:
1. Remove SQLite `pipeline_runs` and `pipeline_steps` from the POC.
2. Build `poc_flow.yaml` orchestrating calls to `search`, then `extract`.
3. Introduce a network disruption in the `extract` step and assert that Windmill's native retry backoff eventually succeeds.
**Acceptance Criteria**:
- Artifacts generated without orchestration-specific SQL tables.
- Windmill UI correctly visualizes the DAG structure.
- Failure of one step successfully halts the DAG and pauses for retry natively.

### Risks, Unknowns, & Self-Hosting Constraints
- **State Limits**: Windmill flow state size limits (fetching massive JSONs inside a Windmill worker memory limit vs keeping payloads small).
- **Concurrency & Queues**: By shifting to Windmill, we must ensure our Self-Hosted Windmill instance has enough generic Workers to avoid queue congestion on massive parallel scrapes.
- **Approvals**: For sensitive actions, Windmill's native Suspend/Approval feature is highly optimal, reducing backend "pending state" logic considerably.

---

## ADDENDUM: Data Moat Grounding and Missing Capabilities

This addendum addresses gaps in the initial review: the affordabot data moat was never explicitly stated, several Windmill capabilities were listed but not applied to affordabot's actual pipeline, and restart/rerun/resume behavior was not researched.

### Affordabot's Data Moat

Affordabot's competitive advantage is **jurisdiction-scoped, provenance-tracked, structurally classified local government data with evidence-gated analysis**. Specifically:

1. **Canonical document identity**: Every raw scrape gets a `canonical_document_key` (deterministic from source_id + document_type + normalized URL or title+date). This enables revision tracking and deduplication across scrape runs — no other system does this for city/county/state government data at scale.

2. **Substrate promotion tiers**: Content is classified into `captured_candidate` / `durable_raw` / `promoted_substrate` based on source trust (`.gov` vs. `legistar.com` vs. unofficial) and substance (real document vs. index page). Only `promoted_substrate` content feeds high-trust analysis.

3. **Jurisdiction-scoped vector retrieval**: Document chunks carry `jurisdiction`, `bill_number`, `source_id` metadata, enabling filtered RAG queries that return only context relevant to a specific jurisdiction. This is what makes affordabot's answers jurisdiction-specific rather than generic web search results.

4. **Evidence-gated analysis**: The 13-step analysis pipeline runs deterministic sufficiency gates before allowing quantified output. If evidence is insufficient, the system falls back to `qualitative_only` and strips all numeric fields. This prevents hallucinated cost-of-living impact estimates.

5. **Evidence provenance**: Every claim in an analysis traces back to a `raw_scrapes` row via `EvidenceEnvelope` objects with explicit provenance (RAG chunk ID, web URL, excerpt, confidence). This is the core differentiator — every number traces to its source.

**Implication for architecture**: Any orchestration change must preserve these five properties. If Windmill's retry logic causes a step to re-execute, the backend's idempotency (via `canonical_document_key` + `content_hash`) must return the existing result. If Windmill's branching causes a step to be skipped, the backend must record that decision in `pipeline_steps`. The moat is in the backend's invariant enforcement, not in Windmill's orchestration.

### Missing Capability: Restart/Rerun/Resume-from-Step

Windmill supports the following recovery behaviors:

| Behavior | How | Doc |
|---|---|---|
| **Batch re-run** | From the Runs UI, select multiple failed/completed jobs and re-run them. Can re-run with original or modified inputs. Scripts can re-run on original or latest version; flows always re-run on latest version. | https://www.windmill.dev/docs/core_concepts/monitor_past_and_future_runs |
| **Rerun single job** | From the run detail page, click "Rerun" to re-execute with same or modified inputs. | Same |
| **Resume from specific step** | Not natively supported in the UI for flows. Windmill flows always start from the beginning. **This is a gap.** | — |
| **Pin/mock step results** | For testing: pin a step's result so it returns a fixed value without executing. | https://www.windmill.dev/docs/flows/step_mocking |
| **Continue on error** | Step-level toggle: error is passed as the step's result, flow continues to next step (enabling branch-based error handling). | https://www.windmill.dev/docs/flows/retries |

**Critical finding: Windmill does NOT support resume-from-step for failed flows.** When a flow fails at step 3 of 5, the only recovery options are:
1. Rerun the entire flow (all steps re-execute)
2. Use step mocking to pin results for already-completed steps, then rerun

For affordabot, this means the backend's idempotency is essential: when Windmill reruns a flow after a mid-pipeline failure, the backend must return existing results for already-completed steps without re-scraping or re-analyzing. The `pipeline_steps` table (with idempotency keys) already enables this.

**Recommendation**: PR #415 should explicitly state that Windmill flow reruns are whole-flow reruns, and that backend idempotency ensures already-completed steps are no-ops. This is not a deficiency — it's the correct pattern for idempotent pipelines. But it must be documented so operators understand why rerunning a "failed" flow completes quickly (steps 1-3 return cached results, step 4 actually re-executes).

### Missing Capability: Postgres Triggers Applied to Affordabot

Windmill can listen to Postgres logical replication streams and trigger flows on INSERT/UPDATE/DELETE. This is **not available on Cloud**, only self-hosted.

**Relevant affordabot use cases**:

1. **New source triggers re-scrape**: When a new `sources` row is inserted (by discovery), a Postgres trigger could immediately queue a scrape flow for that source — instead of waiting for the next daily cron. This would make the pipeline event-driven rather than batch-only.

2. **New legislation triggers analysis**: When a new `legislation` row is inserted with `analysis_status='pending'`, a Postgres trigger could queue an analysis flow. Currently, analysis is triggered manually via API.

3. **Raw scrape completion triggers ingestion**: When a `raw_scrapes` row is updated with `processed=false` (indicating new content), a trigger could queue ingestion. Currently, ingestion is bundled inside the scrape cron jobs.

**Prerequisites**: The affordabot Postgres must have `wal_level = logical` enabled, which requires a restart and increases WAL size by 10-30%. For Railway-hosted Postgres, this may require a configuration change.

**Recommendation**: Do NOT implement Postgres triggers in the initial Windmill-maximal POC. They add operational complexity (WAL config, replication slot management) and the batch cron model works for the current scale. Add Postgres triggers as a follow-up when:
- The pipeline needs sub-hour freshness for high-priority jurisdictions
- The discovery-to-scrape latency (currently up to 24 hours) is unacceptable
- The operator wants to trigger analysis automatically on new legislation

### Missing Capability: Resources, Variables, and Secrets Mapped to Affordabot

Windmill's resources and variables system should hold all configuration that Windmill scripts need:

| Windmill Resource/Variable | Purpose | Current Location |
|---|---|---|
| `affordabot/backend_url` (resource) | Backend API base URL | `BACKEND_URL` env var in trigger_cron_job.py |
| `affordabot/cron_secret` (secret) | Authentication header for cron endpoints | `CRON_SECRET` env var |
| `affordabot/slack_webhook` (secret) | Slack alerting webhook | `SLACK_WEBHOOK_URL` env var |
| `affordabot/postgres` (resource, type: postgres) | Affordabot DB connection (for future Postgres triggers) | Not currently in Windmill |
| `affordabot/jurisdictions` (variable) | Default jurisdiction list | Hardcoded in each cron script |
| `affordabot/pipeline_defaults` (variable) | Default freshness_policy, processing_policy, families | Not currently in Windmill |

**Current gap**: `trigger_cron_job.py` reads all config from environment variables. If the pipeline moves to multi-step flows, each step script needs access to these same values. Using Windmill resources/variables instead of env vars provides:
- Workspace-level versioning and audit trail
- Per-workspace overrides (dev vs. staging vs. prod)
- Type-safe resource references (e.g., postgres resource for trigger setup)

**Recommendation**: Migrate `BACKEND_URL`, `CRON_SECRET`, and `SLACK_WEBHOOK_URL` from env vars to Windmill resources/secrets as part of the trigger_pipeline_step script (bd-jxclm.14).

### Missing Capability: While Loops Applied to Affordabot

Windmill's while-loop step repeats a sub-flow until a predicate expression evaluates to false. Affordabot use cases:

1. **Poll-while-scraping**: Some scrapers (Playwright-based Municode, Granicus video players) are slow and may timeout. A while-loop could poll the backend's ingestion status endpoint until all raw scrapes for a source are marked `processed=true`, with a max iteration count and sleep between iterations.

2. **Retry-while-rate-limited**: If the SearXNG or Z.ai API returns rate-limit responses, a while-loop could back off and retry until the rate limit window expires. However, Windmill's native retry with exponential backoff is a better fit for this case.

**Recommendation**: Do NOT use while-loops in the initial POC. The poll-while-scraping pattern adds complexity and the daily cron model handles this implicitly (scrapes that don't complete in one run are retried the next day). Consider while-loops only for real-time event-driven triggers (e.g., Postgres trigger -> scrape -> poll until processed).

### Missing Capability: Webhooks and HTTP Routes Applied to Affordabot

Windmill supports:
- **Webhook triggers**: Any script/flow can be triggered by an HTTP POST to a unique URL
- **HTTP routes**: Custom HTTP endpoints that execute a script and return the result

**Relevant affordabot use cases**:

1. **On-demand re-scrape webhook**: An operator or external system sends a POST to a Windmill webhook URL with `{jurisdiction: "San Jose", source_id: "uuid"}`, which triggers a single-jurisdiction scrape flow. Currently, re-scraping requires running the entire daily_scrape cron.

2. **Analysis request webhook**: A POST with `{legislation_id: "uuid"}` triggers the analysis pipeline for a single bill. Currently requires manual API call.

3. **Health check HTTP route**: A Windmill HTTP route that queries the backend's `/health` endpoint and returns pipeline status. Could be used by monitoring systems.

**Recommendation**: Add on-demand re-scrape webhook in the initial POC. This proves that Windmill can handle both scheduled and event-driven triggers, and gives operators a way to trigger per-jurisdiction runs without waiting for the daily cron.

### Revised Gap Analysis (Grounded in Actual Pipeline)

The initial gap analysis was too abstract. Here is the revised analysis grounded in what the backend actually does today:

| Current Pipeline Behavior | What Windmill Could Orchestrate | What Must Stay in Backend | Gap Severity |
|---|---|---|---|
| Daily cron: discovery (05:00) -> scrape (06:00) -> rag_spiders (07:00) -> harvester (08:00) — each is a monolithic cron endpoint | Windmill flow with 4 sequential steps, each calling the same backend endpoints but with step-level retry, timeout, and observability | The actual discovery/scraping/ingestion logic inside each endpoint | High — current cron model has no step-level visibility, no retry, no branching |
| Discovery generates LLM queries per jurisdiction inside a single Python function | Windmill for-loop over jurisdictions, with per-jurisdiction visibility and skip-failure | LLM query generation, URL classification, classifier validation gate | High — single-jurisdiction failure kills the entire discovery run |
| Daily scrape runs 2 pilot scrapers (San Jose, California) inside a single function | Windmill for-loop over jurisdictions, with per-jurisdiction retry and timeout | Legistar/OpenStates API calls, HTML parsing, content extraction, ingestion | High — San Jose scraper failure prevents California from running |
| Ingestion is bundled inside scrape — no separate step | Separate Windmill step for ingestion, with its own retry policy (embedding API failures are transient) | Chunking, embedding, vector upsert, ingestion truth tracking | Medium — embedding failures currently cause the entire scrape to fail |
| Analysis pipeline has 13 steps with sufficiency gates, all inside one Python function | Windmill flow with the 13 steps as separate flow nodes, each with native retry and timeout | All 13 steps' business logic (research, classification, quantification, validation, persistence) | Medium — the 13-step pipeline is analysis, not orchestration; Windmill orchestration here is lower priority than the scrape pipeline |
| No freshness/staleness tracking — daily cron is the only freshness mechanism | Windmill freshness-gate step that checks `raw_scrapes.last_seen_at` before re-scraping | Freshness policy evaluation, staleness calculation, stale-backing decisions | High — PR #415 proposes this; Windmill should orchestrate the check, backend should evaluate the policy |
| No approval/suspend for stale-ceiling or promotion review | Windmill suspend/approval step | Ceiling policy, approval message generation | Medium — needed when freshness policies are enforced |
| No event-driven triggers (only batch cron) | Windmill Postgres triggers + webhooks | — | Low — future enhancement, not POC scope |
| No restart-from-step for failed pipelines | Windmill rerun whole flow + backend idempotency for already-completed steps | Idempotency enforcement, pipeline_steps state tracking | Medium — must be documented as a design decision, not a deficiency |

### Impact on Core Questions

**Q4 revised**: Should Windmill write directly to affordabot Postgres/MinIO? — **Absolutely not.** The data moat (canonical_document_key, substrate promotion, evidence provenance, sufficiency gates) is enforced by backend code. If Windmill wrote directly to `raw_scrapes` or `legislation`, it would bypass all five moat properties. The backend must own all writes to preserve the moat.

**Q5 revised**: Should pipeline_steps remain? — **Yes, even more critical than initially stated.** pipeline_steps is not just a domain audit trail — it's the mechanism that makes Windmill reruns safe. When Windmill reruns a whole flow after a failure, the backend checks pipeline_steps for existing completed steps and returns their results. Without pipeline_steps, every rerun would re-scrape, re-analyze, and potentially overwrite evidence-gated results.
