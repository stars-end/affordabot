# Cycle 30 Manual Audit: Data Moat

Feature-Key: bd-3wefe.13
Final live artifact: `artifacts/live_cycle_30i_windmill_domain_run.json`
Final status: `evidence_ready_with_gaps`

## Verdict

Cycle 30 materially improved the San Jose Commercial Linkage Fee data package, but it did not reach `decision_grade_data_moat`.

The final package is a real, persisted, unified scraped + structured package. It is not just orchestration scaffolding. It exercised Windmill, Railway dev backend, private SearXNG, Postgres, MinIO references, pgvector indexing, Legistar Web API metadata, Tavily secondary search, and the package builder.

The package still fails the data moat gate because the structured lane is not economically deep enough. Legistar Web API resolves the correct matter and attachment count, but it does not itself contribute structured fee rows, nexus-study parameters, methodology, or cost-impact inputs. The authoritative fee parameters come from the scraped Legistar artifact, not from a true structured source.

## What Passed

Runtime spine:

- Windmill job `019d97ee-4a45-5db5-92ac-38c281071b8e` completed successfully.
- Step sequence matched the expected domain path: `search_materialize`, `freshness_gate`, `read_fetch`, `index`, `analyze`, `summarize_run`.
- Idempotent rerun passed.
- Stale-but-usable drill passed.
- Stale-blocked drill passed.

Storage spine:

- Postgres product rows: passed.
- MinIO object references: passed.
- Reader output reference: passed.
- pgvector index probe: passed, with `9584` document chunks and `9584` chunks with embeddings.
- Analysis provenance chain: passed.

Private SearXNG product path:

- Runtime provider label is now derived from the active client, not hardcoded.
- Runtime client class: `OssSearxngWebSearchClient`.
- Configured provider: `searxng`.
- Endpoint host: `searxng-private.railway.internal:8080`.
- Selected candidate was an official artifact at rank 1: `https://sanjose.legistar.com/View.ashx?M=F&ID=8758120&GUID=6C299331-91E9-48ED-B7A5-43601D63FBF6`.
- Top-5 official recall count: `3`.
- Top-5 artifact recall count: `1`.

Scraped artifact quality:

- Evidence card `ev-1` is tier A, source type `ordinance_text`, and cites the official Legistar PDF.
- Reader substance passed.
- Primary parameter extraction now emits source-bound fee rows from the official artifact rather than relying entirely on Tavily.
- Final package contains 11 primary-source parameter cards from `ev-1`, including office, retail, hotel, industrial/R&D, warehouse, and an ambiguous residential-care row.

Structured lane:

- Evidence card `ev-2` resolves San Jose Legistar Matter `7526`.
- Structured source family: `legistar_web_api`.
- Access method: `public_api_json`.
- Matter title: `Council Policy Priority # 5: Commercial Linkage Impact Fee.`
- Attachment count: `19`.
- Policy match confidence: `0.95`.
- This is true structured metadata, not scraped text.

Secondary lane:

- Tavily evidence is explicitly tier C and marked `secondary_search_derived_not_authoritative`.
- Tavily no longer carries the same trust as true structured primary sources.
- Secondary override is blocked by the source-of-truth policy: primary artifact precedence over secondary evidence.

## What Did Not Pass

Structured economic depth:

- The true structured source does not provide fee table rows, economic parameters, nexus-study methodology, or impact assumptions.
- The Legistar Web API path currently proves matter identity and attachment presence, not economic content extraction.
- The package does not yet ingest the 19 Legistar attachments as structured/related artifacts in the same package.

Lineage completeness:

- `authoritative_policy_text`: present.
- `meeting_context`: present.
- `staff_fiscal_context`: present.
- `related_attachments`: missing.
- Lineage completeness score: `0.75`.

Parameter reliability:

- The primary artifact fee table is now parsed into rows, but the residential-care value remains ambiguous because the source text appears as `$18.706.00`.
- The package correctly keeps that row ambiguous instead of normalizing it into a false number.
- Some extracted rows still lack richer scope metadata such as subarea, threshold, applicability date, and fee-resolution finality.

Gate result:

- `economic_handoff_ready`: `false`.
- `gate_report.verdict`: `fail_closed`.
- `blocking_gate`: `parameterization`.
- Failure codes: `parameter_missing`, `parameter_unverifiable`.

## Cycle Improvements

Cycle 30b proved live storage and runtime mechanics but had shallow structured evidence.

Cycle 30c proved a broad query can still select the wrong source shape, so broad discovery alone is insufficient.

Cycle 30d proved explicit CLF queries helped, but external sources could still outrank official sources.

Cycle 30e fixed official-source ranking and selected an official San Jose CLF page, but primary parameters still relied too much on secondary search.

Cycle 30f added reader-content fee extraction and produced source-bound primary fee rows.

Cycle 30g tightened fee extraction to avoid obvious non-fee dollar false positives.

Cycle 30h selected the official Legistar PDF artifact and proved private SearXNG artifact recall, but exposed row-fragmentation and local private-DNS storage-probe limits.

Cycle 30i used the deployed row extractor plus public DB probe and produced the final honest artifact: runtime/storage pass, official artifact pass, structured metadata pass, data moat still not decision-grade.

## Final Data Moat Decision

Status: `evidence_ready_with_gaps`.

The architecture can produce a durable, unified scraped + structured package for San Jose CLF. It is now credible as a product spine and much closer to the intended data moat than Cycle 25.

It is not yet a moat-quality data package because true structured economic content remains missing. To reach `decision_grade_data_moat`, the next implementation must add at least one of:

- Legistar attachment traversal that ingests the related attachment set for Matter `7526` into the same package.
- A true structured source containing fee schedule rows or nexus-study inputs.
- A structured extraction layer that converts official attachment tables into normalized rows with subarea, land-use, threshold, amount, unit, effective date, and citation.
