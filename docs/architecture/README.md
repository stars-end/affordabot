# Affordabot Architecture Index

This directory is the first stop for agents changing Affordabot pipeline,
storage, economic-analysis, Windmill, admin, or frontend read-model code.

## Required Reading For Pipeline Work

Read these in order before proposing or implementing pipeline changes:

1. `docs/architecture/2026-04-15-affordabot-pipeline-brownfield-map.md`
2. `docs/architecture/2026-04-15-economic-literature-inventory.md`
3. `docs/specs/2026-04-14-evidence-package-dependency-lockdown.md`
4. `docs/specs/2026-04-16-data-moat-quality-gates.md`
5. `docs/reviews/2026-04-15-full-pipeline-code-audit-results.md`

Then inspect the live code paths listed in each document's freshness contract.
The docs are routing maps, not a substitute for source inspection.

## Future Agent Start Here

**Data moat is the product objective; architecture is the means.**

Cycle 25 was a mechanics/narrow scraped pass, not a full data-moat pass. Honest
verdict: `PASS_SCRAPED_ARTIFACT_AND_PACKAGE_MECHANICS_ONLY__STRUCTURED_MOAT_NOT_PROVEN__ECONOMIC_DECISION_GRADE_NOT_PROVEN`.

For the next implementation wave, the dependency-lockdown spec and the [data moat quality gates](../specs/2026-04-16-data-moat-quality-gates.md) are authoritative. Treat those as the current working locks until `bd-3wefe.8` either confirms or revises them. Do not claim pass/done on any architecture validation without completing the new D0-D11 data moat gates.

The next POC must prove comprehensive, accurate, robust, fit-for-purpose evidence or honestly classify the result as `package_mechanics_only`, `evidence_ready_with_gaps`, `fail`, or `blocked_hitl`. Tavily/Exa secondary search does not count as true structured-source proof.

Decision-grade data moat means the package is not merely persisted. It must include policy lineage, primary artifact substance, true structured-source depth or source-catalog-proven absence, quote/row-grounded extraction accuracy, cross-source reconciliation, stable package identity, storage/replay proof, fallback/source-drift robustness, manual audit, Windmill linkage, and economic handoff fitness.

## Current Non-Obvious Truths

- Scheduled Windmill cron jobs currently create substrate and chunks; they do
  not automatically run the full economic `AnalysisPipeline`.
- The full economic analysis path exists today in
  `backend/services/llm/orchestrator.py` and
  `backend/services/legislation_research.py`.
- `PipelineDomainBridge` is the intended Windmill/backend boundary candidate,
  but its current `analyze` command is a narrower chunk-summary JSON step, not
  the canonical cost-of-living analysis engine.
- `backend/schemas/economic_evidence.py` and
  `backend/services/economic_assumptions.py` are package-contract candidates.
  They must wrap, project, or deliberately migrate the existing
  `schemas.analysis` / `evidence_gates` / `WAVE2_*` runtime path.
- Frontend pages and admin panels are display/read-model surfaces. They must not
  become sources of economic truth, and mock fallbacks can hide backend failures.

## Findability Keywords

If an agent is searching semantically or with `rg`, use these terms:

- `Affordabot brownfield pipeline map`
- `raw_scrapes document_chunks AnalysisPipeline frontend output`
- `scheduled substrate ingestion not economic analysis`
- `PipelineDomainBridge not canonical AnalysisPipeline`
- `economic literature inventory WAVE2 AssumptionCard`
- `PolicyEvidencePackage dependency lockdown`
- `PASS_SCRAPED_ARTIFACT_AND_PACKAGE_MECHANICS_ONLY`
- `data moat quality gates D0 D1 D2 D3 D4 D5 D6 D7 D8 D9 D10 D11`
- `decision_grade_data_moat package_mechanics_only evidence_ready_with_gaps`
- `policy lineage completeness extraction accuracy citation gate cross-source reconciliation`

## Staleness Rule

If any stale-if path in the brownfield map or literature inventory changed,
refresh the relevant architecture document before making architecture claims.
If you skip the refresh, state why the changed path is irrelevant.
