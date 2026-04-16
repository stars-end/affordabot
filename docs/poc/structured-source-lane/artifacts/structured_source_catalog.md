# Structured Source Catalog

- Feature key: `bd-2agbe.9`
- Artifact version: `2026-04-14.structured-source-breadth.v1`
- Mode: `replay`
- Generated at: `2026-04-16T00:25:29.859039+00:00`

## Summary

- Total catalog rows: `8`
- Runtime integrated: `2`
- POC only: `6`
- Average usefulness score: `66.0`

## Catalog Matrix

| source_family | free_status | signup_or_key | access_method | jurisdiction_coverage | cadence_freshness | storage_target | runtime_status | usefulness_score |
|---|---|---|---|---|---|---|---|---|
| legistar_sanjose | free_public | none_required | rest_api | city_san_jose | agenda_and_minutes_event_driven | postgres_source_snapshots+minio_raw_artifacts | runtime_integrated | 95 |
| ca_pubinfo_leginfo | free_public | none_required | official_raw_file_zip | state_california | daily_pubinfo_feed | postgres_source_snapshots+minio_raw_artifacts | runtime_integrated | 92 |
| arcgis_public_gis_dataset | free_public | none_required | rest_api_feature_service | regional_multi_county | dataset_defined_variable | postgres_source_snapshots+minio_raw_artifacts | poc_only | 62 |
| ca_ckan_open_data_catalog | free_public | none_required | ckan_api | state_california | dataset_defined_variable | postgres_source_snapshots+minio_raw_artifacts | poc_only | 70 |
| public_opendatasoft_catalog | free_public | none_required | catalog_api | multi_jurisdiction | dataset_defined_variable | candidate_catalog_only | poc_only | 35 |
| official_static_xlsx_census | free_public | none_required | raw_file_download | national_context | annual_or_periodic_release | candidate_catalog_only | poc_only | 40 |
| socrata_open_data_portals | free_tier_key_optional_limits | https://dev.socrata.com/ | socrata_api | city_county_varies | dataset_defined_variable | candidate_catalog_only | poc_only | 76 |
| granicus_agenda_portals | free_public | none_required | html_pdf_portal | city_county_varies | meeting_event_driven | scrape_reader_lane_minio_raw_artifacts | poc_only | 58 |
