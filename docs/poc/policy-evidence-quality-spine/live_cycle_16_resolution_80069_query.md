# Live Cycle 16: Resolution 80069 Query

Feature-Key: bd-3wefe.13

## Purpose

Cycle 16 tested whether explicitly naming `Resolution 80069` would force the live pipeline to select the rate-resolution artifact.

Query:

`RES80069 Commercial Linkage Fee San Jose fee per square foot`

## Evidence Artifacts

- `docs/poc/policy-evidence-quality-spine/artifacts/live_cycle_16_windmill_domain_run.json`
- `docs/poc/policy-evidence-quality-spine/live_cycle_16_windmill_domain_run.md`

## Result

The run again selected the official base CLF page:

`https://www.sanjoseca.gov/your-government/departments-offices/housing/developers/commercial-linkage-fee`

The LLM analysis correctly reported:

- affected projects are new/existing non-residential projects adding floor area or changing use
- fees are adjusted by ENR Construction Cost Index
- annual adjustments begin July 1
- specific dollar rates are still missing
- secondary research is needed for Resolution 80069 and household pass-through assumptions

## Candidate Evidence

The live search result universe contained possible follow-on artifacts:

- `https://records.sanjoseca.gov/Resolutions/RES80069.pdf`
- `https://www.sanjoseca.gov/home/showpublisheddocument/62335/637320438859400000`

Direct Z.ai reader probing showed:

- `RES80069.pdf`: reader returned transient `500`
- `showpublisheddocument/62335`: reader returned transient `500`
- `showpublisheddocument/61766`: reader succeeded but was a status memo, not the rate table

## Learning

The blocker is now precise:

- SearXNG can surface relevant official/rate-adjacent artifacts.
- Z.ai reader can miss dynamic table rows on the official page and can fail on some official PDF/document endpoints.
- The pipeline needs a governed secondary evidence lane and likely multi-artifact package assembly.

## Gate Delta

- D2 scraped evidence: no pass improvement beyond Cycle 14.
- D4 package completeness: still blocked by single primary artifact.
- E2/E5 economic quality: still correctly fail-closed due missing fee-rate parameters.

## Decision

Continue. Cycle 17 should add provider-snippet-backed structured evidence from a governed fallback source, then the architecture should decide whether to promote this into multi-artifact package assembly.
