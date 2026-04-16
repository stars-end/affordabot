# Manual Audit Cycle 25: Data Moat

Feature-Key: bd-3wefe.13

## Audited Artifacts

- `docs/poc/policy-evidence-quality-spine/artifacts/live_cycle_25_windmill_domain_run.json`
- `docs/poc/policy-evidence-quality-spine/artifacts/live_cycle_25_admin_analysis_status.json`

## Gate A Result

Status: PASS_FOR_NARROW_VERTICAL_WITH_REVIEWER_CAVEATS.

Cycle 25 reran the San Jose Commercial Linkage Fee vertical after source-quality metrics were implemented and deployed.

The live package now proves:

- Windmill executed the six-step backend flow.
- Backend selected an official artifact-grade Legistar attachment.
- Source-quality metrics were persisted into the package and surfaced by the admin endpoint.
- Scraped/search gate passed for selected-artifact quality, but the original Cycle 25 artifact labeled the provider from a hardcoded `private_searxng` value. Follow-up code now derives provider provenance from the active search client and records runtime provider metadata.
- Structured evidence was unified with scraped evidence in the same package.
- Secondary search-derived evidence rescued numeric fee parameters in the captured Cycle 25 run.
- Canonical LLM binding passed for the package.

## Selected Artifact Quality

Admin read model:

- selected_candidate_url: `https://sanjose.legistar.com/View.ashx?M=F&ID=8758120&GUID=6C299331-91E9-48ED-B7A5-43601D63FBF6`
- selected_artifact_family: `artifact`
- selected_candidate_rank: `1`
- top_n_window: `5`
- top_n_official_recall_count: `3`
- top_n_artifact_recall_count: `1`
- reader_substance_observed: `true`
- selection_quality_status: `pass`

Manual judgment: this is the strongest scraped-data result in the San Jose CLF loop. It selected the official fee schedule attachment instead of the portal/public landing page.

Reviewer correction: the selected artifact was high quality, but the original package builder incorrectly let economic fail-closed reasons degrade the inner `reader_substance` gate. Follow-up code separates reader-source readiness from economic sufficiency so a good reader artifact is not marked failed merely because household-impact analysis still needs secondary research.

## Structured + Secondary Evidence

The package contains:

- scraped official Legistar attachment evidence,
- structured Legistar Web API metadata, which was mechanically live but economically shallow for this run (`event_attachment_hint_count=0` and no fee values),
- Tavily secondary search-derived evidence from an official San Jose news page.

The secondary search lane extracted two source-bound fee parameters:

- `$3.00` per square foot,
- `$3.58` per square foot.

Manual judgment: this is enough to prove the unified scraped + structured package path for the narrow CLF vertical. It is still not broad moat proof across source families or jurisdictions.

Reviewer correction: the captured Cycle 25 parameter table was almost entirely rescued by the Tavily secondary search-derived lane. The primary Legistar text was summarized by the LLM but did not emit parameter cards in the captured run. Follow-up code now extracts source-bound fee parameter facts from the primary analysis chunks and flags malformed currency strings such as `$18.706.00`.

## Remaining Gate A Limits

- The harness DB/storage probe still reports local DNS limitations for direct DB probing, so the storage/read-back `pass` claims are based on the successful admin read model retrieval and prior MinIO probes proving the storage path.
- The live-run markdown bakeoff used a public SearXNG instance that failed separately from the product path. The product path used the configured backend search client; follow-up code records the actual client class/configured provider/endpoint host so future artifacts can prove this directly.
- CKAN/San Jose Open Data was cataloged but not proven in this run. Follow-up code marks unavailable catalog entries as `cataloged_unavailable` with `live_proven=false`.
- Provider metrics are present for the fresh package, but broader search-quality breadth is still required before claiming production recall.
- The source-quality gate is now useful: old packages show `source_quality_metrics_missing`, fresh packages show selected-artifact quality explicitly.
