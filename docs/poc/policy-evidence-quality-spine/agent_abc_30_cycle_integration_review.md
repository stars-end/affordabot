# Agent A/B/C 30-Cycle Integration Review

Feature-Key: `bd-3wefe.13`  
Date: 2026-04-16  
Scope: data-moat quality gates D0-D11 for San Jose policy evidence packages.

## Execution

Three workers ran 10 substantive cycles each:

- Agent A: scraped evidence lane, D1/D2/D4/D5/D8.
- Agent B: structured evidence lane, D0/D1/D3/D5/D8.
- Agent C: unified package identity and economic handoff, D6/D7/D9/D10/D11.

Cycle ledgers:

- `docs/poc/policy-evidence-quality-spine/scraped_lane_cycles_agent_a.md`
- `docs/poc/policy-evidence-quality-spine/structured_lane_cycles_agent_b.md`
- `docs/poc/policy-evidence-quality-spine/package_handoff_cycles_agent_c.md`

## Orchestrator Review Findings

The worker outputs were not accepted as-is. Two integration defects would have preserved false-positive data-moat claims:

1. Agent C canonical dedupe collapsed scraped and structured candidates with the same canonical document key and content hash into one lane. That erased cross-lane provenance. Integration fix: dedupe now preserves `source_lane`, so duplicate scraped candidates collapse but scraped and structured lineage remain separately visible.

2. Agent B excluded Tavily secondary search from `true_structured`, but the builder still let Tavily-derived numeric parameters satisfy the global parameterization gate. That recreated the Cycle 25 failure shape. Integration fix: economic parameterization now distinguishes diagnostic numeric rows from economic parameters, and true structured depth requires a resolved economic parameter from a true structured source.

## Current Local Gate Movement

- D0 improved: catalog now records more source families with `lane_classification`, `runtime_status`, and `live_proven`.
- D1 improved: structured and scraped lanes carry policy lineage and reconciliation metadata.
- D2 improved: search provider provenance comes from the runtime client label, with portal/fallback counters.
- D3 improved: secondary search cannot count as true structured evidence, and shallow structured rows fail closed.
- D4 improved: primary scraped extraction emits raw value, normalized value, unit, denominator, locator, confidence, and sanity metadata.
- D5 improved: package run context includes source reconciliation records and source-of-truth policy.
- D6 improved: package identity dedupe is explicit and preserves source-lane provenance.
- D7 improved locally: storage refs carry content hashes and proof mode fields. Direct live storage proof still requires a deployed run.
- D8 improved: source-shape drift is detected and has regression tests.
- D9 improved locally: run context carries scope idempotency, package identity, and proof mode fields. Direct Windmill proof still requires a deployed run.
- D10 improved: economics read model now emits a manual audit scaffold.
- D11 improved: economics read model now emits a machine-actionable handoff contract.

## Validation

Targeted merged regression:

```bash
cd backend
poetry run pytest tests/services/llm/test_web_search_factory.py tests/services/pipeline/test_policy_evidence_package_builder.py tests/services/pipeline/test_bridge_runtime.py tests/services/pipeline/test_structured_source_enrichment.py tests/services/pipeline/test_policy_evidence_quality_spine_economics.py tests/routers/test_admin_pipeline_read_model.py tests/verification/test_verify_scraped_lane_data_moat.py
```

Result: `108 passed, 4 warnings`.

Diff hygiene:

```bash
git diff --check
git diff --cached --check
```

Result: clean.

## Verdict Before Live Deployment

Status: `evidence_ready_with_gaps`.

The local package builder, bridge payload, structured catalog, scraped lane provenance, and economic handoff contract are materially stronger than Cycle 25. They specifically address the reviewer concerns about hardcoded provider provenance, Tavily secondary-search false credit, shallow Legistar structured data, stale/manual audit ambiguity, and unstructured economic handoff.

This does not yet satisfy `decision_grade_data_moat`, because the new code has not been deployed and exercised through Railway dev plus Windmill. The next required proof is a live San Jose run that produces a fresh stored package with:

- private SearXNG provider label derived from runtime client provenance;
- primary scraped artifact parameter extraction from the Legistar PDF or explicit fail-closed reason;
- true structured source rows with economic parameter depth, not just Legistar event metadata;
- cross-source reconciliation between scraped and structured facts;
- Postgres, MinIO, and pgvector refs with direct or explicitly caveated proof mode;
- admin read-model economic handoff fields populated from the current package.
