# Full Pipeline Code Audit Results

Beads: `bd-3wefe.9`

PR: <https://github.com/stars-end/affordabot/pull/436>

Command:

```bash
dx-review run \
  --beads bd-3wefe.9 \
  --worktree /tmp/agents/bd-2agbe.1/affordabot \
  --pr https://github.com/stars-end/affordabot/pull/436 \
  --prompt-file /tmp/agents/bd-2agbe.1/affordabot/docs/reviews/2026-04-15-full-pipeline-code-audit-dx-review-prompt.md \
  --gemini \
  --read-only-shell \
  --wait \
  --timeout-sec 1800
```

## Run Outcome

`dx-review doctor --worktree /tmp/agents/bd-2agbe.1/affordabot --gemini` passed for:

- `claude-code-review`
- `cc-glm-review`
- `gemini-burst`

The review run itself produced mixed-quality output:

- Claude/Opus completed and produced a substantive code audit.
- GLM completed with exit code 0, but the captured log did not include substantive review findings.
- Gemini launched and explored the codebase, but did not finish within the 1800 second wrapper timeout. It was manually stopped after the required Claude/GLM quorum had completed.

Important DX caveat:

`dx-review summarize --beads bd-3wefe.9 --gemini` reported `effective quorum: 3/3 completed`, but this is misleading because the Gemini lane was manually stopped and the GLM lane had no substantive captured review body. Treat the reliable substantive review evidence as Claude/Opus only, with GLM/Gemini usage friction documented below.

Local artifacts:

- `/tmp/dx-review/bd-3wefe.9/summary.md`
- `/tmp/dx-review/bd-3wefe.9/summary.json`
- `/tmp/dx-runner/claude-code/bd-3wefe.9.claude.log`
- `/tmp/dx-runner/cc-glm/bd-3wefe.9.glm.log`
- `/tmp/dx-runner/gemini/bd-3wefe.9.gemini.log`

## Claude/Opus Findings

Verdict: `approve_with_changes`

### F1: Dual gate taxonomy divergence risk

New `GateReport` / `GateStageResult` / `GateVerdict` / `QualityGateStage` types in `backend/schemas/economic_evidence.py` define a parallel gate taxonomy to the existing `SufficiencyBreakdown` / `ImpactGateSummary` / `SufficiencyState` system in `backend/schemas/analysis.py` and `backend/services/llm/evidence_gates.py`.

Risk:

Two independent gate systems can diverge or disagree.

Required response:

`bd-3wefe.1` must declare whether `GateReport` replaces, wraps, or composes the existing sufficiency system. No dual authoritative gate taxonomy.

### F2: `AssumptionRegistry` is disconnected from the live pipeline

`backend/services/economic_assumptions.py` is currently POC/test wired. The live pipeline still uses `WAVE2_PASS_THROUGH_LITERATURE` and `WAVE2_ADOPTION_ANALOGS` in `backend/services/legislation_research.py`.

Risk:

Two sources of truth for pass-through/take-up/compliance assumptions.

Required response:

`bd-3wefe.11` must reconcile `WAVE2_*` constants with new `AssumptionCard` profiles and define the migration boundary.

### F3: New card schemas are not persisted

`EvidenceCard`, `ParameterCard`, `AssumptionCard`, `ModelCard`, and `GateReport` have no explicit durable storage path yet.

Risk:

Schemas enforce invariants only at construction time, not across replay, admin review, or analysis provenance.

Required response:

`bd-3wefe.10` must prove either explicit tables or a documented, queryable JSONB storage contract over existing tables.

### F4: Hardcoded assumption values lack staleness enforcement

New assumption profiles include `stale_after_days`, but no runtime gate consumes that metadata.

Risk:

Stale assumptions can silently support decision-grade analysis.

Required response:

`bd-3wefe.5` must enforce assumption staleness by warning or failing closed according to the package contract.

### F5: Search provider quality variance is not gated

