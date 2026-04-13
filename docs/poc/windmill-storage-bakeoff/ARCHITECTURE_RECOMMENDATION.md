# Architecture Recommendation: Windmill Storage Boundary Bakeoff

Date: 2026-04-12
Tracking: `bd-jxclm.15` used as temporary reconciliation key while Beads mutations are broken.

## Recommendation

Adopt a hybrid architecture:

- Windmill owns orchestration: schedule/manual trigger, DAG shape, retries, branches, per-jurisdiction fanout, failure handlers, run history, and operator controls.
- Affordabot owns product data invariants through a small domain-command layer or shared package: canonical document identity, idempotency, freshness semantics, artifact references, chunk provenance, sufficiency gates, and analysis output shape.
- Storage remains boring infrastructure: Postgres/pgvector/MinIO are the durable state systems. Windmill may write operational run reports, but product records should be written through affordabot domain commands.

The final locked boundary, including frontend, Postgres, pgvector, and MinIO ownership, is documented in `docs/architecture/2026-04-12-windmill-affordabot-boundary-adr.md`.

The brownfield implementation contract, including exact existing-stack mapping, command contracts, identity, atomicity, concurrency, frontend read models, and two-agent execution waves, is documented in `docs/specs/2026-04-13-windmill-domain-brownfield-spec-lock.md`.

This is not a recommendation to preserve the current monolithic backend cron pattern. The current pattern should still be replaced by Windmill-native DAGs.

## Evidence Produced

Two comparable San Jose meeting-minutes POCs were implemented:

- Path A, Windmill-heavy direct storage: `backend/scripts/verification/windmill_bakeoff_direct_storage.py`
- Path B, Windmill plus affordabot domain boundary: `backend/scripts/verification/windmill_bakeoff_domain_boundary.py`

Both paths exercised:

- SearXNG-shaped search input
- Z.ai reader-shaped content extraction
- MinIO-shaped artifact references
- pgvector-shaped chunk indexing
- final analysis with evidence references
- first run
- rerun/idempotency
- source failure
- reader failure
- storage failure
- stale-but-usable
- stale-blocked

Live Windmill/SearXNG/Z.ai/Postgres/MinIO execution was intentionally not used in this pass because agent secret access was restricted after the 1Password popup incident. The local substitutes preserve contract shape but do not prove live service connectivity.

## Path A Findings: Windmill-Heavy Direct Storage

Path A proved that a Windmill/direct-storage implementation can be made to pass the thin slice:

- first run succeeds
- rerun avoids duplicate documents, chunks, and analysis rows
- stale-but-usable emits an alert and proceeds
- stale-blocked fails closed
- failure states are explicit
- a Windmill export is present

But the implementation had to recreate domain logic inside the direct-storage runner:

- canonical document key generation
- content hashing
- object key construction
- search snapshot identity
- document upsert semantics
- chunk identity and upsert behavior
- evidence references
- freshness gates
- analysis idempotency

The final Path A implementation is also larger:

- direct-storage runner: about 1,000 lines
- path docs plus flow export: about 1,200 additional lines

The most important architectural signal is that Path A works only by making the Windmill script act like an application backend. A truly Windmill-maximal version would need many granular scripts and explicit state handoff between steps, which moves even more product semantics into Windmill.

## Path B Findings: Windmill Plus Domain Boundary

Path B also passed the same thin slice:

- first run succeeds
- rerun avoids duplicate search snapshots, documents, artifacts, chunks, and analysis
- stale-but-usable emits `freshness_gate:stale_but_usable` and proceeds
- stale-blocked fails closed before read/index/analyze
- source, reader, and storage failures stop at the correct boundary
- analysis fails closed when evidence chunks are absent
- a Windmill flow/script export is present
- unit tests cover idempotency, stale-blocked behavior, and no-analysis-without-evidence

The Path B domain commands are coarse enough to justify the backend/domain layer:

- `search_materialize`: query-scope snapshot identity
- `freshness_gate`: freshness policy and zero-result semantics
- `read_fetch`: canonical document identity and artifact dedupe
- `index`: chunk provenance and upsert idempotency
- `analyze`: sufficiency/evidence gate
- `summarize_run`: links Windmill run IDs to product state counts

The important architectural signal is that Path B keeps Windmill as the orchestration runtime without turning Windmill scripts into the hidden product backend.

## Decision Matrix

| Criterion | Path A: Windmill Direct Storage | Path B: Domain Boundary |
| --- | --- | --- |
| Windmill orchestration usage | Medium; flow export exists, but main logic remains one large runner | High; flow can call coarse commands while preserving step graph |
| Product invariant locality | Weak; invariants live in Windmill/direct-storage code | Strong; invariants are named domain commands |
| Idempotency | Proven, but hand-implemented in storage runner | Proven and tied to domain commands |
| Provenance | Proven for thin slice, but assembled inside runner | Proven as domain invariant |
| Failure behavior | Proven, but warm/cold state must be carefully documented | Proven with clearer step-scoped fail-closed behavior |
| Testability | Possible, but scripts trend toward a second backend | Better; domain commands can move into normal backend/package tests |
| Frontend/read-side fit | Needs a read model/API anyway | Natural fit; backend/domain layer owns product views |
| Risk of reinventing backend in Windmill | High | Lower |

## Architecture To Lock For Next Implementation

Use Windmill as the pipeline application shell, not as the product data owner:

1. Windmill flow: `pipeline_daily_refresh`
2. Windmill steps:
   - `search_materialize`
   - `freshness_gate`
   - branch on freshness status
   - `read_fetch`
   - `index`
   - `analyze`
   - `summarize_run`
3. Windmill native features:
   - per-step retries/backoff
   - branch-one/fail-closed behavior
   - per-jurisdiction loop
   - schedule and manual trigger
   - failure handler
   - run history
4. Affordabot domain commands:
   - implemented as a small tested Python package or coarse HTTP endpoints
   - no low-level `insert_row` / `upload_object` endpoint sprawl
   - own all Postgres/pgvector/MinIO product writes
5. Direct Windmill writes:
   - allowed only for operational reports/log mirrors
   - not allowed for canonical documents, chunks, analysis outputs, or provenance rows

## What Still Needs Live Validation

This POC is enough for architecture discussion, but not final deployment readiness.

Live validation still needs:

- private/dev SearXNG endpoint call from Windmill
- Z.ai direct reader call from the same runtime path
- Z.ai LLM analysis call from the same runtime path
- Postgres + pgvector write/read using real schema or migration prototype
- MinIO artifact write/read with real bucket config
- Windmill run URL evidence from the shared `affordabot` workspace
- failure handler notification evidence
- no raw 1Password GUI prompts during the live run

## Strategic HITL Question

The architecture decision to discuss is:

Should the next implementation build Path B as:

1. coarse backend HTTP endpoints called by Windmill, or
2. a shared affordabot domain package imported by Windmill worker scripts?

The POC evidence favors the domain boundary either way. The remaining choice is transport/deployment ergonomics, not whether product invariants should live in Windmill.
