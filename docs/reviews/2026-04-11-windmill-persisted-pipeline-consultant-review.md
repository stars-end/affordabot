# Consultant Review: Windmill-Driven Persisted Discovery Pipeline

**Date:** 2026-04-11
**Reviewer:** External Architecture Consultant

## Verdict
**Verdict:** `approve_with_changes`

## Tool routing exception
Tool routing exception: Semantic discovery via `llm-tldr` and symbol-aware navigation via `serena` were not required because the user explicitly provided the exact 4 file paths needed for the targeted architectural review.

## Top Risks (Ordered by Severity)
1. **Unbounded Artifact Growth (MinIO Storage Exhaustion):** The introduction of raw HTML, PDF, and JSON snapshot artifacts for every search query could rapidly deplete storage. If MinIO lifecycle policies are not implemented *before* rollout, it will lead to an operational failure.
2. **Hidden Stale Fallback Degradation:** While the spec includes `stale_backed=true` in decisions, without a loud observability hook in Windmill, a completely broken SearXNG could be masked for weeks if the maximum stale hours are set broadly.
3. **Windmill Timeout Sync Vulnerability:** If a backend step (e.g., embedding or extraction) takes longer than Windmill's HTTP timeout, Windmill may retry the step while the backend is still running the first attempt. The backend must have strong locking or atomic upserts on the `idempotency_key`.

## Boundary Critique: Windmill vs Backend
The proposed boundaries are well-defined and adhere to best practices. Windmill is correctly constrained to scheduling, branching, retries, and manifest-passing. Keeping the domain logic, table writes, and artifact persistence strictly within the affordabot backend prevents "orchestrator bloat" and maintains a clean single source of truth for business rules.

## Persistence/Schema Critique
The persistence schema successfully separates orchestration state (`pipeline_runs`, `pipeline_steps`) from domain state (`search_queries`, `fetch_artifacts`, `ingestion_jobs`). This separation allows for clean auditability and simplifies debugging. Moving large blobs (raw HTML, resulting markdown) into MinIO instead of Postgres is the right architectural choice to maintain DB health. 

## Freshness Fallback Critique
The "latest-good fallback" mechanism is intelligent for handling external SearXNG flakiness. However, it is paramount that Windmill triggers a non-fatal alert when a fallback occurs. Silent usage of stale data can be as dangerous as no data in a financial/legislative context. The inclusion of `status`, `freshness_policy`, and `stale_backed` flags in `pipeline_freshness_decisions` is necessary but sufficient only if actively monitored.

## Required Spec Changes Before Implementation
1. **Idempotency Locking:** Specifically address how the backend will handle concurrent requests for the same `idempotency_key` (e.g., if Windmill times out and retries while the backend is still processing the first request).
2. **Alerting on Fallback:** Update the Windmill Flow orchestration (Phase 6) to include a requirement that Windmill sends a Slack alert to the operator when `stale_backed` is true, ensuring operators know the system is masking a SearXNG outage.
3. **Data Retention Timelines:** Explicitly define the TTL (Time-To-Live) / Retention policy for MinIO raw artifacts in Phase 2 or Phase 8.

## MVP Cut Recommendations
- **Search Rerank Step (`search_rerank`):** This is likely an optimization that isn't strictly required to prove pipeline correctness.
- **Complex Extraction Layers:** Defer the Playwright (JS-heavy) and OCR (Z.ai fallback) pathways for Phase 1 MVP. Stick to strict HTTP fetch + standard readability extraction to validate the whole pipeline flow end-to-end sooner.

## Optional Future Improvements
- **Automated Replay Testing:** Once idempotent steps exist, create a dedicated test environment that reruns pipeline events against stale snapshots to test the recovery paths safely off-production.
- **Circuit Breakers for SearXNG:** Instead of waiting for per-query timeouts, implement a rapid-failure circuit breaker to switch to fallback mode earlier if the first 3 SearXNG requests fail globally.

---

## Direct Answers to Review Questions

**1. Does the spec keep Windmill as orchestrator and affordabot backend as domain executor, or does business logic still leak across the boundary?**
Yes, it strictly maintains the boundary. Windmill is passed a manifest and routes HTTP calls, but the actual domain decisions (like what constitutes a valid source) and database writes remain in the affordabot backend.

**2. Are the backend step endpoints too fine-grained, too coarse, or appropriately resumable?**
They are appropriately resumable. Steps like `search-plan`, `fetch`, and `extract` represent specific, retryable jobs that each produce a durable outcome.

**3. Is the proposed schema enough for auditability and replay without creating avoidable operational burden?**
Yes, the explicit separation of step execution metadata and artifact persistence (MinIO) guarantees auditability without bogging down the relational database.

**4. Is latest-good fallback safe? What metadata or alerting is missing to prevent silent stale behavior?**
The metadata (`stale_backed` column) exists, but the alerting behavior is missing. Windmill must alert operators when `stale_backed=true` to prevent prolonged masking of Search API outages.

**5. Are SearXNG, reader/fetcher, MinIO artifacts, Postgres, and pgvector responsibilities separated cleanly?**
Yes. SearXNG acts purely as candidate generation. MinIO handles blob storage, Postgres manages relational step state, and pgvector handles embeddings derived only from the extracted artifacts.

**6. Which pieces should be cut from MVP?**
Cut `search_rerank`, Playwright-based fetching, and OCR fallbacks. Focus strictly on direct HTTP fetching and pipeline idempotency.

**7. What failure drills are missing before rollout?**
- SearXNG complete outage simulation to verify alert firing.
- Windmill execution timeout handling to verify backend idempotency locks.
- MinIO write failure handling.

**8. What sequencing changes would reduce implementation risk?**
Move `bd-jxclm.8` (Infra: define artifact storage retention and observability) to an earlier phase (Phase 2 alongside schema design). Storage limits must be bounded early before tests write gigabytes of HTML.

**9. Are there any security or data-retention risks in the proposed MinIO/raw artifact model?**
Yes, retaining raw artifacts indefinitely can expose PII or copyrighted material and consume tremendous storage. A strict, automated retention policy (e.g., 14 or 30 days max for raw data) is mandatory.

**10. Should any logic currently proposed for backend belong in Windmill, or vice versa?**
No, the boundary is optimal as defined. Windmill handles scheduling and inputs, while the backend processes all states and artifacts.