Provider selection can shift between Z.ai, SearXNG, Tavily, Exa, and fallback modes, but provider identity and recall quality are not consistently carried into downstream evidence.

Risk:

Provider quality regressions silently change final analysis quality.

Required response:

`bd-3wefe.2` must preserve provider identity through result/candidate artifacts and report provider/query-family metrics.

### F6: Z.ai reader substance is not gated early enough

Live reader probes show portal/boilerplate extraction risk. Existing placeholder checks happen later in analysis, not before ingestion/chunking.

Risk:

Low-substance reader output can pollute the vector store and downstream package generation.

Required response:

`bd-3wefe.2` and `bd-3wefe.10` should include reader-substance gates before evidence packaging and storage acceptance.

### F7: Verification scripts are fixture/replay heavy

The POC verification scripts are fixture/replay-oriented.

Risk:

They are useful architecture evidence but not live integration coverage.

Required response:

Keep live/storage/Windmill proof in separate gates (`bd-3wefe.10`, `bd-3wefe.12`) and do not count replay-only scripts as production integration evidence.

## Existing Pipeline Map From Review

Claude identified these existing capabilities that must be reused or explicitly migrated:

- Source discovery/scrape: `backend/services/scraper/*`, `backend/services/discovery/*`
- Structured state source: `backend/services/scraper/california_state.py`
- Storage: `backend/db/postgres_client.py`, `backend/services/storage/s3_storage.py`, `backend/services/retrieval/*`
- Economic analysis: `backend/services/llm/orchestrator.py`, `backend/services/legislation_research.py`, `backend/services/llm/evidence_gates.py`, `backend/services/llm/evidence_adapter.py`
- Windmill/domain bridge: `backend/services/pipeline/domain/*`
- Admin/glassbox: `backend/routers/admin.py`, `backend/services/glass_box.py`

Already-built economic pieces:

- `SufficiencyBreakdown` and `assess_sufficiency()` should be reused or explicitly wrapped.
- `ImpactMode` should be reused and mapped to mechanism families.
- `WAVE2_PASS_THROUGH_LITERATURE` and `WAVE2_ADOPTION_ANALOGS` must be migrated, not ignored.
- `ScenarioBounds` and `SourceTier` already exist and should not be reinvented.
- New card schemas and `AssumptionRegistry` are POC-only until wired into the live pipeline and persistence path.

## DX Review Friction

Observed issues:

- `dx-review summarize` did not extract verdict/findings from reviewer logs.
- `dx-review summarize` counted a manually stopped Gemini lane as completed.
- GLM exited successfully but produced no substantive captured review text beyond wrapper metadata.
- Gemini repeatedly logged missing `/Users/fning/.gemini/AGENTS.md`.
- Gemini hit Serena MCP read/symbol errors during exploration and did not finish within 1800 seconds.
- Read-only enforcement reported `unavailable`.
- All three lanes reported `mutation_count=1`; no repo mutations were visible besides pre-existing `.serena/project.yml`, but this should be investigated because the run was read-only by contract.

## Plan Changes Already Applied

The dependency spec was patched after this audit to require:

- `bd-3wefe.1`: no dual authoritative gate taxonomy.
- `bd-3wefe.2`: provider identity and per-provider quality metrics survive downstream.
- `bd-3wefe.4`: reuse existing `ImpactMode`, `SourceTier`, sufficiency gate, and evidence adapter concepts unless a concrete replacement is justified.
- `bd-3wefe.10`: card persistence via explicit tables or documented queryable JSONB contract.
- `bd-3wefe.5`: assumption staleness enforcement.
- `bd-3wefe.11`: `WAVE2_*` migration into assumption/model cards.

## Current Recommendation

Do not proceed directly to package implementation.

Next work should be:

1. `bd-3wefe.11`: economic literature/assumption audit, focused on reconciling `WAVE2_*` with `AssumptionCard`.
2. `bd-3wefe.1`: package spec, explicitly composing or replacing existing sufficiency gates.
3. `bd-3wefe.2/.3`: source quality POCs using provider identity, source catalog, and reader-substance gates.

`bd-3wefe.9` is partially satisfied from a technical-audit standpoint, but not fully clean as a dx-review workflow because GLM/Gemini output quality was not usable.

## Targeted High-Effort Audit Supplement

After the mixed-quality `dx-review` run, two targeted `gpt-5.3-codex-high` read-only audits were dispatched to reduce the risk of missing already-built brownfield pipeline pieces.

### Agent A: Data moat / ingestion / storage / Windmill

Verdict:

- The architecture has one production-used backend path, one intended domain-boundary path, and one POC duplication path.
- `PipelineDomainBridge` and backend domain commands are the right Windmill boundary candidate.
- Direct-storage Windmill should not become canonical architecture; keep it as a test harness only if useful.
- Provider identity, ranking metadata, storage atomicity, and structured-source cataloging remain under-proven.

Key mapped paths:

- `backend/services/llm/web_search_factory.py`
- `backend/services/pipeline/domain/commands.py`
- `backend/clients/web_reader_client.py`
- `backend/services/legislation_research.py`
- `backend/services/llm/orchestrator.py`
- `backend/services/pipeline/domain/bridge.py`
- `backend/services/scraper/california_state.py`
- `backend/services/scraper/san_jose.py`
- `backend/services/scraper/registry.py`
- `backend/services/discovery/municode_discovery.py`
- `backend/db/postgres_client.py`
- `backend/services/ingestion_service.py`
- `backend/services/storage/s3_storage.py`
- `backend/services/pipeline/domain/storage.py`
- `backend/services/pipeline/domain/models.py`
- `ops/windmill/f/affordabot/trigger_cron_job.py`
- `ops/windmill/f/affordabot/pipeline_daily_refresh_domain_boundary.py`
- `ops/windmill/f/affordabot/pipeline_daily_refresh_direct_storage.py`

### Agent B: Economic evidence / gates / literature / frontend-admin

Verdict:

- Migrate and compose; do not replace.
- `AnalysisPipeline`, `LegislationResearchService`, `SufficiencyBreakdown`, `ImpactGateSummary`, and `evidence_adapter` are the authoritative economic-analysis path.
- `GateReport` and card schemas should initially project/wrap existing runtime outputs.
- `AssumptionRegistry` is promising but not yet runtime-authoritative; `WAVE2_*` constants remain live and must be migrated.
- Frontend/admin visibility exists but does not yet render card-level package contracts, and mock fallbacks can mask backend truth.

Key mapped paths:

- `backend/main.py`
- `backend/services/llm/orchestrator.py`
- `backend/services/llm/evidence_gates.py`
- `backend/services/llm/evidence_adapter.py`
- `backend/services/legislation_research.py`
- `backend/services/llm/web_search_factory.py`
- `backend/schemas/analysis.py`
- `backend/schemas/economic_evidence.py`
- `backend/services/economic_assumptions.py`
- `backend/services/scraper/california_state.py`
- `backend/services/pipeline/domain/bridge.py`
- `backend/services/pipeline/domain/commands.py`
- `backend/routers/admin.py`
- `frontend/src/components/admin/PipelineStatusPanel.tsx`
- `frontend/src/app/admin/audits/trace/[id]/page.tsx`
- `frontend/src/app/api/admin/pipeline-runs/route.ts`
- `frontend/src/app/api/admin/pipeline-runs/[id]/route.ts`

### Durable map artifacts created from supplement

- `docs/architecture/2026-04-15-affordabot-pipeline-brownfield-map.md`
- `docs/architecture/2026-04-15-economic-literature-inventory.md`

These are now required routing artifacts for future Affordabot pipeline/economic-analysis work. They include stale-if paths so future agents know when the map must be refreshed instead of trusted blindly.
