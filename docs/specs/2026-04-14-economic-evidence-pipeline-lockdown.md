# 2026-04-14 Economic Evidence Pipeline Lockdown (bd-2agbe.1)

## Status

Draft implementation spec for `bd-2agbe.1`, intended as the source contract for `bd-2agbe.2` to `bd-2agbe.7`.

## Why This Spec Exists

Current search/reader hardening proves whether official artifacts can be found and parsed. It does not fully prove that downstream economic analysis is decision-grade and auditable.

This spec makes quality attribution explicit across stages so provider quality, source quality, and economic-model quality are not conflated.

## Dependency Chain (Quality Gates)

The pipeline must treat these as distinct gates with independent pass/fail evidence:

1. `search_recall`: provider/query fanout surfaces candidate artifacts.
2. `reader_substance`: chosen artifacts yield sufficient text substance.
3. `artifact_classification`: backend distinguishes concrete artifacts from portals/boilerplate.
4. `evidence_extraction`: text is normalized into `EvidenceCard` artifacts.
5. `parameterization`: required economics parameters become `ParameterCard` artifacts.
6. `assumption_selection`: missing values are mapped to explicit, applicability-constrained `AssumptionCard` records.
7. `quantification`: deterministic formula execution yields validated bounds via `ModelCard`.
8. `llm_explanation`: LLM explains from structured artifacts only.

`GateReport` is the canonical run-level object for stage verdicts, blocker attribution, and audit notes.

## Boundary Options Still Open

### Option A: Windmill-max orchestration + backend domain commands
- Windmill owns DAG control, retries, branch routing, schedule/fanout.
- Backend owns economic/product invariants and persistence contracts.
- Preferred if artifact contracts remain coarse and stable.

### Option B: Backend-driven pipeline with Windmill trigger shell
- Backend owns most orchestration.
- Windmill reduced to cron/webhook trigger.
- Fallback if runtime orchestration friction overwhelms Option A.

### Option C: Windmill direct-storage/direct-ETL with thin backend
- Rejected for core economic logic by default.
- Acceptable only for commodity ingestion transforms.
- High risk of recreating hidden backend logic in scripts.

Decision rule for lockdown:
- Choose A if evidence contracts + registry + gate reports prove stable.
- Choose B only if live orchestration evidence shows A is operationally unstable.
- Do not choose C for core economics unless moat steps become demonstrably commodity.

## Canonical Artifact Contracts (This Wave)

Implemented in [backend/schemas/economic_evidence.py](/tmp/agents/bd-2agbe.1/affordabot/backend/schemas/economic_evidence.py):

- `EvidenceCard`: URL, type, content hash, excerpt, retrieval time, provenance/tier, optional artifact/reader IDs.
- `ParameterCard`: parameter state (`resolved|missing|ambiguous|unsupported`) with required evidence fields for resolved values.
- `AssumptionCard`: bounded low/central/high with applicability tags, source, confidence, version, staleness.
- `ModelCard`: mechanism family + formula + parameter/assumption IDs + scenario bounds + arithmetic/unit checks.
- `GateReport`: per-stage results, blocking gate, failure codes, artifact counts, unsupported claim count, manual audit notes.

These contracts are intentionally backend-owned and JSON-serializable for Windmill/read-model transport.

## Assumption Registry Contract (This Wave)

Implemented in [backend/services/economic_assumptions.py](/tmp/agents/bd-2agbe.1/affordabot/backend/services/economic_assumptions.py):

- Registry families:
  - `direct_fiscal`
  - `compliance_cost`
  - `fee_or_tax_pass_through`
  - `adoption_take_up`
- Assumptions are applicability-tag constrained and versioned.
- Registry returns a fail-closed resolution when tags do not match.
- No generic fallback assumption is allowed.

## Existing Codepaths This Spec Extends

- [backend/schemas/analysis.py](/tmp/agents/bd-2agbe.1/affordabot/backend/schemas/analysis.py): existing impact-level sufficiency states, failure codes, scenario bounds.
- [backend/services/llm/evidence_gates.py](/tmp/agents/bd-2agbe.1/affordabot/backend/services/llm/evidence_gates.py): deterministic gate checks for quantification eligibility.
- [backend/services/llm/orchestrator.py](/tmp/agents/bd-2agbe.1/affordabot/backend/services/llm/orchestrator.py): canonical step sequence and quantification flow.
- [backend/services/legislation_research.py](/tmp/agents/bd-2agbe.1/affordabot/backend/services/legislation_research.py): current parameter extraction and wave2 literature heuristics to be migrated onto the explicit registry contract.
- [docs/bd-affordabot-1mz/EPIC_PLAN.md](/tmp/agents/bd-2agbe.1/affordabot/docs/bd-affordabot-1mz/EPIC_PLAN.md): prior evidence-envelope direction; this spec extends into economics-grade artifacts.

## Minimum Validation For This Subtask

Required test evidence:

- Contract serialization and required field enforcement:
  - [backend/tests/schemas/test_economic_evidence.py](/tmp/agents/bd-2agbe.1/affordabot/backend/tests/schemas/test_economic_evidence.py)
- Assumption registry match and fail-closed mismatch behavior:
  - [backend/tests/services/test_economic_assumptions.py](/tmp/agents/bd-2agbe.1/affordabot/backend/tests/services/test_economic_assumptions.py)
- Existing deterministic sufficiency tests remain green:
  - [backend/tests/services/llm/test_evidence_gates.py](/tmp/agents/bd-2agbe.1/affordabot/backend/tests/services/llm/test_evidence_gates.py)

## Non-Goals For bd-2agbe.1

- No verifier/corpus implementation (`bd-2agbe.4` and `bd-2agbe.5`).
- No admin/read-model persistence wiring (`bd-2agbe.6`).
- No final architecture lock decision (`bd-2agbe.7`).

## Next Wave Handoff

`bd-2agbe.2` and `bd-2agbe.3` should:
- Adopt these contracts directly (avoid parallel schema variants).
- Move wave2 hard-coded assumptions to registry-driven selection.
- Emit `GateReport` and artifact IDs through pipeline outputs for verifier/read-model consumption.
