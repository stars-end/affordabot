# Windmill Storage Boundary Architecture Review

Reviewer: External architecture consultant (independent)
Date: 2026-04-12
PR: #426 at ea26fbc8e67832bfc6d846d759b2b41840b85727
Feature-Key: bd-jxclm.15
Beads: offline; reconciliation pending infra repair.

## Verdict

approve_with_changes

## Score

72 / 100

## Executive Summary

The POC evidence supports locking Path B (domain boundary) as the architecture direction, but not at the confidence level the recommendation claims. The core signal is correct: Path A's direct-storage runner necessarily absorbs domain invariants (canonical identity, idempotency, provenance, sufficiency) that should not live in orchestration code. However, the POC has structural limitations that weaken the comparison: Path A was implemented as one monolithic runner rather than decomposed Windmill scripts, and neither path was tested against live infrastructure. The recommendation is directionally right but overconfident. Three specific spec gaps must be closed before the architecture lock is final: canonical document key divergence between paths, partial-write rollback semantics, and multi-jurisdiction concurrency isolation.

## Findings

### F1: Canonical document key divergence between paths (Severity: HIGH)

Path A and Path B produce **different canonical document keys** for the same document:

- Path A (`windmill_bakeoff_direct_storage.py:102-107`): `canonical_document_key(url)` returns `sanjoseca.gov/your-government/departments-offices/city-clerk/city-council-meetings` — pure URL-derived, jurisdiction-agnostic.
- Path B (`windmill_bakeoff_domain_boundary.py:43-49`): `canonical_document_key(jurisdiction, url)` returns `san-jose-ca::a653e7debe31e650` — jurisdiction-prefixed + URL hash.

This is not cosmetic. Path B's key is jurisdiction-scoped, which is the correct invariant for a multi-jurisdiction product. Path A's key is global by URL, meaning two jurisdictions sharing the same URL would collide or overwrite each other's document records. The POC did not expose this because it only tested one jurisdiction.

The recommendation document (`ARCHITECTURE_RECOMMENDATION.md:57`) lists "canonical document key generation" as a domain invariant Path A recreates, but does not flag that the two implementations disagree on what the invariant *is*. This is a latent data-integrity bug in Path A that the POC missed because its scope was too narrow.

**Required change**: Before architecture lock, specify the canonical document identity contract explicitly. The key must include jurisdiction scope. Path A's URL-only key is incorrect for a multi-jurisdiction system.

### F2: Path A was not given a fair Windmill-native decomposition (Severity: MEDIUM)

The POC's Path A implementation is a single 1122-line monolithic runner (`windmill_bakeoff_direct_storage.py`). The Windmill flow export calls this one script with different `scenario` arguments rather than decomposing into per-step scripts.

The POC acknowledges this at `path-a-direct-storage/README.md:18-19`:

> "The current Windmill export demonstrates flow shape and retry wiring, but most execution remains concentrated in one script entrypoint."

And the bakeoff root `README.md:67-68`:

> "The most important architectural signal is that Path A works only by making the Windmill script act like an application backend."

This is true but partially self-inflicted. A Windmill-native Path A with per-step scripts and explicit `results.*` state passing would look different: each step script would be small, state would flow through Windmill's built-in step-output mechanism, and the domain logic would be more spread but also more inspectable per-step. Whether this is *better* depends on whether spreading domain invariants across many Windmill scripts is worse than concentrating them in a domain package.

The POC did not test this alternative. The comparison is between "one big direct-storage runner" vs "domain boundary with step decomposition." A more Windmill-native Path A could narrow the gap on step-level observability while still having the invariant-locality problem.

**Impact on verdict**: This finding does not change the directional recommendation, but it reduces confidence that the POC fully explored Path A's design space. The finding is a fairness gap, not a reason to reconsider Path A. A more Windmill-native Path A would spread the same invariants across more scripts, making them *harder* to test and review, not easier.

### F3: No partial-write rollback or transaction boundary evidence (Severity: HIGH)

Both paths fail fast on storage errors, but neither demonstrates what happens when a **partial write** occurs:

- Path B's `index` step (`windmill_bakeoff_domain_boundary.py:319-345`) writes chunks one at a time in a loop. If chunk 3 of 5 fails, chunks 1-2 are already written. The POC's `storage_failure` drill only tests failure at the *start* of a step (via `fail_storage_step`), not mid-step.
- Path A's `DirectStoragePipelineRunner.run()` writes objects, relational rows, and vector entries across multiple stores with no transaction boundary.

