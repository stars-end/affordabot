# Golden Policy Regression Set (Cycle 45)

Feature-Key: `bd-3wefe.13.4.2`  
Benchmark: `local_government_data_moat_benchmark_v0`

Artifact:

- `docs/poc/policy-evidence-quality-spine/artifacts/golden_policy_regression_set.json`

Verifier:

- `backend/scripts/verification/verify_local_government_corpus_manual_audit.py`
- `backend/tests/verification/test_verify_local_government_corpus_manual_audit.py`

## Required Fields Per Golden Row

Each row includes:

1. stable query input
2. expected jurisdiction
3. expected policy family
4. selected source URL
5. package id
6. verdict
7. failure class
8. taxonomy version
9. split (`tuning` or `blind`)

## Cycle 45 Row Set

- Golden rows: `30`
- Unique package ids: `30`
- Split coverage:
  - `tuning`: 20
  - `blind`: 10
- Taxonomy version: `corpus_taxonomy_v1` on every row

## False-Pass Guardrails

The verifier fails on:

- San-Jose-only manual audit sampling
- Missing manual-audit required fields
- Missing golden-row required fields
- Missing audited-package coverage in golden rows
