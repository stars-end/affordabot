# Windmill Storage Boundary Architecture Review

Reviewer: external architecture consultant
Date: 2026-04-12
PR under review: #426 at `ea26fbc8e67832bfc6d846d759b2b41840b85727`
Feature-Key: `bd-jxclm.15`
Beads status: offline; reconciliation pending infra repair.

## Verdict

**approve_with_changes**

## Score

78/100

## Executive Summary

The bakeoff provides genuine architectural evidence that a domain boundary
between Windmill orchestration and affordabot product-data writes is worth
locking. Path A (direct storage) works but silently recreates an application
backend inside Windmill scripts. Path B (domain boundary) keeps Windmill as a
pure orchestrator and concentrates product invariants in testable, named
commands.

However, the evidence has structural gaps that prevent a full architecture lock
without qualification. Both paths were exercised only with deterministic local
substitutes — no live SearXNG, Z.ai, Postgres, pgvector, or MinIO calls were
made. The Windmill flow exports are reviewable YAML but have never executed on
an actual Windmill instance. The bakeoff proves *contract shape* and *design
intent*, not *runtime behavior*.

Lock Path B as the target architecture, but require a bounded live-infra
validation pass before treating the architecture as final.

## Findings

### F1: Path A script is a hidden backend (Severity: HIGH)

`windmill_bakeoff_direct_storage.py` is 1,122 lines. It contains:

- `DirectObjectStore`, `DirectVectorStore`, `DirectRelationalStore` (three
  persistence layers)
- `canonical_document_key()`, `chunk_text()`, `deterministic_embedding()`,
  `cosine_similarity()` (domain logic)
- `SearxClient`, `ReaderClient`, `AnalysisClient` (service adapters)
- `freshness_status()` (policy logic)
- `DirectStoragePipelineRunner.run()` — a 230+ line method that is a full
  pipeline implementation

This is not a Windmill script. It is an application backend that happens to be
invocable from Windmill. Moving to "many granular Windmill scripts" would not
fix this — it would scatter these invariants across scripts while making them
harder to test as a unit.

**Evidence**: `backend/scripts/verification/windmill_bakeoff_direct_storage.py`
lines 150–835.

### F2: Path B domain commands are genuinely coarse (Severity: INFO — positive)

`windmill_bakeoff_domain_boundary.py` is 591 lines total. The
`DomainBoundaryService` class owns six named commands, each protecting a
specific invariant:

| Command | Lines | Invariant |
| --- | ---: | --- |
| `search_materialize` | ~25 | idempotent snapshot by query+scope hash |
| `freshness_gate` | ~15 | explicit stale policy with zero-result semantics |
| `read_fetch` | ~30 | canonical document identity + artifact dedup |
| `index` | ~20 | chunk provenance + upsert idempotency |
| `analyze` | ~15 | fail-closed without evidence |
| `summarize_run` | ~20 | orchestration-to-domain linkage |

None of these are thin SQL wrappers. Each enforces at least one product rule
that would be unsafe to push into Windmill flow logic.

**Evidence**: `backend/scripts/verification/windmill_bakeoff_domain_boundary.py`
lines 200–380.

### F3: Path A Windmill flow export is misleading (Severity: MEDIUM)

The Path A flow YAML (`pipeline_daily_refresh_direct_storage__flow/flow.yaml`)
defines five steps, but each step invokes the *same script* with a different
`scenario` parameter. This is a test harness masquerading as a flow graph, not
a production DAG. Steps like `rerun_idempotency` and `searx_failure_drill` are
verification drills, not pipeline stages.

In contrast, Path B's flow YAML defines six steps that map 1:1 to domain
commands, with per-step retry policies, input transforms referencing prior step
outputs (`results.search_materialize`, `results.freshness_gate`, etc.), and a
concurrency limit. This is a credible production flow shape.

