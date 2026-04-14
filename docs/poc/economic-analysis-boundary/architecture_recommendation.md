# Architecture Recommendation After Structured Source + Economic Handoff POCs

Date: 2026-04-14
Feature keys: `bd-2agbe.9`, `bd-2agbe.10`

## Decision

Recommend **Option A: Windmill-max orchestration with backend-owned domain commands**.

This is the cleanest boundary supported by the current evidence:

- Windmill owns schedules, fanout, retries, branch routing, run visibility, and calls to coarse backend commands.
- Affordabot backend owns source ranking policy, reader gates, artifact classification, evidence-card extraction, parameterization, assumption selection, deterministic quantification, LLM guardrails, persistence invariants, and read APIs.
- Postgres owns canonical relational truth for runs, steps, gate reports, evidence cards, parameter cards, assumption cards, model cards, and final analysis/read models.
- pgvector owns retrieval indexes derived from canonical chunks; it is not the source of truth.
- MinIO owns immutable raw/reader/intermediate artifacts by content-addressed URI.
- Frontend/admin owns display only over backend-authored read models.

## Evidence Used

Structured-source breadth:

- `docs/poc/structured-source-lane/artifacts/structured_source_breadth_audit.json`
- `docs/poc/structured-source-lane/artifacts/structured_source_breadth_audit.md`

Economic handoff:

- `docs/poc/economic-analysis-boundary/artifacts/structured_economic_handoff_report.json`
- `docs/poc/economic-analysis-boundary/artifacts/structured_economic_handoff_report.md`

Earlier no-key source/access overlay:

- `docs/poc/structured-source-lane/artifacts/structured_source_lane_poc_report.json`
- `docs/poc/structured-source-lane/artifacts/structured_source_economic_readiness_overlay.json`

## Data Source Finding

The first implementation wave should include:

- `legistar_sanjose`: high usefulness for local matters, staff reports, agenda/minutes links, and direct-fiscal or compliance-cost discovery.
- `ca_pubinfo_leginfo`: high usefulness for state legislation and official raw-file access.
- `ca_ckan_open_data_catalog`: medium usefulness as a no-key state catalog; useful for source discovery and contextual structured datasets.
- `arcgis_public_gis_dataset`: medium usefulness as a public GIS API family, but **not yet policy-specific enough** for San Jose zoning/parcel/housing claims.

Keep out of wave 1:

- `socrata_open_data_portals`: likely valuable, but explicitly deferred because no signup/API key was requested for this round.
- `public_opendatasoft_catalog`: API reachable, but no local policy-specific binding yet.
- `official_static_xlsx_census`: raw-file access works, but it is contextual, not a core policy artifact feed.
- `granicus_agenda_portals`: scrape/reader lane, not structured-source lane.

## Economic Analysis Finding

The economic handoff POC supports the architecture at the **contract level**:

- One deterministic replay case reaches `quantified_pass`.
- One local-government control reaches `fail_closed` at `parameterization` despite source/reader success.
- Gate attribution separates source access, reader substance, evidence-card extraction, parameterization, assumption selection, quantification, LLM guardrail, persistence/read-model, and orchestration-boundary failures.

This is the critical product boundary: source gathering can succeed while economic quantification still fails closed. That means Windmill should not own economic decision logic. It should orchestrate backend commands that return explicit gate outcomes.

## Why Not Option B

Option B, backend-driven pipeline with Windmill as a cron shell, remains viable as a fallback if live Windmill runtime friction becomes dominant. It is not the current recommendation because existing evidence already shows backend contracts can be coarse enough for Windmill DAG control without moving business logic into Windmill.

## Why Not Option C

Option C, Windmill direct-storage/direct-ETL with thin Affordabot, should be rejected for core economics.

The data moat is not just raw extraction. It includes:

- canonical document identity,
- source/artifact classification,
- evidence-card provenance,
- parameter and assumption gating,
- deterministic formulas,
- fail-closed logic,
- operator-readable audit trails.

Moving those into Windmill scripts would recreate an application backend inside orchestration code and make economic correctness harder to test, review, and preserve.

## What Remains Unproven

Do not treat this as Railway-dev rollout proof yet. Remaining gates:

1. Live multi-jurisdiction run where structured sources produce real evidence cards.
2. Live reader run that extracts staff-report or fiscal-note substance from linked artifacts.
3. Persistence proof that gate reports and artifact cards are visible through backend read APIs.
4. Admin/frontend proof that operators can inspect blocking gates and artifact provenance without reading logs.
5. Policy-specific ArcGIS cataloging for zoning/parcel/housing/permit/fee datasets, or explicit demotion of ArcGIS to contextual-only.

## Next Implementation Wave

Proceed with Option A under an `ALL_IN_NOW` dev/staging posture:

1. Implement backend structured-source adapters for `legistar_sanjose`, `ca_pubinfo_leginfo`, and `ca_ckan_open_data_catalog`.
2. Add an ArcGIS adapter only behind a curated catalog manifest until policy-specific San Jose/Santa Clara layers are proven.
3. Extend backend pipeline results to persist evidence-card, parameter-card, assumption-card, and model-card summaries in Postgres, with large artifacts in MinIO and derived chunks in pgvector.
4. Extend admin read APIs to expose gate status, blocking gate, artifact counts, and provenance.
5. Keep Windmill flows thin: call backend commands, branch on backend-authored statuses, and persist Windmill job/run IDs only as operational metadata.
