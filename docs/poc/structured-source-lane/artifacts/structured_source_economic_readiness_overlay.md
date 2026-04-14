# Structured Source Economic Readiness Overlay

- feature_key: `bd-2agbe.1`
- verifier_version: `2026-04-14.structured-source-overlay-v1`
- generated_at: `2026-04-14T17:17:55.509548+00:00`
- probe_report: `docs/poc/structured-source-lane/artifacts/structured_source_lane_poc_report.json`

## No-Key Scope Verdict

- sufficient_for_wave1: `True`
- reason: `no_key_scope_ready_for_wave1`
- present_source_families: `['ca_pubinfo_leginfo', 'legistar_sanjose', 'arcgis_public_gis_dataset']`
- missing_source_families: `[]`

## Source Overlay

| source_family | structured_ready | policy_fact_field_count | reader_handoff_count | seed_query_count |
|---|---:|---:|---:|---:|
| ca_pubinfo_leginfo | yes | 7 | 1 | 3 |
| legistar_sanjose | yes | 8 | 1 | 3 |
| arcgis_public_gis_dataset | yes | 7 | 1 | 3 |

## Path Comparison

- thin_windmill_domain_path entrypoint: `backend/main.py:521 (/cron/pipeline/domain/run-scope)`
- canonical_analysis_pipeline_path entrypoint: `backend/main.py:258 (AnalysisPipeline construction)`
- current_disconnect: `Windmill domain bridge analyze path does not call AnalysisPipeline or LegislationResearchService directly; it runs a thin question-over-chunks analysis.`
- handoff_boundary: `Structured-source lane should publish policy facts + linked artifact refs into backend-owned evidence contracts, then invoke canonical AnalysisPipeline for economic research and quantification gating.`

## Backlog Preserved

- Sources intentionally kept in scrape/reader backlog for this POC: `['boarddocs_public_portal', 'civicplus_agenda_center', 'cleargov_budget_book', 'escribe_public_filestream', 'granicus_public_pages', 'novusagenda_public_portal', 'opengov_budget_book', 'primegov_public_portal', 'swagit_public_archive']`
- Rationale: first POC validates boundary across three no-key structured shapes (state feed, local legislative API, public GIS dataset) before broad adapter expansion.
