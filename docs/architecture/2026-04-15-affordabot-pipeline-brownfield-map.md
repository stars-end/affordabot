# 2026-04-15 Affordabot Pipeline Brownfield Map

Status: working draft for `bd-3wefe`

Purpose: give future agents one required, source-grounded map before changing the Affordabot data/economic-analysis pipeline. This file is not a replacement for code inspection; it is the routing index that tells agents what code must be checked first.

Findability:

- Start at `docs/architecture/README.md`.
- Search terms: `Affordabot brownfield pipeline map`, `raw_scrapes document_chunks AnalysisPipeline frontend output`, `scheduled substrate ingestion not economic analysis`, `PipelineDomainBridge not canonical AnalysisPipeline`.
- Beads memory pointer: `affordabot-pipeline-brownfield-map`.

## Freshness Contract

Treat this map as stale if any of these paths change:

- `backend/services/llm/orchestrator.py`
- `backend/services/legislation_research.py`
- `backend/services/llm/evidence_gates.py`
- `backend/services/llm/evidence_adapter.py`
- `backend/schemas/analysis.py`
- `backend/schemas/economic_evidence.py`
- `backend/services/pipeline/domain/`
- `backend/services/llm/web_search_factory.py`
- `backend/clients/web_reader_client.py`
- `backend/services/scraper/`
- `backend/services/discovery/`
- `backend/db/postgres_client.py`
- `backend/services/storage/`
- `backend/services/retrieval/`
- `backend/migrations/`
- `backend/routers/admin.py`
- `frontend/src/app/api/admin/`
- `frontend/src/components/admin/`
- `ops/windmill/`

## Current Architectural Verdict

The canonical path is not a blank slate.

- Production-used backend analysis is authoritative today: `AnalysisPipeline`, `LegislationResearchService`, `SufficiencyBreakdown`, `ImpactGateSummary`, `SourceTier`, and evidence adapter code.
- Scheduled Windmill cron jobs currently create substrate and chunks; they do not automatically run the full economic `AnalysisPipeline`.
- `PipelineDomainBridge` is the correct Windmill/backend boundary candidate for new orchestration work, but its current `analyze` command is a narrower chunk-summary JSON step rather than the canonical cost-of-living analysis engine.
- Direct-storage Windmill scripts are POC/test-harness code, not the target architecture.
- `EvidenceCard`, `ParameterCard`, `AssumptionCard`, `ModelCard`, and `GateReport` are useful package contracts, but they must initially wrap/project existing runtime outputs instead of becoming a second independent authority.
- Data is part of the product moat. Search quality, structured-source quality, reader substance, storage durability, and economic-analysis sufficiency must be evaluated as separate gates.

## Current Wired Pipelines

There is no single clean scheduled path from source discovery to final frontend
economic output. The current codebase has three partially overlapping paths:

1. Scheduled substrate ingestion:
   Windmill calls backend cron endpoints, which run `run_daily_scrape.py`,
   `run_rag_spiders.py`, `run_universal_harvester.py`, and `run_discovery.py`.
   These paths create or update `sources`, `legislation`, `raw_scrapes`,
   MinIO/S3 artifacts where configured, and `document_chunks`.
2. Canonical economic analysis:
   `/scrape/{jurisdiction}` and rerun/verification scripts instantiate
   `AnalysisPipeline`. This path reads latest raw scrape and vector stats,
   runs `LegislationResearchService` for RAG plus web research, applies
   deterministic sufficiency gates, invokes LLM generate/review/refine when
   permitted, and persists `pipeline_runs`, `pipeline_steps`, `legislation`,
   and `impacts`.
3. Windmill domain-boundary candidate:
   `/cron/pipeline/domain/run-scope` invokes `PipelineDomainBridge`, which can
   persist search snapshots, reader artifacts, raw scrapes, chunks, command
   results, and a simple analysis summary. This path proves the intended
   orchestration boundary, but it is not yet wired into canonical
   `AnalysisPipeline`.

Architecture work must explicitly say which path it is changing and how it
preserves or composes with the other two.

## End-to-End Map

