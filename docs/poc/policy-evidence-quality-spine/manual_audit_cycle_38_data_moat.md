# Manual Audit: Cycle 38 Data Moat

Feature-Key: `bd-3wefe.13`

Artifacts:
- `artifacts/live_cycle_38_windmill_domain_run.json`
- `artifacts/live_cycle_38_policy_package_payload.json`
- `artifacts/live_cycle_38_admin_analysis_status.json`
- `live_cycle_38_windmill_domain_run.md`

Runtime identity:
- Package: `pkg-af204fc661686d86332a8a88`
- Backend run: `e70b69c0-a50a-4182-8991-0e681d50c46a`
- Windmill run: `bd-3wefe.13-live-cycle-38-20260417050653`
- Windmill job: `019d99d5-df4f-1354-fcea-af9c129b6e49`

## Verdict

`EVIDENCE_READY_WITH_GAPS__REAL_CLF_PACKAGE_BUT_ROW_QUALITY_NOT_CLEAN`

Cycle 38 is the first cycle that materially resembles the product data moat. It found the correct San Jose Commercial Linkage Fee matter, selected an official Legistar artifact, ingested official attachments, persisted the package, and exposed it through the admin read model.

It is not a clean data-moat pass yet. Row-level audit found weak attachment-derived rows that should not be promoted into economic-ready parameter cards.

## What Passed

- Selected source is official, artifact-grade Legistar:
  - `https://sanjose.legistar.com/View.ashx?M=F&ID=8758120&GUID=6C299331-91E9-48ED-B7A5-43601D63FBF6`
- Structured Legistar enrichment found the correct Matter:
  - Matter `7526`
  - `Council Policy Priority # 5: Commercial Linkage Impact Fee.`
- Private SearXNG product path was proven:
  - configured provider: `searxng`
  - client class: `OssSearxngWebSearchClient`
  - endpoint host: `searxng-private.railway.internal:8080`
- Candidate ranking improved:
  - selected candidate rank: `1`
  - selected artifact family: `artifact`
  - top-5 official recall count: `5`
  - top-5 artifact recall count: `2`
- Attachment ingestion improved:
  - related attachment refs: `19`
  - attachment probes: `6`
  - readable official PDFs: `5`
  - malformed PDF handled as `attachment_pdf_parse_failed`, not backend 500
- Storage/admin proof passed:
  - Postgres source-of-truth row present
  - MinIO package artifact present
  - MinIO reader artifact present
  - pgvector derived index present
  - admin analysis-status endpoint returned HTTP 200
- The economic gate correctly refused household cost-of-living analysis:
  - direct project-fee exposure: analysis-ready
  - household incidence/pass-through: not proven
  - final verdict: `not_decision_grade`

## Manually Verified Good Rows

The primary official resolution artifact produced plausible CLF fee table rows with land-use and threshold context:

- Office `<100,000 sq. ft.`: `$3.00/sq ft`
- Retail `>=100,000 sq. ft.`: `$3.00/sq ft`
- Retail `<100,000 sq. ft.`: `$0`
- Hotel: `$5.00/sq ft`
- Industrial/R&D `>=100,000 sq. ft.`: `$3.00/sq ft`
- Industrial/R&D `<100,000 sq. ft.`: `$0`
- Downtown office `>=100,000 sq. ft.`: `$10.00/sq ft`
- Rest-of-city office `>=100,000 sq. ft.`: `$5.00/sq ft`
- Warehouse: `$5.00/sq ft`

These rows are source-bound to the official Legistar artifact and include table-row locators such as `analysis_chunk:10:fee_table_row`.

## What Still Failed

Attachment-derived rows are still too permissive. The supplemental memorandum for residential care correctly contains:

- Residential Care: `$6 per square foot`

But the same attachment also produced false/weak rows:

- `$600`
- `$52.30`

Those values came from contextual discussion, not CLF fee-rate table rows. They must not become `usd_per_square_foot` parameter cards.

Other weak signals:

- Several attachment rows have `locator_quality=chunk_locator_only`.
- Some attachment rows have `land_use=unknown`.
- `missing_true_structured_corroboration_count=15`.
- `fail_closed_locator_signal_count=11`.
- Admin status says `official_attachment_depth_ready=true`, but this is too coarse while weak attachment rows are present.

## Manual Data Assessment

Cycle 38 proves the architecture can now build a real San Jose CLF data package. This is a significant product step beyond prior cycles.

The product moat is not proven cleanly until row-quality enforcement is stricter. A moat-grade package should prefer fewer accurate rows over many mixed-quality rows. The primary scraped resolution rows look useful for direct project-fee exposure, but attachment-derived rows need stronger line/table provenance before they can be treated as authoritative structured data.

The economic-analysis handoff behavior is correct: the system can support direct project-fee exposure, but blocks household cost-of-living conclusions until secondary research provides pass-through/incidence assumptions.

## Required Next Wave

1. Make attachment extraction line/table-aware so contextual dollar values do not ride along with a nearby per-square-foot phrase.
2. Filter weak attachment facts before parameter-card creation.
3. Tighten official attachment depth to distinguish:
   - authoritative table-row attachment facts;
   - context-only attachment facts;
   - rejected false/ambiguous facts.
4. Surface row-quality gaps explicitly in the admin read model.
5. Rerun live cycle and manually verify that:
   - `$600` and `$52.30` are gone;
   - `$6/sq ft` Residential Care remains;
   - primary resolution table rows remain;
   - economic handoff remains direct-project-fee-ready but household-incidence-blocked.

## Stop Condition For This Vertical

The next pass must exceed Cycle 38 by producing a cleaner package, not merely the same package with a pass label. A high-quality data moat package should have source-bound CLF rows with row/table provenance and no known false fee-rate rows.
