# Consultant Review: Windmill-Driven Persisted Discovery Pipeline

**Spec under review**: `docs/specs/2026-04-11-windmill-driven-persisted-pipeline.md`
**PR**: https://github.com/stars-end/affordabot/pull/415
**Reviewer**: External architecture consultant
**Date**: 2026-04-11
**Beads**: bd-jxclm.11

---

## Verdict: `approve_with_changes`

The spec is sound in its core contract — Windmill as orchestrator, backend as domain executor, persisted intermediates for resumability. The boundary definitions are the best part of this document. However, several concrete issues must be resolved before implementation begins: the step API is one step too fine in the search phase, the schema is missing a critical column for replay safety, the freshness fallback needs alerting and TTL guardrails, and the MinIO artifact model needs a retention enforcement design. These are fixable without re-architecting.

---

## Top Risks (Ordered by Severity)

### R1. Search step granularity creates fragile orchestration coupling

The spec proposes four search-phase endpoints: `search-plan`, `search-execute`, `search-rerank`, and `freshness-gate`. The first three are so tightly coupled that Windmill must sequence them with no branching value — `search-plan` produces a query list that immediately feeds `search-execute`, which immediately feeds `search-rerank`. If any of these fails, the recovery is always "redo from search-plan." This is one logical unit with three HTTP round-trips, three idempotency checks, and three step rows for what is semantically one operation: "generate and materialize search candidates."

**Impact**: Increased Windmill flow complexity, more places for version drift, and no resumability gain between plan/execute/rerank since they share a single failure domain.

**Fix**: Collapse `search-plan`, `search-execute`, and `search-rerank` into a single `search-materialize` step. Freshness-gate remains separate because it has genuine branching logic (fresh results vs. stale fallback). The backend can still internally decompose into plan/execute/rerank; the step API just doesn't expose that as separate HTTP calls.

### R2. `pipeline_steps` schema missing `manifest_hash` for idempotency replay

The spec's idempotency key is `run_id:step_key:manifest_hash`, but `pipeline_steps` does not include a `manifest_hash` column. Without it, the idempotency key cannot be reconstructed from persisted state after a Windmill restart. The `idempotency_key` column itself is a derived string, but it cannot be validated against the manifest that produced it without the hash stored separately.

**Impact**: If Windmill retries a step with a slightly different manifest (e.g., a jurisdiction was added), the idempotency key would differ, but there is no persisted way to detect manifest drift from the database alone.

**Fix**: Add `manifest_hash TEXT` to `pipeline_steps`. The backend should reject a step invocation if the stored `manifest_hash` for the same `(run_id, step_key)` differs from the incoming one, unless the step is explicitly being re-run.

### R3. Freshness fallback can mask indefinite SearXNG outages

The spec correctly marks `stale_backed=true` in `pipeline_freshness_decisions`, but there is no mechanism to escalate when stale fallback becomes the norm rather than the exception. A SearXNG outage that lasts days would produce runs that silently succeed on stale data, with only a `stale_backed=true` column that nobody reads.

**Impact**: Data drift accumulates without operator awareness. The system appears healthy while producing increasingly stale results.

**Fix**: Add two guardrails:
1. A `consecutive_stale_fallbacks` counter on `search_queries` that increments on stale use and resets on fresh success. Alert when it exceeds a configurable threshold (default: 3).
2. A hard TTL: if `latest_success_at` is older than `2 * max_stale_hours`, the step must fail rather than fall back, regardless of policy. This prevents indefinite stale operation.

### R4. MinIO artifact retention is specified but not enforced

The spec mentions "retention windows, size budgets, and MinIO lifecycle cleanup" as mitigation for artifact growth, but does not define the lifecycle policy or where enforcement lives. Without a concrete retention design, artifact growth is a known risk with no committed countermeasure.

**Fix**: Define a minimum retention policy in the spec before Phase 2:
- Raw search JSON: 30 days
- Fetched HTML/PDF: 90 days
- Extracted markdown: 90 days (or until superseded by content_hash match)
- Debug screenshots: 7 days
- Reports: indefinite

