# Manual Audit: Cycle 43 External-Source Guard Verification

Feature key: `bd-3wefe.13`  
Commit under test: `8375212`  
Run key: `bd-3wefe.13-live-cycle-43-20260417062432`  
Backend run: `044f2532-29b5-475f-918a-b1c71283f1bf`  
Package: `pkg-72c61e051ff27ad3861cb9a6`  
Scenario: `parking_policy`

## Cycle Goal

Cycle 43 verified the Cycle 42 regression fix: broad-data gate relaxation must
not convert external-source selection failures into product passes.

## Manual Evidence Inspected

- Windmill run artifact:
  `docs/poc/policy-evidence-quality-spine/artifacts/live_cycle_43_windmill_domain_run.json`
- Admin read model:
  `docs/poc/policy-evidence-quality-spine/artifacts/live_cycle_43_admin_analysis_status.json`
- Stored package payload:
  `docs/poc/policy-evidence-quality-spine/artifacts/live_cycle_43_policy_package_payload.json`

## Result

The selected source remained external:

- selected URL:
  `https://actionnetwork.org/user_files/user_files/000/077/644/original/SJ_Parking_Policy_Council_Letter.pdf`
- selected artifact family: `external_page`
- selection quality status: `fail`
- private SearXNG runtime: proven
- storage/read-back: pass via admin read model
- Windmill/orchestration: pass
- economic output: `not_proven`

The corrected guard worked:

- `data_moat_value.status=stored_not_economic`
- `readiness_layers.stored_policy_evidence_value=stored_not_economic`
- `readiness_layers.economic_handoff_readiness=not_analysis_ready`
- `readiness_layers.economic_output_readiness=not_proven`
- `data_moat_status.status=fail`

## Gate Check

- D2 scraped evidence quality: fail. Private SearXNG returned and the backend
  selected an external advocacy PDF instead of official San Jose/Legistar
  evidence.
- D3 structured evidence quality: not proven for this run.
- D4 unified package identity: not sufficient because source selection failed.
- D5 storage/readback: pass via backend admin read model.
- D6 Windmill integration: pass.
- Economic gates: not proven and correctly fail closed.

## Verdict

`FAIL_DATA_MOAT__EXTERNAL_SOURCE_SELECTION_CORRECTLY_BLOCKED`

This cycle did not improve source quality, but it did verify that the previous
false-positive gate relaxation was fixed. The next substantive product work
should be source-selection improvement for broad local policy scenarios:
official San Jose/Legistar records must outrank third-party advocacy PDFs for
`parking_policy`, while external sources remain available only as context or
secondary evidence.