| Stage | Canonical owner | Status | Primary code paths | Storage/read model | Required proof before expansion |
| --- | --- | --- | --- | --- | --- |
| Scheduled orchestration | Windmill | canonical legacy plus domain-boundary candidate | `ops/windmill/f/affordabot/trigger_cron_job.py`; `ops/windmill/f/affordabot/pipeline_daily_refresh_domain_boundary.py`; `ops/windmill/f/affordabot/pipeline_daily_refresh_domain_boundary__flow/flow.yaml` | Windmill job/run ids plus backend `pipeline_runs`/`pipeline_steps` | Windmill proves scraped and structured flows while delegating product decisions to backend commands |
| Scheduled substrate cron lane | backend | active, substrate-only | `backend/main.py` cron routes; `backend/scripts/cron/run_daily_scrape.py`; `backend/scripts/cron/run_rag_spiders.py`; `backend/scripts/cron/run_universal_harvester.py`; `backend/scripts/cron/run_discovery.py` | `sources`, `legislation`, `raw_scrapes`, `document_chunks`, optional MinIO/S3 | Do not claim final analysis proof from this lane alone; prove handoff into canonical analysis separately |
| Direct-storage Windmill lane | Windmill | POC only | `ops/windmill/f/affordabot/pipeline_daily_refresh_direct_storage.py` | POC storage writes | Retire as canonical target; keep only as comparison harness if useful |
| Search provider selection | backend | canonical but quality gate incomplete | `backend/services/llm/web_search_factory.py` | provider response artifacts should land in `search_result_snapshots` or package provenance | provider identity survives ranking, reading, evidence cards, and final package |
| Search/ranker/reader candidate policy | backend | canonical-new domain command layer | `backend/services/pipeline/domain/commands.py` (`rank_reader_candidates`, `prefetch_skip_reason`, `assess_reader_substance`) | `search_result_snapshots`, `content_artifacts`, package evidence cards | metric gates for recall@N, selected candidate, portal skip, reader substance, fallback trigger |
| Z.ai direct reader | backend | canonical reader candidate, not search primary | `backend/clients/web_reader_client.py` | raw/read artifacts in MinIO plus content hashes | reader-substance gate before package acceptance and chunking |
| End-to-end research assembly | backend | canonical inside analysis path | `backend/services/legislation_research.py` | research evidence in impact/pipeline payloads | reconcile provider provenance and assumption registry with package contract |
| Structured state source | backend | active | `backend/services/scraper/california_state.py` | `legislation`, `raw_scrapes`, downstream chunks | source catalog entry for OpenStates/LegInfo, including free/key/cadence/coverage |
| Legistar/local source | backend | active | `backend/services/scraper/san_jose.py`; `backend/services/scraper/registry.py` | `legislation`, `raw_scrapes`, MinIO artifacts | artifact identity, package provenance, and replay proof |
| Municode discovery | backend | present, not proven core daily path | `backend/services/discovery/municode_discovery.py` | discovery artifacts when wired | classify as structured/scrape/contextual/backlog in source catalog |
| CKAN/ArcGIS/Socrata/static files | backend/docs/scripts | partial/POC or absent from runtime | `docs/poc/source-expansion/`; verification scripts where present | not canonical until source catalog and ingest proof exist | do not count as integrated until active runtime path writes auditable rows/artifacts |
| Ingestion/persistence | backend/storage | canonical | `backend/db/postgres_client.py`; `backend/services/ingestion_service.py`; `backend/services/storage/s3_storage.py` | `raw_scrapes`, `legislation`, `impacts`, `document_chunks`, MinIO objects | persisted/read-back proof for rows, MinIO objects, content hashes, pgvector chunks |
| Domain bridge storage | backend | canonical-new candidate, not final analysis | `backend/services/pipeline/domain/storage.py`; `backend/services/pipeline/domain/models.py`; migrations `003`, `008` | `pipeline_runs`, `pipeline_steps`, `search_result_snapshots`, `content_artifacts`, `pipeline_command_results` | no in-memory fallback in production proof; idempotent replay and partial-write drills; prove handoff into `AnalysisPipeline` before calling it final product analysis |
| Retrieval/RAG | backend | canonical | `backend/services/retrieval/`; `backend/services/legislation_research.py` (`_retrieve_bill_context`) | `document_chunks` / pgvector | embedding dimension guard and proof chunks derive from canonical artifacts |
| Economic analysis orchestration | backend | authoritative | `backend/services/llm/orchestrator.py` (`AnalysisPipeline.run`, `_research_step`, `_generate_step`, `_review_step`, `_refine_step`, `_apply_wave1_quantification`, `_apply_fail_closed_review_gates`) | `pipeline_runs`, `pipeline_steps`, `impacts.evidence`, command result JSON | new package must compose/wrap this path before replacing anything |
| Evidence gates | backend | authoritative | `backend/services/llm/evidence_gates.py`; `backend/schemas/analysis.py` | `SufficiencyBreakdown`, `ImpactGateSummary`, `SufficiencyState` | `GateReport` must wrap/project or explicitly migrate these semantics; no dual authority |
| Evidence adapter | backend | canonical | `backend/services/llm/evidence_adapter.py` | persisted impact evidence payloads | package builder reuses adapter concepts unless replacement is justified |
| Economic evidence cards | backend | POC/contract candidate | `backend/schemas/economic_evidence.py` | no proven durable contract yet | prove table or queryable JSONB storage for cards and gate reports |
| Assumption registry | backend | POC/contract candidate | `backend/services/economic_assumptions.py` | not runtime-authoritative | migrate `WAVE2_*` literature and enforce staleness in runtime gates |
| Admin/glassbox API | backend | active but incomplete for cards | `backend/routers/admin.py`; `backend/services/glass_box.py` | run/step/evidence refs | expose package status, blocking gate, card refs, storage refs, provenance |
| Frontend admin display | frontend | active read-only display | `frontend/src/components/admin/PipelineStatusPanel.tsx`; `frontend/src/app/admin/audits/trace/[id]/page.tsx`; `frontend/src/app/api/admin/pipeline-runs/` | Next API routes and backend admin API | remove or disable mock fallback in evidence-critical flows; render card-level package status |

