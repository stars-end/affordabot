# Live Cycle 17: Tavily Rate Probe

Feature-Key: bd-3wefe.13

## Purpose

Cycle 17 tested whether a controlled secondary-search provider can recover fee-rate parameters that the official-page Z.ai reader path missed.

Query:

`San Jose Commercial Linkage Fee Resolution 80069 fee per square foot`

## Evidence Artifact

- `docs/poc/policy-evidence-quality-spine/artifacts/live_cycle_17_tavily_rate_probe.json`

## Result

Tavily returned the missing rate table in the official San Jose result snippet.

The official San Jose result includes source-bound rate facts:

- Office `>=100,000 sq.ft.`: `$14.31` when paid before building permit issuance, `$17.89` at scheduling of final building inspection.
- Office `<100,000 sq.ft.`: `$0` for all square footage `<=50,000 sq.ft.`, and `$3.58` for remaining square footage.
- Retail: `$0`.
- The snippet also included older or alternate `$5.96` office values, so extraction must preserve provenance/category/effective-context rather than collapsing all rows into one parameter.

The top non-official news result included historical political compromise rates:

- `$3` per square foot after first 40,000 sq.ft.
- `$12` or `$15` for office projects over 100,000 sq.ft. depending on payment timing.

Those non-official values are useful background but should not become primary parameters without official-source confirmation.

## Learning

This cycle strongly supports using Tavily as a governed secondary-search complement, not as the primary search-of-record:

- SearXNG remains useful for open discovery and official artifact recall.
- Z.ai reader remains useful for page/PDF reading, but it missed dynamic official table rows and failed on some official PDF endpoints.
- Tavily snippets can recover structured table facts from the official page and should be stored as source-bound secondary evidence with provider provenance.

## Gate Delta

- D2 scraped/provider quality: improved by proving provider complement recovers official-source numeric facts.
- D3 structured evidence: target improvement identified; needs implementation to land snippets as structured facts.
- E1/E2 economic analysis: target improvement identified; needs implementation so fee facts enter parameter table.

## Decision

Continue with implementation:

1. Add bounded Tavily secondary evidence ingestion for missing economic parameters.
2. Extract only source-bound official San Jose fee facts.
3. Preserve provider/source provenance and mark Tavily as complement/fallback.
4. Feed extracted fee facts into the economic parameter table without producing decision-grade output until assumptions/model/uncertainty/canonical binding are also proven.
