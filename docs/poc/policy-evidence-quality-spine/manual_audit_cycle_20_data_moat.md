# Manual Audit Cycle 20: Data Moat

Feature-Key: bd-3wefe.13

## Audited Artifacts

- `docs/poc/policy-evidence-quality-spine/artifacts/live_cycle_20_windmill_domain_run.json`
- `docs/poc/policy-evidence-quality-spine/artifacts/live_cycle_20_storage_probe.json`
- `docs/poc/policy-evidence-quality-spine/artifacts/live_cycle_20_admin_analysis_status.json`

## Gate A Result

Status: PASS_FOR_RUNTIME_SPINE, PARTIAL_FOR_DATA_QUALITY.

The live package proves the storage and orchestration spine:

- Windmill invoked the six-step backend domain flow.
- Backend persisted a package row for the current run.
- MinIO readback passed for the reader output and package artifact.
- pgvector derivation passed with 233 chunks and 233 embeddings for the selected document.
- Admin provenance shows both scraped and structured source lanes.

## Scraped Evidence Audit

The scraped lane selected the official San Jose Commercial Linkage Fee page:

`https://www.sanjoseca.gov/your-government/departments-offices/housing/developers/commercial-linkage-fee`

This is an official source, but it is lower quality than the Cycle 18 Legistar fee schedule attachment because the reader output emphasizes the public webpage and navigation content. The package still includes a Tavily secondary card with official-source fee snippets, but the primary scraped artifact did not provide the strongest table artifact in this run.

Manual conclusion: the system is robust enough to store and surface the package, but source ranking remains a quality bottleneck. The data moat should prefer durable fee schedule artifacts over public portal pages when both are present.

## Structured Evidence Audit

The package includes structured Legistar metadata:

- source_family: `legistar_web_api`
- access_method: `public_api_json`
- provider_run_id: `7927`
- endpoint: `https://sanjose.legistar.com/MeetingDetail.aspx?LEGID=7927&GID=317&G=920296E4-80BE-4CA2-A78F-32C5EFCF78AF`

The package also includes a bounded secondary structured-search lane:

- source_family/query_family: `tavily_secondary_search`
- source URL: official San Jose CLF page

Manual conclusion: scraped + structured lanes are unified in one package with provenance. Breadth remains narrow: this proves the San Jose CLF vertical, not the full structured-source catalog.

## Storage Audit

Storage gate is pass:

- package_id: `pkg-189ea06455b12e96370c5ebd`
- backend_run_id: `a599344a-ca06-4d4b-85cf-4e1f47cf15d8`
- MinIO package ref: `minio://affordabot-artifacts/policy-evidence/packages/pkg-189ea06455b12e96370c5ebd.json`
- pgvector truth role: `derived_index`

Manual conclusion: storage is no longer the limiting factor for this vertical.

## Data Moat Improvement Needed

The next data-moat improvement should not be another generic storage test. It should improve selected-artifact quality by requiring provider/ranker metrics in the package:

- top-N artifact recall,
- selected artifact family,
- portal-vs-artifact penalty result,
- reader substance result,
- fallback provider trigger,
- whether secondary structured snippets rescued missing numeric parameters.
