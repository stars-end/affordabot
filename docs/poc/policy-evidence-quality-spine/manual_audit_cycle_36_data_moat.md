# Manual Audit: Cycle 36 Data Moat

Feature-Key: `bd-3wefe.13`

Artifacts:
- `artifacts/live_cycle_36_windmill_domain_run.json`
- `artifacts/live_cycle_36_policy_package_payload.json`
- `live_cycle_36_windmill_domain_run.md`

Runtime identity:
- Package: `pkg-560d7455fa43b21376e8479e`
- Backend run: `c9e7a12a-6098-4237-b102-11b1ba54c7e3`
- Windmill run: `bd-3wefe.13-live-cycle-36-20260417045457`
- Windmill job: `019d99ca-f5ee-0ff7-cc6b-3560d0a651ee`

## Verdict

`FAIL_DATA_MOAT__EXTRACTION_FAILS_CLOSED_BUT_DISCOVERY_DRIFTED_TO_WRONG_POLICY`

Cycle 36 is a partial improvement over Cycle 35. The new extraction guard prevented false `usd_per_square_foot` fee rows from annual-report-like content. That is the correct accuracy direction.

The data moat still failed because discovery selected the wrong source path and policy family:

- selected scraped source: `https://www.legigram.com/places/san-jose`
- selected artifact family: external page
- structured Legistar matter: `15773`
- matter title: `Providing Access and Transforming Health Capacity and Infrastructure Transition, Expansion, and Development Intergovernmental Transfer Grant Funding for California Advancing and Innovating Medi-Cal Readiness and Implementation.`

That matter is not Commercial Linkage Fee policy evidence.

## What Passed

- Windmill orchestration completed the expected six-step sequence.
- Private SearXNG runtime provenance was present:
  - configured provider: `searxng`
  - client class: `OssSearxngWebSearchClient`
  - endpoint host: `searxng-private.railway.internal:8080`
- The attachment probe ingested official San Jose Legistar PDFs:
  - `attachment_ref_count=2`
  - `attachment_probe_count=2`
  - `attachment_ingested_count=2`
  - `content_ingested=true`
- The Cycle 35 false-row failure was fixed in this run:
  - `attachment_economic_row_count=0`
  - `true_structured_row_count=0`
  - `official_attachment_row_count=0`
  - `parameter_cards=0`

Zero rows is the correct result for the wrong policy material. It is better than emitting false economic parameters.

## What Failed

- Data moat status: `fail`.
- The search query in the live gate was still the generic historical query:
  - `San Jose CA city council meeting minutes housing`
- Private SearXNG top result was an external aggregator:
  - `https://www.legigram.com/places/san-jose`
- The reader selected the external page because the query was not economic-policy-specific and candidate scoring rewarded generic meeting/agenda/housing tokens.
- Structured enrichment then followed unrelated San Jose meeting context to Matter `15773`, a Medi-Cal grant funding matter.
- Source quality metrics correctly showed:
  - `selected_artifact_family=external_page`
  - `selection_quality_status=fail`
  - `artifact_candidate_count=0`
  - `top_n_artifact_recall_count=0`

## Manual Data Assessment

Cycle 36 proves the extraction guard is moving in the right direction, but it also proves the data moat cannot depend on a generic meeting-minutes query. Accurate row extraction is irrelevant if the upstream discovery step points at the wrong policy.

For this vertical, the live gate must search for the San Jose Commercial Linkage Fee itself, not generic San Jose housing meeting minutes. A data-moat cycle should target adoption actions, ordinances, resolutions, staff memoranda, nexus studies, and fee schedules. Meeting minutes are lineage context, not the primary retrieval objective.

The generated package is useful as a failure artifact because it demonstrates fail-closed behavior: wrong policy plus no local fee table produced no economic rows. It is not useful as a positive moat artifact.

## Required Next Wave

1. Make the San Jose CLF live gate use a CLF-specific canonical query and analysis question.
2. Penalize external aggregator pages for economic-policy runs unless they point to authoritative official artifacts.
3. Prefer official adoption/rate-schedule evidence over generic meeting/agenda pages.
4. Preserve context-only official documents as evidence, but do not let them satisfy row-family depth.
5. Require the next pass to prove accurate row-level official CLF fee data or fail closed with a clear discovery-quality blocker.

## Stop Condition For This Vertical

The next live cycle must not pass merely because Windmill, storage, or LLM mechanics work. It must either:

- retrieve and package authoritative San Jose CLF rate evidence with accurate source-bound rows; or
- fail closed with `selected_source_not_policy_target` / `no_authoritative_fee_schedule_rows` style evidence.
