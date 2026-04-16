# Manual Audit Cycle 25: Data Moat

Feature-Key: bd-3wefe.13

## Audited Artifacts

- `docs/poc/policy-evidence-quality-spine/artifacts/live_cycle_25_windmill_domain_run.json`
- `docs/poc/policy-evidence-quality-spine/artifacts/live_cycle_25_admin_analysis_status.json`

## Gate A Result

Status: PASS_FOR_NARROW_VERTICAL.

Cycle 25 reran the San Jose Commercial Linkage Fee vertical after source-quality metrics were implemented and deployed.

The live package now proves:

- Windmill executed the six-step backend flow.
- Backend selected an official artifact-grade Legistar attachment.
- Source-quality metrics were persisted into the package and surfaced by the admin endpoint.
- Scraped/search gate passed for selected-artifact quality.
- Structured evidence was unified with scraped evidence in the same package.
- Secondary structured-search evidence rescued numeric fee parameters.
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

## Structured + Secondary Evidence

The package contains:

- scraped official Legistar attachment evidence,
- structured Legistar Web API metadata,
- Tavily secondary structured-search evidence from an official San Jose news page.

The secondary structured lane extracted two source-bound fee parameters:

- `$3.00` per square foot,
- `$3.58` per square foot.

Manual judgment: this is enough to prove the unified scraped + structured package path for the narrow CLF vertical. It is still not broad moat proof across source families or jurisdictions.

## Remaining Gate A Limits

- The harness DB/storage probe still reports local DNS limitations for direct DB probing, but the admin read model and prior MinIO probe have proven the storage path.
- Provider metrics are now present for the fresh package, but broader search-quality breadth is still required before claiming production recall.
- The source-quality gate is now useful: old packages show `source_quality_metrics_missing`, fresh packages show selected-artifact quality explicitly.
