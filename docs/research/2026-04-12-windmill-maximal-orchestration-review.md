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
