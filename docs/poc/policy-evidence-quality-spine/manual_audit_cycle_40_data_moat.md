# Cycle 40 Manual Data-Moat Audit

Feature-Key: bd-3wefe.13

Run artifact: `docs/poc/policy-evidence-quality-spine/artifacts/live_cycle_40_windmill_domain_run.json`
Package payload: `docs/poc/policy-evidence-quality-spine/artifacts/live_cycle_40_policy_package_payload.json`
Admin read model: `docs/poc/policy-evidence-quality-spine/artifacts/live_cycle_40_admin_analysis_status.json`

## Verdict

`EVIDENCE_READY_WITH_GAPS__CLF_FALSE_ROW_FIXED_BUT_BROAD_MOAT_NOT_PROVEN`

Cycle 40 made a real data-quality improvement, but it is not a decision-grade data moat and should not be treated as a general city/county evidence architecture proof.

## Improvements Since Cycle 39

- The invalid `$600 per square foot` construction/development-cost assumption is no longer emitted as a resolved `commercial_linkage_fee_rate_usd_per_sqft` parameter.
- The valid Residential Care fee row remains:
  - value: `$6`
  - source excerpt: `The recommended fee level for Residential Care Facilities is $6 per square foot.`
  - source URL: `https://legistar.granicus.com/sanjose/attachments/eb98bc80-6c09-4b45-ba75-db970576e5f3.pdf`
- The package still selects the correct official Legistar CLF artifact.
- Private SearXNG remains proven in the product path through the admin provider runtime summary.
- The package is stored and visible through the admin read model.

## Remaining Failures

- Admin status remains `evidence_ready_with_gaps`, not `decision_grade_data_moat`.
- `row_quality_gate_status=fail`, `row_quality_gap=true`, `row_quality_weak_row_count=1`.
- The package is still highly CLF-specific. It proves useful vertical hardening, not broad city/county data moat breadth.
- The broader data moat must preserve high-quality evidence even when it does not directly feed economic analysis. Cycle 40 does not test meeting minutes, permits, parking, compliance rules, or other city/county policy evidence families.
- Economic handoff remains blocked for household cost-of-living because pass-through/adoption assumptions are missing.

## Product Interpretation

The CLF vertical is a calibration slice. It is useful because it forced the pipeline to distinguish real fee rates from nearby but non-fee cost assumptions. It should not become the product architecture by itself.

The general product architecture needs three separate states:

- `stored_policy_evidence`: high-quality city/county evidence preserved for moat value even when not economic-ready.
- `economic_handoff_candidate`: evidence appears to contain parameters or mechanisms relevant to cost-of-living analysis.
- `economic_analysis_ready`: evidence has source-bound parameters, model/assumption support, units, and uncertainty needed for analysis.

Cycle 40 improves the second and third states for one CLF slice, but the next substantive cycle should broaden the first state.

## Required Next Direction

Stop adding narrow CLF-only patches unless they remove a clearly proven false positive. The next product-improving wave should broaden the moat:

- Store and classify useful non-economic local-policy evidence, not only fee rows.
- Add a package-level evidence-use classification so data can be valuable even when economic analysis is not ready.
- Validate at least one additional San Jose local-policy family, such as parking, housing permits, meeting actions, or business compliance rules.
- Keep economic handoff as a downstream readiness classifier, not the only definition of data value.

