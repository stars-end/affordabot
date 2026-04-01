# Golden Bill Corpus Fixture Contract

This directory contains the `bd-bkco.1` curated corpus manifest, `bd-bkco.2` replayable research fixtures, and `bd-bkco.3` analyst-labeled step expectations used by downstream golden-suite tasks.

## Files

- `golden_bill_corpus_manifest.json`: canonical machine-readable bill corpus
- `research_fixture_set_metadata.json`: machine-readable scope contract for the checked-in fixture subset
- `golden_bill_step_expectations.json`: analyst-labeled expected step outputs for each manifest bill
- `research_fixtures/`: replayable research fixtures for selected golden bills

## Validation

### Manifest Validation

Run:

```bash
python backend/scripts/verification/validate_golden_bill_corpus_manifest.py
```

The validator enforces:
- required bill fields
- record uniqueness (`bill_id`)
- corpus size target (`10-16`)
- mode/control quotas or explicit `gap_notes`

### Research Fixtures Validation

Run:

```bash
python backend/scripts/verification/validate_research_fixtures.py
```

The validator enforces:
- fixture schema compliance
- fixture-to-manifest coverage
- fixture-set scope stays a bootstrap control subset rather than a frozen corpus
- required fields for scraped text, RAG chunks, web sources
- explicit provenance rules and synthetic-fixture guardrails

### Step Expectations Validation

Run:

```bash
python backend/scripts/verification/validate_golden_bill_step_expectations.py
```

The validator enforces:
- one expectation record per manifest bill
- required machine-readable step expectations (`impact_discovery`, `mode_selection`, `parameter_resolution`, `sufficiency_gate`)
- mode-to-parameter contract alignment
- control bill fail-closed expectations
- fixture-scope-aware expectation labeling (`strong` vs `provisional_bootstrap`)
- provisional bootstrap placeholder semantics for manifest-only bills (no checked-in fixture): `expected_impact_count.exact=0`, `selected_mode=qualitative_only`, empty parameter expectations, and `sufficiency_gate` fail-closed (`research_incomplete` + `impact_discovery_failed`)

### Golden Suite Harness

Run:

```bash
python backend/scripts/verification/run_golden_suite.py
```

The harness orchestrates the manifest, fixture, step-expectation, retrieval-quality, and web/no-web comparison surfaces and emits one machine-readable suite report under `backend/scripts/verification/artifacts/`.

## Research Fixtures

The checked-in fixture subset is intentionally narrower than the full manifest:
- synthetic fixtures are reserved for explicit fail-closed/adversarial controls
- positive quantitative bills stay manifest-only until live captures are available
- `research_fixture_set_metadata.json` is the machine-readable source of truth for that narrower scope

See `research_fixtures/README.md` for the fixture storage contract, provenance rules, and replay limitations.
