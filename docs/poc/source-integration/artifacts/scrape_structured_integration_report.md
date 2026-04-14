# Scrape + Structured Source Integration POC

Date: 2026-04-14T17:48:47.411740+00:00
Feature key: `bd-2agbe.11`
Mode: `replay`

## Objective

Prove one backend-owned merged artifact/evidence contract across:

- structured lane (`legistar`, `leginfo`, `ckan`, `arcgis`)
- scrape/search lane (`private_searxng`, `tavily`, `exa`)

## Contract Outcome

- total envelopes: `8`
- integrated cross-lane dedupe groups: `1`
- evidence_card_ready: `3`
- reader_required: `3`
- insufficient: `2`
- economic_handoff_ready: `3`
- quantified-ready subset: `3`
- quality assessment: `sufficient_for_quantified_handoff_in_subset`

## Provider Role Recommendation

- `private_searxng`: primary scrape/search lane
- `tavily`: hot fallback
- `exa`: bakeoff/eval only
- structured providers first when available (`legistar`, `leginfo`, `ckan`, `arcgis`)

## ImpactMode -> MechanismFamily Mapping

[
  {
    "impact_mode": "direct_fiscal",
    "mechanism_family": "direct_fiscal",
    "supports_quantified_handoff": true,
    "note": "Direct appropriations/tax spend flows map 1:1."
  },
  {
    "impact_mode": "compliance_cost",
    "mechanism_family": "compliance_cost",
    "supports_quantified_handoff": true,
    "note": "Regulatory/admin burden costs map 1:1."
  },
  {
    "impact_mode": "pass_through_incidence",
    "mechanism_family": "fee_or_tax_pass_through",
    "supports_quantified_handoff": true,
    "note": "Explicit normalization required due enum label mismatch."
  },
  {
    "impact_mode": "adoption_take_up",
    "mechanism_family": "adoption_take_up",
    "supports_quantified_handoff": true,
    "note": "Program participation/uptake mechanics map 1:1."
  },
  {
    "impact_mode": "qualitative_only",
    "mechanism_family": null,
    "supports_quantified_handoff": false,
    "note": "No economic_evidence mechanism family exists for qualitative-only."
  }
]

## Schema Validation

- mode: `local_contract_only`
- validated ready evidence count: `0`
- schema errors count: `0`
- schema import error: `ModuleNotFoundError: No module named 'pydantic'`

## Evidence Quality Note

Merged contract is suitable for backend economic handoff in a subset; items marked reader_required/insufficient remain fail-closed or qualitative.
