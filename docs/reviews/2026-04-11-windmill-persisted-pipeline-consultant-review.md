# Consultant Review: Windmill-Driven Persisted Discovery Pipeline

- **Spec under review:** `docs/specs/2026-04-11-windmill-driven-persisted-pipeline.md`
- **Spec PR:** https://github.com/stars-end/affordabot/pull/415
- **Spec PR head:** `385338ffce5108a0c15080c65946b1e11549fd31`
- **Reviewer role:** External architecture consultant
- **Beads:** epic `bd-jxclm`, subtask `bd-jxclm.11`
- **Date:** 2026-04-11

Tool routing exception: skipped `llm-tldr` / `serena` MCP navigation — the review scope is the spec document plus two adjacent files (`ops/windmill/README.md`, `backend/scripts/cron/run_universal_harvester.py`, `backend/services/llm/web_search_factory.py`) and a targeted Read was cheaper and sufficient than symbolic navigation across the whole repo.

## Verdict

**`approve_with_changes`**

The architecture is directionally correct and the Windmill/backend split is the right one for a single-founder team. The spec is publishable as a reviewed design, but several concrete changes should be applied before the first implementation task (`bd-jxclm.2`) starts. Most of them are guardrails on freshness, schema, and MVP scope — not architectural rewrites.

## Top Risks (Ordered by Severity)

1. **Silent staleness via "latest-good" fallback.** The spec allows stale search snapshots to back a run up to `max_search_stale_hours` (168h default). Without explicit, loud alerting on *every* fallback hit and a hard ceiling after N consecutive fallbacks, a quiet SearXNG outage can degrade discovery for a full week before a human notices. This is the single highest-blast-radius risk in the design.
2. **Step API proliferation.** Ten `/internal/pipeline/*` endpoints at MVP is ~2–3× what a bounded single-jurisdiction run actually needs. Each endpoint adds auth coverage, contract tests, idempotency tests, and Windmill branch logic. For a founder-led team this is a concrete cognitive-load tax that the spec does not acknowledge.
3. **Pipeline schema is large and sequenced too early.** Eight new tables (`pipeline_runs`, `pipeline_steps`, `search_queries`, `search_result_snapshots`, `pipeline_freshness_decisions`, `fetch_artifacts`, `extraction_artifacts`, `ingestion_jobs`) all land in Phase 2 before any business value is proven. Schema churn during Phases 4–5 is very likely and will be painful.
4. **Unbounded MinIO growth with no retention in the MVP.** Retention is mentioned as a risk but is deferred to `bd-jxclm.8` and never defined numerically. Raw HTML + screenshots per fetch can grow fast per jurisdiction onboarded.
5. **No pipeline contract version field in the canonical request/response envelope.** The spec mentions version drift in the risk section and says "include pipeline contract version in manifests and backend responses," but the Backend Step API example payloads in §"Backend Step API" do not include the field. This is a trivial but easy-to-forget omission that will bite at rollout.
6. **Promotion step is described but not scope-gated.** Auto-promotion mentions "explicitly allowed families and high-confidence first-party surfaces" without specifying which families qualify at MVP. Without a gate, this becomes an open-ended policy surface.
7. **Rollback plan is "additive" but does not specify the shadow-run period.** Phase 7 says rollback is "additive" and existing cron endpoints remain, but there is no explicit parity window ("run old and new in parallel for N days, compare X metric"). Without that, cutover is implicitly a flag flip.
8. **Playwright and Z.ai OCR fallback are listed as Phase 5 scope but not sequenced behind measured need.** Both are operationally heavy (Playwright needs a runtime, Z.ai OCR is cost-metered). They should only land when direct HTTP + readability has been shown to fail for a quantified share of real pages.
9. **No data classification or PII handling for raw HTML / screenshot artifacts.** Municipal pages are usually public, but screenshots and raw HTML may carry embedded third-party content, cookies in HAR-like captures, or staff contact details. The spec does not say this is intentionally out of scope.
10. **`trigger_source` is free-form string.** This is fine for logs but should be explicitly not-load-bearing for routing or retry policy — a small note prevents the pattern from calcifying.

