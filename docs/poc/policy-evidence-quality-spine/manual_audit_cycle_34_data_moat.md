# Manual Audit: Cycle 34 Data Moat

Feature-Key: `bd-3wefe.13`

Artifacts:
- `artifacts/live_cycle_34_windmill_domain_run.json`
- `artifacts/live_cycle_34_admin_analysis_status.json`
- `artifacts/live_cycle_34_policy_package_payload.json`

Runtime identity:
- Package: `pkg-56135a398200c78dcdb4a5ce`
- Backend run: `71c3dcc9-39de-4462-8fa0-dd1b5c35b63a`
- Windmill run: `bd-3wefe.13-live-cycle-34-20260417041200`
- Windmill job: `019d99a2-f688-57e4-bbca-5241a52ecb41`

## Verdict

`FAIL_DATA_MOAT__ATTACHMENT_ROW_DEPTH_STILL_ZERO`

Cycle 34 verified that the new row-family gate semantics are working, but the live package still does not satisfy the data moat objective. The runtime spine is healthy and the selected source is in the correct San Jose policy family. The package still lacks decision-grade official data depth.

This is a product-quality failure, not an infra failure.

## What Passed

- Windmill orchestration completed the expected six-step sequence:
  - `search_materialize`
  - `freshness_gate`
  - `read_fetch`
  - `index`
  - `analyze`
  - `summarize_run`
- Admin read model reports:
  - storage/read-back: `pass`
  - Windmill/orchestration: `pass`
  - LLM narrative: `pass`
- Provider provenance is now runtime-derived:
  - configured provider: `searxng`
  - client class: `OssSearxngWebSearchClient`
  - endpoint host: `searxng-private.railway.internal:8080`
- Policy identity and jurisdiction identity pass:
  - `identity_ready=true`
  - `policy_identity_ready=true`
  - `jurisdiction_identity_ready=true`
- The package contains 20 related Legistar attachment refs for Matter 7526, including memorandum, ordinance, resolution, and public-letter PDFs.

## What Failed

- Data moat status: `fail`.
- Scraped/search gate: `fail`.
- Selected artifact family: `official_page`.
- Source quality status: `fail`.
- Structured depth readiness: `false`.
- Economic handoff readiness: `false`.
- True structured economic rows: `0`.
- Official attachment economic rows: `0`.
- Official attachment authoritative rows: `0`.
- Secondary search rows: `1`.

The only normalized economic row remains Tavily secondary-search-derived:

- field: `commercial_linkage_fee_rate_usd_per_sqft`
- value: `3.58`
- source: San Jose Commercial Linkage Fee page via Tavily secondary search
- status: `secondary_only_not_authoritative`
- fail-closed signals:
  - `locator_precision_insufficient_for_artifact_grade`
  - `missing_source_locator_requires_manual_trace`

## Manual Data Assessment

Cycle 34 proves that the architecture can preserve and expose a correct failure. It does not prove that Affordabot has a data moat for this vertical yet.

The official Legistar lineage is present as attachment references, but the content was not ingested. The attachment probes skipped the high-value Matter 7526 PDFs as `skipped_non_official_attachment`, including:

- `Memorandum`
- `Memorandum from Peralez, 8/28/2020`
- `Memorandum from Jimenez, 8/28/2020`
- `Memorandum from Mayor, Jones, Diep, Davis & Foley, 8/28/2020`
- `Supplemental Memorandum`

That skip classification is too conservative for the data moat goal. San Jose Legistar attachment PDFs hosted at `legistar.granicus.com/sanjose/attachments/...` are official policy lineage artifacts for this Matter. They must be fetchable/readable, classified by source family, and mined for row-level economic facts before the package can claim source depth.

The generated Windmill summary says the backend bridge surface is ready. That is true for mechanics, but insufficient for product readiness. The authoritative product verdict is this manual audit plus the admin read model: identity is repaired, but official attachment depth is still missing.

## Required Next Wave

1. Treat San Jose Legistar attachment PDFs as official artifacts when they are tied to a verified San Jose Matter/Event lineage.
2. Fetch and parse official attachment PDFs instead of skipping them as `non_official_attachment`.
3. Prefer high-value source families for ingestion:
   - ordinance
   - resolution
   - staff memorandum
   - nexus/feasibility study
   - fee schedule
4. Extract row-level economic facts with direct provenance:
   - attachment id
   - attachment title
   - attachment URL
   - page or chunk locator
   - raw quote/excerpt
   - raw value
   - normalized value
   - unit
   - land use/category
   - threshold
   - payment timing
   - effective/adoption/final status
5. Keep Tavily/Exa rows secondary and non-authoritative unless corroborated by official attachment or true structured rows.
6. Do not mark `structured_depth_ready=true` until at least one true structured row or authoritative official attachment row is available.

## Stop Condition For This Vertical

The next data moat pass requires more than runtime success. It requires at least one authoritative official attachment row or true structured row, manually audited against the source artifact, before any economic handoff can be considered product-grade.
