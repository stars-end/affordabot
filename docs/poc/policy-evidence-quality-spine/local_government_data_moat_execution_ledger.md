# Local Government Data Moat Execution Ledger

Feature-Key: `bd-3wefe.13`

This ledger records the post-review implementation cycles for
`local_government_data_moat_benchmark_v0`. The cycle budget is up to 80, but it
is a ceiling, not a target. A cycle must make substantive product/code progress
toward the city/county/state local-government data moat, prove a concrete
blocker, or stop for HITL guidance.

## Operating Rules

- Product A is the priority: robust scraped plus structured local-government
  data that is durable, official-source-dominant, queryable, and reusable.
- Product B remains a required handoff: economic analysis must consume the data
  moat honestly or fail closed with named missing evidence.
- Max concurrent implementation workers: 3 `gpt-5.3-codex` subagents.
- Do not run another live corpus eval before the blocking implementation work
  for C0-C14 is implemented or explicitly blocked.
- Every cycle must record changed files, gate movement, validation, and next
  blocker.

## Cycle 44: C0-C14 Infrastructure Implementation Wave

Status: `completed`

Started: 2026-04-17

Why this cycle exists:

Prior cycles proved important mechanics but remained too San-Jose/CLF-shaped.
The late Opus/GLM review made clear that the next material step is not another
live Windmill run. The next material step is implementation of the corpus
infrastructure that makes false passes impossible and breaks the narrow
vertical overfit.

Target gates:

- `C0` corpus scope and composition;
- `C1` official-source dominance;
- `C2` structured-source depth;
- `C3` first-class data-moat classification and D11 reconciliation;
- `C7-C14` durability, identity/dedupe, exportability, licensing, schema,
  known-policy coverage, Windmill batch orchestration, and non-fee extraction;
- Product-surface contract for standalone data product consumption.

Worker split:

| Worker | Beads | Ownership | Expected Material Product Change |
| --- | --- | --- | --- |
| A | `bd-3wefe.13.1` | Corpus matrix and scorecard spine | Machine-readable 75-120 row target matrix/scorecard contract with C0-C14 false-pass checks. |
| B | `bd-3wefe.13.2`, `bd-3wefe.13.3` | Source identity, officialness, freshness/drift | Backend-owned source classification and durability primitives consumed by scoring/read-model paths. |
| C | `bd-3wefe.13.6` | Non-San-Jose structured runtime and non-fee extraction | Runtime structured enrichment outside San Jose plus non-fee policy-family templates. |
| Orchestrator | `bd-3wefe.13` | Review, integration, validation, re-dispatch | Integrate patches, run validation, update Beads, and decide whether a live corpus pass is justified. |

Pre-cycle changes already landed:

- Spec/Beads contract upgraded to C0-C14.
- `corpus_taxonomy_v1.json` seeded.
- Beads max cycle ceiling updated to 80.
- PR #439 head before worker patches: `434dceb4f0b138340fbf05d8d996c1231e43db04`.

Stop/continue decision:

- Continue. Cycle 44 made material code/product progress and did not hit a
  strategic HITL blocker.
- Do not claim `decision_grade_corpus` yet. The current corpus scorecard is
  `corpus_ready_with_gaps`.

Material changes integrated:

- Added `LocalGovernmentCorpusBenchmarkService` and generated
  `local_government_corpus_matrix.json`, `local_government_corpus_scorecard.json`,
  and `local_government_corpus_report.md`.
- Added backend source identity/durability primitives and wired them into
  candidate ranking, package building, quality-spine scorecards, and artifact
  generation.
- Added official-source dominance/cap enforcement so Tavily/Exa cannot silently
  count as primary evidence.
- Corrected deterministic fixtures so official artifacts available through
  private SearXNG remain private-SearXNG primary selections rather than Tavily
  primary rescues.
- Added non-San-Jose structured runtime enrichment for California CKAN and
  non-fee extraction templates for zoning/land-use, parking/TDM, business
  compliance, and meeting-action lineage.
- Added product-surface artifacts:
  `known_policy_reference_list.json`, `source_licensing_tos_register.json`,
  `package_schema_version_contract.json`, and
  `data_product_surface_contract.json`.

Gate movement:

- `C1` now has executable official-source dominance and secondary-primary caps.
- `C2` now has non-Legistar/non-San-Jose structured runtime coverage and
  non-fee template depth.
- `C3` now has a first-class corpus classification enum plus C3-to-D11
  reconciliation checks.
- `C7-C12` now have product-surface artifacts and a verifier for freshness,
  identity, exportability, licensing, schema versioning, and known-policy
  coverage prerequisites.
- `C14` now has concrete non-fee extraction templates and tests.

Current corpus verdict:

- `local_government_corpus_scorecard.json`: `corpus_ready_with_gaps`.
- Passing gates: `C1`, `C2`, `C3`, `C4`, `C6`, `C7`, `C8`, `C9`, `C9a`, `C10`,
  `C11`, `C12`, `C14`.
- Remaining non-pass gates: `C0` corpus size/scope below 75 package target,
  `C5` manual audit not yet stratified enough, `C13` live Windmill orchestration
  share not yet decision-grade.

Validation:

- `cd backend && poetry run pytest` -> `820 passed`.
- `cd backend && poetry run ruff check ...` on touched Python files -> pass.
- `cd backend && poetry run python scripts/verification/verify_policy_evidence_quality_spine_data.py --attempt-id bd-3wefe.13-cycle44 --retry-round 44 --targeted-tweak private_searxng_primary_source_identity` -> pass.
- `cd backend && poetry run python scripts/verification/verify_policy_evidence_quality_spine_economics.py --max-cycles 80` -> `verdict=partial`, `failed=0`.
- `python backend/scripts/verification/verify_local_government_data_product_surface.py --json` -> pass.

Next blocker:

- Cycle 45 should expand the corpus toward the 75-120 package target and shift
  generation from deterministic seed/CLI artifacts to live Windmill-orchestrated
  rows, while preserving the C1/C2/C14 quality gates.
