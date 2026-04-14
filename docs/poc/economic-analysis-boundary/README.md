# Structured Economic Handoff POC (`bd-2agbe.10`)

This POC extends structured-source readiness into decision-grade economic-analysis boundary evidence.

Goal: prove or falsify that structured facts + linked artifacts can hand off into canonical backend economic-analysis contracts while keeping Windmill focused on orchestration.

## Scope

- Deterministic replay verifier:
  - [verify_structured_economic_handoff_poc.py](/tmp/agents/bd-2agbe.1/affordabot/backend/scripts/verification/verify_structured_economic_handoff_poc.py)
- Focused tests:
  - [test_structured_economic_handoff_poc.py](/tmp/agents/bd-2agbe.1/affordabot/backend/tests/verification/test_structured_economic_handoff_poc.py)
- Generated artifacts:
  - [structured_economic_handoff_report.json](/tmp/agents/bd-2agbe.1/affordabot/docs/poc/economic-analysis-boundary/artifacts/structured_economic_handoff_report.json)
  - [structured_economic_handoff_report.md](/tmp/agents/bd-2agbe.1/affordabot/docs/poc/economic-analysis-boundary/artifacts/structured_economic_handoff_report.md)

## Gate Contract

The verifier evaluates these gates in order:

1. `source_access`
2. `reader_substance`
3. `evidence_card_extraction`
4. `parameterization`
5. `assumption_selection`
6. `deterministic_quantification`
7. `llm_explanation_guardrail`
8. `persistence_read_model`
9. `orchestration_boundary`

## Replay Cases

- `case_direct_fiscal_quantified_pass`
  - Positive path where structured evidence supports direct-fiscal quantified output.
- `case_local_control_fail_closed_insufficient`
  - Fail-closed path where source/reader pass but parameterization remains insufficient.

## Canonical Boundary Recommendation

- Recommended architecture option: `option_a` from [2026-04-14-economic-evidence-pipeline-lockdown.md](/tmp/agents/bd-2agbe.1/affordabot/docs/specs/2026-04-14-economic-evidence-pipeline-lockdown.md).
- Windmill should own DAG scheduling/retries/branching only.
- Backend should own product/domain logic: evidence extraction, parameterization, assumption selection, deterministic quantification, and fail-closed sufficiency.
- Postgres should remain canonical run/step/read-model storage.
- pgvector should remain retrieval substrate.
- MinIO should remain object storage for raw/reader artifacts referenced by URI.
- Frontend/admin should consume backend-authored read models only.

## Evidence Quality Limits

This is replay-only proof of contract behavior and gate attribution. It is not live production proof.

Before Railway-dev rollout, run live multi-jurisdiction checks proving:

- search/read -> structured artifact extraction parity with replay gate decisions,
- persisted artifact linkage in `pipeline_runs`/`pipeline_steps` + evidence endpoints,
- stable operator read models in admin views.

## Commands

```bash
python3 backend/scripts/verification/verify_structured_economic_handoff_poc.py --mode replay --self-check
python3 - <<'PY'
from backend.tests.verification.test_structured_economic_handoff_poc import (
    test_replay_contract_has_required_gates_for_all_cases,
    test_replay_contains_quantified_pass_and_fail_closed_case,
    test_contract_validator_rejects_missing_case_structure,
)
test_replay_contract_has_required_gates_for_all_cases()
test_replay_contains_quantified_pass_and_fail_closed_case()
test_contract_validator_rejects_missing_case_structure()
print("direct_test_execution: PASS")
PY
git diff --check
```
