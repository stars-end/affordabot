# Cycle 23: Direct Fee Model-Card Readiness

Feature-Key: bd-3wefe.13

## Goal

Improve Gate B by adding deterministic, source-bound model-card output for direct developer-fee calculations while preserving fail-closed household cost-of-living behavior when pass-through/incidence assumptions are missing.

## Scope

Code ownership stayed in the economics/readiness surface:

- `backend/services/pipeline/policy_evidence_quality_spine_economics.py`
- `backend/tests/services/pipeline/test_policy_evidence_quality_spine_economics.py`

No selected-artifact ranking/provider scoring logic was changed in this cycle.

## Tweak Implemented

For direct mechanism packages, when source-bound parameter rows contain per-square-foot fee units (for example `usd_per_sqft`), the economics service now emits a deterministic `direct_fee_model_card` under `economic_trace`:

- formula: `direct_fee_usd = project_size_sqft * fee_rate_usd_per_sqft`
- explicit bounded project-size assumptions:
  - low: 75,000 sqft
  - base: 100,000 sqft
  - high: 125,000 sqft
- arithmetic output:
  - per-parameter base-project fee totals
  - aggregate low/base/high direct fee sensitivity range
- source-bound parameter references:
  - `parameter_id`, `source_url`, `source_excerpt`, `evidence_card_id`

This is deterministic and auditable. It improves direct model arithmetic readiness without claiming a final household decision.

## Fail-Closed Household Guardrail

The model card now carries an explicit `household_impact_readiness` field:

- `status=not_proven` when source-bound pass-through/incidence assumptions are missing
- reason clearly states household incidence is not decision-grade without those assumptions

This preserves the required product behavior: direct developer fee math can be ready while household cost-of-living claims remain blocked.

## Read-Model Contract Delta

`economic_readiness` now exposes:

- `direct_model_card_readiness` (pass/not_proven/not_applicable)

This separates:

1. direct model-card arithmetic readiness, and
2. final decision-grade readiness.

## Test Evidence Added

1. `test_direct_sqft_fee_parameters_generate_source_bound_model_card`
   - verifies model card is generated from source-bound `usd_per_sqft` parameters
   - verifies arithmetic low/base/high ordering and source refs
   - verifies `economic_readiness.direct_model_card_readiness == pass`

2. `test_direct_model_card_keeps_household_conclusion_fail_closed_without_pass_through_assumptions`
   - verifies household impact remains `not_proven` without source-bound pass-through assumptions
   - verifies final decision-grade output remains fail-closed (`economic_output.status=not_proven`)

## Gate B Impact

Cycle 23 improves model-card and arithmetic auditability for direct fee paths, but intentionally does not overclaim final household impact. This reduces ambiguity in the economics handoff: direct fee math can be inspected and reused while final household conclusions remain blocked until assumption governance is complete.
