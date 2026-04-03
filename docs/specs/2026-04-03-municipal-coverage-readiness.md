# Municipal Coverage Readiness

Date: 2026-04-03
Beads: `bd-pd1s`

## Verdict

The municipal/county substrate expansion lane is ready for repeated bounded manual operator use.

That verdict is based on:

- the broad Pack A campaign run (`manual-substrate-20260403T041421Z-831ef130`)
- direct inspection of raw outputs and inspection artifacts
- repair of the two actual substrate defects found in the run path

The only incomplete follow-up in this pass is a fresh post-fix broad rerun, which was attempted but blocked by a transient Railway CLI rate-limit response rather than a product/runtime defect.

## Reliable Now

- branch-local manual substrate campaigns against Railway dev context
- handler-aware document targeting for:
  - San Jose Legistar
  - Santa Clara County Legistar
  - Saratoga AgendaCenter
  - Sunnyvale Legistar meeting/detail lanes
- truthful preservation and promotion of official substantive PDFs
- truthful storage integrity reporting for bounded municipal sweeps

## Repaired In `bd-pd1s`

1. `upsert_source()` no longer fails on dict/list metadata.
2. same-URL multi-asset source roots no longer collapse into one row purely because they share a URL.
3. Sunnyvale agenda target selection no longer accepts the known non-Legistar 403 page as the winning candidate.

## Still Sparse

These are coverage gaps, not framework failures:

- many `attachments` and `staff_reports` lanes
- municipal code outside current Pack A seeds
- county-specific asset classes without source inventory yet
- vector integrity checks for this run, because the broad campaign remained `capture_only`

## Operator Guidance

- keep campaigns bounded
- prefer Pack A jurisdictions first
- use `capture_only` when validating breadth
- use failure buckets to decide where new inventory or adapter work is worth doing next

## Next Logical Expansion

1. widen Pack A municipal inventory where the failure bucket is `no_matching_sources`
2. rerun with one capture-and-ingest municipal sweep after breadth is stable
3. only then consider a larger jurisdiction pack