## Boundary Critique: Windmill vs Backend

**What the spec gets right:**
- The prohibition list in §"Active Contract" (Windmill must not write `sources`, `raw_scrapes`, `document_chunks`, etc.) is the correct invariant. It matches the existing shared-instance pattern documented in `ops/windmill/README.md` and does not require a mental model change.
- Pushing scoring, dedupe, and promotion into the backend is the right call. Windmill should never encode domain truth.
- The step request envelope (`run_id`, `step_key`, `idempotency_key`, `trigger_source`, `manifest`) is the correct shape.

**What leaks or is ambiguous:**
- **Retry policy ownership.** The spec says "Windmill is allowed to retry safe steps according to backend-declared retryability" and the response includes `retryable: true|false`. Good. But the spec does not say whether retry *count* is a Windmill policy or a backend policy. If Windmill owns it, a flow-version bump changes retry behavior silently. Recommendation: backend returns `retryable`, `max_retries`, and `retry_after_seconds`; Windmill obeys, does not guess.
- **`next_recommended_step` in the response.** This quietly moves a flow-graph decision from Windmill into the backend. It is a hint, but Windmill flow authors may code against it. Either declare it advisory-only in the spec or remove it and let Windmill own the DAG. I recommend declaring it advisory, because the backend is the only component that knows whether a step's output justifies skipping ahead, but the flow-graph itself must stay declarative in Windmill.
- **Alerting ownership.** Spec says Windmill "send Slack/operator alerts." Good. But freshness/stale-backed alerts are semantically a backend concern (the backend is the only thing that knows `stale_backed=true`). Clarify: backend emits the alert *content* in `operator_summary` + a structured `alerts[]` field; Windmill is the dumb transport.
- **Contract version.** Must move from risk section into the mandatory envelope as noted in Risk 5.

**Net assessment:** the boundary is ~90% right. The remaining 10% is ownership of retry *policy*, alert *content*, and the advisory nature of `next_recommended_step`.

## Persistence / Schema Critique

The schema is well-normalized and lineage-preserving, which is good for audit. It is also larger than MVP warrants.

**Concrete critiques:**
- **`pipeline_steps` and `pipeline_runs` can land at MVP.** Everything else can be staged.
- **`search_queries` as a registry table is premature.** At MVP a manifest-driven list is enough. A registry table becomes necessary when (a) the same query must fire across multiple runs on different cadences, or (b) operators need to edit queries without a deploy. Neither is true on day one.
- **`pipeline_freshness_decisions` is one table too many.** The decision is a property of the step that consumed the snapshot; it belongs as columns on `pipeline_steps` (`freshness_policy`, `stale_backed`, `latest_success_at`, `decision_reason`) or as a single JSON column. A dedicated table is "correct" but introduces an avoidable join and a second place to keep consistent.
- **`fetch_artifacts` and `extraction_artifacts` should not both be tables at MVP.** Collapse into one `content_artifacts` row with an `artifact_kind` enum (`fetch`, `extraction`, `screenshot`). This preserves lineage via `parent_artifact_id` without doubling the migration surface.
- **`search_result_snapshots.provider_endpoint_hash` is good** — that is exactly the kind of field that lets a post-mortem distinguish two SearXNG instances. Keep it.
- **`idempotency_key` format.** Spec suggests `run_id:step_key:manifest_hash`. Good, but note that `manifest_hash` must be a stable canonical serialization (sorted keys, no whitespace variance). Add a one-line note to prevent silent cache misses.
- **Missing:** `pipeline_runs.contract_version` and `pipeline_steps.contract_version`. This is the persistence home for Risk 5.
- **Missing:** an explicit `pipeline_runs.parent_run_id` for "resume from failed step" lineage. Without it, a resumed run either overwrites the original (loses history) or has no link back (loses audit).
- **Missing:** `pipeline_runs.jurisdiction_id` as a first-class column for cheap filtering. Putting it only in the manifest makes ops queries painful.

