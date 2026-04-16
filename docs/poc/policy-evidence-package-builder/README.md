# Policy Evidence Package Builder POC (`bd-3wefe.4`)

This POC proves a backend-owned builder can unify scraped and structured inputs
into one package envelope without moving product logic into Windmill.

## Scope

Implemented in:

- `backend/services/pipeline/policy_evidence_package_builder.py`
- `backend/tests/services/pipeline/test_policy_evidence_package_builder.py`
- `backend/scripts/verification/verify_policy_evidence_package_builder.py`

Artifact output:

- `docs/poc/policy-evidence-package-builder/artifacts/policy_evidence_package_builder_output.json`

## What this POC proves

1. Scraped + structured candidate inputs can be normalized into one
   schema-valid `PolicyEvidencePackage` payload.
2. Provider/source/read/structured lineage fields are preserved on each
   package via `scraped_sources`, `structured_sources`, and evidence cards.
3. Readiness partitions are emitted by the verifier as report metadata:
   - `readiness_summary.package_ready_evidence_count`
   - `readiness_summary.reader_required_evidence_count`
   - `readiness_summary.insufficient_evidence_count`
4. Economic handoff readiness is fail-closed when the package lacks a
   quantitative support path (for example missing parameterization).
5. Storage references are schema-native and include pgvector only as
   `derived_index`.

## What this POC does not claim

- No storage durability/read-back proof (`bd-3wefe.10`).
- No Windmill run proof (`bd-3wefe.12`).
- No final economic sufficiency gate claim (`bd-3wefe.5`).
- No second economic engine; this builder only prepares an auditable handoff
  envelope.

## Re-run

```bash
python3 backend/scripts/verification/verify_policy_evidence_package_builder.py
```

This writes/refreshes the artifact JSON under `artifacts/`.