**Evidence**:
- `ops/windmill/f/affordabot/pipeline_daily_refresh_direct_storage__flow/flow.yaml`
- `ops/windmill/f/affordabot/pipeline_daily_refresh_domain_boundary__flow/flow.yaml`

### F4: No live Windmill execution evidence (Severity: HIGH)

Neither path has been executed on a real Windmill instance. The flow YAMLs are
committed but never pushed via `wmill sync push`. This means:

- Windmill's native retry/backoff behavior is untested
- `$flow_job_id` variable substitution is untested
- `results.search_materialize` inter-step data passing is untested
- Concurrency limits (`limit: 1`) are untested
- Error handler wiring (`ws_error_handler_muted: false`) is untested

This is the single largest gap in the bakeoff evidence.

### F5: Idempotency proven but scope is narrow (Severity: MEDIUM)

Both paths prove idempotency for the happy path: rerun with same idempotency
key produces no duplicate documents, chunks, or analyses. Path B shows
`chunks_created: 0` and `reused: true` on the analysis.

However, neither path tests:

- idempotency under *partial* prior state (e.g., search succeeded but
  read_fetch crashed mid-write)
- idempotency with *changed content* at same URL (content drift)
- idempotency across Windmill retries of the *same step* within a single flow
  run (the Windmill retry-with-same-job-id scenario)

### F6: Freshness gate is well-designed (Severity: INFO — positive)

The freshness gate correctly distinguishes:

- `fresh` (within max_stale_hours)
- `stale_but_usable` (within fallback ceiling, emits alert)
- `stale_blocked` (exceeds ceiling, fails closed)
- `empty_result` (zero results, not a transport error)

The stale_blocked drill confirms fail-closed behavior: pipeline stops before
`read_fetch`, no partial product records created. The stale_usable drill
confirms graceful degradation with an explicit alert.

**Evidence**: `docs/poc/windmill-storage-bakeoff/path-b-domain-boundary/failure-drills.md`

### F7: Analysis evidence gate is correct but untested for edge cases (Severity: MEDIUM)

The `analyze` command correctly refuses to run without evidence chunks
(`analysis_requires_evidence` error). This is the right invariant. But the
tests don't cover:

- chunks from a *different* jurisdiction leaking into analysis scope
- chunks from a prior run with different idempotency key
- stale chunks from an old run being used for a new analysis

### F8: Path A Windmill script shells out to a subprocess (Severity: LOW)

`pipeline_daily_refresh_direct_storage.py` uses `subprocess.run()` to invoke
the runner script. This is an honest workaround for the POC, but it means the
Windmill worker would need the full repo checked out — contradicting the
existing shared-instance execution model documented in `ops/windmill/README.md`
where Windmill calls backend HTTP endpoints.

Path B's Windmill script (`pipeline_daily_refresh_domain_boundary.py`) returns
deterministic step payloads inline — also a stub, but one that correctly
models the target: Windmill calls a function that calls an HTTP endpoint.

### F9: Storage failure drill only covers index step (Severity: LOW)

Path B's `storage_failure` drill injects failure at the `index` step. It does
not test:

- storage failure during `search_materialize` (snapshot write fails)
- storage failure during `read_fetch` (artifact upload fails)
- storage failure during `analyze` (analysis row write fails)

Path A covers warm-state and cold-state failures for all three failure types
but with the same limitation of testing one injection point per drill.

## Architecture Decision

**Lock Path B (domain boundary)** as the target architecture, subject to one
bounded live validation pass.

Path A is not unfairly penalized. The evidence shows that making Path A "more
Windmill-native" (many granular scripts) would make the problem worse, not
better: product invariants would scatter across scripts, become harder to test,
and create a maintenance surface that duplicates what a tested domain package
provides. The 1,122-line runner is the honest result of trying to keep product
invariants in one place without a domain boundary — and it proves the boundary
is needed.

## Boundary Recommendation

### Windmill owns

