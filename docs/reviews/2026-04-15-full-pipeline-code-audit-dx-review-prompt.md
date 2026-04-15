# dx-review Prompt: Full Affordabot Pipeline Code Audit

Beads: `bd-3wefe.9`

Review type: code review

Repository: `affordabot`

## Goal

Perform a findings-first code review of the existing Affordabot raw/structured-data-to-analysis pipeline before new evidence-package implementation proceeds.

The founder's concern is that new architecture work may be missing or duplicating existing code. Your job is to map what already exists, identify correctness risks, and recommend what future implementation should reuse, delete, or extend.

## Required Scope

Review the full path from source discovery to final user-facing analysis:

- Raw scrape ingestion, artifact promotion, canonical document identity, raw scrape storage, and chunking.
- Structured source paths and any existing Legistar, LegInfo, OpenStates, CKAN, ArcGIS, or official raw-file integration code.
- Search providers and fallback behavior: private SearXNG, Tavily, Exa, deprecated Z.ai search, ranking, portal skipping, query fanout, and freshness gates.
- Z.ai reader usage, reader-substance gates, reader artifacts, and failure handling.
- Postgres, pgvector, MinIO, content hashes, replay/idempotency, partial-write behavior, and read APIs.
- `AnalysisPipeline`, `LegislationResearchService`, evidence/economic schemas, deterministic gates, assumption registry, formula/model-card logic, and LLM analysis.
- Economic literature, constants, assumptions, elasticities, pass-through/take-up/compliance-cost values, formulas, and mechanism mappings already integrated in code or docs. Identify source citations where present and hard-coded/unsupported values where not.
- Secondary research behavior during economic analysis, if present.
- Admin endpoints, frontend/admin display, glassbox views, and whether frontend recomputes business logic.
- Windmill/domain bridge paths versus canonical backend analysis paths.

## Required Output

Use code-review style. Findings first, ordered by severity.

For each finding, include:

- Severity.
- Exact file path and line reference where possible.
- Why it matters for decision-grade economic analysis.
- Whether the issue is a correctness bug, architecture boundary risk, duplication risk, data-quality risk, storage/auditability risk, or missing-test risk.
- Concrete recommendation.

Also include these sections:

1. Existing Pipeline Map
   - Source discovery/read path.
   - Structured source path.
   - Storage path.
   - Economic analysis path.
   - Final LLM analysis/final result path.
   - Admin/frontend read path.

2. Already-Built Economic Capabilities
   - What exists today and should be reused.
   - What exists but appears disconnected from current Windmill/domain flow.
   - What is only POC/test code.

3. Storage Truth Table
   - Postgres truth.
   - MinIO raw/intermediate artifacts.
   - pgvector derived retrieval state.
   - Admin/read API visibility.
   - Any unprobeable or unverified storage layer.

4. Search and Reader Quality Risks
   - SearXNG quality at each intermediate step.
   - Tavily/Exa roles.
   - Z.ai reader robustness.
   - Whether second-round economic research search already exists.

5. Implementation Guidance
   - What `bd-3wefe.1` should specify.
   - What `bd-3wefe.2/.3` should test.
   - What `bd-3wefe.4/.5/.10/.12` should build or avoid.
   - Whether any planned Beads tasks should be renamed, split, or reordered.

6. Economic Literature Inventory
   - Existing assumptions/constants/formulas by code path.
   - Source citations, dates, units, ranges, and applicability tags where available.
   - Which assumptions can support direct costs, indirect mechanisms, and secondary research.
   - Which values must migrate into explicit `AssumptionCard` or `ModelCard` records.

## Verdict

Return one of:

- `approve_plan`
- `approve_with_changes`
- `revise_plan`
- `block_plan`

The plan should be blocked only if there is a high-confidence existing implementation that makes the proposed path materially wrong, or if required evidence cannot be gathered with the current repo/runtime.

## Suggested Command

```bash
dx-review run \
  --beads bd-3wefe.9 \
  --worktree /tmp/agents/bd-2agbe.1/affordabot \
  --pr https://github.com/stars-end/affordabot/pull/436 \
  --prompt-file docs/reviews/2026-04-15-full-pipeline-code-audit-dx-review-prompt.md \
  --gemini \
  --read-only-shell \
  --wait \
  --timeout-sec 1800
```
