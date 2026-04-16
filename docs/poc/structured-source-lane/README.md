# Structured Source vs Economic Analysis Comparison POC

Date: 2026-04-14
Feature key: `bd-2agbe.1`

## Goal

Answer this specific product question with auditable evidence:

`Can structured source records + linked canonical artifacts feed the existing AnalysisPipeline / LegislationResearchService better than the thin Windmill domain analyze path?`

## First No-Key POC Scope

This POC intentionally uses source families that do not require new API signup:

1. `ca_pubinfo_leginfo` (official California raw feed)
2. `legistar_sanjose` (public Legistar Web API)
3. `arcgis_public_gis_dataset` (public ArcGIS REST dataset)

Inventory is broader and preserved in backlog. This first POC is narrow to prove boundary behavior quickly across three structured-source shapes:

- state legislative feed
- local legislative/meeting API
- local GIS dataset

## Why This Scope Is Narrow

The first POC is not trying to maximize source count. It is proving the handoff boundary before adapter expansion:

1. Structured records produce stable policy-fact fields.
2. Linked artifact refs are explicit where reader extraction is still required.
3. Output can seed second-round economic research queries.
4. Handoff is explicit to canonical analysis path, not a new parallel analyzer.

Once this passes, adding CKAN, OpenDataSoft, static CSV/XLSX, and other structured families is an adapter/catalog wave, not a new architecture decision.

## Current Path Disconnect (Code-Cited)

Thin Windmill/domain bridge path:

- endpoint: [backend/main.py](/tmp/agents/bd-2agbe.1/affordabot/backend/main.py#L521)
- steps:
  - [backend/services/pipeline/domain/bridge.py](/tmp/agents/bd-2agbe.1/affordabot/backend/services/pipeline/domain/bridge.py#L479) (`_search_materialize`)
  - [backend/services/pipeline/domain/bridge.py](/tmp/agents/bd-2agbe.1/affordabot/backend/services/pipeline/domain/bridge.py#L635) (`_read_fetch`)
  - [backend/services/pipeline/domain/bridge.py](/tmp/agents/bd-2agbe.1/affordabot/backend/services/pipeline/domain/bridge.py#L1127) (`_analyze`)
- analyze behavior uses a thin prompt returning JSON keys `summary`, `key_points`, `sufficiency_state`:
  [backend/services/pipeline/domain/bridge.py](/tmp/agents/bd-2agbe.1/affordabot/backend/services/pipeline/domain/bridge.py#L1204)

Canonical economic analysis path:

- pipeline construction: [backend/main.py](/tmp/agents/bd-2agbe.1/affordabot/backend/main.py#L258)
- research step call:
  [backend/services/llm/orchestrator.py](/tmp/agents/bd-2agbe.1/affordabot/backend/services/llm/orchestrator.py#L1126)
- research service internals:
  - [backend/services/legislation_research.py](/tmp/agents/bd-2agbe.1/affordabot/backend/services/legislation_research.py#L260) (`research`)
  - [backend/services/legislation_research.py](/tmp/agents/bd-2agbe.1/affordabot/backend/services/legislation_research.py#L405) (`_web_research`)
  - [backend/services/legislation_research.py](/tmp/agents/bd-2agbe.1/affordabot/backend/services/legislation_research.py#L743) (`_derive_wave1_candidates`)
  - [backend/services/legislation_research.py](/tmp/agents/bd-2agbe.1/affordabot/backend/services/legislation_research.py#L794) (`_derive_wave2_prerequisites`)
- generation step:
  [backend/services/llm/orchestrator.py](/tmp/agents/bd-2agbe.1/affordabot/backend/services/llm/orchestrator.py#L1248)

Current disconnect:

- domain bridge path does not invoke `AnalysisPipeline` directly;
- canonical path is where economic research/quantification gating already lives.

Required handoff boundary for wave 1:

`structured_source_refresh -> policy facts + linked artifact refs -> canonical AnalysisPipeline`.

## Probe Artifact + Readiness Overlay

Worker-A probe artifact input:

- [structured_source_lane_poc_report.json](/tmp/agents/bd-2agbe.1/affordabot/docs/poc/structured-source-lane/artifacts/structured_source_lane_poc_report.json)

Overlay verifier:

- [verify_structured_source_analysis_readiness.py](/tmp/agents/bd-2agbe.1/affordabot/backend/scripts/verification/verify_structured_source_analysis_readiness.py)

Outputs:

- [structured_source_economic_readiness_overlay.json](/tmp/agents/bd-2agbe.1/affordabot/docs/poc/structured-source-lane/artifacts/structured_source_economic_readiness_overlay.json)
- [structured_source_economic_readiness_overlay.md](/tmp/agents/bd-2agbe.1/affordabot/docs/poc/structured-source-lane/artifacts/structured_source_economic_readiness_overlay.md)

## Runbook

```bash
cd /tmp/agents/bd-2agbe.1/affordabot
python3 backend/scripts/verification/verify_structured_source_lane_poc.py --mode live --self-check
python3 backend/scripts/verification/verify_structured_source_analysis_readiness.py
```

No Socrata token is required for this POC scope.

## Implementation Gate for Wave 1

Proceed to implementation wave 1 only if:

1. no-key scope verdict is `sufficient_for_wave1=true`
2. all three no-key source families map to explicit policy-fact fields
3. linked-reader requirements are explicit per source
4. economic seed query templates are emitted per source
5. output records the path disconnect and handoff boundary above

Current limitation: the live ArcGIS probe validates public ArcGIS REST mechanics and structured GIS attributes. It does not yet guarantee that the selected public layer is a zoning, parcel, or housing-capacity layer for San Jose. Treat that as adapter-catalog work before relying on ArcGIS for a specific policy mechanism.

If any condition fails, do not expand adapters first. Fix boundary mapping and handoff contract first.

## Breadth Audit Addendum (bd-2agbe.9)

Structured breadth verifier:

- [verify_structured_source_breadth_poc.py](/tmp/agents/bd-2agbe.1/affordabot/backend/scripts/verification/verify_structured_source_breadth_poc.py)

Artifacts:

- [structured_source_breadth_audit.json](/tmp/agents/bd-2agbe.1/affordabot/docs/poc/structured-source-lane/artifacts/structured_source_breadth_audit.json)
- [structured_source_breadth_audit.md](/tmp/agents/bd-2agbe.1/affordabot/docs/poc/structured-source-lane/artifacts/structured_source_breadth_audit.md)

Run:

```bash
cd /tmp/agents/bd-2agbe.1/affordabot
python3 backend/scripts/verification/verify_structured_source_breadth_poc.py --mode replay --self-check
python3 backend/scripts/verification/verify_structured_source_breadth_poc.py --mode live --self-check
```
