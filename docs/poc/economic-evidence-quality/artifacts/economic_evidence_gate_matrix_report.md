# Economic Evidence Gate Matrix Report (bd-2agbe.4)

- generated_at: `2026-04-14T07:39:59.832435+00:00`
- verifier_version: `2026-04-14.fixture-v1`
- fixture_path: `backend/scripts/verification/fixtures/economic_evidence_gate_cases.json`

## Summary

- total_cases: `6`
- quantified_pass_count: `3`
- qualitative_fail_closed_count: `2`
- llm_blocked_count: `1`

## Case Results

| case_id | provider | final_verdict | blocking_gate | evidence_cards | parameter_cards | assumption_cards | unsupported_claims |
|---|---|---|---|---:|---:|---:|---:|
| direct_fiscal_positive_city_staff_report | fixture | quantified_pass |  | 2 | 2 | 0 | 0 |
| compliance_cost_positive_recurring_reporting | fixture | quantified_pass |  | 2 | 4 | 0 | 0 |
| pass_through_positive_declared_assumption | fixture | quantified_pass |  | 1 | 1 | 1 | 0 |
| local_minutes_control_fail_closed_no_numeric_basis | fixture | fail_closed_qualitative_only | parameterization | 1 | 0 | 0 | 0 |
| provider_failure_no_artifact_candidates | fixture | fail_closed_qualitative_only | search_recall | 0 | 0 | 0 | 0 |
| llm_explanation_failure_unsupported_claims | fixture | qualitative_only_due_to_unsupported_claims | llm_explanation | 1 | 1 | 0 | 2 |

## Manual Audit Notes

### direct_fiscal_positive_city_staff_report

- jurisdiction: `San Jose CA`
- source_family: `staff_report`
- notes: Official city staff report includes explicit annual appropriation amount and implementation horizon.
- integration_note: TODO integrate with bd-2agbe.2/.3 contract classes once merged.

### compliance_cost_positive_recurring_reporting

- jurisdiction: `Saratoga CA`
- source_family: `ordinance_text`
- notes: Ordinance text and implementation memo define population, recurrence, labor burden, and wage rate assumptions.
- integration_note: TODO integrate with bd-2agbe.2/.3 contract classes once merged.

### pass_through_positive_declared_assumption

- jurisdiction: `Santa Clara County CA`
- source_family: `fiscal_analysis`
- notes: County impact memo provides annual levy amount; pass-through assumption is registry-aligned for housing rental local tax or fee incidence.
- integration_note: TODO integrate with bd-2agbe.2/.3 contract classes once merged.

### local_minutes_control_fail_closed_no_numeric_basis

- jurisdiction: `San Jose CA`
- source_family: `meeting_minutes`
- notes: Official minutes confirm policy discussion and vote but provide no fiscal amount or numeric compliance basis.
- integration_note: TODO integrate with bd-2agbe.2/.3 contract classes once merged.

### provider_failure_no_artifact_candidates

- jurisdiction: `Mountain View CA`
- source_family: `city_council_minutes`
- notes: Provider returned no useful artifact URLs; attribution must stop at search gate.
- integration_note: TODO integrate with bd-2agbe.2/.3 contract classes once merged.

### llm_explanation_failure_unsupported_claims

- jurisdiction: `Sunnyvale CA`
- source_family: `staff_report`
- notes: Deterministic calculation succeeds, but the generated narrative introduces unsupported numeric claims.
- integration_note: TODO integrate with bd-2agbe.2/.3 contract classes once merged.