For Postgres/pgvector, a partial chunk write means the vector index contains some chunks for a document but not all. A downstream `analyze` step that queries by `canonical_document_key` would find incomplete evidence and potentially produce a partial analysis. The POC's `analyze` command checks `if not usable_chunks` but does not check chunk completeness relative to the source document.

This is an architectural gap, not a POC deficiency. The architecture recommendation should specify whether domain commands must be transactional, whether partial writes are acceptable operational state, or whether a compensating action is required.

**Required change**: The architecture lock must include a write atomicity contract. At minimum: domain commands must either complete fully or leave no partial product state. For commands spanning multiple stores (Postgres + MinIO), specify whether two-phase commit is required or whether eventual consistency with compensating writes is acceptable.

### F4: No multi-jurisdiction fanout isolation evidence (Severity: MEDIUM)

The POC tests a single jurisdiction (San Jose CA). The architecture recommendation proposes "per-jurisdiction loop" as a Windmill feature. But the POC does not demonstrate:

- Whether two jurisdictions running concurrently share storage state correctly
- Whether idempotency keys are properly scoped per-jurisdiction
- Whether a failure in one jurisdiction's pipeline affects another's

The `idempotency_key` format (`san-jose-ca:meeting_minutes:2026-04-12`) is jurisdiction-scoped, which is good. But `InMemoryDomainStore` (Path B) and the flat-file stores (Path A) have no isolation boundaries between jurisdictions. If two Windmill flow instances write concurrently, the in-memory dict / JSON file will have interleaved mutations.

This matters because the architecture recommendation's `concurrency: limit: 1` in both flow YAML exports is a bakeoff guard, not a production constraint. Production will need parallel jurisdiction fanout.

**Required change**: The architecture lock must specify the concurrency model for multi-jurisdiction execution and whether domain commands must be concurrency-safe.

### F5: Path B's DomainBoundaryService is not yet a boundary — it is a monolithic class (Severity: MEDIUM)

The `DomainBoundaryService` class (`windmill_bakeoff_domain_boundary.py:204-394`) owns all domain commands and all storage adapters. It is ~190 lines of coupled logic where `search_materialize` directly calls `self.search_client.search()` and writes to `self.store`.

This is fine for a POC. But the architecture recommendation presents these as "coarse affordabot domain commands" that could be HTTP endpoints or a shared package. The current implementation is neither: it is a single class that mixes I/O (search, reader), domain logic (identity, idempotency), and storage writes in one object.

The risk is that when this gets refactored into the actual implementation, the "domain boundary" becomes a thin wrapper if each command is extracted without preserving the invariant logic. The POC does not clearly separate "what is the domain invariant" from "what is the storage operation."

**Required change**: Before implementation, each domain command should have a documented contract specifying: (1) the invariant it protects, (2) the storage operations it performs, (3) the failure modes and their effects on storage state, (4) the idempotency guarantee.

### F6: Path A Windmill flow export is a test harness, not a pipeline (Severity: MEDIUM)

The Path A flow YAML (`pipeline_daily_refresh_direct_storage__flow/flow.yaml`) defines five modules: `search_materialize`, `rerun_idempotency`, `searx_failure_drill`, `reader_failure_drill`, `storage_failure_drill`. These are verification drills, not pipeline stages. Each calls the same monolithic script with different `scenario` parameters.

In contrast, Path B's flow YAML defines six steps that map 1:1 to domain commands, with per-step retry policies, input transforms referencing prior step outputs (`results.search_materialize`, `results.freshness_gate`, etc.), and a realistic concurrency limit. This is a credible production flow shape.

**Evidence**:
- `ops/windmill/f/affordabot/pipeline_daily_refresh_direct_storage__flow/flow.yaml`
- `ops/windmill/f/affordabot/pipeline_daily_refresh_domain_boundary__flow/flow.yaml`

### F7: No live Windmill execution evidence (Severity: HIGH)

Neither path has been executed on a real Windmill instance. The flow YAMLs are committed but never pushed via `wmill sync push`. This means:

- Windmill's native retry/backoff behavior is untested
- `$flow_job_id` variable substitution is untested
- `results.search_materialize` inter-step data passing is untested
- Concurrency limits (`limit: 1`) are untested
- Error handler wiring (`ws_error_handler_muted: false`) is untested

This is the single largest gap in the bakeoff evidence. The POC proves contract shape and design intent, not runtime behavior.

### F8: Analysis evidence gate is correct but incomplete (Severity: LOW)

The `analyze` command correctly refuses to run without evidence chunks (`analysis_requires_evidence` error in Path B, checked via `if not usable_chunks`). But neither path tests:

