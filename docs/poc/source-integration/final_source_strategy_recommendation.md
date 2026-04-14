# Final Source Strategy Recommendation

Date: 2026-04-14
Beads: `bd-2agbe.7`, `bd-2agbe.11`, `bd-2agbe.12`
PR: https://github.com/stars-end/affordabot/pull/436

## Decision Summary

Proceed with a **hybrid source strategy**:

1. Structured sources first when they expose policy facts or canonical linked artifact refs.
2. Private SearXNG as the primary scrape/search discovery lane for official artifacts not exposed through structured APIs.
3. Tavily as a quota-aware hot fallback when SearXNG fails source recall/ranking.
4. Exa as bakeoff/evaluation only, not default production search.
5. Backend-owned merge/dedupe/evidence contracts for both lanes before economic analysis.

This preserves the data moat while keeping the final product aligned to decision-grade cost-of-living analysis.

## a) Scraping / SearXNG Lane

Recommendation:

- Primary: `private_searxng`
- Hot fallback: `tavily`
- Eval/bakeoff only: `exa`

Evidence:

- `docs/poc/source-integration/artifacts/scrape_structured_integration_report.json`
- `docs/poc/search-source-quality-bakeoff/artifacts/search_source_quality_bakeoff_report.json`
- `docs/poc/structured-source-lane/artifacts/structured_source_breadth_audit.json`

Rationale:

- SearXNG is the cheapest broad discovery lane and can find official artifacts that structured APIs do not expose.
- Tavily should be held for recovery from SearXNG recall/ranking failures because its quota is capped.
- Exa should stay evaluation-only because it is useful for comparative search quality but too quota-constrained for broad daily source discovery.

Quality note:

Search discovery alone is not product-grade evidence. SearXNG results must pass backend ranker, portal-skip, reader-substance, artifact-classification, and evidence-card gates before economic handoff.

## b) Scraped + Structured Integration

Recommendation:

Both lanes must merge into one backend-owned artifact/evidence envelope before analysis.

Required canonical fields:

- `source_lane`
- `provider`
- `canonical_document_key`
- `jurisdiction`
- `artifact_url`
- `artifact_type`
- `source_tier`
- `content_hash`
- `retrieved_at`
- `structured_policy_facts[]`
- `linked_artifact_refs[]`
- `reader_artifact_refs[]`
- `dedupe_group`
- `selected_impact_mode`
- `mechanism_family`
- `evidence_readiness`
- `economic_handoff_ready`

Evidence:

- `docs/poc/source-integration/artifacts/scrape_structured_integration_report.json`

POC result:

- `total_envelopes`: 8
- `evidence_card_ready`: 3
- `reader_required`: 3
- `insufficient`: 2
- `economic_handoff_ready`: 3
- cross-lane dedupe group proven: `sj-13000001-program-cost`

Decision:

The integrated data is **sufficient for quantified economic handoff in a subset**, but not universally. The correct product behavior is quantified output for ready evidence and fail-closed/qualitative behavior for reader-required or insufficient evidence.

## c) Breadth Expansion

Wave 1:

- `legistar_public_api`: structured, high value, no key.
- `ca_leginfo_pubinfo_raw_files`: structured, high value, no key.
- `ca_ckan_open_data_api`: structured, medium value, no key, needs dataset curation.
- `private_searxng`: search provider, high value, no key but needs `SEARXNG_BASE_URL`.
- `granicus_civicplus_boarddocs_portals`: scrape/reader lane, high value, no key.

Wave 2:

- `arcgis_hub_rest_public`: structured mechanics proven, but policy-specific curation required.
- `opendatasoft_public_catalog_api`: API works, but local policy relevance must be mapped.
- `openstates_plural_api`: useful structured legislative metadata, requires key.
- `tavily_search_api`: fallback provider, requires key.
- `exa_search_api`: bakeoff/eval provider, requires key.

Backlog/defer:

- `socrata_open_data`: likely high value where available, but deferred because no signup is desired now.
- `official_static_csv_xlsx_raw`: contextual denominators, not primary policy artifacts.

Evidence:

- `docs/poc/source-expansion/artifacts/source_expansion_api_key_matrix.json`
- `docs/poc/source-expansion/artifacts/source_expansion_api_key_matrix.md`

## d) API Keys / Railway Variables

Required now:

- `SEARXNG_BASE_URL`

No new key is required for wave 1 structured/scrape baseline.

Optional soon:

- `OPENSTATES_API_KEY`
- `TAVILY_API_KEY`
- `EXA_API_KEY`

Deferred:

- `SOCRATA_APP_TOKEN`

Do not add now:

- none

Note: source expansion does not change the canonical economic mechanism mapping. Backend remains the owner of `ImpactMode -> MechanismFamily` mapping and downstream deterministic gates.

## dx-review Feedback Integrated

Reviewer concern: verifiers were using raw dicts while typed Pydantic models existed.

Action:

- The source integration POC now attempts to validate `evidence_card_ready` items through `schemas.economic_evidence.EvidenceCard`.
- Current local env lacks `pydantic`, so the artifact records `schema_validation_mode=local_contract_only` and uses strict local checks. This is not the final implementation target; production wiring must run in an environment with backend dependencies installed.

Reviewer concern: `analysis.ImpactMode` and `economic_evidence.MechanismFamily` overlap without mapping.

Action:

- The source integration POC now emits explicit mapping:
  - `direct_fiscal -> direct_fiscal`
  - `compliance_cost -> compliance_cost`
  - `pass_through_incidence -> fee_or_tax_pass_through`
  - `adoption_take_up -> adoption_take_up`
  - `qualitative_only -> null`

## Final Recommendation

Lock the architecture direction as:

**Windmill orchestration + backend-owned source/evidence/economic contracts + unified source envelope + quantified-or-fail-closed analysis.**

Do not treat breadth as success by itself. A source is product-relevant only if it improves one of:

- official artifact recall,
- structured policy fact extraction,
- evidence-card provenance,
- parameter resolution,
- assumption applicability,
- deterministic quantification,
- grounded cost-of-living explanation.

The current evidence is sufficient to proceed to implementation of the unified source/evidence contract and wave-1 adapters. It is not yet sufficient to claim full Railway-dev rollout readiness until a live multi-jurisdiction run proves persisted evidence cards and admin-visible gate outcomes.
