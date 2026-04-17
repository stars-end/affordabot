# Agent B Normalized Economic Rows Cycles (`bd-3wefe.13`)

Scope: normalized official economic rows + CLF fee-table extraction + cross-source reconciliation hardening.

## Cycle B11 (current)

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
