# Manual Audit Cycle 18: Data Moat

Feature-Key: bd-3wefe.13

## Verdict

PASS_FOR_DATA_MOAT_VERTICAL, PARTIAL_FOR_BREADTH.

Cycle 18 proves a meaningful San Jose vertical data moat: scraped official artifact, structured metadata, secondary official-source snippets, storage readback, pgvector derivation, and source-bound economic parameters all appear in one package.

## Manual Checks

I inspected:

- `docs/poc/policy-evidence-quality-spine/artifacts/live_cycle_18_windmill_domain_run.json`
- `docs/poc/policy-evidence-quality-spine/artifacts/live_cycle_18_storage_probe.json`
- `docs/poc/policy-evidence-quality-spine/artifacts/live_cycle_18_admin_analysis_status.json`

## Passed Checks

- Primary scraped artifact is a San Jose Legistar attachment with fee schedule content.
- Secondary Tavily lane contributes official San Jose CLF snippet facts.
- Structured Legistar metadata remains present but diagnostic.
- Package persists to Postgres.
- Package and reader artifacts read back from MinIO.
- pgvector has chunks/embeddings for the selected document.
- Parameter table includes source-bound fee-rate rows.

## Remaining Gaps

- Fee schedule extraction is incomplete; `$14.31` and `$17.89` were visible in the standalone Tavily probe but not in the live parameter table.
- The LLM saw a malformed reader extraction token (`$18.706.00`), which shows PDF/table text extraction still needs audit guards.
- Breadth is not proven across other jurisdictions or policy domains.

## Gate Status

- D1 source catalog: pass.
- D2 scraped evidence quality: pass for this vertical.
- D3 structured evidence quality: partial/pass for secondary numeric facts.
- D4 unified package identity/provenance: pass for this vertical.
- D5 storage readback: pass.
- D6 Windmill integration: pass.

## Decision

Continue. The data moat is now viable for this narrow vertical, but economic decision-grade output remains blocked by assumption/model/uncertainty and canonical binding gaps.