- Schedule and manual trigger entry points
- DAG step graph shape (linear with freshness branch)
- Per-step retry policy (attempts, backoff intervals)
- Step timeout
- Concurrency limits per flow
- Inter-step data passing (`results.<step>`)
- Failure handler notifications (Slack/operator alerts)
- Run history and operator visibility
- Per-jurisdiction fanout (future: `for_loop` over jurisdictions)

### Affordabot owns

- Canonical document identity (`canonical_document_key`)
- Search snapshot identity and idempotent materialization
- Freshness policy evaluation (max_stale_hours, fallback ceiling)
- Zero-result vs. transport-failure distinction
- Artifact content hashing and dedup
- Chunk provenance (chunk → document → artifact → snapshot linkage)
- Chunk upsert idempotency
- Analysis evidence sufficiency gate
- Analysis output shape and claim/evidence structure
- Run summary linking orchestration IDs to domain state

### Storage owns

- Postgres: relational rows for snapshots, documents, analyses, run summaries
- pgvector: embedding storage and similarity search
- MinIO: artifact blobs (markdown, PDFs, raw payloads)
- All durability, consistency, and retention

### Operators own

- Manual rerun decisions
- Stale-but-usable acknowledgment
- Freshness policy parameter tuning
- Jurisdiction/source-family configuration

## HTTP Endpoints vs Shared Package

**Recommendation: staged approach.**

1. **First implementation**: shared Python domain package imported by Windmill
   scripts. This avoids HTTP overhead, keeps the stack simple for pre-MVP, and
   matches the current shared-instance model where Windmill already has
   Python execution capability.

2. **Promotion trigger**: when any of these become true, extract to HTTP
   endpoints:
   - A second consumer (not Windmill) needs the same domain commands
   - The domain package needs dependencies that conflict with Windmill worker
     environment
   - The team wants to deploy domain logic independently from Windmill workers
   - Frontend/API needs to invoke pipeline steps directly

3. **Contract preservation**: whether package-import or HTTP, the domain
   command interface (input envelope, output status vocabulary, idempotency
   key semantics) must remain identical. Design the package API as if it will
   become HTTP — function signatures should map cleanly to request/response.

**Rationale**: The existing cron jobs already use HTTP endpoints
(`trigger_cron_job.py` → `POST /cron/<endpoint>`). For the new pipeline, the
domain commands are finer-grained than cron triggers. Starting with a package
avoids premature endpoint sprawl while the command surface stabilizes. The
POC's `DomainBoundaryService` class is already shaped correctly for this — its
methods take an envelope and return a status dict.

## Evidence Assessment

| Scenario | Path A | Path B | Assessment |
| --- | --- | --- | --- |
| First run | Pass | Pass | Both produce expected storage state |
| Rerun/idempotency | Pass | Pass | No duplicate records; Path B shows explicit `reused=true` |
| Stale fallback | Pass | Pass | Correct three-way distinction (fresh/usable/blocked) |
| Source failure | Pass | Pass | Clean fail-closed at search step |
| Reader failure | Pass | Pass | Clean fail-closed before index/analyze |
| Storage failure | Pass | Pass | Bounded partial state in both paths |
| Provenance | Pass | Pass (stronger) | Path B has explicit `claim → evidence_refs → chunk_id → canonical_document_key → artifact_ref → snapshot` chain |
| Windmill flow shape | Weak | Credible | Path A flow is a test harness; Path B flow has real step separation, retries, input transforms |
| Local deterministic limitation | Documented | Documented | Honest about what was not tested against live infra |

### Validation scripts executed during this review

```
python3 windmill_bakeoff_domain_boundary.py --scenario happy_rerun   → PASS
python3 windmill_bakeoff_domain_boundary.py --scenario stale_usable  → PASS
python3 windmill_bakeoff_domain_boundary.py --scenario stale_blocked → PASS
python3 windmill_bakeoff_direct_storage.py suite --reset-state       → PASS
git diff --check                                                     → PASS (clean)
```

## Missing Evidence