Enforcement: backend writes a `retention_expires_at` column on each artifact row. A daily Windmill-scheduled cleanup job calls a backend endpoint that deletes expired artifacts from MinIO and marks the row `purged`.

### R5. No contract version negotiation mechanism

The spec mentions "include pipeline contract version in manifests and backend responses" but does not define the version format, the negotiation behavior, or what happens when versions diverge. This is a known risk (`Version Drift Between Windmill and Backend`) with a placeholder mitigation.

**Fix**: Add a `contract_version` field to the manifest (semver, starting at `1.0.0`). The backend rejects any request with an unsupported major version. Minor version differences are logged but allowed. The version should be a constant in the backend codebase, not a Windmill variable.

---

## Boundary Critique: Windmill vs Backend

### What the spec gets right

The Active Contract section is the strongest part of this spec. The "Windmill is allowed to" / "Windmill is not allowed to" / "Backend is required to" enumeration is exactly the right abstraction level. The prohibition on Windmill writing domain tables, implementing scoring, or holding unversioned business rules is clear and enforceable.

The manifest-in, status-out pattern is clean. Windmill passes intent; backend returns fact.

### Where business logic leaks

1. **Freshness policy in the manifest**: The manifest includes `freshness_policy` and `max_search_stale_hours`. If Windmill is setting these values, the operator is making a business decision about data freshness in the orchestration layer. This should either be a backend-enforced default with optional override, or the manifest should reference a named policy (e.g., `"freshness_policy": "standard_daily"`) whose parameters are owned by the backend.

2. **`sample_size_per_bucket` in the manifest**: This is a business logic parameter controlling how many documents to process. It should be a backend default with optional override, not a required manifest field.

3. **The `report` step**: The spec lists `POST /internal/pipeline/report` as a backend step, but report generation is purely a synthesis of already-persisted data. If Windmill needs to trigger a report, it should be a lightweight query, not a state-changing step. Making it a step with its own `pipeline_steps` row implies it has side effects, which it shouldn't.

### Recommendation

Move freshness policy names and sample size defaults into a backend `pipeline_policies` table or configuration. The manifest should reference policy names, not policy parameters. The `report` endpoint should be a GET, not a POST, and should not create a step row.

---

## Persistence/Schema Critique

### Sufficient

The separation of `pipeline_runs` / `pipeline_steps` / `search_result_snapshots` / `fetch_artifacts` / `extraction_artifacts` / `ingestion_jobs` is well-scoped. Each table answers a distinct question. The lineage chain from search snapshot to fetch artifact to extraction artifact to ingestion job is traceable.

### Missing

1. **`manifest_hash` on `pipeline_steps`** (see R2 above).
2. **`content_hash` uniqueness constraint**: `fetch_artifacts.content_hash` should have a unique constraint (or at minimum a per-run unique index) to support idempotent re-fetch. The spec mentions content hashing but does not declare the constraint.
3. **`extraction_artifacts.markdown_hash` uniqueness**: Same concern. Re-extraction of identical content should be a no-op, which requires a uniqueness check.
4. **`pipeline_freshness_decisions.stale_backed` should be NOT NULL with a DEFAULT FALSE**: The spec lists it as a column but does not declare default or nullability. If freshness decisions are written before fallback is evaluated, `NULL` would be ambiguous (not yet evaluated vs. evaluated as not stale).
5. **No `pipeline_runs.manifest` column**: The manifest JSON is referenced throughout but not persisted. If you need to replay a run or understand what was requested, you need the manifest stored with the run, not just its hash.

### Overbuilt

The `search_result_snapshots` table has both `provider_score` and `local_score`. Until the backend implements local scoring (which is not in Phase 1-4), `local_score` will always be NULL. Consider adding it in the phase where scoring is implemented, not upfront.

---

## Freshness Fallback Critique

### What works

- The `pipeline_freshness_decisions` table with `stale_backed`, `freshness_policy`, `latest_success_at`, and `decision_reason` provides a solid audit trail for individual fallback decisions.
- The principle of "allow stale fallback only inside explicit policy" is correct.