- Chunks from a *different* jurisdiction leaking into analysis scope
- Chunks from a prior run with different idempotency key being reused
- Stale chunks from an old run being used for a new analysis

Path B's `analyze` filters by `jurisdiction` match, which partially addresses the first case, but the filter is in-memory and not enforced at the storage/schema level.

### F9: stale_but_usable does not trigger re-read (Severity: LOW)

In both paths, when freshness is `stale_but_usable`, the pipeline proceeds with existing data without re-reading. This is correct for the POC scope, but the architecture should specify whether `stale_but_usable` means:
- (a) "Proceed with existing data and alert" (current behavior)
- (b) "Re-read and compare; if unchanged proceed, if changed alert and update"

Option (b) is more useful for a product that needs to detect when source material changes. The current implementation is not wrong, but may need extension.

### F10: Path B domain commands are genuinely coarse — positive finding (Severity: INFO)

`DomainBoundaryService` owns six named commands, each protecting a specific invariant:

| Command | Invariant |
| --- | --- |
| `search_materialize` | idempotent snapshot by query+scope hash |
| `freshness_gate` | explicit stale policy with zero-result semantics |
| `read_fetch` | canonical document identity + artifact dedup |
| `index` | chunk provenance + upsert idempotency |
| `analyze` | fail-closed without evidence |
| `summarize_run` | orchestration-to-domain linkage |

None of these are thin SQL wrappers. Each enforces at least one product rule that would be unsafe to push into Windmill flow logic. This is the strongest evidence in favor of Path B.

**Evidence**: `backend/scripts/verification/windmill_bakeoff_domain_boundary.py:204-394`

## Architecture Decision

**Path B domain boundary** — with the changes specified below.

The directional signal is correct. Path A's monolithic runner proves that direct storage writes work, but also proves that they necessarily absorb domain invariants. The POC's own evidence (`path-a-direct-storage/README.md:35-42`) lists nine domain responsibilities that Path A's runner had to recreate. This is the strongest signal in the entire POC: the list is not hypothetical, it is what the implementation actually needed.

Lock Path B as the target architecture, subject to closing the three high-severity spec gaps (F1, F3, F4) in a bounded live validation pass.

## Boundary Recommendation

| Layer | Owns | Does Not Own |
|-------|------|--------------|
| **Windmill** | DAG shape, schedule/manual trigger, per-step retries/backoff, branch on freshness, per-jurisdiction fanout, failure handlers, run history, operator controls, run-level observability | Product data writes, domain invariant enforcement, canonical identity decisions |
| **Affordabot domain commands** | Canonical document identity (jurisdiction-scoped), idempotent writes, freshness policy evaluation, artifact deduplication, chunk provenance, sufficiency/evidence gating, analysis output shape, write atomicity | Search execution, reader execution, LLM calls, DAG branching decisions, schedule management |
| **Storage** | Durable persistence (Postgres/pgvector/MinIO), read-path queries, backup/recovery | Domain logic, invariant enforcement, orchestration state |

### Direct Windmill write allowance

Windmill may write operational metadata only: run summaries, error logs, retry counters. Windmill must never write canonical documents, chunks, analysis outputs, provenance rows, or artifact references.

## HTTP Endpoints vs Shared Package

**Recommendation: Staged approach.**

**Stage 1 (pre-MVP): Shared Python package.**

Start with a `affordabot-domain` package imported directly by Windmill worker scripts.

Reasons:
- Fastest path to working pipeline; no HTTP overhead, no auth layer, no service deployment
- Windmill workers run Python; a shared package is the natural integration
- The domain commands are small and testable; they do not need a separate service boundary yet
- Package versioning provides contract enforcement: Windmill scripts depend on `affordabot-domain>=0.1.0`
- Design the package API as if it will become HTTP — function signatures should map cleanly to request/response

**Stage 2 (post-MVP): Migrate to HTTP endpoints when triggered.**

Trigger conditions for migration:
- Multiple consumers of domain commands (not just Windmill)
- Need for independent deployment/scaling of domain layer
- Need for language-agnostic access
- Need for rate limiting / auth at the domain boundary
- Frontend/API needs to invoke pipeline steps directly

**Why not HTTP-first**: The POC's `ops/windmill/README.md` documents the current Windmill integration pattern as "Windmill triggers authenticated backend cron endpoints over HTTP." This is the existing pattern for *triggering* jobs. But the domain commands are *inside* the pipeline, not *triggering* it. Adding HTTP for every step of a 6-step pipeline creates 6 new endpoints, each needing auth, error handling, and observability. That is premature for a single consumer.

