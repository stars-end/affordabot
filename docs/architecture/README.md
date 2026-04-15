# Affordabot Architecture Index

This directory is the first stop for agents changing Affordabot pipeline,
storage, economic-analysis, Windmill, admin, or frontend read-model code.

## Required Reading For Pipeline Work

Read these in order before proposing or implementing pipeline changes:

1. `docs/architecture/2026-04-15-affordabot-pipeline-brownfield-map.md`
2. `docs/architecture/2026-04-15-economic-literature-inventory.md`
3. `docs/specs/2026-04-14-evidence-package-dependency-lockdown.md`
4. `docs/reviews/2026-04-15-full-pipeline-code-audit-results.md`

Then inspect the live code paths listed in each document's freshness contract.
The docs are routing maps, not a substitute for source inspection.

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

## Staleness Rule

If any stale-if path in the brownfield map or literature inventory changed,
refresh the relevant architecture document before making architecture claims.
If you skip the refresh, state why the changed path is irrelevant.
