# Live Cycle 14 Manual Findings

Feature-Key: bd-3wefe.13

## Verdict

Cycle 14 is the strongest live proof so far for the data-moat spine, but not for decision-grade economic analysis.

## Evidence Artifacts

- Live run: `docs/poc/policy-evidence-quality-spine/artifacts/live_cycle_14_windmill_domain_run.json`
- Live run summary: `docs/poc/policy-evidence-quality-spine/live_cycle_14_windmill_domain_run.md`
- Storage probe: `docs/poc/policy-evidence-quality-spine/artifacts/live_cycle_14_storage_probe.json`
- Admin read model: `docs/poc/policy-evidence-quality-spine/artifacts/live_cycle_14_admin_analysis_status.json`

## Data-Moat Result

Gate A is materially improved.

The live run selected and read the official San Jose Commercial Linkage Fee page:

- `https://www.sanjoseca.gov/your-government/departments-offices/housing/developers/commercial-linkage-fee`

Storage and derivation passed:

- Postgres package row: pass
- MinIO object readback: pass
- pgvector derivation: pass
- atomicity/replay gate: pass
- storage/read-back: pass

The package has:

- scraped official San Jose source lane
- structured Legistar Web API source lane
- Windmill current-run id binding
- backend run id binding
- package artifact in MinIO
- 233 chunks with 233 embeddings

Remaining data-moat weakness:

- structured source content is still diagnostic meeting metadata, not economic policy parameters.
- selected-artifact provider-quality metrics are not yet surfaced into the admin economic gate.

## Economic-Analysis Result

Gate B is not decision-grade, and the fail-closed behavior is correct.

The canonical LLM analysis completed and found:

- affected project categories: non-residential projects that add floor area or change use
- mechanism: one-time impact fee based on geographic subareas and annual ENR index adjustment
- missing information: specific dollar rates, which are in a separate Fee Resolution
- secondary research needed for household pass-through/cost-of-living impact

The admin read model correctly reports:

- `decision_grade_verdict`: `not_decision_grade`
- `sufficiency_readiness_level`: `qualitative_only`
- `economic_output.user_facing_conclusion`: `null`
- `canonical_analysis_binding`: `not_proven`
- `parameter_readiness`: fail
- `model_readiness`: fail
- `uncertainty_readiness`: fail

## Product Implication

The pipeline can now produce an official-source, durable, queryable evidence package for San Jose. It cannot yet produce quantitative economic analysis because it needs at least one more governed evidence artifact: the fee-resolution/rate schedule with dollar rates per square foot.

## Next Tweak

Cycle 15 targets the missing rate schedule directly with a narrower query:

`site:sanjoseca.gov San Jose Commercial Linkage Fee Resolution fee schedule per square foot PDF`

If Cycle 15 finds the rate schedule, the next product architecture decision is whether to implement package-level multi-document evidence assembly so the base ordinance/source page and fee-resolution artifact land in one unified package for analysis.
