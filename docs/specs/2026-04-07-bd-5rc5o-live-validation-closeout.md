# 2026-04-07 Live Validation Closeout (bd-5rc5o)

## Scope

Bounded live discovery validation against dev backend runtime using:

- San Jose (control city)
- Milpitas (challenging city)
- Alameda County (challenging county)

Runtime context (non-interactive Railway):

- Project: `1ed20f8a-aeb7-4de6-a02c-8851fff50d4e`
- Environment: `dev`
- Service: `backend`

## Command Run

```bash
railway run -p 1ed20f8a-aeb7-4de6-a02c-8851fff50d4e -e dev -s backend -- \
  bash -lc 'cd backend && poetry run python scripts/cron/run_discovery.py \
    --jurisdiction "San Jose" \
    --jurisdiction "Milpitas" \
    --jurisdiction "Alameda County" \
    --max-queries-per-jurisdiction 2'
```

## Live Outcome

Final run summary:

- `found=0`
- `accepted=0`
- `new=0`
- `duplicates=0`
- `rejected=0`
- `jurisdictions_processed=3`
- `jurisdiction_scope=["alameda county","milpitas","san jose"]`
- `max_queries_per_jurisdiction=2`
- classifier acceptance gate status: `passed`
- classifier trusted: `true`

Observed operational failures during candidate generation:

1. Primary `WebSearchClient` failure for every query:
   - `[zai] Search failed: [Errno 8] nodename nor servname provided, or not known`
2. Structured fallback (`services.discovery.search_discovery.SearchDiscoveryService`) returned zero URLs for tested queries.
3. Playwright DuckDuckGo fallback failed repeatedly:
   - `Page.wait_for_selector(".result__body")` timeout.

Additional non-blocking runtime issue:

- `admin_tasks` insert fails because `task_type='discovery'` violates DB check constraint (current allowed enum excludes `discovery`).

## Interpretation

This bounded live run completed but is **not operationally useful yet** for evaluating classifier gate quality on real candidates because upstream candidate generation produced zero candidates across all three jurisdictions.

The gate itself did not fail; it was never meaningfully exercised (`found=0` means no accepted/rejected/duplicate path execution).

## In-PR Non-Strategic Fixes Applied

1. Added bounded jurisdiction scope controls to discovery cron:
   - `--jurisdiction ...` (repeatable)
   - `--jurisdictions "a,b,c"` (comma-separated)
2. Added optional bounded query cap:
   - `--max-queries-per-jurisdiction <N>`
3. Added resilient search adapter in cron wiring:
   - primary `llm_common.WebSearchClient`
   - fallback to existing structured-search service when primary fails/returns empty
4. Added/updated focused tests in `backend/tests/cron/test_run_discovery.py`.

## Next Implication

Immediate next work should target candidate-generation transport reliability (primary DNS failure and fallback search extraction reliability) before any policy judgment on discovery classifier threshold strictness.
