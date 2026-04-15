# Policy Economic Mechanism Cases (bd-3wefe.6)

This POC validates that `PolicyEvidencePackage` can represent deterministic
economic-analysis inputs for:

- direct cost cases
- indirect pass-through/adoption cases
- secondary-research-required cases (as a second package)
- unsupported claims that fail closed

## Scope

This lane is deterministic and offline:

- no live search
- no live reader
- no live LLM analysis

The objective is representational readiness for the economic-analysis handoff,
not narrative quality.

## Generated Cases

1. `direct_cost_case`
   - direct compliance-cost mechanism
   - source-bound parameter table
   - low/base/high range
   - deterministic conclusion
2. `indirect_pass_through_case`
   - indirect fee/tax pass-through mechanism
   - explicit assumption card + usage
   - sensitivity range and uncertainty notes
3. `secondary_research_required_case`
   - primary package is qualitative-only and blocked
   - secondary package restores quantified readiness
   - secondary evidence provenance is explicit and auditable
4. `unsupported_fail_closed_control`
   - unsupported numeric claim
   - fail-closed gate report
   - explicit rejection reason

## Commands

```bash
cd backend && poetry run pytest tests/services/pipeline/test_policy_economic_mechanism_cases.py
cd backend && poetry run python scripts/verification/verify_policy_economic_mechanism_cases.py
```

## Artifact

- JSON report:
  `docs/poc/policy-economic-mechanism-cases/artifacts/policy_economic_mechanism_cases_report.json`

The report includes per-case payloads, deterministic gate results, readiness
summary, and remaining non-goals for this lane.

Additional coverage in this lane:
- canonical document keys are policy-identity stable (not package-id encoded)
- scraped-source provenance fields are case-specific, not shared fixture placeholders

## Integration Note

The verifier persists and reads back each mechanism package through the storage
harness, then evaluates it with `PolicyEvidencePackageSufficiencyService`. This
keeps the economic-analysis proof tied to the same package sufficiency gate used
by `bd-3wefe.5`.