### What is missing

1. **Consecutive stale counter** (see R3): No escalation mechanism.
2. **Hard TTL floor** (see R3): No absolute staleness ceiling.
3. **SearXNG health probe**: Before executing a search, the backend should probe SearXNG availability with a lightweight request. If SearXNG is down, the backend can immediately decide to use stale data rather than waiting for a timeout. This reduces latency and avoids filling connection pools with doomed requests.
4. **Stale snapshot validity signal**: `search_result_snapshots` does not record whether a snapshot was later validated (i.e., did the URLs in the snapshot still exist when fetched?). A stale snapshot that references dead URLs is worse than no snapshot. Add a `validated_at` column that is updated when fetch results confirm snapshot URLs.

---

## MVP Cut Recommendations

Cut from MVP (Phase 1-4):

| Item | Reason |
|------|--------|
| `search-rerank` as separate endpoint | Merge into `search-materialize`. Reranking is internal logic, not a resumable boundary. |
| `search-plan` as separate endpoint | Merge into `search-materialize`. Plan and execute share a failure domain. |
| `local_score` on `search_result_snapshots` | No implementation in MVP phases. Add when scoring logic exists. |
| `screenshot_artifact_path` on `fetch_artifacts` | Screenshots are debug-only. Ship in Phase 8 (observability). |
| `metadata_artifact_path` on `extraction_artifacts` | Undefined contract. Add when metadata extraction is specified. |
| `report` as a POST step | Make it a GET query. Reports are reads, not state transitions. |
| Z.ai layout/OCR fallback (Phase 5) | Defer to post-MVP. Ship direct HTTP + readability + PDF extraction first. |

Keep in MVP:

| Item | Reason |
|------|--------|
| `search-materialize` (combined) + `freshness-gate` | Core search boundary |
| `read-fetch` + `extract` | Core content acquisition |
| `embed` + `promote` | Core ingestion and source trust |
| MinIO raw artifact writes | Required for idempotent re-extraction |
| All pipeline state tables | Required for resume and audit |
| Content hash reuse | Required to avoid re-ingesting unchanged content |

---

## Required Spec Changes Before Implementation

1. **Collapse `search-plan`, `search-execute`, `search-rerank` into `search-materialize`** (see R1).
2. **Add `manifest_hash` to `pipeline_steps`** (see R2).
3. **Add `manifest` JSONB column to `pipeline_runs`**.
4. **Add `consecutive_stale_fallbacks` to `search_queries`** with alerting threshold (see R3).
5. **Add hard TTL floor**: `2 * max_stale_hours` must fail, not fall back (see R3).
6. **Define concrete MinIO retention policy with `retention_expires_at`** (see R4).
7. **Define `contract_version` format and rejection behavior** (see R5).
8. **Make `report` a GET endpoint, not a POST step**.
9. **Move freshness policy parameters to backend-owned defaults with named policy references in manifests**.
10. **Add `validated_at` to `search_result_snapshots`** for snapshot validity tracking.

---

## Optional Future Improvements

- **Snapshot diffing**: When a new search snapshot matches a prior one by URL set, record the diff (added/removed URLs) for operator review.
- **Backpressure on Windmill**: If the backend is under load, step endpoints should return a `retry_after_seconds` field so Windmill can back off without failing the step.
- **Step timeout contracts**: Each step endpoint should declare its expected maximum runtime so Windmill can set appropriate timeouts.
- **Artifact deduplication across runs**: If two runs fetch the same URL with the same content hash, they should share the same MinIO object rather than duplicating storage.
- **Cross-run lineage**: `fetch_artifacts` and `extraction_artifacts` reference `run_id`, but the same URL fetched across runs has no explicit linkage. A `canonical_url` index would support "show me all fetches of this URL across time."
- **SearXNG query result caching**: For jurisdictions that change slowly, materialized search snapshots can be reused across daily runs without re-querying SearXNG, reducing search volume.

---

## Direct Answers to Review Questions

