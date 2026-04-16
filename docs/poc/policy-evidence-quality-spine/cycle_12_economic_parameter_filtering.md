# Cycle 12 - Economic Parameter Filtering and Indirect Assumption Guardrails

Date: 2026-04-16
Owner lane: Worker C (economic handoff/read-model/eval)

## Problem observed in cycle 11

`economic_trace.parameter_table` treated diagnostic metadata as economic support:

- `event_id`
- `event_body_id`
- `dataset_match_count=0`

This inflated parameter readiness and mixed pipeline diagnostics with decision-support economics.

## Tweak implemented

### 1) Conservative economic parameter classification

In `PolicyEvidenceQualitySpineEconomicsService`:

- Added explicit filtering for economically meaningful resolved parameters.
- Excluded diagnostic/metadata-like parameters from economic support:
  - id/metadata patterns (`event_id`, `body_id`, `dataset_match_count`, etc.)
  - structured-fact placeholder excerpts (`"Structured fact ... resolved from source payload."`)
  - non-economic count-only metrics without economic semantic hints
- Kept excluded rows visible under:
  - `economic_trace.diagnostic_parameter_table`
- `economic_trace.parameter_table` now includes only economically meaningful rows.

### 2) Gate B parameter readiness now uses economic-only rows

- `economic_readiness.parameter_readiness` now passes only when at least one economically meaningful, source-bound resolved parameter exists.
- Diagnostic rows are explicitly counted as excluded in the readiness reason.

### 3) Indirect path assumption guardrail tightened

For indirect mechanisms:

- Assumption governance now requires non-placeholder source-bound pass-through/take-up assumptions.
- Placeholder assumption text (for example, `"Mapped mechanism assumption from source evidence and policy context."`) is treated as non-admissible.
- If this guardrail fails, `secondary_research_needed` remains required.

## Validation

Added tests:

- `test_diagnostic_parameters_are_excluded_from_economic_support`
- `test_indirect_mechanism_requires_non_placeholder_assumption_or_secondary_research`

Both tests assert:

- diagnostic metadata remains visible but not counted as economic support
- indirect assumptions must be source-bound and non-placeholder, otherwise Gate B remains fail-closed/secondary-research-required
