# Structured Source Lane Audit

Date: 2026-04-14

Related work:
- Beads epic: `bd-2agbe`
- Product PR: https://github.com/stars-end/affordabot/pull/436
- Context: Windmill/domain POC, economic evidence pipeline lockdown, and structured-source breadth audit

## Decision

Affordabot should treat free, easily ingestible structured sources as a parallel acquisition lane, not as part of the manual scrape/search/reader lane.

The structured-source lane is limited to sources that expose at least one of:

- documented public API
- public JSON/CSV/GeoJSON/XML endpoint
- public bulk data archive
- direct official CSV/XLSX/TXT/ZIP file

If a source requires browser automation, rendered portal traversal, form interaction, or HTML scraping to discover records, it belongs in the scrape/reader lane even if the resulting attachment is a public PDF or HTML page.

## Why This Matters

The San Jose search/reader POC proved that search and reader are useful for coverage, but not sufficient by themselves to maximize affordabot's data moat. Some public-policy sources are already structured and should not be downgraded into brittle search results.

The structured-source lane should feed the same canonical evidence/dossier layer as scrape/reader sources:

```text
structured_source_refresh
  -> raw payload artifact
  -> normalized source record
  -> optional official linked document fetch/read
  -> canonical evidence cards
  -> economic research dossier
```

```text
search_or_scrape_reader_refresh
  -> discovered URL
  -> reader/OCR/scraper artifact
  -> normalized source record
  -> canonical evidence cards
  -> economic research dossier
```

Windmill should orchestrate both lanes. Affordabot should own source adapters, normalization, canonical identity, provenance, evidence gates, and economic analysis.

## Acceptance Standard

A source can enter `structured_lane` only if the audit records:

- signup/key path or `none_required`
- free status
- API/raw-file proof
- sample endpoint/file URL
- no-browser sample pull feasibility
- stable identity fields
- date/update fields
- target jurisdictions or examples
- existing affordabot refs if already integrated

Decision values:

- `structured_lane`: free/public or free-key source with API/raw file access and no browser automation.
- `scrape_reader_lane`: useful public civic source, but requires portal traversal, HTML scraping, reader/OCR, or attachment discovery.
- `needs_manual_signup_check`: plausible structured API exists, but key/free-access/sample-pull needs manual confirmation.
- `reject`: paid-only, blocked, irrelevant, or no usable public records confirmed.

## Audit Summary

### Structured Lane Winners

| Source family | Signup / key path | Free status | API/raw proof | Existing affordabot integration | Recommendation |
|---|---|---|---|---|---|
| OpenStates / Plural Open | https://open.pluralpolicy.com/ | `free_key_required` | API + bulk data | Partial: California discovery/metadata and admin mapping | `structured_lane` |
| California LegInfo PUBINFO | `none_required` | `free_public` | Official raw ZIP/DAT feeds | Adjacent: current California path follows official LegInfo text | `structured_lane` |
| LegiScan | https://legiscan.com/legiscan/1000 | `free_limited` | API + dataset archives | None found | `structured_lane` |
| Legistar Web API | `none_required` | `free_public` | Public API | Partial: San Jose/Santa Clara/Sunnyvale Legistar-shaped code and admin mapping | `structured_lane` |
| Socrata / Tyler Data & Insights | https://dev.socrata.com/docs/app-tokens | `free_public` for public datasets; optional app token | Public SODA API | Mentioned in docs, no generic adapter found | `structured_lane` |
| ArcGIS REST / ArcGIS Hub | `none_required` for public items | `free_public` | REST APIs + download/export support | Mentioned in docs, no generic adapter found | `structured_lane` |
| CKAN | `none_required` for public datasets | `free_public` | API + resource files | None found | `structured_lane` |
| OpenDataSoft | `none_required` for public datasets | `free_public` | API + export endpoints | None found | `structured_lane` |
| Static official CSV/XLSX/TXT/ZIP | `none_required` | `free_public` | Direct raw file | Mentioned as open data in docs, no generic adapter found | `structured_lane` |

### Manual Signup / Confirmation

| Source family | Signup / key path | Status | Recommendation |
|---|---|---|---|
| Accela | https://developer.accela.com/ | API exists; free-limited/public agency data access not verified end-to-end | `needs_manual_signup_check` |
| New York State Senate Open Legislation | https://legislation.nysenate.gov/ | Free key required; relevant if expanding beyond CA/Bay Area | `structured_lane` for NY-only future scope |
| Virginia LIS Budget Web Service | `none_required` observed | API surface found; free status not explicit | `structured_lane` only for future VA scope after confirmation |

