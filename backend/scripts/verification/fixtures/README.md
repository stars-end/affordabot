# Golden Bill Corpus Fixture Contract

This directory contains the `bd-bkco.1` curated corpus manifest used by downstream golden-suite tasks.

## Files

- `golden_bill_corpus_manifest.json`: canonical machine-readable bill corpus.

## Validation

Run:

```bash
python backend/scripts/verification/validate_golden_bill_corpus_manifest.py
```

The validator enforces:
- required bill fields
- record uniqueness (`bill_id`)
- corpus size target (`10-16`)
- mode/control quotas or explicit `gap_notes`