**Why not package-only forever**: A shared package means Windmill workers have direct database access. This is acceptable pre-MVP but becomes a deployment coupling problem when the backend needs to evolve its schema or add cross-cutting concerns (audit logging, rate limiting). HTTP endpoints decouple deployment at the cost of operational complexity.

## Evidence Assessment

### First run
- **Path A**: Pass. Status `succeeded`, 3 search results, 1 document, 1 chunk, 1 analysis.
- **Path B**: Pass. Status `succeeded`, 2 search results, 1 document, 5 chunks, 1 analysis.
- **Notable**: Path B produces 5 chunks (line-based splitting) vs Path A's 1 chunk (size-based splitting at 450 chars with 80-char overlap). The chunking strategies differ, which is acceptable for POC but must be standardized in the implementation contract.

### Rerun/idempotency
- **Path A**: Pass. Document count stable (1), chunk count stable (1), analysis count stable (1). `snapshot_created: false`, `document_created: false`, `chunks_reused: 1`, `analysis_created: false`.
- **Path B**: Pass. `chunks_created: 0` on rerun, `analysis.reused: true`, same `canonical_document_key`, same `artifact_ref`.
- **Gap**: Neither path proves idempotency under concurrent rerun (two Windmill instances hitting the same jurisdiction simultaneously).

### Stale fallback
- **Path A**: Pass. `stale_but_usable` proceeds with alert. `stale_blocked` fails closed with `reason: age_hours=96.00`.
- **Path B**: Pass. `stale_but_usable` proceeds with alert `freshness_gate:stale_but_usable`. `stale_blocked` fails closed, pipeline stops before `read_fetch`.

### Source failure
- **Path A**: Pass. `source_error` status, downstream steps not executed. Cold-state: zero storage writes.
- **Path B**: Pass. `search_materialize: source_error`, pipeline terminates early.

### Reader failure
- **Path A**: Pass. `reader_error` after successful `search_materialize` + `freshness_gate`. Warm-state: prior state preserved. Cold-state: only search snapshot present.
- **Path B**: Pass. `read_fetch: reader_error`, `index` and `analyze` not executed.

### Storage failure
- **Path A**: Pass. `storage_error` at `search_materialize` step. But this tests failure at the first storage write, not mid-pipeline.
- **Path B**: Pass. `storage_error` at `index` step. Same limitation — one injection point per drill.
- **Gap**: Neither path demonstrates partial-pipeline storage failure where earlier writes succeeded but a later write fails.

### Provenance
- **Path A**: Partial. Provenance is implicit in step chain and artifact refs. No explicit claim-to-evidence linkage.
- **Path B**: Stronger. `analyze` returns `claims[].evidence_refs[]` with `chunk_id`, `canonical_document_key`, and `artifact_ref` per citation.
- **Gap**: Neither path demonstrates provenance queries (e.g., "find all analyses that cite this document"). Provenance is written but not read back.

### Windmill flow shape
- **Path A**: Weak. Flow is a test harness with verification drills as steps. Monolithic script invocation.
- **Path B**: Credible. Flow has real step separation, per-step retries, input transforms with `results.*` references. Script is a stub but the shape is production-ready.

### Local deterministic substitute limitation
Both paths use deterministic local substitutes for SearXNG, Z.ai reader, Z.ai analysis, Postgres, pgvector, and MinIO. These substitutes preserve contract shape but:
- Do not prove latency, timeout, or retry behavior under real conditions
- Do not prove connection pooling, auth, or resource cleanup
- Do not prove that the contract shape survives real API responses
- Embedding strategies differ (Path A: 12-dim; Path B: 8-dim) — neither is production-realistic

This is a known limitation, not a blocker. But it means the POC proves architectural boundaries, not operational readiness.

### Validation scripts executed during this review

```
python3 windmill_bakeoff_domain_boundary.py --scenario happy_rerun   → PASS
python3 windmill_bakeoff_domain_boundary.py --scenario stale_usable  → PASS
python3 windmill_bakeoff_domain_boundary.py --scenario stale_blocked → PASS
python3 windmill_bakeoff_direct_storage.py suite --reset-state       → PASS
git diff --check                                                     → PASS (clean)
```

## Missing Evidence

The following must be proven in live validation before the architecture lock is final:

1. **Multi-jurisdiction concurrency**: Two jurisdictions executing simultaneously against shared Postgres/pgvector/MinIO. Verify no cross-jurisdiction data leakage and correct idempotency under concurrent writes.

