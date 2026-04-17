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

Status: `in_progress`

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

- Continue while the worker patches make material code/product changes.
- Stop for HITL if one or two cycles in a row produce only documentation,
  reshuffling, or diagnosis without better data-moat capability.
