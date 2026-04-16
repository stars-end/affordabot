# Structured Source Breadth Audit

- Feature key: `bd-2agbe.9`
- Artifact version: `2026-04-14.structured-source-breadth.v1`
- Mode: `replay`
- Generated at: `2026-04-16T00:25:29.859039+00:00`

## Summary

- Total candidates: `8`
- By recommendation: `{"backlog": 3, "scrape_reader_lane": 1, "structured_lane": 4}`
- By live probe status: `{"not_run": 2, "pass": 6}`
- Wave-1 structured feeds: `legistar_sanjose, ca_pubinfo_leginfo, arcgis_public_gis_dataset, ca_ckan_open_data_catalog`
- Note: ArcGIS confirms public GIS API mechanics. Policy-specific zoning/parcel/housing coverage still needs catalog curation before production reliance.

## Candidate Matrix

| source_family | scope | recommendation | relevance | probe | api/raw | usefulness |
|---|---|---|---|---|---|---|
| legistar_sanjose | city_san_jose | structured_lane | direct_fiscal | pass | api | high |
| ca_pubinfo_leginfo | state_california | structured_lane | land_use_capacity | pass | raw_official_file | high |
| arcgis_public_gis_dataset | regional_public_gis | structured_lane | contextual_only | pass | api | medium |
| ca_ckan_open_data_catalog | state_california | structured_lane | household_affordability | pass | api | medium |
| public_opendatasoft_catalog | multi_jurisdiction | backlog | unknown | pass | api | low |
| official_static_xlsx_census | national_context | backlog | contextual_only | pass | raw_public_file | low |
| socrata_open_data_portals | city_county_varies | backlog | direct_fiscal | not_run | api | high |
| granicus_agenda_portals | city_county_varies | scrape_reader_lane | compliance_cost | not_run | not_confirmed | medium |

## Evidence Notes

- `legistar_sanjose`: Replay fixture indicates row payload with Matter identifiers.
- `ca_pubinfo_leginfo`: Replay fixture indicates official PUBINFO feed and daily archive reachable.
- `arcgis_public_gis_dataset`: Replay fixture confirms ArcGIS REST mechanics only; policy-specific zoning/parcel relevance not guaranteed.
- `ca_ckan_open_data_catalog`: Replay fixture includes CKAN package_search response envelope.
- `public_opendatasoft_catalog`: Replay fixture confirms ODS catalog API shape; local-jurisdiction dataset mapping still required.
- `official_static_xlsx_census`: Replay fixture confirms direct XLSX retrieval from official Census domain.
- `socrata_open_data_portals`: Excluded from this POC by explicit user constraint: no Socrata signup now.
- `granicus_agenda_portals`: Agenda portals are generally HTML/PDF-first and belong to scrape+reader lane.