## Freshness / Latest-Good Fallback Critique

Latest-good fallback is the riskiest feature in the design because it turns a loud failure (SearXNG down) into a quiet success. The spec mitigations are directionally right but insufficient.

**What must be added to the spec before implementation:**
1. **Hard ceiling on consecutive fallbacks.** After N (recommended: 2) consecutive runs that fallback for the same `query_key`, the run must fail closed, not degrade silently further. N should be configurable per source family.
2. **Alert on *every* fallback, not just on refresh failure.** Currently the spec says "Windmill should still alert on refresh failure." That is necessary but not sufficient — if the refresh step *itself* marks partial and returns stale-backed results, Slack should get it.
3. **Fallback telemetry as a first-class metric.** Add `stale_backed_count` to the run summary. Operator should be able to see "N of M query keys used stale fallback" at a glance, not dig through step rows.
4. **`max_stale_hours` per source family, not global.** Permit pages rot faster than municipal code. 168h is probably too generous for meetings, too tight for code. Make the 168h value a default, not a policy.
5. **Fallback must preserve the *original* `provider_endpoint_hash`** so a post-mortem can distinguish "SearXNG was up but the provider was different" from "we used a 6-day-old snapshot".
6. **Explicit "no fallback on empty result set" rule.** If SearXNG returns `200 OK` with zero results, that is *not* a failure and must not trigger latest-good. Zero-result is a real state that should surface as `created_count: 0`. The spec does not currently distinguish these.

## MVP Cut Recommendations

The spec has 7 execution phases and 10 subtasks. For a founder-led team the MVP that delivers business value is smaller than what is currently sequenced.

**Cut from MVP (defer to post-parity):**
- `bd-jxclm.6` Private SearXNG provisioning as a *blocking* dependency. Start with the existing Z.ai search path behind the new step contract; swap the backend of `/internal/pipeline/search-execute` to SearXNG as a later, isolated change. This lets the pipeline skeleton land without waiting on infra.
- `pipeline_freshness_decisions` table (fold into `pipeline_steps`, see schema critique).
- `search_queries` registry table (use manifest-driven queries at MVP).
- `fetch_artifacts` + `extraction_artifacts` as two separate tables (collapse into `content_artifacts`).
- `/internal/pipeline/search-rerank` as a separate endpoint — merge into `search-execute` at MVP. Rerank logic is small enough to live inside the execute step until there is a demonstrated need for a re-rank-only pass.
- `/internal/pipeline/promote` endpoint at MVP. Promotion is an explicit non-goal for day-one trust (spec says promotion is a separate concern). Run the MVP in `capture_only` mode and have promotion land in a later wave.
- Playwright fallback at MVP. Require direct HTTP + readability only, with failures recorded. Add Playwright when a measured >X% of real target pages require it.
- Z.ai layout/OCR fallback at MVP. Same reasoning — bounded hard-document fallback can land after parity is proven.
- `pipeline_retry_step` dedicated Windmill flow. A single `pipeline_manual_run` flow with a `resume_from_step` manifest field is enough at MVP.

**Keep at MVP:**
- `pipeline_runs`, `pipeline_steps` (with freshness columns inlined).
- `/internal/pipeline/runs`, `/search-execute`, `/read-fetch`, `/extract`, `/embed`, `/report` — six endpoints, not ten.
- `search_result_snapshots` + `content_artifacts` tables.
- MinIO artifact layout (keep as designed).
- Daily Windmill flow + manual Windmill flow.

**Result:** one round of schema migration instead of three, six endpoints instead of ten, no infra block on SearXNG provisioning.

## Failure Drills Missing Before Rollout

The Runtime Smokes section is reasonable but skews toward happy-path verification. The following drills must be exercised before calling the rollout complete:

1. **Crash-mid-step drill.** Kill the backend process while a `/read-fetch` step is mid-write to MinIO + Postgres. Verify the step row reflects the actual terminal state on restart, not a zombie `running`.
2. **Partial MinIO write drill.** Simulate an S3/MinIO 500 during an artifact write. Verify the step returns `failed` (or `partial` only if safe) and does not leave a half-written row pointing to a non-existent artifact.
3. **Idempotency replay drill.** Call the same endpoint with the same `idempotency_key` twice, concurrently. Verify one wins cleanly and the other returns the original result with `reused_count > 0`.
4. **Contract-version skew drill.** Call a v2 endpoint with a v1 manifest. Verify fail-closed behavior, not silent coercion.
5. **Stale-ceiling drill.** Simulate SearXNG down for three consecutive runs. Verify the run fails closed after N=2 and alerts fire.
6. **Resume-from-failed-step drill.** Fail a run at `extract`, then call the manual flow with `resume_from_step=extract` and verify upstream `read-fetch` results are reused, not redone.
7. **Rollback drill.** With new pipeline running, disable the Windmill schedule and re-trigger the old cron endpoint. Verify zero data loss and zero cross-contamination of run tables.
8. **Auth-drift drill.** Rotate `CRON_SECRET`. Verify the Windmill flow and the backend fail loudly in the same window rather than one side failing silently.

## Required Spec Changes Before Implementation

These are the blocking edits to the spec document. None are architectural rewrites; all are tightening.

1. Add `contract_version` to the canonical request and response envelopes (§"Backend Step API").
2. Add `alerts: [{severity, code, summary}]` to the canonical response envelope.
3. Change `retryable: true|false` to `retry: { retryable, max_retries, retry_after_seconds }` and declare that Windmill obeys these values rather than setting its own.
4. Declare `next_recommended_step` as advisory-only; the Windmill DAG remains the source of truth for flow graph.
5. Under §"Persistence Model", mark `pipeline_freshness_decisions`, `search_queries`, `fetch_artifacts`, and `extraction_artifacts` as **Phase 3+**, not Phase 2. Collapse fetch/extraction into `content_artifacts` at MVP.
6. Add `pipeline_runs.contract_version`, `pipeline_runs.parent_run_id`, `pipeline_runs.jurisdiction_id`, `pipeline_runs.stale_backed_count` columns.
7. Add a §"Freshness Policy" subsection covering: per-family `max_stale_hours`, hard ceiling on consecutive fallbacks, always-alert on `stale_backed=true`, zero-result is not a failure.
8. Add §"Retention" numeric defaults (recommended starting values: 30d for raw fetch HTML, 90d for extracted markdown, 7d for debug screenshots, indefinite for `pipeline_runs` and `pipeline_steps` rows).
9. Move private SearXNG (`bd-jxclm.6`) off the MVP blocking path; document that MVP may run with the existing search backend behind the new step contract.
10. Document the parity window in §"Rollback": explicit duration, explicit pass/fail criteria, explicit metric comparison (e.g., "7 days, ≥95% equivalent created_count per jurisdiction, zero net new failures").
11. State that raw HTML and screenshot artifacts are assumed public-data-only and that any PII-handling policy is out of scope for this epic (or in scope with a concrete plan).

## Optional Future Improvements

- A `pipeline_dashboard` materialized view for operator queries (runs, durations, stale counts).
- Trace correlation: propagate a W3C traceparent from Windmill → backend → artifacts for cross-tool debugging.
- Backfill tooling to replay a historical `pipeline_run` from its persisted artifacts — useful for prompt/model upgrades without re-fetching.
- Content-hash-based dedupe across runs (not just within a run) for `content_artifacts`.
- A `pipeline_run_diffs` helper that compares two runs of the same manifest to expose drift.
- Export of run summaries to Beads as an `evidence` attachment on the originating subtask.

## Direct Answers to Review Questions

