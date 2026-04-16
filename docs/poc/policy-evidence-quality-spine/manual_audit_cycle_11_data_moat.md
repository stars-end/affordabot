# Manual Audit Cycle 11 - Data Moat Gate A

- Date: `2026-04-16`
- Feature key: `bd-3wefe.13`
- Package id: `pkg-d04e8a67cc9bb4eac46e4d9a`
- Backend run id: `085ff7ce-eb4d-4df6-9df2-7ba488c904ae`
- Windmill job id: `019d955c-74e6-353f-705c-c21c6bca4366`
- Source query: `San Jose Resolution 79705 commercial linkage fee affordable housing impact fee per square foot staff report`

## Audited Artifacts

- Live Windmill run: `docs/poc/policy-evidence-quality-spine/artifacts/live_cycle_11_windmill_domain_run.json`
- Storage probe: `docs/poc/policy-evidence-quality-spine/artifacts/live_cycle_11_storage_probe.json`
- Admin read model: `docs/poc/policy-evidence-quality-spine/artifacts/live_cycle_11_admin_analysis_status.json`

## What Passed

The runtime data-moat spine is real for this package:

- Windmill executed the expected sequence: `search_materialize -> freshness_gate -> read_fetch -> index -> analyze -> summarize_run`.
- The package persisted with both source lanes: `scraped` and `structured`.
- Postgres package row readback passed.
- MinIO readback passed for the reader output and package artifact.
- pgvector derivation passed with `20` chunks and `20` embeddings, with pgvector marked as `derived_index`, not source of truth.
- Idempotent rerun passed.
- Stale drills behaved correctly:
  - `stale_but_usable` proceeded with alerts.
  - `stale_blocked` stopped before read/index/analyze.

## Scraped Evidence Audit

Selected scraped URL:

- `https://sanjose.legistar.com/gateway.aspx?m=l&id=/matter.aspx?key=15360`

The selected source is official and relevant to the target policy family, but it is a procedural Legistar matter page for accepting the Fiscal Year 2024-2025 AHIF/CLF annual report. The Z.ai reader output and analysis correctly identified that the source confirms the existence of the fees but does not contain enough fee-rate or cost-impact detail for quantitative analysis.

Search-provider bakeoff evidence shows better candidate quality was available:

- Private SearXNG top result: San Jose Commercial Linkage Fee city page, likely better for fee schedule/rate facts.
- Exa top results included the San Jose city page and a published San Jose document URL.
- Tavily top result was the same Legistar matter, but its second result contained richer extracted fee snippets.

Manual assessment: scraped source quality is **partial**, not pass. The retrieval stack can find relevant official sources, but rank/selection still over-prefers procedural Legistar agenda artifacts for an economic query that needs fee-rate evidence.

## Structured Evidence Audit

Structured sources present:

- `legistar_web_api`, field count `2`
- `san_jose_open_data_ckan`, field count `1`

The structured lane is integrated into the same package and provenance model, but the actual facts are economically weak:

- `event_id=7927`
- `event_body_id=258`
- `dataset_match_count=0`

These are useful diagnostic/source-catalog fields, not economic parameters. They should not count as source-bound economic support for cost-of-living analysis.

Manual assessment: structured source quality is **partial**, not pass. The unified storage and provenance mechanics work, but the structured lane must fetch or expose economically meaningful fields such as fee rates, effective dates, affected project categories, square-foot thresholds, or adopted report attachments.

## Gate A Verdict

`PARTIAL`

Cycle 11 proves the durable unified data-moat spine, but not high-quality data moat content. The next cycle should improve selected scraped source quality and structured-source economic usefulness before claiming the package is fit for quantitative economic analysis.
