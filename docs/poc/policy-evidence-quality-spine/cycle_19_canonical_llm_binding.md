# Cycle 19: Canonical LLM Binding

Feature-Key: bd-3wefe.13

## Purpose

Cycle 18 had a successful backend domain `analyze` step with an `analysis_id`, but the package gate projection did not carry that id. The admin read model therefore reported `canonical_analysis_binding.status=not_proven` even though a canonical domain analysis had run.

Cycle 19 fixes that projection gap.

## Tweak

`RailwayRuntimeBridge._materialize_policy_evidence_package` now passes canonical analysis hints into the package builder only when:

- the `analyze` command exists,
- `analyze.status == "succeeded"`,
- `analyze.refs.analysis_id` is present.

Promoted fields:

- `canonical_pipeline_run_id`
- `canonical_pipeline_step_id`
- `canonical_breakdown_ref`
- `canonical_analysis_id` in run context

Provider-unavailable or fail-closed analysis responses do not get these fields promoted.

## Validation

Focused validation:

- `poetry run pytest tests/services/pipeline/test_bridge_runtime.py tests/services/pipeline/test_structured_source_enrichment.py tests/services/pipeline/test_policy_evidence_quality_spine_economics.py -q` -> 56 passed
- `poetry run ruff check services/pipeline/domain/bridge.py services/pipeline/structured_source_enrichment.py services/pipeline/policy_evidence_quality_spine_economics.py tests/services/pipeline/test_bridge_runtime.py tests/services/pipeline/test_structured_source_enrichment.py tests/services/pipeline/test_policy_evidence_quality_spine_economics.py` -> passed

## Expected Gate Delta

- E4 canonical LLM binding should move from `not_proven` to pass for successful domain analysis runs.
- Gate B should still remain not decision-grade for Cycle 18/19 because model, assumption, uncertainty, and household pass-through requirements are not satisfied.

## Live Follow-Up

Cycle 20 should deploy this change and rerun the San Jose CLF vertical. Manual audit should verify:

1. `canonical_analysis_binding.status` changes to pass.
2. `economic_output.status` remains `not_proven`.
3. `parameter_readiness` remains pass.
4. No unsupported household cost-of-living conclusion is emitted.
