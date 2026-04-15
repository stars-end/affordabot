# Policy Evidence Package Sufficiency POC (`bd-3wefe.5`)

This POC verifies deterministic economic-analysis handoff sufficiency from
persisted/read-back `PolicyEvidencePackage` records.

## Scope

Verifier input is persisted storage rows (`PersistedPackageRecord`) produced by:

1. `PolicyEvidencePackageBuilder` (`bd-3wefe.4`)
2. `PolicyEvidencePackageStorageService` (`bd-3wefe.10`)

The sufficiency service does not accept ad hoc in-memory payloads as canonical
proof input.

## Deterministic gate checks

`PolicyEvidencePackageSufficiencyService` enforces:

1. schema validity of persisted payload
2. storage proof/readback (`artifact_readback_status=proven`)
3. package completeness (lanes, evidence cards, gate projection/stages)
4. gate projection alignment with runtime handoff state
5. parameter readiness for quantified paths
   - quant model inputs must map to resolved parameter cards
   - quant model assumptions must map to assumption cards plus governed assumption usage
6. source-support hierarchy for resolved parameters
7. assumption staleness/applicability for quantitative usage
8. uncertainty/sensitivity support for quant-eligible models
9. unsupported-claim handling with fail-closed posture (`fail_closed` verdict is compatible)

Readiness levels returned:

- `economic_handoff_ready`
- `qualitative_only`
- `fail_closed`

## Verification command

```bash
cd backend
poetry run python scripts/verification/verify_policy_evidence_package_sufficiency.py
```

Default artifact output:

- `docs/poc/policy-evidence-package-sufficiency/artifacts/policy_evidence_package_sufficiency_report.json`

## Required proof cases

The verifier emits all required cases:

1. persisted/read-back positive package passes
2. unproven readback fails closed
3. stale assumption blocks quantitative handoff
4. missing parameter support fails closed
5. qualitative-only package remains qualitative-usable but not quantified
