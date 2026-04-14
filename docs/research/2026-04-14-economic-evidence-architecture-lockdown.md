# Economic Evidence Architecture Lockdown (bd-2agbe.7)

Date: 2026-04-14  
Status: consultant-review package (POC evidence consolidation)  
Feature key: `bd-2agbe.7`

## Scope

This document answers one question:

Can the current Windmill + affordabot backend + Postgres/pgvector/MinIO architecture produce data quality high enough for reasonable economic analysis?

It separates failure attribution across six dependency classes:

1. search provider quality
2. source/data quality
3. reader/substrate quality
4. evidence-card structuring quality
5. parameter/assumption/quantification quality
6. LLM explanation quality

## Evidence Base Used

1. Windmill San Jose live gate (real runtime path):
   - `docs/poc/windmill-domain-boundary-integration/artifacts/sanjose_live_gate_report.json`
   - `docs/poc/windmill-domain-boundary-integration/artifacts/sanjose_live_gate_report.md`
2. Search-source bakeoff (SearXNG vs Exa vs Tavily):
   - `docs/poc/search-source-quality-bakeoff/artifacts/search_source_quality_bakeoff_report.json`
   - `docs/poc/search-source-quality-bakeoff/artifacts/search_source_quality_bakeoff_report.md`
3. Economic gate taxonomy and contracts:
   - `docs/specs/2026-04-14-economic-evidence-pipeline-lockdown.md`
   - `backend/schemas/economic_evidence.py`
   - `backend/services/economic_assumptions.py`
4. Strict fixture matrix verifier outputs (this run):
   - `docs/poc/economic-evidence-quality/artifacts/economic_evidence_gate_matrix_report.json`
   - `docs/poc/economic-evidence-quality/artifacts/economic_evidence_gate_matrix_report.md`
5. Live reader economic source probe:
   - `docs/poc/economic-evidence-quality/artifacts/live_reader_economic_source_probe_report.json`
   - `docs/poc/economic-evidence-quality/artifacts/live_reader_economic_source_probe_report.md`
   - `docs/poc/economic-evidence-quality/artifacts/live_reader_economic_source_probe_report_replay.json`
   - `docs/poc/economic-evidence-quality/artifacts/live_reader_economic_source_probe_report_replay.md`
6. Boundary decision artifacts:
   - `docs/architecture/2026-04-12-windmill-affordabot-boundary-adr.md`
   - `docs/specs/2026-04-13-windmill-domain-brownfield-spec-lock.md`
   - `docs/poc/windmill-storage-bakeoff/ARCHITECTURE_RECOMMENDATION.md`

## What Current POCs Prove

From San Jose live gate:

- Windmill flow + backend command chain executed successfully (`search_materialize -> freshness_gate -> read_fetch -> index -> analyze -> summarize_run`).
- Persistence chain exists in runtime: Postgres rows, pgvector chunks with embeddings, MinIO references, reader output reference, and analysis provenance.
- Idempotent rerun and stale drills passed (`stale_but_usable`, `stale_blocked`).
- Manual audit was marked `PASS_MANUAL_AUDIT`.

From search-source bakeoff:

- Provider spread exists and no provider reached MVP lock threshold in that run (`mvp_ready: false`).
- Official-domain hit rates and reader-ready rates diverge by provider; this confirms search quality needs separate scoring from downstream analysis quality.

From strict economic gate matrix (fixture):

- Deterministic gate taxonomy is now executable and fail-attributable.
- 6 fixture cases split into:
  - `quantified_pass`: 3
  - `fail_closed_qualitative_only`: 2
  - `qualitative_only_due_to_unsupported_claims`: 1
- Blockers are explicit at the correct gate (`search_recall`, `parameterization`, `llm_explanation`).

From live reader economic source probe:

- 3 real San Jose source URLs were tested through the Z.ai reader path.
- 0 of 3 were decision-grade candidates for numeric economic analysis.
- The Legistar Cost of Residential Development page produced substantive topic text, but no non-boilerplate numeric economics parameter; it correctly blocks at `parameterization_sufficiency`.
- The San Jose records PDF and housing memos portal block at `reader_source_quality` because the reader sees navigation/portal content or a not-found response.
- A repaired regression guard now ignores boilerplate `$500` Levine Act/campaign-contribution text so generic meeting logistics cannot become a false economic parameter.

## What Current POCs Do Not Prove Yet

