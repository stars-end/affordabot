# Data Moat Takeover Handoff - 2026-04-22

Feature-Key: `bd-3wefe.13`

PR: `https://github.com/stars-end/affordabot/pull/439`

PR head at handoff: `b34fd09960869bd56c9fc49ae745d32be735d25d`

Branch: `feature-bd-3wefe.13-agent-b`

Base branch: `feature-bd-3wefe.20-data-moat-gates`

## Objective

The product objective is a broad local-government data moat, not another narrow
San Jose CLF proof.

The data moat must combine scraped and structured city/county/state/local
government data into durable, source-grounded, queryable packages. The economic
analysis engine is a downstream consumer and a required handoff gate, but the
data package itself is also product value. A package may be valuable as
`stored_not_economic` or `qualitative_only` when it is accurate, official,
fresh enough, deduped, exportable, and manually auditable.

## Required Reading

Read these repo-relative files before starting new work:

- `docs/specs/2026-04-17-local-government-data-moat-benchmark-v0.md`
- `docs/specs/2026-04-16-data-moat-quality-gates.md`
- `docs/poc/policy-evidence-quality-spine/local_government_corpus_report.md`
- `docs/poc/policy-evidence-quality-spine/local_government_data_moat_execution_ledger.md`
- `docs/poc/policy-evidence-quality-spine/manual_audit_local_government_corpus.md`
- `docs/poc/policy-evidence-quality-spine/golden_policy_regression_set.md`
- `docs/poc/policy-evidence-quality-spine/product_target_cost_of_living_analysis_archetype.md`

Machine-readable corpus artifacts:

- `docs/poc/policy-evidence-quality-spine/artifacts/local_government_corpus_matrix.json`
- `docs/poc/policy-evidence-quality-spine/artifacts/local_government_corpus_scorecard.json`
- `docs/poc/policy-evidence-quality-spine/artifacts/local_government_corpus_windmill_orchestration.json`
- `docs/poc/policy-evidence-quality-spine/artifacts/manual_audit_local_government_corpus.json`
- `docs/poc/policy-evidence-quality-spine/artifacts/corpus_taxonomy_v1.json`
- `docs/poc/policy-evidence-quality-spine/artifacts/source_identity_rules.json`
- `docs/poc/policy-evidence-quality-spine/artifacts/source_freshness_drift_scorecard.json`
- `docs/poc/policy-evidence-quality-spine/artifacts/non_fee_extraction_templates.json`
- `docs/poc/policy-evidence-quality-spine/artifacts/data_product_surface_contract.json`

## Current State

Current terminal state: `corpus_ready_with_gaps`.

This is not `decision_grade_corpus`.

The PR currently proves a much stronger corpus architecture than the earlier
San Jose-only run, but the data moat is not complete because structured-source
runtime proof and live Windmill proof are still partial.

Current scorecard highlights:

- `package_rows=90`
- `row_count_total=92`
- `C0=pass`
- `C1=pass`
- `C2=not_proven`
- `C3=pass`
- `C4=pass`
- `C5=pass`
- `C6=pass`
- `C7=pass`
- `C8=pass`
- `C9=pass`
- `C9a=pass`
- `C10=pass`
- `C11=pass`
- `C12=pass`
- `C13=not_proven`
- `C14=not_proven`

The next blocker reported by the scorecard is `C2`.

## What Was Achieved

### Cycle 51: Seeded Windmill Intent Reclassification

Issue: `bd-3wefe.13.4.9`

Commit: `39975b2417b62995f858d1ae29cefd0d985decc8`

Result: completed.

The corpus previously risked treating generated Windmill references as live
Windmill proof. Cycle 51 reclassified generated refs as
`orchestration_intent`, and live rows only become `windmill_live` through the
orchestration overlay artifact.

Post-cycle C13 metrics:

- `windmill_live=8`
- `orchestration_intent=82`
- `cli_only=0`
- `mixed=0`
- `live_proven_rows=8`
- `seeded_not_live_proven_rows=82`
- `live_proof_coverage_ratio=0.0889`

Product effect: this removed a false live-proof interpretation from the corpus
and made C13 an honest burn-down problem.

### Cycle 52: Structured-Source Proof Reclassification

Issue: `bd-3wefe.13.4.10`

Commit: `b34fd09960869bd56c9fc49ae745d32be735d25d`

Result: completed.

The corpus previously risked treating generated structured-source observations
as live structured data. Cycle 52 split generated acquisition targets from
runtime-proven structured evidence.

Generated structured rows now carry:

- `live_proven=false`
- `proof_status=cataloged_intent`
- `proof_source=generated_expansion_matrix`
- `source_infrastructure_status=cataloged_intent`

Generated non-fee extraction depth now carries:

- `live_exercised=false`
- `proof_status=cataloged_intent`
- `proof_source=generated_expansion_matrix`

Post-cycle C2/C14 metrics:

- `C2.status=not_proven`
- `C2.live_structured_coverage_ratio=0.1778`
- `C2.live_true_structured_family_count=5`
- `C2.cataloged_true_structured_family_count=5`
- `C14.status=not_proven`
- `C14.live_non_fee_family_count=11`
- `C14.cataloged_non_fee_family_count=6`