2. **Partial-write rollback**: A storage failure occurring mid-command (e.g., after writing 3 of 5 chunks). Verify that the domain command either completes atomically or provides a compensating action.

3. **Live Windmill flow execution**: Run the actual Windmill flow with real step outputs passed between steps. Verify that the `results.*` references work correctly in Windmill's runtime.

4. **Live SearXNG call from Windmill worker**: Verify search payload shape, timeout handling, and error mapping from real HTTP responses.

5. **Live Z.ai reader/analysis calls**: Verify contract shape alignment between POC stubs and real API responses.

6. **Real Postgres/pgvector/MinIO writes**: Verify schema compatibility, connection handling, and upsert semantics against real infrastructure.

7. **Rerun after partial failure**: A pipeline that fails at `index` on first run, then succeeds on rerun. Verify that the partial state from the first run does not corrupt the rerun.

8. **Canonical document identity across jurisdictions**: Two jurisdictions that share the same source URL. Verify that they produce distinct document keys and do not overwrite each other.

## Required Spec Changes

1. **Canonical document identity contract**: Specify that canonical document keys must be jurisdiction-scoped. Document the key format (e.g., `{jurisdiction_slug}::{hash(canonical_url)}`). Path A's URL-only key must be rejected as a data-integrity bug.

2. **Write atomicity contract**: Domain commands must specify whether they are atomic. For commands that write to multiple stores (e.g., `read_fetch` writes to both MinIO and Postgres), specify the expected behavior if one write succeeds and the other fails.

3. **Concurrency model**: Specify whether domain commands must be safe for concurrent execution by different Windmill flow instances. If yes, specify the locking/optimistic concurrency strategy.

4. **Chunk completeness check**: The `analyze` command must check not just that chunks exist, but that the chunk set is complete (matches the expected chunk count for the document). Otherwise, partial writes can produce incomplete analysis.

5. **Domain command contracts**: Each domain command must have a documented contract specifying: (a) invariants protected, (b) storage operations performed, (c) failure modes and storage state effects, (d) idempotency guarantee.

6. **Retry ownership**: The spec should explicitly state that Windmill owns retry *execution* (attempts, backoff) while the backend owns retry *eligibility* (returning `retryable: true/false` in step response). Currently the flow YAML defines retry policies but the domain commands don't return retryability signals.

7. **Stale-but-usable behavior specification**: Document whether `stale_but_usable` means "proceed with existing data" or "re-read and compare." The current implementation does the former; the product may need the latter.

8. **Provenance query contract**: Specify whether the read-side model must support provenance queries (claim → evidence → document → search snapshot). If yes, the storage schema must include the appropriate indexes and relations.

9. **Multi-jurisdiction fanout mechanism**: Specify whether Windmill uses its native `for_loop` construct or a top-level fan-out flow that spawns per-jurisdiction sub-flows.

10. **Contract versioning enforcement**: The `contract_version` field is in the envelope but not validated by domain commands. Add a version check at the domain package entry point that fails closed on major version mismatch.

## Final Recommendation

Lock **Path B (domain boundary)** as the architecture direction, but do not treat this lock as final until three high-severity spec gaps are closed:

1. Canonical document identity must be jurisdiction-scoped (F1)
2. Write atomicity must be specified (F3)
3. Concurrency model must be specified (F4)

Use the **staged approach** for implementation: shared Python package first, HTTP endpoints only when trigger conditions are met.

The POC's strongest evidence is the list of nine domain invariants that Path A's runner had to recreate (`path-a-direct-storage/README.md:35-42`). This is not theoretical — it is what the implementation actually needed. That list is the reason to prefer Path B: the invariants exist regardless of architecture, and Path B puts them in a place where they can be tested, reviewed, and evolved independently of the orchestration layer.

The POC's weakest aspects are the lack of live infrastructure validation and the Path A fairness gap. These reduce confidence but do not change the directional signal.

**What would change the recommendation**:
- If the domain commands turn out to be thin SQL wrappers with no real invariant logic, Path B becomes unnecessary middleware. The implementation must demonstrate that each command protects a non-trivial invariant.
- If the shared package approach creates deployment coupling that blocks iteration speed, the HTTP endpoint migration should be accelerated.
- If Windmill's step-output passing proves unreliable or hard to debug in live runs, the architecture may need to shift more state management into the domain layer, reducing Windmill's orchestration role.
- If Windmill's concurrency limits prove insufficient for multi-jurisdiction fanout at scale, a queue-based architecture may be needed.
