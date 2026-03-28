# Golden Bill Corpus Fixture Contract

This directory contains the `bd-bkco.1` curated corpus manifest and `bd-bkco.2` replayable research fixtures used by downstream golden-suite tasks.

## Files

- `golden_bill_corpus_manifest.json`: canonical machine-readable bill corpus
- `research_fixtures/`: replayable research fixtures for each golden bill

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
- required fields for scraped text, RAG chunks, web sources

## Research Fixtures

See `research_fixtures/README.md` for the fixture storage contract and replay mechanism.
