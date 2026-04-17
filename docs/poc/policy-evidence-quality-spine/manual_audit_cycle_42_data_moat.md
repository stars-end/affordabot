# Manual Audit: Cycle 42 Gate-Relaxation Regression

Feature key: `bd-3wefe.13`  
Commit under test: `8cb9695`  
Run key: `bd-3wefe.13-live-cycle-42-20260417061813`  
Backend run: `835704d9-4ab0-4caa-a5a5-4e812f818359`  
Package: `pkg-5cc79df1e9a1067dd990eb9d`  
Scenario: `parking_policy`

## Cycle Goal

Cycle 42 tested the gate split introduced after Cycle 41: valuable stored
local-government evidence should not fail the product data-moat gate merely
because it is not economic-analysis-ready.

## What Improved

The read model now exposes the intended three-layer split:

- `readiness_layers.stored_policy_evidence_value=stored_not_economic`
- `readiness_layers.economic_handoff_readiness=not_analysis_ready`
- `readiness_layers.economic_output_readiness=not_proven`

This is the correct product model: stored data value is separate from economic
handoff and final output readiness.

## Manual Finding

Cycle 42 exposed a regression in the first gate-relaxation patch.

The top-level `data_moat_status.status` became `evidence_ready_with_gaps`, but
the selected candidate was not official San Jose evidence:

- selected URL:
  `https://siliconvalleyathome.org/wp-content/uploads/2022/06/June-14-SJ-Parking-Policy-Council-letter-Updated.pdf`
- selected artifact family: `external_page`
- selection quality status: `fail`
- economic output: `not_proven`

That should remain a data-moat failure. Broad data value can include official
pages, meeting records, ordinances, staff reports, permits, and structured
metadata, but it must not silently upgrade external advocacy or third-party
sources as if they were source-grounded policy evidence.

## Gate Check

- D2 scraped evidence quality: fail. Selected source is external, not official.
- D3 structured evidence quality: not proven.
- D4 unified package identity: not enough, because the selected source quality
  is bad.
- D5 storage/readback: pass via admin read model.
- D6 Windmill integration: pass.
- Economic gates: not proven and correctly fail closed.

## Fix Applied After This Audit

The reconciliation guard was tightened so `stored_not_economic` can soften the
top-level data-moat status only when the selected artifact family is not
external and the source-selection reason is not an external-source selection.

Validation after the fix:

- targeted read-model tests: `59 passed`
- full backend tests: `797 passed`
- Ruff: passed
- `git diff --check`: passed

## Verdict

`FAIL_DATA_MOAT__GATE_RELAXATION_TOO_PERMISSIVE_FOR_EXTERNAL_SOURCE`

Cycle 42 was still a useful cycle because it found and fixed a false-positive
gate relaxation. The next live cycle must prove the corrected behavior:

- external-source parking packages remain fail;
- official/source-grounded broad policy packages can be
  `evidence_ready_with_gaps`;
- economic analysis remains `not_proven` unless strict economic gates pass.
