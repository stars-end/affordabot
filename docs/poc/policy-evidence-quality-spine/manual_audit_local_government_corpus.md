# Manual Audit: Local Government Corpus (Cycle 49)

Feature-Key: `bd-3wefe.13.4.7`
Benchmark: `local_government_data_moat_benchmark_v0`

## Scope

This manual audit is the C5 stratified sample for the local government corpus.
It is machine-checked by:

- `backend/scripts/verification/verify_local_government_corpus_manual_audit.py`
- `backend/tests/verification/test_verify_local_government_corpus_manual_audit.py`

Artifact:

- `docs/poc/policy-evidence-quality-spine/artifacts/manual_audit_local_government_corpus.json`

## Required Per-Package Manual Fields

Each audited package includes:

1. selected primary source
2. source officialness
3. source-family type
4. structured-source contribution
5. package identity
6. storage/readback evidence
7. data-moat classification
8. D11/economic handoff classification
9. freshness/drift
10. licensing/schema posture
11. Windmill orchestration classification
12. product-surface/export status
13. dominant failure class

## Stratified Sample

- Matrix package count at audit time: `90`
- Required C5 manual sample: `30` (>=30 rule)
- Audited package count: `30`

Jurisdiction stratification:

- `san_diego_ca`: 5
- `sacramento_ca`: 5
- `fresno_ca`: 5
- `portland_or`: 5
- `king_county_wa`: 5
- `austin_tx`: 5

Policy-family stratification:

- `commercial_linkage_fee`: 6
- `parking_policy`: 6
- `housing_permits`: 6
- `zoning_land_use`: 6
- `code_enforcement`: 6

Source-family stratification:

- `official_pdf_html_attachment`: 12
- `official_clerk_or_code_portal`: 18

Non-San-Jose jurisdictions with >=5 audited packages: `6` (requirement: `>=2`).

## Live-Proven Windmill Rows (Lightweight Audit Surface)

These rows are now represented explicitly in
`live_proven_audits` inside the JSON artifact.

This section is intentionally lightweight and does not upgrade corpus quality
claims by itself.

| corpus_row_id | jurisdiction_id | policy_family | source_lane_status | d11_handoff | manual_audit_status |
| --- | --- | --- | --- | --- | --- |
| `lgm-001` | `san_jose_ca` | `commercial_linkage_fee` | `windmill_live` | `analysis_ready_with_gaps` | `lightweight_live_proven_triage` |
| `lgm-007` | `oakland_ca` | `business_licensing_compliance` | `windmill_live` | `not_analysis_ready` | `lightweight_live_proven_triage` |
| `lgm-013` | `portland_or` | `short_term_rental` | `windmill_live` | `not_analysis_ready` | `lightweight_live_proven_triage` |
| `lgm-015` | `king_county_wa` | `meeting_action` | `windmill_live` | `not_analysis_ready` | `lightweight_live_proven_triage` |
| `lgm-018` | `austin_tx` | `procurement_contract` | `windmill_live` | `not_analysis_ready` | `lightweight_live_proven_triage` |

Evidence boundary marker (required per row):

- `evidence_boundary=orchestration_proof_only_not_substantive_quality`

Interpretation:

- `windmill_live` + concrete run/job refs proves orchestration evidence only.
- Substantive policy quality and decision-grade handoff quality remain governed
  by C0–C14 (not this lightweight list alone).

## Result

Cycle 49 manual-audit verification status: `pass` for C5 stratified sample plus
live-proven row representation checks.
