# Data-Moat Windmill Ratchet Planning Review

Date: 2026-04-27
Status: Additional planning review, no implementation dispatched
Related spec: `docs/specs/2026-04-27-data-moat-cycle-review-architecture.md`
Related review: `docs/reviews/2026-04-27-data-moat-original-workflow-pain-point-review.md`
Related Beads: `bd-cc6a4`, `bd-0si04`, `bd-dcq8f`, `bd-n6h1c`

## Summary

The current PR correctly blocks cycle reporting on Windmill-native transparency
and keeps Affordabot product truth in Railway Postgres, pgvector, MinIO, and
backend/admin read models.

The remaining planning risk is not "missing dashboard." It is another long run
of cycles where operators can see more activity but the structured and
unstructured data paths do not materially improve. After 30+ low-progress
iterations, the architecture needs a ratchet: every cycle must either upgrade
specific jurisdiction/source-family cells, produce reason-coded blockers that
change the next source-catalog/query/probe plan, or explicitly stop the current
line of work.

## Windmill Docs Consulted

Primary source:

- `https://www.windmill.dev/docs/core_concepts`

Relevant concepts:

- workflows as code: checkpointed tasks, parallel child jobs, sleeps, approval,
  deterministic replay, and git/CLI sync
- labels: static labels plus runtime `wm_labels` propagate to jobs and support
  Runs filtering
- assets: `s3://`, `res://`, and `volume://` references can visualize data
  movement and connect runtime evidence to datasets/resources
- resources/resource types: structured credentials/config for databases and
  third-party systems
- object storage/S3: `S3Object` inputs/outputs and bucket explorer support for
  large files and binary artifacts
- concurrency limits and job debouncing: native controls for provider pressure,
  duplicate triggers, and high-volume change events
- Postgres triggers, streaming/progress, generated UIs, rich rendering, service
  logs, search, git/CLI sync, and CI governance

Implication: Windmill should become the runtime laboratory and execution
ledger for data-moat iteration, not only a scheduler that links out to backend
cron jobs.

## Progress Ratchet

Before implementation dispatch, the plan should add this operating rule:

Each cycle must classify every target cell as exactly one of:

- `upgraded`: moved from missing/intent/blocked to a stronger stored or
  live-proven state
- `regressed`: lost freshness, proof, extractability, or storage/read-back
- `unchanged_reasoned`: still missing/blocked, but with a stable reason code
  and a changed next action
- `unchanged_stale`: no meaningful new information

`unchanged_stale` is the failure mode that created many low-progress cycles.
After two consecutive stale cycles for the same cell, the next cycle may not
repeat the same action. It must choose one:

- revise source catalog / known official roots
- revise structured probe or query template
- move to official-root crawl/index evaluation
- close the cell as not worth current effort
- escalate to HITL for source-family/jurisdiction correction

This is a product planning rule, not a UI feature.

## Windmill Utilization Review

The spec already names the right Windmill primitives. The implementation plan
should make them executable in this order:

1. Build a Windmill-native `data_moat_cycle` flow or workflow-as-code harness
   before report generation. Use tasks for external/provider work and steps for
   cheap stable values like `cycle_id`, selected jurisdiction pack, and source
   family config.
2. Require labels and `wm_labels` on every job so Runs can filter by
   `cycle_id`, `feature_key`, `jurisdiction_id`, `source_family`,
   `policy_family`, `lane`, `stage`, and `provider`.
3. Return small `cycle_evidence_envelope` payloads from every relevant job.
   Large payloads must be S3/MinIO pointers, not job-result blobs.
4. Register Railway Postgres, MinIO/S3, SearXNG, and provider configs as
   Windmill Resources where secret policy permits. Product writes still go
   through backend-owned contracts when invariants matter.
5. Use Windmill Assets to expose `s3://`, `res://`, and, if used,
   `volume://` references for runtime data movement. Do not add a duplicate
   Affordabot lineage table that only repeats those runtime links.
6. Use concurrency limits and worker groups for provider pressure before
   adding app-side throttling. Use debouncing for future trigger-heavy change
   events, especially Postgres-triggered or webhook-triggered follow-on work.
7. Use generated UIs for manual runtime probes and jurisdiction-pack launch
   inputs. Do not make Windmill Apps the product review/admin truth surface.
8. Use progress/streaming/rich results/service logs for operator debugging
   during a run. Persist only normalized evidence pointers and product verdicts
   into Affordabot.
9. Keep flows/scripts/workflows-as-code git/CLI managed and reviewable. Avoid
   UI-only Windmill edits for anything that becomes part of the data-moat path.

Decision: `ALL_IN_NOW` for Windmill as the data-moat runtime laboratory and
evidence ledger. `CLOSE_AS_NOT_WORTH_IT` for replacing Railway Postgres,
pgvector, MinIO, or Affordabot admin product truth during this work.

## Structured Path Review

The structured path needs a smaller and stricter loop than "expand corpus."
The first structured implementation pass should be a jurisdiction-pack proof
ratchet:

1. Choose 3-6 jurisdictions and 3-5 source families.
2. For every target, record `jurisdiction_id`, `source_family`,
   `policy_family`, endpoint/root, expected extraction depth, and economic
   relevance before coding probes.
3. Require each proof row to include row count, schema fingerprint, freshness,
   provenance, storage/read-back state, Windmill run URL, and extraction depth.
4. Reject upgrades where the proof is only catalog existence, endpoint intent,
   generated config, or planned schedule.