- San Jose live gate proves retrieval, reader extraction, storage chain, and qualitative LLM output, but it does not yet prove live quantified economic analysis quality by itself.
- Fixture gate matrix proves taxonomy and fail-closed behavior, but not live artifact extraction quality because inputs are fixture-declared.
- Live reader source probing proves the current San Jose source set is not yet enough for numeric analysis. The blocker is now attributable: either `reader_source_quality` or `parameterization_sufficiency`, not Windmill orchestration.
- There is no live end-to-end run yet where evidence cards, parameter cards, assumptions, quantification, and LLM explanation are all produced from real San Jose/Saratoga source artifacts in one audited path.

## Dependency-Chain Matrix (Final Product Quality)

| Stage | Primary failure class | Observable signal | Downstream required behavior | Evidence needed to prove readiness |
|---|---|---|---|---|
| `search_recall` | provider/query quality | no artifact candidates or portal-heavy set | fail closed or fallback branch; do not fabricate downstream certainty | provider bakeoff + live run showing artifact-class candidates |
| `reader_substance` | source/data + reader extraction | short/boilerplate/empty reader output | block parameterization; preserve raw artifact for audit | live reader artifact with content-length and substantive checks |
| `artifact_classification` | source/data classification | portal/list pages selected over artifact pages | penalize/skip portal pages before quant pipeline | ranked candidate trace with chosen/non-chosen reasons |
| `evidence_cards` | structuring/provenance | missing hash/source excerpt/claim mapping | fail closed on quant path; keep qualitative-only route explicit | serialized `EvidenceCard` objects from live artifacts |
| `parameterization` | economic extraction | required numeric fields unresolved | block quantification; emit missing parameter inventory | `ParameterCard` set with resolved/missing reasons |
| `assumption_selection` | model governance | assumptions applied without applicability match | fail closed; require tagged, versioned registry assumption | `AssumptionCard` linked to registry version and tags |
| `quantification` | arithmetic/model | formula failure or invalid bounds | no quant claim output; emit deterministic failure code | `ModelCard` with formula id, bounds, unit checks |
| `llm_explanation` | narrative grounding | unsupported claims in explanation text | downgrade to qualitative-only and flag unsupported claims | unsupported-claim audit tied to evidence ids |

## Architecture Recommendation (Falsifiable)

Recommendation: lock **Path B hybrid boundary** for implementation.

- Windmill owns orchestration runtime (schedule, fanout, retries, branching, run controls).
- Affordabot backend/domain owns all product invariants and canonical writes across Postgres/pgvector/MinIO.
- Frontend consumes backend read models only.

Why this is the best-supported option now:

- Live San Jose run already demonstrates operational viability of Windmill orchestration with backend domain command sequencing.
- Existing ADR/specs and storage bakeoff showed direct-storage Path A tends to recreate backend logic inside orchestration scripts.
- Economic gate contracts now provide explicit failure attribution needed for consultant review and production audits.
- Live reader source probing shows the next blocker is data/extraction quality, which should remain a backend domain concern. Moving more logic into Windmill would not make the San Jose source text more quantitative; it would just move the false-positive and fail-closed rules out of the product boundary.

This recommendation is falsifiable. It should be reversed only if one of these is demonstrated:

1. Backend-domain command boundary cannot sustain reruns/failure drills at acceptable complexity while a Windmill-direct approach can do so with equal invariant protection.
2. Live end-to-end quantified runs repeatedly fail due to backend boundary transport overhead rather than gate/data quality causes.
3. Consultant review finds that gate attribution is not sufficiently independent to separate provider failures from economics-model failures.

## Railway Dev Rollout Gaps (Still Required)

Before calling the architecture economically ready in Railway dev, collect missing evidence:

1. Live quantified run using real sources:
   - one San Jose case and one non-San-Jose case
   - full chain to quantified output with citation-backed evidence cards
2. Live gate artifact serialization:
   - persist and expose live `EvidenceCard`, `ParameterCard`, `AssumptionCard`, `ModelCard`, `GateReport`
3. Cross-provider attribution run:
   - same query corpus through SearXNG/Tavily/Exa
   - prove quality differences are isolated at search/data gates, not misattributed downstream
4. Crash/replay evidence:
   - mid-step failure and replay without duplicate canonical artifacts or inconsistent quant outputs
5. Reviewer audit packet:
   - machine-readable run manifest plus human-readable audit summary per run

## Decision

Current evidence is sufficient to lock the boundary direction (Windmill orchestration + affordabot domain ownership), but it is not sufficient to claim full decision-grade live economic analysis readiness.

Proceed with this boundary and run one additional live quantified evidence round before Railway dev rollout signoff.
