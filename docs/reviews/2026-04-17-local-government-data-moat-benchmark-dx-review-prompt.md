# dx-review Prompt: Local Government Data Moat Benchmark v0

Review target:

- PR: https://github.com/stars-end/affordabot/pull/439
- Feature-Key: `bd-3wefe.13`
- Planning docs:
  - `docs/specs/2026-04-17-local-government-data-moat-benchmark-v0.md`
  - `docs/specs/2026-04-16-data-moat-quality-gates.md`
  - `docs/specs/2026-04-14-evidence-package-dependency-lockdown.md`
  - `docs/architecture/README.md`
  - `docs/poc/policy-evidence-quality-spine/README.md`

## Context

Affordabot's product moat is a durable local-government data corpus, not one
San Jose fee vertical. The corpus must combine scraped official artifacts and
true structured API/raw sources, preserve provenance/storage/readback, and
classify each package for economic-analysis handoff. Economic analysis remains
required for selected packages, but not every data-moat package must be
quantitative.

The previous cycles showed:

- San Jose/CLF can produce useful deep-package evidence but risks overfitting.
- Broad policy evidence can have standalone data value as `stored_not_economic`.
- External advocacy PDFs can still outrank official sources; gates now block
  that false pass, but source selection remains a product-quality failure.
- The old San-Jose-first plan is too narrow for architecture lock.

## Review Questions

1. Does the new `local_government_data_moat_benchmark_v0` plan correctly shift
   the target from a San Jose vertical to a reusable corpus-level data moat?
2. Are the C0-C6 corpus gates sufficiently ambitious and precise for the stated
   product goal?
3. Are the corpus scope targets reasonable: 30 to 50 packages, 3+ jurisdictions,
   5+ policy families, 3+ source families, 80% official-source dominance, 5
   economic-handoff candidates, and 2 economic deep dives?
4. Does the plan preserve the existing architecture boundary: Windmill
   orchestration only, backend product logic, Postgres truth, MinIO artifacts,
   pgvector derived indexes, frontend display only?
5. Does the plan correctly separate standalone data-moat value from economic
   analysis readiness?
6. Does the plan still keep economic-analysis suitability visible enough to
   prevent building a corpus that cannot feed the economic engine?
7. Are there missing gates around structured-source breadth, official-source
   selection, package identity, storage/readback, idempotency, manual audit, or
   golden regression fixtures?
8. Is the plan implementation-ready for up to 3 implementation agents without
   causing duplicate work or unclear ownership?
9. What should block the next implementation wave before another live cycle is
   run?

## Expected Review Output

Use findings-first review style:

- P0/P1/P2/P3 findings with exact file/path references.
- Agreement/disagreement with the strategic shift.
- Specific patch recommendations for the docs/Beads plan.
- Verdict: `approve`, `approve_with_changes`, or `request_changes`.
- Score 0-100 for usefulness/readiness of the plan.

Do not review product code implementation unless it directly affects whether
the plan is executable or duplicates existing brownfield paths.