5. Treat C14 non-fee depth as a cycle-level metric, not an afterthought.
   At least one target in the first pack should exercise non-fee extraction
   depth: zoning, permits, inspections, meeting-action lineage, housing
   mandates, business licensing, or parking/TDM.
6. Each cycle must update a source-catalog diff: added official roots,
   removed/invalid roots, schema changes, extractor gaps, and economic
   handoff blockers.

The structured path should not start with more adapter architecture. It should
start with target selection and a live proof pack that makes C2/C13/C14 move
or fail loudly.

## Unstructured Path Review

The unstructured path needs to stop proving search plumbing and start proving
official-source acquisition cells.

1. Build deterministic jurisdiction profiles and source-family query templates
   first. The profile must have an owner/reviewer because a wrong profile makes
   every downstream search look productive while targeting the wrong thing.
2. Use SearXNG as the primary validation lane only after provider health,
   query/result counts, and zero-silent-fallback behavior are visible per
   cell/query.
3. Separate gates:
   - retrieval found a candidate
   - candidate is official or accepted official-platform equivalent
   - candidate matches the source family
   - reader output has substance
   - artifact is stored and read back
   - cell is economically useful or explicitly blocked
4. Report baseline-vs-current template movement per jurisdiction/source
   family. Provider-level benchmark metrics are not enough.
5. After two stale cycles for a weak-SEO jurisdiction/source-family cell,
   evaluate official-root crawling/indexing, such as Scrapy+Meilisearch or
   YaCy, rather than repeating SearXNG queries.
6. Keep LLM enrichment downstream and measured only as uplift over weak or
   missing deterministic cells. It cannot declare absence, validate official
   source truth, or replace the canonical query/profile path.

## Proposed Pre-Implementation Gate

Before any backend/frontend implementation dispatch, HITL should approve one
cycle-pack launch contract:

- jurisdiction pack: 3-6 jurisdictions
- source families: 3-5 families with at least one non-fee/depth family
- target cells: explicit `jurisdiction_id + source_family + policy_family`
- structured targets: official endpoints/roots and expected proof depth
- unstructured targets: deterministic query templates and known official roots
- Windmill contract: labels, `wm_labels`, evidence envelope, assets/resources,
  concurrency/debounce plan, and generated runtime input UI
- progress rule: no third repeat of an `unchanged_stale` action
- stop rule: if a lane produces no upgraded cells or new reason-coded blockers
  after two cycles, revise the source catalog/query/probe strategy before
  rerunning

## External Model Review Checkpoint

Run one bounded external-model red-team review after the cycle-pack launch
contract is drafted and before implementation dispatch.

Use this review for adversarial planning critique only. It does not replace
HITL approval, Beads dependency order, or source-grounded verification.

Recommended lanes:

- DeepSeek V4-Pro or equivalent long-context reviewer: full-package architecture
  critique across PR docs, Beads graph summary, Windmill docs-derived
  requirements, and the first cycle-pack launch contract.
- Kimi K2.6 or equivalent agentic-coding reviewer: implementation-plan
  critique focused on whether future agents will overbuild custom code instead
  of using Windmill-native workflows, labels, resources, assets, object storage,
  generated inputs, concurrency, debouncing, and git/CLI governance.

Boundaries:

- The review is advisory. It can produce findings, but cannot mark the PR ready
  or authorize implementation.
- Each finding must cite an exact file section, Beads id, or missing acceptance
  criterion. Generic model advice is ignored.
- Each accepted finding must map to one of:
  - spec/docs patch
  - Beads acceptance-criteria/comment update
  - explicit `CLOSE_AS_NOT_WORTH_IT`
- Do not ask the reviewer to design a new architecture from scratch.
- Do not let the review re-open settled decisions: Railway Postgres, pgvector,
  MinIO, and Affordabot admin remain product truth.
- If model/API access is unavailable, do not block implementation indefinitely.
  Record `external_model_review_unavailable` and require a human skim of the
  same prompt before dispatch.

Suggested review questions:

1. Does this plan prevent another 30+ low-progress iteration cycle?
2. Where are we still underusing Windmill-native capabilities?
3. Where does the plan risk moving product truth into Windmill scripts/apps?
4. Are the structured path gates strong enough to move C2/C13/C14?
5. Are the unstructured path gates strong enough to avoid search-plumbing churn?
6. Which acceptance criterion should change before the first implementation
   task starts?

## Recommended Beads Tightening

No new implementation epic is needed. Tighten existing Beads instead:

- `bd-cc6a4.1`: include the progress-ratchet enum and stale-repeat stop rule
  in the cycle report contract.
- `bd-cc6a4.2`: require the Windmill runtime-laboratory plan, not only labels
  and run links.
- `bd-cc6a4.8`: implement the Windmill harness/evidence primitives before the
  report generator.
- `bd-0si04.1`: require the structured target matrix to name non-fee/depth
  targets and source-catalog diff expectations.
- `bd-dcq8f.1`: require profile owner/reviewer, baseline-vs-current query
  comparison, and official-root crawl escalation criteria.
- `bd-cc6a4`: require one bounded external-model red-team review before
  implementation dispatch, unless unavailable and replaced by a human skim of
  the same prompt.

## Verdict

Recommendation: revise PR #445 before HITL approval.

The current package is directionally right. The revision should make the
progress ratchet explicit so the next 10-20 cycles cannot become 30 more
iterations of visible activity with little data-path movement.