Product effect: this made the structured-source gate honest. The corpus keeps
valuable acquisition targets, but those targets no longer count as proprietary
runtime-proven structured data until a probe/ingestion artifact proves them.

## What Is Not Proven

Do not overclaim these:

- The corpus is not decision-grade.
- C2 structured-source breadth/depth is not proven.
- C13 Windmill batch orchestration is not proven across the corpus.
- C14 non-fee extraction depth is not fully proven.
- Generated `cataloged_intent` rows are not live structured evidence.
- Generated `orchestration_intent` rows are not live Windmill proof.
- Economic handoff remains a required consumer gate, but it should not erase
  the standalone value of accurate stored local-government data.

## Active Next Issue

Issue: `bd-3wefe.13.4.11`

Title: `Impl: Cycle 53 structured-source runtime proof overlay`

Status at handoff: `in_progress`, not implemented in this PR head.

Recommended next implementation:

1. Add a structured-source runtime proof artifact/schema.
2. Consume that artifact in the corpus scorecard.
3. Upgrade `cataloged_intent` rows to `live_proven` only when a proof row
   matches row identity, jurisdiction, source family, and extraction depth.
4. Prove at least one currently cataloged target with a real public structured
   source probe, or produce a precise blocker with source/error details.
5. Regenerate matrix, scorecard, report, manual audit, and ledger.
6. Add tests for both positive upgrade and false-proof rejection.

The likely first target is a non-San-Jose, non-Legistar structured source such
as ArcGIS, Socrata, CKAN, OpenStates, OpenDataSoft, or raw CSV from an official
local government source. Prefer public/free sources before adding credentials.

## Manual Audit Status

The corpus manual audit currently passes C5, but manual audit is not a substitute
for C2/C13/C14 proof.

Manual audit metrics:

- `required_sample_count=30`
- `sampled_count=31`
- `sampled_jurisdiction_count=7`
- `sampled_policy_family_count=8`
- `sampled_source_family_count=2`

Use the manual audit files to verify artifacts yourself. Do not rely only on
scorecard booleans.

## Validation Last Recorded

Cycle 51 validation:

- `poetry run pytest tests/services/pipeline/test_local_government_corpus_benchmark.py tests/verification/test_verify_local_government_corpus_windmill_orchestration.py tests/verification/test_regenerate_local_government_corpus_scorecard.py` -> `34 passed`
- targeted Ruff -> pass
- `poetry run python scripts/verification/verify_local_government_corpus_manual_audit.py` -> pass
- full backend `poetry run pytest` -> `861 passed, 70 warnings`

Cycle 52 validation:

- `poetry run pytest tests/services/pipeline/test_local_government_corpus_benchmark.py tests/verification/test_regenerate_local_government_corpus_scorecard.py tests/verification/test_verify_local_government_corpus_manual_audit.py` -> `28 passed`
- targeted Ruff -> pass
- `poetry run python scripts/verification/verify_local_government_corpus_manual_audit.py` -> pass
- full backend `poetry run pytest` -> `863 passed, 70 warnings`

Before continuing from this handoff, rerun focused checks around any touched
files and at least:

```bash
cd backend
poetry run pytest tests/services/pipeline/test_local_government_corpus_benchmark.py tests/verification/test_regenerate_local_government_corpus_scorecard.py tests/verification/test_verify_local_government_corpus_manual_audit.py -q
poetry run python scripts/verification/verify_local_government_corpus_manual_audit.py
```

Run full backend pytest before claiming merge readiness for substantive code
changes.

## Stop Rules For The Next Agent

Continue only while each cycle makes material data-moat progress.

Stop and ask for HITL if one or two cycles in a row only reshuffle docs,
diagnostics, or generated metadata without improving real source breadth,
source depth, officialness, structured proof, package quality, or economic
handoff readiness.

Valid terminal states:

- `decision_grade_corpus`
- `corpus_ready_with_gaps` with exact remaining gaps and no non-destructive
  improvement left in the current cycle
- `package_mechanics_only`
- `fail` with architectural proof
- `blocked_hitl`

Invalid terminal states:

- "San Jose works."
- "SearXNG found one PDF."
- "Windmill/storage/admin worked."
- "Economic analysis failed closed."
- "Tavily rescued the parameters."
- "Generated structured targets exist."

## Infra And HITL

The founder approved non-destructive use of Railway dev, Windmill dev,
Postgres/pgvector, MinIO, private SearXNG, and public/free structured data
sources for this work.

Do not perform destructive deletes, production-impacting changes, paid provider
primary selection, architecture lock, or hidden assumption changes without HITL.

Routine secret access must use agent-safe cached/service-account helpers. Do not
use raw `op read`, `op item get`, `op item list`, or `op whoami`.

## Recommended Next Wave

Use up to three agents only if the work splits by outcome:

1. Structured proof overlay implementation: schema, scorecard ingestion, tests.
2. Public structured source probe: one or more real non-San-Jose official
   sources that can populate the proof artifact.
3. Manual audit/reporting: regenerate artifacts, verify C2/C14 metrics, update
   ledger, and write precise blockers.

The orchestrator should review diffs, run validation, manually inspect the
generated artifacts, then either merge or redispatch the next failed gate.