**1. Windmill as orchestrator vs domain executor — does business logic leak?**
Mostly no, with two thin leaks: (a) retry policy is implicitly Windmill-owned, and (b) `next_recommended_step` risks encoding flow-graph decisions on the backend side. Both are fixable in the spec with two sentences. The §"Active Contract" prohibition list is strong and matches the existing shared-instance pattern in `ops/windmill/README.md`.

**2. Are the backend step endpoints too fine, too coarse, or appropriately resumable?**
Too fine. Ten endpoints at MVP is ~2× what a single bounded run needs. Merge `search-rerank` into `search-execute`, defer `promote` to post-MVP, and the remaining six endpoints are appropriately resumable.

**3. Is the proposed schema enough for auditability and replay without avoidable operational burden?**
Over-built for MVP. Eight tables can compress to four: `pipeline_runs`, `pipeline_steps`, `search_result_snapshots`, `content_artifacts`. Freshness decisions fold into `pipeline_steps`. The full schema is a good *eventual* target, not a good starting migration.

**4. Is latest-good fallback safe? What metadata / alerting is missing?**
Not yet safe. Missing: consecutive-fallback ceiling, per-family `max_stale_hours`, always-alert on `stale_backed=true`, zero-result vs failure distinction, preservation of original `provider_endpoint_hash`, and a `stale_backed_count` summary metric. See "Freshness / Latest-Good Fallback Critique" for the full list.

**5. Are SearXNG, reader, MinIO, Postgres, pgvector responsibilities separated cleanly?**
Yes. The spec correctly treats SearXNG as a *primitive* returning candidates, reader/extraction as persisted evidence, MinIO as bulk artifact home, Postgres as state-of-record, and pgvector as downstream ingestion only. The one nuance: the spec should say explicitly that `document_chunks` writes are the *only* place pgvector is mutated by the pipeline.

**6. Which pieces should be cut from MVP?**
Private SearXNG provisioning as a blocker, `pipeline_freshness_decisions` table, `search_queries` registry table, split fetch/extraction tables, `search-rerank` endpoint, `promote` endpoint, Playwright fallback, Z.ai OCR fallback, and the dedicated `pipeline_retry_step` flow. See "MVP Cut Recommendations" for details.

**7. What failure drills are missing before rollout?**
Eight drills listed above. The critical four are: crash-mid-step, partial MinIO write, idempotency replay, and stale-ceiling fail-closed.

**8. What sequencing changes would reduce implementation risk?**
Reorder so that `bd-jxclm.2` ships the *reduced* schema (four tables), `bd-jxclm.3` ships only the six MVP endpoints, `bd-jxclm.4` lands with the *existing* search backend (not SearXNG), `bd-jxclm.5` ships reader with direct HTTP + readability only (no Playwright, no OCR), `bd-jxclm.9` ships the daily + manual flows, and `bd-jxclm.6/.7/.8` and `.10` run in parallel after the skeleton exists. This sequences value in front of infra rather than behind it.

**9. Security or data-retention risks in MinIO / raw artifact model?**
Three: (a) no numeric retention is committed in-spec, (b) raw HTML screenshots may carry third-party tracking content or contact details, (c) MinIO bucket ACLs are not mentioned. All three should be explicitly either in scope with a plan or declared out of scope with a rationale. Recommend explicit numeric retention in §"Retention" and a one-line statement that MinIO buckets are private with backend-only access.

**10. Should any logic currently proposed for backend belong in Windmill, or vice versa?**
No "backend → Windmill" moves are warranted — the backend bias is correct. One small "Windmill → backend" move: the alert *content* for freshness and promotion should be constructed in the backend (returned in `operator_summary` + `alerts[]`) and Windmill should be a dumb transport, not a message formatter. Everything else can stay where the spec puts it.

---

**Summary.** Approve with the spec edits above. The direction is correct; the MVP shape is slightly too ambitious for a founder-led team and the freshness semantics need two paragraphs of tightening. After those edits, `bd-jxclm.2` is a safe place to start implementation.
