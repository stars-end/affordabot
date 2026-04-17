# Agent B Normalized Economic Rows Cycles (`bd-3wefe.13`)

Scope: normalized official economic rows + CLF fee-table extraction + cross-source reconciliation hardening.

## Cycle B12 (current)

Date: 2026-04-16
Lane objective: stop reconciliation collapse by promoting richer economic-row identity (value/timing/threshold/raw label/locator/family) and emit fail-closed locator signals for manual audit.

### Changes

- Hardened primary CLF extraction with explicit payment/exemption semantics:
  - `payment_timing` (e.g. `paid_before_building_permit_issuance`, `paid_at_final_building_inspection`)
  - `payment_reduction_context` + `payment_reduction_percent`
  - `exemption_context` (including threshold-bound no-fee rows)
- Expanded normalized/reconciliation row payloads to carry audit-critical context:
  - `raw_land_use_label`, payment fields, `source_family`, and `fail_closed_signals`
  - fail-closed signal emitted when locator quality is chunk/page-only or missing table/artifact locator.
- Replaced coarse reconciliation grouping with identity-preserving semantics:
  - row identity now includes value + timing/reduction/exemption + raw label + source locator + source family
  - primary rows are no longer overwritten by dict-key collision
  - secondary-search rows remain strictly non-authoritative; true structured count remains independent.
- Extended builder parameter-card citation formatting with payment/exemption/raw-label/source-family/fail-closed metadata for manual data-moat traceability.

### Validation

```bash
cd backend
poetry run pytest \
  tests/services/pipeline/test_bridge_runtime.py \
  tests/services/pipeline/test_policy_evidence_package_builder.py
poetry run ruff check \
  services/pipeline/domain/bridge.py \
  services/pipeline/policy_evidence_package_builder.py \
  tests/services/pipeline/test_bridge_runtime.py \
  tests/services/pipeline/test_policy_evidence_package_builder.py
```

### Gate impact

- D4 (extraction + citation auditability): payment timing/reduction/exemption and raw row labels now survive into parameter-card citations and normalized rows.
- D5 (cross-source reconciliation correctness): multi-row CLF primary evidence stays distinct instead of collapsing to coarse `(field, land_use, subarea, threshold)` keys.
- D3 strict authority preserved: `secondary_search_derived` rows remain non-authoritative; they do not create true-structured corroboration.

### Remaining gap after B12

- Cycle still fails closed on structured depth for decision-grade claims because true structured economic rows remain zero unless attachment/API rows provide artifact-grade structured facts.

## Cycle B11

Date: 2026-04-16  
Lane objective: turn CLF-style official fee facts into auditable normalized rows that can feed parameter cards and reconciliation without allowing secondary snippets to masquerade as structured proof.

### Changes

- Extended primary CLF fee extraction with richer row metadata:
  - `land_use`, `subarea`, `geography`, `threshold`
  - `source_locator`, `chunk_locator`, `table_locator`, `page_locator`, `locator_quality`
  - `effective_date`, `adoption_date`, `final_status`
  - explicit sanity/ambiguity fields for malformed money values
- Added normalized-row projection in runtime package context:
  - `run_context.normalized_official_economic_rows`
  - each row carries policy/source identity, locator quality, units/denominator, hierarchy, confidence, and arithmetic eligibility.
- Hardened reconciliation semantics:
  - primary official rows remain source of truth
  - secondary-search rows are labeled non-authoritative
  - missing true-structured corroboration is explicit (`missing_structured_corroboration`)
  - counts for primary/true-structured/secondary and missing corroboration are emitted.
- Extended builder citation payload formatting so parameter-card excerpts carry normalized row context (subarea/threshold/locator quality/policy key/date/status).

### Validation

```bash
cd backend
poetry run pytest \
  tests/services/pipeline/test_bridge_runtime.py \
  tests/services/pipeline/test_policy_evidence_package_builder.py \
  tests/verification/test_verify_scraped_lane_data_moat.py
```

Result: `48 passed`.

### Gate impact

- D4 (Extraction Accuracy + Citation): improved auditability of each extracted fee row/parameter via explicit locators, date/status fields, and sanity flags.
- D5 (Cross-Source Reconciliation): explicit source-of-truth decisions now separate:
  - confirmed vs conflict vs missing true-structured corroboration vs secondary-only-not-authoritative.
- D3 remains intentionally strict:
  - no Tavily/secondary snippet can satisfy true structured economic-row proof.

### Remaining gap after B11

- True structured economic row depth is still not proven from structured APIs alone; official attachment traversal/normalization must supply structured corroboration beyond metadata/count rows.
