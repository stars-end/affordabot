# Source Expansion API-Key Matrix

- Date: 2026-04-14T17:52:45.683773+00:00
- Feature key: `bd-2agbe.12`
- Artifact version: `2026-04-14.source-expansion-api-key-matrix.v1`

## Matrix

| source_family | lane | free_status | api_key_required | railway_variable_needed | economic_value | wave |
|---|---|---|---|---|---|---|
| legistar_public_api | structured | free_public | no | none | high | wave1 |
| ca_leginfo_pubinfo_raw_files | structured | free_public | no | none | high | wave1 |
| ca_ckan_open_data_api | structured | free_public | no | none | medium | wave1 |
| opendatasoft_public_catalog_api | structured | free_public | no | none | medium | wave2 |
| official_static_csv_xlsx_raw | contextual | free_public | no | none | low | backlog |
| arcgis_hub_rest_public | structured | free_public | no | none | medium | wave2 |
| openstates_plural_api | structured | free_tier_available | yes | OPENSTATES_API_KEY | medium | wave2 |
| socrata_open_data | structured | free_tier_key_optional_limits | deferred | SOCRATA_APP_TOKEN | high | backlog |
| private_searxng | search_provider | self_hosted_infra_cost_only | no | SEARXNG_BASE_URL | high | wave1 |
| tavily_search_api | search_provider | free_tier_capped | yes | TAVILY_API_KEY | medium | wave2 |
| exa_search_api | search_provider | free_tier_capped | yes | EXA_API_KEY | medium | wave2 |
| granicus_civicplus_boarddocs_portals | scrape_reader | free_public | no | none | high | wave1 |

## Key Actions

### required_now
- `SEARXNG_BASE_URL` -> `private_searxng`: Primary discovery lane for reader artifacts; not a structured source but critical complement.

### optional_soon
- `OPENSTATES_API_KEY` -> `openstates_plural_api`: Useful structured legislative metadata; key needed for robust rate limits and stable operations.
- `TAVILY_API_KEY` -> `tavily_search_api`: Useful fallback to mitigate SearXNG quality failures; reserve for targeted runs due to quota.
- `EXA_API_KEY` -> `exa_search_api`: Useful as bakeoff/eval fallback; avoid default routing due to monthly quota limits.

### defer
- `SOCRATA_APP_TOKEN` -> `socrata_open_data`: Potentially high value where available, but explicitly deferred by user (no signup this wave).

### do_not_add
- none

## Mapping Notes

- MechanismFamily: Source expansion does not change canonical MechanismFamily or ImpactMode ownership. Those mappings stay backend-authored in economic analysis contracts.
- ImpactMode: New sources broaden evidence availability but must map into existing deterministic parameterization and assumption gates, not introduce ad-hoc per-source impact logic.
- Key strategy: No new API key is required for wave1 structured/scrape baseline. Use OPENSTATES_API_KEY/TAVILY_API_KEY/EXA_API_KEY only when enabling wave2 lanes; keep SOCRATA_APP_TOKEN deferred.

## Quality Guardrail

- Breadth alone is insufficient. A source is wave-eligible only when it can provide policy facts or linked artifacts that improve evidence cards for deterministic economic quantification.
