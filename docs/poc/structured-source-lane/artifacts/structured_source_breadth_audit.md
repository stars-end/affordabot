# Structured Source Breadth Audit

- Feature key: `bd-2agbe.9`
- Artifact version: `2026-04-14.structured-source-breadth.v1`
- Mode: `live`
- Generated at: `2026-04-14T17:17:55.441749+00:00`

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

- `legistar_sanjose`: rows=3, keys_present=True
- `ca_pubinfo_leginfo`: root_head=200, daily_head=200
- `arcgis_public_gis_dataset`: selected_title='NFHL Flood Hazard Zones'; policy_specific_match=False. ArcGIS probe confirms public GIS API mechanics; policy-specific San Jose zoning/parcel/housing may require tighter curation.
- `ca_ckan_open_data_catalog`: package_count=20
- `public_opendatasoft_catalog`: catalog_total_count=406; API reachable, but local policy-specific dataset binding not done.
- `official_static_xlsx_census`: http_status=206
- `socrata_open_data_portals`: Explicitly excluded from this POC by user decision: no Socrata signup at this time.
- `granicus_agenda_portals`: Portal-first HTML/PDF source; classify into scrape+reader lane.
