# Policy Evidence Package Storage POC (bd-3wefe.10)

This POC proves the first persistence/readback boundary for `PolicyEvidencePackage` with fail-closed semantics.

## Scope

- Postgres-oriented package row contract (`policy_evidence_packages` migration shape).
- MinIO artifact write/readback distinction:
  - `proven` only when a probe confirms URI existence.
  - `unproven` when probe is unavailable.
  - never silently treated as proven.
- pgvector refs constrained to `derived_index` role.
- Idempotent replay via `idempotency_key` (no duplicate package truth rows).
- Partial-failure drills:
  - artifact write failure -> fail-closed result.
  - db upsert failure -> fail-closed result with compensation rollback signal.

## Files

- Storage service: [policy_evidence_package_storage.py](/tmp/agents/bd-2agbe.1/affordabot/backend/services/pipeline/policy_evidence_package_storage.py)
- Tests: [test_policy_evidence_package_storage.py](/tmp/agents/bd-2agbe.1/affordabot/backend/tests/services/pipeline/test_policy_evidence_package_storage.py)
- Verifier: [verify_policy_evidence_package_storage.py](/tmp/agents/bd-2agbe.1/affordabot/backend/scripts/verification/verify_policy_evidence_package_storage.py)
- Migration: [009_add_policy_evidence_package_storage.sql](/tmp/agents/bd-2agbe.1/affordabot/backend/migrations/009_add_policy_evidence_package_storage.sql)
- Artifact: [policy_evidence_package_storage_report.json](/tmp/agents/bd-2agbe.1/affordabot/docs/poc/policy-evidence-package-storage/artifacts/policy_evidence_package_storage_report.json)

## Validation Commands

```bash
git diff --check
cd backend && poetry run pytest tests/services/pipeline/test_policy_evidence_package_storage.py
cd backend && poetry run python scripts/verification/verify_policy_evidence_package_storage.py
```

## Notes

- This is a deterministic local proof harness; it does not require live Railway auth.
- Live Postgres/MinIO smoke can be layered later without changing the fail-closed storage contract.