### Q1: Does the spec keep Windmill as orchestrator and affordabot backend as domain executor, or does business logic still leak across the boundary?

**Mostly yes, with three leaks.** The Active Contract section is excellent and the manifest-in/status-out pattern is clean. However: (a) freshness policy parameters (`max_search_stale_hours`, `freshness_policy`) in the manifest are business decisions that should be backend-owned defaults with named policy references; (b) `sample_size_per_bucket` in the manifest is a business parameter; (c) the `report` step as a state-changing POST blurs the read/write boundary. These are fixable without re-architecting.

### Q2: Are the backend step endpoints too fine-grained, too coarse, or appropriately resumable?

**Too fine-grained in the search phase, appropriately scoped elsewhere.** The three-step search decomposition (`plan`/`execute`/`rerank`) creates orchestration overhead with no resumability benefit — they share a single failure domain and must always be re-executed together. Collapsing into `search-materialize` reduces HTTP round-trips and step rows without losing any recovery granularity. The remaining steps (`freshness-gate`, `read-fetch`, `extract`, `embed`, `promote`) are well-scoped — each has a distinct failure mode and resumable state.

### Q3: Is the proposed schema enough for auditability and replay without creating avoidable operational burden?

**Almost sufficient, with two gaps.** The lineage chain from search to ingestion is traceable. The freshness decisions table provides auditability. Two gaps: (a) `manifest_hash` is not stored on `pipeline_steps`, breaking idempotency replay verification (R2); (b) the manifest itself is not stored on `pipeline_runs`, making it impossible to reconstruct what was requested without cross-referencing Windmill logs. The schema is not overbuilt — the table count is appropriate for the domain boundaries. The one overbuilt element is `local_score` on `search_result_snapshots`, which has no implementation in any planned phase.

### Q4: Is latest-good fallback safe? What metadata or alerting is missing to prevent silent stale behavior?

**Not safe without additions.** The `stale_backed=true` flag is necessary but insufficient. Missing: (a) a consecutive stale counter with alerting — three consecutive stale fallbacks should trigger an operator alert; (b) a hard TTL ceiling — if the last successful search is older than `2 * max_stale_hours`, the step must fail rather than fall back; (c) a SearXNG health probe to fail fast on outage rather than timing out; (d) a `validated_at` column on `search_result_snapshots` to track whether snapshot URLs were later confirmed live. Without these, a prolonged SearXNG outage produces runs that appear healthy while serving increasingly stale and potentially dead-link data.

### Q5: Are SearXNG, reader/fetcher, MinIO artifacts, Postgres, and pgvector responsibilities separated cleanly?

**Yes, with one ambiguity.** The separation is well-defined: SearXNG returns candidates, backend owns scoring and promotion, MinIO holds raw artifacts, Postgres holds relational and pipeline state, pgvector holds embeddings. The ambiguity: the spec does not clarify whether the reader/fetcher writes directly to `raw_scrapes` (the existing domain table) or only to `fetch_artifacts`/`extraction_artifacts` (the new pipeline tables). If both, what is the synchronization contract? The spec should state that pipeline tables are the source of truth for the pipeline, and promotion to `raw_scrapes` happens at the `promote` step. The fetcher should not write `raw_scrapes` directly.

### Q6: Which pieces should be cut from MVP?

- `search-plan`, `search-execute`, `search-rerank` as separate endpoints → collapse into `search-materialize`
- `local_score` on `search_result_snapshots` → no implementation planned
- `screenshot_artifact_path` on `fetch_artifacts` → debug-only, defer
- `metadata_artifact_path` on `extraction_artifacts` → undefined contract
- `report` as POST step → make it a GET query
- Z.ai layout/OCR fallback → defer to post-MVP

### Q7: What failure drills are missing before rollout?

