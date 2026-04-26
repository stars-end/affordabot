# Cycle 30 Final Gate Decision

Feature-Key: bd-3wefe.13
PR: #439
Final live artifact: `artifacts/live_cycle_30i_windmill_domain_run.json`

## Stop Condition

Stopped at: `evidence_ready_with_gaps`.

This is not `decision_grade_data_moat`. It is also not architecture failure.

The architecture can satisfy the mechanical product spine:

- Windmill orchestration.
- Railway dev backend.
- private SearXNG product search.
- official scraped artifact materialization.
- true structured source metadata.
- Postgres package persistence.
- MinIO artifact references.
- pgvector derived index.
- admin/read-model evidence.
- fail-closed economic handoff.

The current implementation cannot yet satisfy the data-moat gate because true structured economic content is missing.

## Why This Is The Correct Stop

The remaining gap is no longer a small ranking, provider-label, or parser tweak. Cycle 30 already exhausted the low-risk improvements available inside this PR:

- provider provenance was made runtime-derived;
- official-source ranking was fixed;
- Tavily was demoted to tier C secondary evidence;
- Legistar Matter `7526` was resolved instead of fallback noise;
- diagnostic structured counts no longer become parameter cards;
- official artifact fee rows are extracted from reader content;
- malformed monetary values stay ambiguous;
- harness classification no longer reports `full_product_pass` when the package gate fails.

The next improvement requires adding a deeper ingestion capability, not just another eval tweak:

- traverse and ingest related Legistar attachments for Matter `7526`;
- normalize official fee tables into structured rows;
- ingest nexus-study/staff-report methodology;
- bind model and assumption cards for economic analysis.

## Final Gate Table

| Gate | Result | Evidence |
| --- | --- | --- |
| Windmill run | pass | Job `019d97ee-4a45-5db5-92ac-38c281071b8e`; expected six-step sequence |
| private SearXNG | pass | Runtime `OssSearxngWebSearchClient`, endpoint `searxng-private.railway.internal:8080` |
| official artifact discovery | pass | Rank-1 Legistar PDF artifact `View.ashx?M=F&ID=8758120` |
| reader substance | pass | Reader output persisted and policy text analyzed |
| true structured source | partial | Legistar Web API Matter `7526`, 19 attachments, no structured economic values |
| unified package | pass | Scraped + structured lanes in package `pkg-d2ca84f146a17beb8b3266a1` |
| storage | pass | Postgres, MinIO refs, reader output ref, pgvector all passed |
| primary parameter extraction | partial | 11 primary artifact cards, one malformed residential-care value kept ambiguous |
| source reconciliation | partial | Primary artifact precedence works; structured economic corroboration missing |
| economic handoff | fail-closed | `economic_handoff_ready=false`, blocking gate `parameterization` |
| final cost-of-living analysis | not ready | No governed model cards, assumptions, sensitivity, or secondary research package |

## Exact Remaining Gaps

P1: True structured economic source gap.

Legistar Web API gives matter metadata and attachments, but not normalized economic rows. The data moat needs either attachment traversal or another free structured source that contributes economic facts.

P1: Related attachment gap.

The package records 19 attachments for Matter `7526`, but does not ingest them as related artifacts in the same package. Policy lineage marks `related_attachments=false`.

P1: Economic model-card gap.

The package has no model cards. Direct fee parameters cannot become household cost-of-living analysis without unit arithmetic, incidence/pass-through assumptions, and uncertainty.

P1: Secondary research loop gap.

Indirect economic impacts require a second-stage research/read package. Cycle 30 did not prove that path.

P2: Parameter normalization depth.

Fee rows need richer fields: subarea, land use, threshold, amount, unit, effective date, final/adopted status, and exact page/table citation.

## Architecture Recommendation

Lock narrow:

- Windmill remains orchestration.
- Backend owns search, read, package construction, quality gates, storage, and economic handoff.
- Postgres is source of truth.
- MinIO is artifact of record.
- pgvector is derived retrieval index.
- Frontend/admin consumes read models and must not invent quality semantics.

Do not lock broad data-moat quality yet.

Next PR should focus on a data-moat depth lane, not more generic orchestration:

1. Legistar Matter attachment traversal.
2. Official attachment/table normalization.
3. Structured economic row schema.
4. Source-bound model-card bridge.
5. New live San Jose gate requiring both scraped artifact and structured/attachment economic rows before economic handoff can pass.
