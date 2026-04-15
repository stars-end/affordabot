# 2026-04-15 Economic Assumption Reconciliation (bd-3wefe.11)

Status: code-grounded audit

Scope: reconcile current runtime economics (`AnalysisPipeline` + `LegislationResearchService` + deterministic sufficiency gates) with candidate package-card schemas and assumption registry work.

## What Is Canonical Runtime Now

The canonical runtime economic path today is:

1. `backend/services/llm/orchestrator.py::AnalysisPipeline.run`
2. `backend/services/llm/orchestrator.py::_research_step`
3. `backend/services/legislation_research.py::LegislationResearchService.research`
4. `backend/services/llm/evidence_gates.py::assess_sufficiency`
5. `backend/services/llm/orchestrator.py::_apply_wave1_quantification`
6. `backend/services/llm/orchestrator.py::_apply_fail_closed_review_gates`
7. `backend/schemas/analysis.py::LegislationAnalysisResponse` payload persisted/read downstream

Within that runtime:

- Wave2 literature and analog assumptions are currently sourced from:
  - `backend/services/legislation_research.py::WAVE2_PASS_THROUGH_LITERATURE`
  - `backend/services/legislation_research.py::WAVE2_ADOPTION_ANALOGS`
- Those values become parameter candidates in:
  - `_derive_pass_through_prerequisite`
  - `_derive_adoption_prerequisite`
- Deterministic eligibility and fail-closed behavior currently depend on:
  - `backend/services/llm/evidence_gates.py::assess_impact_sufficiency`
  - `backend/services/llm/evidence_gates.py::assess_sufficiency`
  - `backend/services/llm/evidence_gates.py::_wave2_literature_confidence_valid`

## What Should Move Into PolicyEvidencePackage Card Metadata

Card-level package metadata should wrap what runtime already emits instead of replacing it first:

1. Evidence provenance:
   - map runtime evidence/envelopes to `EvidenceCard` fields in
     `backend/schemas/economic_evidence.py::EvidenceCard`
2. Parameter provenance and gating:
   - map `ParameterResolutionOutput` values from
     `backend/schemas/analysis.py::ParameterResolutionOutput` to
     `ParameterCard`
3. Assumption provenance:
   - represent wave2 constants and registry profiles as versioned
     `AssumptionCard` records with applicability and staleness metadata
4. Deterministic arithmetic and mode outcome:
   - project `ImpactMode`, `ScenarioBounds`, validation, and failures from
     `LegislationImpact` into `ModelCard`
5. Gate trace:
   - project existing `SufficiencyBreakdown` / `ImpactGateSummary` into
     `GateReport` while preserving original `FailureCode` semantics

This gives package-level auditability without creating a second runtime decision path.

## What Is Stale, Unsupported, or Over-Generalized

1. `backend/services/economic_assumptions.py::AssumptionRegistry` is not wired into
   canonical runtime call paths; it is currently a candidate catalog plus tests.
2. `stale_after_days` exists in `AssumptionCard` and registry profiles but is not
   enforced by `assess_sufficiency` or `AnalysisPipeline` runtime flow.
3. Wave2 constants in `WAVE2_PASS_THROUGH_LITERATURE` and
   `WAVE2_ADOPTION_ANALOGS` are useful but broad; they require explicit
   applicability tags and jurisdiction/scope constraints before decision-grade
   indirect-cost claims.
4. `backend/schemas/economic_evidence.py::QualityGateStage` / `GateVerdict` define
   a parallel taxonomy to `SufficiencyBreakdown`; this is unresolved governance,
   not runtime authority today.

## Source-Bound Assumption Requirements Before Quantitative Analysis

Before decision-grade quantitative output, assumptions must be source-bound and
gated with:

1. stable assumption id/version
2. source URL and excerpt
3. mechanism-family applicability tags
4. jurisdiction/scope statement
5. unit and low/base/high bounds
6. staleness policy (`stale_after_days` + evaluated timestamp)
7. confidence with rationale

The current runtime already has partial support for this structure in wave2
parameter candidate metadata and in `AssumptionCard` schema shape; missing piece
is canonical runtime enforcement and persistence.

## Required Blocking Gates for Unsupported Indirect-Cost Claims

To block unsupported indirect-cost claims, runtime/package must fail-closed when
any of these are true:

1. no source-bound assumption card for the selected indirect mechanism
   (`pass_through_incidence` or `adoption_take_up`)
2. assumption card stale under policy and no approved refresh
3. assumption applicability tags do not match bill/context tags
4. cited evidence lacks numeric and fiscal support for quantified claims
   (already partially enforced via `supports_quantified_evidence` and
   deterministic review gates)
5. parameter resolution falls back to failed hierarchy or unverifiable status

## Do Not Duplicate (Already Exists)

These pieces already exist and should be reused:

- deterministic gate/failure semantics:
  `backend/schemas/analysis.py::{FailureCode,SufficiencyState,SufficiencyBreakdown,ImpactGateSummary}`
- runtime mode and quantification envelope:
  `backend/schemas/analysis.py::{ImpactMode,ScenarioBounds,LegislationImpact}`
- runtime research + wave2 prerequisite extraction:
  `backend/services/legislation_research.py::LegislationResearchService`
- deterministic claim support suppression:
  `backend/services/llm/orchestrator.py::_apply_fail_closed_review_gates`

## Recommendations By Beads Task

### `bd-3wefe.1` (package contract)

- Make `GateReport` a projection/wrapper over canonical `SufficiencyBreakdown`
  and `ImpactGateSummary` first.
- Define one authority rule: analysis-schema gates decide runtime eligibility;
  package-schema gates mirror and expose that decision.

### `bd-3wefe.4` (package builder)

- Build cards from existing runtime artifacts and fields:
  - Evidence envelope -> `EvidenceCard`
  - Parameter resolution -> `ParameterCard`
  - Wave2 assumptions/registry profile -> `AssumptionCard`
  - Mode/scenario/failure outputs -> `ModelCard`
- Do not introduce new independent formula/gate logic in builder.

### `bd-3wefe.5` (sufficiency verifier)

- Add deterministic staleness and applicability checks for assumption cards
  before quantification.
- Fail closed for indirect modes when source-bound assumption cards are absent,
  stale, or inapplicable.

### `bd-3wefe.6` (mechanism + secondary research)

- Test direct and indirect mechanisms using canonical mode/failure structures.
- Require secondary-research packages to emit source-bound parameter/assumption
  cards before allowing quantified indirect-cost output.
- Explicitly verify unsupported-claim rejection through existing deterministic
  review gates plus package-level blocking reason.

## Validation Evidence Used In This Audit

Primary source files inspected:

- `backend/services/llm/orchestrator.py`
- `backend/services/legislation_research.py`
- `backend/services/llm/evidence_gates.py`
- `backend/schemas/analysis.py`
- `backend/schemas/economic_evidence.py`
- `backend/services/economic_assumptions.py`
- `backend/scripts/verification/verify_economic_evidence_gate_matrix.py`
- `backend/scripts/verification/verify_economic_readiness_overlay.py`
- `backend/tests/services/llm/test_evidence_gates.py`
- `backend/tests/services/test_economic_assumptions.py`
- `backend/tests/schemas/test_economic_evidence.py`

Spec change requests discovered here were recorded as recommendations in this
doc, per lane ownership constraints.
