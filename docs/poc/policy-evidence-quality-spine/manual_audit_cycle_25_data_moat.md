# Manual Audit Cycle 25: Data Moat

Feature-Key: bd-3wefe.13

## Audited Artifacts

- `docs/poc/policy-evidence-quality-spine/artifacts/live_cycle_25_windmill_domain_run.json`
- `docs/poc/policy-evidence-quality-spine/artifacts/live_cycle_25_admin_analysis_status.json`

## Gate A Result

Status: PASS_FOR_NARROW_VERTICAL.

Cycle 25 reran the San Jose Commercial Linkage Fee vertical after source-quality metrics were implemented and deployed.

The live package now proves:

- Windmill executed the six-step backend flow without interruption.
- The `private_searxng` provider successfully bypassed the public SearXNG HTTP 429 block, locating the official PDF fee schedule attachment.
- Source-quality metrics correctly observed and materialized the raw scrape content, overriding stale test claims that it hit navigation/menu content.
- However, the LLM analysis of the primary PDF **failed to extract numeric parameters** into structured cards, despite accurately summarizing the fee rates in plain text.
- Additionally, the Legistar Web API structured endpoint retrieved event metadata but yielded **zero actual economic parameters** (no attachments found).
- The entire economic parameterization was **rescued exclusively** by the Tavily secondary search, which mapped press-release snippets to required structured fee values.

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

The package contains three distinct sources, but exposes significant depth limitations:

1. **Scraped Official Document (SearXNG)**: Successfully captured and summarized, but failed to yield structured parameter cards.
2. **Structured Metadata (Legistar Web API)**: Successfully called, but failed to surface actual attachments or economic data, yielding only diagnostic facts (e.g. `event_attachment_hint_count: 0`).
3. **Secondary Search (Tavily)**: Completely rescued the parameter ingestion phase, extracting the only two source-bound fee parameters (`$3.00` and `$3.58` per square foot).

Manual judgment: The data moat successfully unifies the sources physically, but the semantic depth is brittle. The primary pipeline failed to parameterize the principal document and the structured API lacked the required depth. Without the secondary search rescue strategy, the entire parameter extraction phase would have failed. This proves the *value* of the moat (unification), but highlights a critical vulnerability in primary document parameterization depth.

## Remaining Gate A Limits

- The harness DB/storage probe still reports local DNS limitations for direct DB probing, so the storage/read-back `pass` claims are based on the successful admin read model retrieval and prior MinIO probes proving the storage path.
- Provider metrics are now present for the fresh package, but broader search-quality breadth is still required before claiming production recall.
- The source-quality gate is now useful: old packages show `source_quality_metrics_missing`, fresh packages show selected-artifact quality explicitly.
