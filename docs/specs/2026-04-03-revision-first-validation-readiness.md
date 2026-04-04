# Revision-First Validation Readiness

Date: 2026-04-03
Beads subtask: `bd-e12k`

## Verdict

Revision-first substrate hardening is ready for the next bounded campaign wave.

The current implementation now proves the three moat-critical behaviors we wanted:

1. unchanged recapture does not create a new revision row
2. amended content creates a new linked revision row
3. unchanged content can reuse existing retrievable ingestion state without re-embedding

## Evidence

### Capture-path evidence

From the `bd-rqup` validation coverage:

- unchanged recapture reuses the existing row and increments recency instead of inserting a duplicate revision
- changed content creates a new row with:
  - `previous_raw_scrape_id`
  - incremented `revision_number`

Covered in:

- `backend/tests/test_manual_capture_substrate.py`

### Ingestion-path evidence

From the `bd-g49i` validation coverage:

- a retrievable identical prior revision can be reused directly during ingestion
- an already retrievable row short-circuits reprocessing
- the ingestion truth payload records reuse provenance

Covered in:

- `backend/tests/test_ingestion_service.py`

### Operator-visibility evidence

From the `bd-gaae` lineage visibility slice:

- substrate admin payloads and inspection reports now expose:
  - `canonical_document_key`
  - `previous_raw_scrape_id`
  - `revision_number`
  - `last_seen_at`
  - `seen_count`

Published separately in:

- PR #388 (`bd-gaae`)

## Validation Runbook

Focused checks for this readiness pass:

```bash
cd backend && pytest -q tests/test_ingestion_service.py
cd backend && pytest -q tests/test_manual_capture_substrate.py
git diff --check
```

## Remaining Risk

The revision model is now good enough for the next bounded campaign, but two follow-ons still remain outside this readiness note:

- dedicated capture-event ledger is still deferred
- richer UI presentation of revision lineage can remain post-MVP

Those are not blockers for the next manual campaign.

## Readiness Decision

`ALL_IN_NOW` for the next bounded post-hardening validation wave, assuming the dependent stacked PRs are merged in order.