## Source-To-Frontend Trace

Current final public output follows this path when the full analysis pipeline is
run:

1. Scrapers or manual/rerun scripts produce bill text and metadata.
2. `PostgresDB.store_legislation(...)` writes or updates `legislation`.
3. `PostgresDB.create_raw_scrape(...)` plus `IngestionService.process_raw_scrape(...)`
   write `raw_scrapes`, optional `storage_uri`, and `document_chunks`.
4. `AnalysisPipeline.run(...)` reads latest raw scrape/vector stats, calls
   `LegislationResearchService`, logs `pipeline_steps`, and persists final
   `pipeline_runs.result`.
5. `_complete_pipeline_run(...)` updates `legislation` and calls
   `PostgresDB.store_impacts(...)`.
6. Public frontend reads `/legislation/{jurisdiction}` and
   `/legislation/{jurisdiction}/{bill_number}` through `frontend/src/lib/api.ts`.
7. `DashboardPage`, `BillDetailPage`, and `ImpactCard` render the final impact
   cards, sufficiency banners, evidence excerpts, and percentile sliders.

Current admin/glassbox output follows a separate read-model path:

1. `pipeline_runs`, `pipeline_steps`, `raw_scrapes`, `document_chunks`, and
   domain-bridge command tables are read by `backend/routers/admin.py` and
   `backend/services/glass_box.py`.
2. `PipelineStatusPanel` displays jurisdiction/source-family status, counts,
   freshness, latest analysis status, and links to Windmill/audit traces.
3. Some Next admin proxy routes still return mock data when the backend is
   unavailable; do not use those mocks as verification evidence.

## Next Product Gap

The highest-leverage product POC is not another isolated provider bakeoff. It is
the handoff from scraped/structured evidence packages into canonical economic
analysis:

- build a package from real scraped and structured artifacts,
- persist and read it back across Postgres, MinIO, pgvector, and admin APIs,
- project it into existing `EvidenceEnvelope`, `ImpactEvidence`,
  `SufficiencyBreakdown`, `ImpactMode`, `ScenarioBounds`, and assumption
  concepts,
- run direct, indirect, and secondary-research-required cases through the
  canonical analysis path or a deliberately documented adapter,
- prove the frontend/admin read models show the resulting truth without
  recomputation or mock fallback.

## Reuse / Extend / Retire

Reuse:

- `AnalysisPipeline` step graph and fail-closed review gates.
- `LegislationResearchService` for research/RAG/web assembly.
- `SufficiencyBreakdown`, `ImpactGateSummary`, `SufficiencyState`, `ImpactMode`, `SourceTier`, `ScenarioBounds`.
- Existing `pipeline_runs`, `pipeline_steps`, `raw_scrapes`, `legislation`, `document_chunks`, MinIO storage, and admin/glassbox surfaces.
- `PipelineDomainBridge` as the Windmill boundary candidate.

Extend:

- Provider identity and ranking metadata across search -> read -> evidence card -> final package.
- Source catalog for structured sources with access/cadence/coverage/economic-usefulness fields.
- Storage proof for package cards/gate reports across Postgres, MinIO, and pgvector.
- Admin/frontend read models for package-quality and economic-analysis sufficiency.
- Runtime assumption staleness enforcement.

Retire or demote:

- Direct-storage Windmill as a canonical architecture target.
- Any frontend mock fallback that can hide backend evidence/package failures.
- Any parallel gate taxonomy after the wrap/replace decision is made.

## Required Agent Routing

Before proposing a new Affordabot pipeline/economic-analysis schema or POC, agents must read:

1. This brownfield map.
2. `docs/architecture/2026-04-15-economic-literature-inventory.md`.
3. `docs/specs/2026-04-14-evidence-package-dependency-lockdown.md`.
4. The current code for every stale-if path relevant to their change.

If an agent introduces a new package/gate/storage concept without explaining how it composes with the mapped canonical path, that is a review finding.
