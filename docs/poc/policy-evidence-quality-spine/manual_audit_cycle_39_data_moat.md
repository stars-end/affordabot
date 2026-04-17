# Cycle 39 Manual Data-Moat Audit

Feature-Key: bd-3wefe.13

Run artifact: `docs/poc/policy-evidence-quality-spine/artifacts/live_cycle_39_windmill_domain_run.json`
Package payload: `docs/poc/policy-evidence-quality-spine/artifacts/live_cycle_39_policy_package_payload.json`
Admin read model: `docs/poc/policy-evidence-quality-spine/artifacts/live_cycle_39_admin_analysis_status.json`

## Verdict

`FAIL_DATA_MOAT__CONSTRUCTION_COST_ASSUMPTION_STILL_PROMOTED_AS_FEE_RATE`

Cycle 39 made real progress versus Cycle 38, but it still does not meet the decision-grade data-moat gate. The package selected the correct San Jose CLF artifact and unified scraped plus structured attachment evidence, but one structured attachment row still promoted a construction-cost assumption as a `commercial_linkage_fee_rate_usd_per_sqft` parameter.

## What Improved

- Private SearXNG was actually exercised through the product path: admin `provider_summary.runtime.client_class=OssSearxngWebSearchClient`, `configured_provider=searxng`, `endpoint_host=searxng-private.railway.internal:8080`.
- Source selection picked the official Legistar artifact: `https://sanjose.legistar.com/View.ashx?M=F&ID=8758120&GUID=6C299331-91E9-48ED-B7A5-43601D63FBF6`.
- Structured attachment ingestion found Matter 7526, 19 attachment refs, 6 probes, 5 readable official PDFs, and 3 attachment-derived economic rows.
- Cycle 38's `$52.30` false row no longer appears in package parameter cards.
- Storage/admin retrieval worked for package `pkg-128c5ae51e85bc28bc94cebc` and run `e6fc63f3-fcae-4fd1-82c6-578af032c379`.

## What Failed

- The package still contains a false resolved parameter card:
  - value: `600`
  - unit: `usd_per_square_foot`
  - source excerpt: `cost of development for residential care on a per square foot basis (assuming $600 per square foot...)`
  - source URL: `https://legistar.granicus.com/sanjose/attachments/eb98bc80-6c09-4b45-ba75-db970576e5f3.pdf`
- That row is not a CLF fee rate. It is a construction/development-cost assumption used in a memorandum discussion.
- Admin correctly reports `row_quality_gate_status=fail`, `row_quality_gap=true`, `economic_handoff_blocked_by=row_quality`, and `recommended_next_action=reject`, but the false row should not be emitted as a resolved parameter in the first place.

## Economic Handoff

The direct project-fee path is close, but the data moat is not clean enough to trust. The backend reports `can_quantify_now=["direct_project_fee_exposure"]`, but the final handoff remains blocked by row quality and missing household incidence assumptions. That is the right fail-closed behavior.

## Required Next Change

Cycle 40 must make a substantive product-quality change:

- Filter construction/development/rent assumption contexts from attachment fee extraction.
- Add domain plausibility for `commercial_linkage_fee_rate_usd_per_sqft` so implausible high-dollar construction-cost rows cannot pass as CLF fee rows.
- Enforce that plausibility at extractor, package-builder, and bridge/reconciliation layers, not only in audit docs.