Before treating the architecture as finally locked, the following must be
demonstrated in a bounded live validation pass:

1. **Windmill flow execution**: push Path B flow YAML to the affordabot
   workspace and trigger a manual run. Verify `$flow_job_id` substitution,
   inter-step `results.*` passing, and retry behavior on a forced step
   failure.

2. **Live SearXNG search**: call the private/dev SearXNG endpoint from
   within the Windmill execution context. Verify the response shape matches
   the `SearxLikeClient` contract.

3. **Live Z.ai reader**: call the Z.ai direct reader from the same execution
   context. Verify markdown extraction produces content suitable for chunking.

4. **Postgres + pgvector write/read**: execute `search_materialize`,
   `read_fetch`, and `index` against the real schema. Verify idempotency
   with real Postgres `ON CONFLICT` or equivalent.

5. **MinIO artifact write/read**: upload a markdown artifact and verify the
   `artifact_ref` resolves correctly on read-back.

6. **Partial-state idempotency**: crash a step mid-execution and verify
   rerun correctly resumes without duplicating prior successful writes.

7. **Concurrency limit**: trigger two simultaneous flow runs and verify the
   `limit: 1` concurrency key prevents parallel execution.

8. **Error handler notification**: verify Slack/operator alert fires on
   step failure.

## Required Spec Changes

Before implementing Path B against real infrastructure:

1. **PR #415 spec update**: add a section documenting the Path B domain
   command interface as the canonical backend boundary. Remove or deprecate
   references to `pipeline_steps` as an affordabot-owned execution-tracking
   table — Windmill's native step history replaces it.

2. **Retry ownership clarity**: the spec should explicitly state that
   Windmill owns retry *execution* (attempts, backoff) while the backend
   owns retry *eligibility* (returning `retryable: true/false` in step
   response). Currently the flow YAML defines retry policies but the domain
   commands don't return retryability signals.

3. **Contract versioning in flow YAML**: the `contract_version` field is in
   the envelope but not validated by the domain commands. Add a version
   check at the domain package entry point that fails closed on major
   version mismatch.

4. **Multi-jurisdiction fanout**: the current POC processes one jurisdiction.
   The spec should define whether Windmill uses its native `for_loop`
   construct or a top-level fan-out flow that spawns per-jurisdiction
   sub-flows.

5. **Run summary persistence**: `summarize_run` currently writes to an
   in-memory dict. Define whether this becomes a Postgres row, a Windmill
   flow result, or both.

6. **Chunk scope isolation**: the `analyze` command queries chunks by
   jurisdiction match. Define whether this is a runtime filter or a
   schema-level partition to prevent cross-jurisdiction data leaks as the
   system scales.

## Final Recommendation

Lock Path B as the target architecture. The evidence is strong enough to
commit to the boundary design, but not strong enough to skip live validation.

**Concrete next steps**:

1. Merge PR #426 as architectural evidence (the POC code is disposable but
   the docs and flow exports are reference material).
2. Create a bounded live validation task: push the Path B flow YAML to the
   affordabot Windmill workspace, wire one domain command to real Postgres,
   and execute one manual flow run.
3. Update PR #415 spec with the boundary changes listed above.
4. Begin implementing the shared domain package for `search_materialize`
   and `freshness_gate` first — these are the highest-leverage commands
   for proving the pattern against real infrastructure.

**What would change this recommendation**:

- If live Windmill execution reveals that inter-step state passing is
  unreliable or that the `$flow_job_id` variable is not stable across
  retries, the idempotency model would need rework.
- If the shared Python package creates unresolvable dependency conflicts
  with Windmill workers, the HTTP endpoint path becomes mandatory
  immediately.
- If Windmill's concurrency limits prove insufficient for multi-jurisdiction
  fanout at scale, a queue-based architecture may be needed.
- If the team decides frontend needs to invoke pipeline steps directly
  (e.g., manual rerun from a dashboard), HTTP endpoints should be built
  from day one.
