# Live Cycle 18: Parameter Table Bridge

Feature-Key: bd-3wefe.13

## Purpose

Cycle 18 verified the deployed Cycle 17 secondary structured evidence lane in Railway dev.

## Evidence Artifacts

- Live run: `docs/poc/policy-evidence-quality-spine/artifacts/live_cycle_18_windmill_domain_run.json`
- Live summary: `docs/poc/policy-evidence-quality-spine/live_cycle_18_windmill_domain_run.md`
- Storage probe: `docs/poc/policy-evidence-quality-spine/artifacts/live_cycle_18_storage_probe.json`
- Admin read model: `docs/poc/policy-evidence-quality-spine/artifacts/live_cycle_18_admin_analysis_status.json`

## Result

Cycle 18 is the first live cycle where the unified data moat directly improves the economic analysis package.

The run selected a San Jose Legistar attachment:

`https://sanjose.legistar.com/View.ashx?M=F&ID=8758120&GUID=6C299331-91E9-48ED-B7A5-43601D63FBF6`

The analysis extracted fee rates and categories from the selected source. The package also included Tavily secondary evidence from the official San Jose CLF page.

Storage/readback passed:

- Postgres package row: pass
- MinIO object readback: pass
- pgvector derivation: pass
- atomicity/replay: pass

## Data-Moat Findings

The package contains three useful evidence cards:

1. Scraped Legistar attachment with fee schedule content.
2. Structured Legistar Web API metadata.
3. Tavily secondary official-source rate snippet from the San Jose CLF page.

The package now crosses the important boundary from "we found a source" to "we extracted source-bound economic parameters":

- `parameter_readiness`: pass
- `economic_resolved_parameters`: 2
- diagnostic metadata excluded: 1

Parameter table rows in the admin read model:

- `$3.58` per square foot
- `$3.00` per square foot

Both are source-bound to the official San Jose CLF page via the Tavily secondary evidence card.

## Economic-Analysis Findings

Economic analysis still correctly refuses final decision-grade output:

- `decision_grade_verdict`: `not_decision_grade`
- `economic_output.status`: `not_proven`
- `economic_output.user_facing_conclusion`: `null`

Remaining blockers:

- assumption governance
- model card/arithmetic integrity
- uncertainty/sensitivity
- canonical analysis binding
- selected-artifact provider-quality metrics in admin output

## Manual Quality Concern

The LLM analysis extracted a malformed row:

`Residential Care $18.706.00`

This is a reader/PDF text extraction artifact and must not become a numeric parameter. The structured parameter table did not include that malformed value, which is correct.

The Tavily structured lane also under-extracted some official snippet values visible in the manual probe, including `$14.31` and `$17.89`. This does not invalidate the gate improvement, but it means the extraction rules should be improved before claiming comprehensive fee schedule coverage.

## Gate Delta

- D2 scraped quality: pass for selecting a fee schedule artifact.
- D3 structured quality: partial/pass for source-bound numeric fee facts.
- D4 unified package: pass for scraped + structured + secondary source lanes.
- D5 storage readback: pass.
- D6 Windmill integration: pass.
- E1 mechanism/parameter coverage: improved; parameter readiness now pass.
- E2 sufficiency: still qualitative-only.
- E3 secondary research: partial; provider lane exists, but pass-through research loop is not complete.
- E4 canonical LLM binding: not_proven.
- E5 decision-grade quality: fail/not_proven.

## Decision

Continue. The next cycle should bind successful domain LLM analysis to the package so the admin read model can distinguish "analysis succeeded but economics not decision-grade" from "canonical LLM narrative missing."
