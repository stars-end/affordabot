# Cycle 24: Stale LLM Binding Override

Feature-Key: bd-3wefe.13

## Goal

Make the admin read model correctly bind a stored package to its canonical analysis run even when the historical `pipeline_runs.result.llm_narrative_proof` block was produced by an older read-model contract.

## Live Finding

After deploying Cycle 22, refetching the stored Cycle 20 package returned HTTP 200, but still showed:

- `canonical_analysis_binding.status=not_proven`
- `gates["LLM narrative"].status=not_proven`
- package projection run id matched the requested backend run id
- package projection step id was present
- `pipeline_runs.result.analysis` was present

Artifact:

- `docs/poc/policy-evidence-quality-spine/artifacts/live_cycle_22_admin_analysis_status_after_quality_metrics.json`

## Root Cause

The admin router only synthesized fallback LLM proof when `llm_narrative_proof` was absent.

The live run had an older explicit `llm_narrative_proof` block with `proof_status=not_proven`, so the router never applied the stronger package projection evidence.

## Tweak

`backend/routers/admin.py` now recomputes the package projection match before evaluating the old proof block. If the package projection matches the current backend run and the run has an analysis payload, the read model overrides stale `not_proven` proof with:

- `proof_status=pass`
- canonical run id
- canonical step id
- `analysis_step_executed=true`
- blocker cleared

## Validation

Focused local validation:

- `poetry run pytest tests/routers/test_admin_pipeline_read_model.py tests/services/pipeline/test_policy_evidence_quality_spine_economics.py -q` -> 39 passed
- `poetry run ruff check routers/admin.py tests/routers/test_admin_pipeline_read_model.py services/pipeline/policy_evidence_quality_spine_economics.py` -> passed

## Next Cycle

Deploy this patch and refetch the same stored package again. Expected result:

- canonical binding: pass/bound
- LLM narrative gate: pass
- source-quality metrics: still `not_proven` for the old Cycle 20 package, because metrics were added after that package was created
- economic output: still `not_proven`

Then run a new live package so Cycle 22 source-quality metrics are actually persisted into a fresh package.
