# dx-review Prompt: Ultra-Reach Data Moat Alignment Review

Review target:

- PR: https://github.com/stars-end/affordabot/pull/439
- Feature-Key: `bd-3wefe.13`
- Current PR head before this prompt: `b333fd4cf0f7ec7cced2053f87cfc88d1d20aa20`

Primary plan docs:

- `docs/specs/2026-04-17-local-government-data-moat-benchmark-v0.md`
- `docs/specs/2026-04-16-data-moat-quality-gates.md`
- `docs/specs/2026-04-14-evidence-package-dependency-lockdown.md`
- `docs/architecture/README.md`
- `docs/poc/policy-evidence-quality-spine/README.md`

## Review Frame

This is not a generic architecture review.

Evaluate whether the current plan is a true **ULTRA reach goal** aligned with
Affordabot's two products:

1. **Primary focus for this session, 90 percent weight:** robust
   city/county/local/state data moat that combines scraped official artifacts
   and true structured API/raw data into durable, auditable, reusable evidence
   packages.
2. **Secondary but required, 10 percent weight:** economic analysis pipeline
   grounded by the proprietary data moat, with explicit handoff classification,
   secondary research when needed, and no hidden LLM assumptions.

The data moat itself may become a standalone product. The plan should therefore
not overfit to packages that immediately produce quantified cost-of-living
analysis. Meeting minutes, agendas, ordinances, permits, compliance rules,
inspection records, source metadata, and policy lineage can all be valuable data
moat assets if they are official, structured/scraped unified, stored, and
auditable.

At the same time, the data moat must remain suitable for downstream economic
analysis. Every package should tell the economic engine whether it is
`economic_analysis_ready`, `economic_handoff_candidate`,
`secondary_research_needed`, `qualitative_only`, `stored_not_economic`,
`not_policy_evidence`, or `fail`.

## Key Context

Prior cycles proved useful mechanics but also exposed product-quality gaps:

- San Jose/CLF work is a calibration fixture, not the full product.
- Cycle 41 showed broad local policy evidence can be valuable as
  `stored_not_economic`.
- Cycle 42/43 showed external advocacy PDFs can still outrank official sources;
  the gate now blocks false pass, but official-source dominance remains a core
  product risk.
- The plan now proposes `local_government_data_moat_benchmark_v0` across 30 to
  50 packages, 3+ jurisdictions, 5+ policy families, 3+ source families, 80%+
  official-source dominance, 5+ economic-handoff candidates, and 2 economic deep
  dives.

## Review Questions

1. Is the plan genuinely ambitious enough to be an **ULTRA reach goal**, or is
   it still too narrow, too San-Jose-shaped, too Legistar-shaped, or too
   fee/economic-analysis-shaped?
2. Does the plan correctly make robust local-government data the primary product
   goal, instead of treating architecture mechanics or economic analysis as the
   only pass condition?
3. Are the corpus gates C0-C6 strong enough to prove a data moat that could be
   valuable as a standalone data product?
4. Are there missing data-moat dimensions, such as source freshness, update
   cadence, historical backfill, policy lineage depth, structured field
   normalization, dedupe across jurisdictions, source licensing/terms,
   schema evolution, replay/idempotency, or data exportability?
5. Are the numeric targets appropriate for an ultra-reach goal? If not, propose
   concrete target changes.
6. Does the plan sufficiently combine structured and scraped sources, or does it
   still allow a mostly scraped/PDF corpus to pass?
7. Is official-source dominance defined strongly enough to prevent external
   advocacy/news/vendor sources from contaminating primary evidence?
8. Does the plan keep the economic engine grounded by proprietary data without
   letting economic readiness dominate the data-moat definition?
9. Is the economic handoff classification detailed enough for direct and
   indirect cost-of-living analysis later?
10. What must be patched before another implementation/eval cycle starts?

## Required Output

Use findings-first review style.

For each finding:

- Severity: P0/P1/P2/P3.
- Exact file/path reference.
- Why it matters for product A, product B, or both.
- Specific patch recommendation.

Then provide:

- Strategic verdict: `ultra_reach_ready`, `ambitious_but_incomplete`, or
  `not_ultra_reach`.
- Score 0-100 for alignment with product A, robust local data moat.
- Score 0-100 for alignment with product B, economic analysis grounded by the
  data moat.
- Top 3 changes that would most improve the plan before implementation.

Do not spend review budget on implementation code unless it proves the plan is
not executable or duplicates existing brownfield paths.
