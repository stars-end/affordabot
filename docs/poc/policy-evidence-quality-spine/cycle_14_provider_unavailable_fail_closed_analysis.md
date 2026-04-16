# Cycle 14: Provider-Unavailable Fail-Closed Analysis

Feature-Key: bd-3wefe.13

## Purpose

Cycle 13 proved that live storage, Windmill binding, and package readback can work, but a transient LLM provider failure made the whole run `failed_terminal`. That was too brittle for the data moat: provider outages should not discard or obscure a persisted evidence package.

Cycle 14 changes the analysis step so a provider-unavailable condition after evidence selection produces an auditable fail-closed analysis payload instead of a terminal run failure.

## Tweak

Changed `RailwayRuntimeBridge._analyze`:

- If evidence chunks exist but the canonical LLM provider is unavailable or errors, return `succeeded_with_alerts`.
- Set `decision_reason` to `analysis_provider_unavailable`.
- Include explicit alerts:
  - `analysis_provider_unavailable`
  - `analysis_fail_closed_provider_unavailable`
  - `canonical_llm_narrative_not_proven`
- Store deterministic `details.analysis` payload:
  - `sufficiency_state=provider_unavailable`
  - `analysis_mode=fail_closed_provider_unavailable`
  - `analysis_not_proven=true`
  - `canonical_llm_narrative_proven=false`
  - selected evidence refs and snippets
  - requested analysis question

No-evidence behavior is unchanged. The command still returns blocked/fail-closed when no evidence chunks exist.

## Product Boundary

This does not create a synthetic economic analysis.

The change lets Gate A keep its storage/readback evidence when Gate B cannot run. The economic gates still fail closed because:

- analysis status is not a clean `succeeded`
- sufficiency state is `provider_unavailable`
- canonical LLM narrative is explicitly not proven
- package fail-closed reasons include `analyze:analysis_provider_unavailable`

## Validation

Focused validation:

- `poetry run pytest tests/services/pipeline/test_bridge_runtime.py -q` -> 19 passed
- `poetry run ruff check services/pipeline/domain/bridge.py tests/services/pipeline/test_bridge_runtime.py` -> passed

## Expected Live Gate Delta

Expected Cycle 14 live behavior:

- D5 storage/readback can pass even when the LLM provider is rate-limited.
- D6 Windmill integration can pass with `succeeded_with_alerts`.
- E4 canonical LLM binding remains `not_proven`.
- E5 decision-grade economic quality remains fail/not_proven.
- The admin read model should show a readable package plus an explicit provider-unavailable analysis state.
