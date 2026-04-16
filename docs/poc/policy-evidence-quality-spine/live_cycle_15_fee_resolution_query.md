# Live Cycle 15: Fee Resolution Query

Feature-Key: bd-3wefe.13

## Purpose

Cycle 15 tested whether a narrower fee-resolution query could find the missing San Jose Commercial Linkage Fee dollar-rate artifact without code changes.

Query:

`site:sanjoseca.gov San Jose Commercial Linkage Fee Resolution fee schedule per square foot PDF`

## Evidence Artifacts

- `docs/poc/policy-evidence-quality-spine/artifacts/live_cycle_15_windmill_domain_run.json`
- `docs/poc/policy-evidence-quality-spine/live_cycle_15_windmill_domain_run.md`

## Result

The live run succeeded mechanically but did not improve economic sufficiency.

Selected URL:

`https://www.sanjoseca.gov/your-government/departments-offices/housing/developers/commercial-linkage-fee`

The analysis completed and again found that the official page contains structure and table headers but not the specific dollar-rate rows in the reader output.

## Learning

This did not prove a new source. It reinforced two product constraints:

1. Search results include possible fee-resolution/rate artifacts, but the current single-document reader path selects the base CLF page first.
2. Z.ai reader output for the official CLF page omits the table rows that other providers can see in snippets.

## Gate Delta

- D2 scraped quality: no improvement over Cycle 14.
- D4 unified package: no improvement; still single scraped artifact plus diagnostic structured lane.
- E1/E2/E5 economic quality: no improvement; still missing source-bound fee-rate parameters.

## Decision

Continue. Query-only tuning is insufficient. The next cycle should target likely rate artifacts and provider snippets directly.
