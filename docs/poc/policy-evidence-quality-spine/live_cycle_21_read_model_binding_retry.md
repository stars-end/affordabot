# Cycle 21: Read Model Binding Retry

Feature-Key: bd-3wefe.13

## Purpose

Cycle 21 deployed the Cycle 20 admin read-model patch and refetched the same stored package:

- package_id: `pkg-189ea06455b12e96370c5ebd`
- backend_run_id: `a599344a-ca06-4d4b-85cf-4e1f47cf15d8`

The goal was to prove the canonical analysis binding without rerunning the whole Windmill flow.

## Observed Result

Artifact:

- `docs/poc/policy-evidence-quality-spine/artifacts/live_cycle_21_admin_analysis_status_after_binding_fix.json`

The read model still returned:

- `canonical_analysis_binding.status=not_proven`
- blocker: `canonical_llm_run_id_unverified_from_package_payload`

Manual inspection showed the package and run still contained matching canonical ids:

- package projection run id: `a599344a-ca06-4d4b-85cf-4e1f47cf15d8`
- package projection step id: `4570a0b3-47bf-5a57-b834-71f9aaf4b53f`
- observed run id: `a599344a-ca06-4d4b-85cf-4e1f47cf15d8`
- observed step id: `4570a0b3-47bf-5a57-b834-71f9aaf4b53f`

## Root Cause

The fallback read-model check only accepted `run_context.backend_run_id`.

The live package stores the backend run under `run_context.run_id`.

This is a brownfield contract mismatch between the package runtime context and the admin fallback proof logic.

## Tweak

`backend/routers/admin.py` now accepts the following route/run identifiers when validating the canonical analysis projection:

1. `run_context.backend_run_id`
2. `run_context.run_id`
3. `pipeline_runs.result.run_id`
4. `pipeline_runs.result.id`

The router test now covers the live-style `run_context.run_id` shape.

## Validation

Focused local validation:

- `poetry run pytest tests/routers/test_admin_pipeline_read_model.py -q` -> 10 passed
- `poetry run ruff check routers/admin.py tests/routers/test_admin_pipeline_read_model.py` -> passed

## Next Cycle

Redeploy this patch and refetch the same stored package again. Expected result:

- `canonical_analysis_binding.status=bound`
- `gates["LLM narrative"].status=pass`
- `economic_output.status=not_proven`

This is still a binding/read-model proof, not a decision-grade economic output proof.