1. **SearXNG total outage**: Disable SearXNG, verify stale fallback works within policy, verify hard TTL fails when exceeded, verify alerting fires on consecutive stale fallbacks.
2. **MinIO write failure**: Simulate MinIO unavailability during `read-fetch`, verify the step returns `failed` (not `partial` with missing artifacts), verify re-execution after MinIO recovery succeeds.
3. **Backend step timeout**: Verify Windmill retries a step that takes longer than expected, and that the backend's idempotency key prevents double execution.
4. **Concurrent step invocation**: Two Windmill workers call the same step with the same `idempotency_key` simultaneously. Verify only one execution completes and the second returns the first's result.
5. **Manifest drift**: Windmill sends a step with a different manifest hash than the original run. Verify the backend rejects it.
6. **Partial extraction**: A fetch succeeds but extraction fails (e.g., PDF parsing error). Verify the fetch artifact is persisted and the step is resumable from `extract` without re-fetching.
7. **Rollback drill**: Disable new pipeline, re-enable existing cron endpoints, verify no data loss in pipeline tables, verify existing scripts still function.

### Q8: What sequencing changes would reduce implementation risk?

The current phase ordering is logical but has one risk: Phase 4 (SearXNG) and Phase 5 (Reader/Extraction) can proceed in parallel but share a dependency on Phase 3 (Backend Step Contracts). However, Phase 4 also depends on Phase 6 (SearXNG provisioning), which is infra work. Recommended reordering:

1. **Phase 2 → Phase 3**: Schema then endpoints, as planned. No change.
2. **Phase 6 before Phase 4**: Provision SearXNG before building the search materialization on top of it. If SearXNG provisioning reveals integration issues (e.g., Railway networking, rate limits), you want to know before building the search step.
3. **Phase 5 and Phase 4 in parallel**: Once endpoints and SearXNG infra exist, reader/extraction and search materialization can be built concurrently since they are independent.
4. **Phase 8 (observability) before Phase 9 (Windmill flows)**: You need artifact retention and observability in place before you wire Windmill flows that will generate real artifacts. Otherwise your first real run will produce artifacts with no cleanup mechanism.

### Q9: Are there any security or data-retention risks in the proposed MinIO/raw artifact model?

**Three risks:**

1. **PII in fetched content**: Government websites sometimes include resident names, addresses, and contact information in meeting minutes and permit documents. Raw HTML/PDF artifacts stored in MinIO will contain this PII. The spec does not address PII handling or redaction. Recommendation: classify artifacts as PII-bearing at the `fetch_artifacts` level (add a `contains_pii` column or `content_classification` field) and apply stricter retention to PII-bearing artifacts.

2. **No access control on MinIO objects**: The spec does not mention access control for MinIO artifacts. Pipeline artifacts should not be publicly accessible. If MinIO is configured with public read (common for development), raw HTML containing PII becomes a data exposure risk. Recommendation: enforce bucket-level access control and require authenticated reads for pipeline artifacts.

3. **Indefinite report retention**: The spec's artifact path includes `pipeline-runs/<run_id>/reports/summary.md` with no stated retention. Reports are operator-facing and could contain summarized PII or sensitive source evaluation details. Define a retention window.

### Q10: Should any logic currently proposed for backend belong in Windmill, or vice versa?

**Two items:**

1. **Freshness policy evaluation should stay in backend** (correct in spec). However, the freshness *policy parameters* should also be backend-owned, not Windmill-supplied. The manifest should reference a named policy, not pass raw hour values. This keeps the business rule in one place.

2. **Slack alerting is listed as a Windmill responsibility** (correct for orchestration-level alerts like "step failed"). However, the spec should clarify that data-quality alerts (e.g., "search returning fewer results than expected", "extraction quality degraded") belong to the backend, not Windmill. Windmill should alert on *step execution health*; the backend should alert on *data quality*. The current spec does not distinguish these two alerting domains.

---

## Summary

This spec represents a significant and well-thought-out improvement over the current architecture. The Z.ai chat-as-reader path in `run_universal_harvester.py` is genuinely brittle — it depends on a proprietary API for both search and content reading, has no intermediate persistence, and cannot resume from partial failure. The proposed pipeline fixes all three problems.

The core contract (Windmill orchestrates, backend executes, everything is persisted) is right. The ten required spec changes are all additive — none require re-architecting. Implement the changes, then proceed with Phase 2.