### Scrape / Reader Lane

These are public and useful, but do not currently meet the structured-lane bar because the confirmed access pattern is portal/page/PDF-oriented rather than a clean API/raw-record feed.

| Source family | Confirmed access shape | Recommendation |
|---|---|---|
| Granicus public pages | Public meeting/video/archive pages; no public structured API confirmed | `scrape_reader_lane` |
| city-scrapers | Maintained scraping wrappers | `scrape_reader_lane` |
| CivicPlus Agenda Center | Public agenda/minutes PDFs; portal discovery | `scrape_reader_lane` |
| BoardDocs | Public portals/pages; no clean API confirmed | `scrape_reader_lane` |
| NovusAgenda | Public agenda pages/attachments; no clean API confirmed | `scrape_reader_lane` |
| PrimeGov | Public portals/PDFs; no clean API confirmed | `scrape_reader_lane` |
| Swagit | Public video/transcript/agenda pages; no clean API confirmed | `scrape_reader_lane` |
| eScribe | Public file streams; no clean API confirmed | `scrape_reader_lane` |
| OpenGov / ClearGov budget books | Public budget pages/PDFs | `scrape_reader_lane` |
| Tyler EnerGov | No free/public structured API confirmed | `reject` unless exposed through ArcGIS/Socrata/static exports |

## Existing Affordabot Evidence

OpenStates is already a brownfield source, not a hypothetical future dependency:

- `OPENSTATES_API_KEY` is documented in `RAILWAY_ENV.md`.
- `pyopenstates` is present in backend dependencies.
- `jurisdictions` schema already has `api_type`, `api_key_env`, `openstates_jurisdiction_id`, and `source_priority`.
- The admin jurisdiction mapper already exposes `openstates` and `legistar`.
- The California scraper uses OpenStates for discovery/metadata, then follows official LegInfo URLs for canonical text.

Legistar is also partially integrated:

- San Jose, Sunnyvale, and Santa Clara code paths already recognize Legistar-shaped sources.
- Existing substrate tooling expands seeded Legistar calendar roots into agenda/minutes source rows.
- The missing piece is a generic `LegistarWebApiSourceAdapter` that treats `webapi.legistar.com` as a structured source before falling back to calendar scraping/search.

## Initial POC Scope

The initial structured-source POC should be narrow but representative:

1. `ca_pubinfo_leginfo` or `openstates_ca`
2. `legistar_sanjose`
3. one Bay Area `socrata_or_arcgis` dataset

This is not because the other sources are unimportant. It is because the POC should validate the adapter boundary across three different structured-source shapes:

- state legislation API/raw feed
- local meeting/local legislation API
- local open-data/GIS table

Once that boundary works, adding CKAN, OpenDataSoft, static CSV/XLSX, and LegiScan is catalog/adapter expansion, not a new architecture decision.

## Why Not POC Everything At Once

Expanding the first POC to every candidate source would blur three questions:

1. Can the structured-source lane persist raw payloads and normalized records correctly?
2. Can those records join the evidence/dossier layer used by the economic analysis pipeline?
3. Which source families are worth integrating first?

The first POC should answer questions 1 and 2. The inventory above answers question 3 well enough to sequence follow-up work.

Candidate follow-up sequence after the initial POC:

1. Add `LegiScan` only if OpenStates/LegInfo gaps justify a second state-legislation provider.
2. Add `CKAN`, `OpenDataSoft`, and static file adapters as generic catalog/file families.
3. Keep CivicPlus, BoardDocs, NovusAgenda, PrimeGov, Swagit, eScribe, OpenGov, and ClearGov in scrape/reader backlog unless a clean public API/raw-record feed is found for a target jurisdiction.

## Open Questions

- Which Bay Area Socrata or ArcGIS dataset should anchor the first local open-data POC?
- Should California prioritize official PUBINFO over OpenStates for daily bulk refresh, with OpenStates retained as metadata/discovery fallback?
- Should Accela be manually checked now, or deferred until a target jurisdiction exposes permit data only through Accela?
- Should LegiScan be added as a breadth source before MVP, or deferred because OpenStates + official CA feeds are enough for the current geography?
