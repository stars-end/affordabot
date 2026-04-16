# Manual Audit Cycle 13: Data Moat

Feature-Key: bd-3wefe.13

## Verdict

PARTIAL. Cycle 13 proves more of the live data-moat spine than Cycle 11, but it does not yet prove a high-quality unified scraped + structured evidence package suitable for downstream quantitative analysis.

## Manual Checks

I inspected these artifacts:

- `docs/poc/policy-evidence-quality-spine/artifacts/live_cycle_13_windmill_domain_run.json`
- `docs/poc/policy-evidence-quality-spine/artifacts/live_cycle_13_storage_probe.json`
- `docs/poc/policy-evidence-quality-spine/artifacts/live_cycle_13_admin_analysis_status.json`

## What Passed

The live package is no longer only a local/deterministic proof:

- Postgres package row exists and is readable.
- MinIO package and reader artifacts are readable.
- pgvector derivation exists for the selected document.
- Admin read model reports storage/read-back as pass.
- Admin read model reports Windmill/orchestration as pass with a current run id.

The data package also contains both source lanes:

- Scraped lane: private SearXNG search -> reader artifact -> raw scrape -> chunks -> pgvector.
- Structured lane: Legistar Web API metadata source with provenance.

The selected scraped evidence is materially better than Cycle 11:

- Cycle 11 selected a procedural Legistar matter/gateway page.
- Cycle 13 selected a substantive Commercial Linkage Fee explainer after the official San Jose page failed in the reader.

## What Did Not Pass

The selected source is not official-of-record:

- The search/ranker found the official San Jose Commercial Linkage Fee source.
- Z.ai reader failed on the official source with transient `500` errors.
- The pipeline fell back to an SV@Home page.

The structured lane is not yet economically useful:

- It contributed Legistar meeting metadata.
- It did not contribute fee rates, affected project categories, nexus-study values, ordinance text, or effective dates.
- The only resolved structured parameter visible to the economic bridge was diagnostic and correctly excluded from economic support.

The package still lacks provider-quality metrics needed for a durable data-moat gate:

- top-N artifact recall
- official-source attempted/read success
- fallback reason and fallback source class
- reader substance score
- numeric/economic-signal coverage

## Gate Status

- D1 source catalog: pass from prior code/artifacts.
- D2 scraped evidence quality: partial.
- D3 structured evidence quality: partial.
- D4 unified package identity/provenance: partial/pass mechanics, not content pass.
- D5 storage readback: pass for Postgres/MinIO/pgvector mechanics.
- D6 Windmill integration: pass for current-run binding.

## Decision

Continue. The next cycle should not lower the economic-analysis bar. It should make provider failures non-destructive to persisted evidence packages, then continue improving official-source reader fallback and structured economic parameter ingestion.
