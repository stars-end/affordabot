# 2026-04-15 Economic Literature Inventory

Status: working draft for `bd-3wefe.11`

Purpose: prevent economic-analysis knowledge from being scattered across docs, constants, tests, and POC schemas. This file is the routing index for assumptions and literature already present in Affordabot.

## Freshness Contract

Treat this inventory as stale if any of these paths change:

- `backend/services/legislation_research.py`
- `backend/services/llm/orchestrator.py`
- `backend/services/llm/evidence_gates.py`
- `backend/services/economic_assumptions.py`
- `backend/schemas/analysis.py`
- `backend/schemas/economic_evidence.py`
- `backend/services/llm/evidence_adapter.py`
- `backend/tests/services/llm/test_evidence_gates.py`
- `backend/tests/services/test_economic_assumptions.py`
- `backend/tests/schemas/test_economic_evidence.py`
- `backend/scripts/verification/verify_economic_evidence_gate_matrix.py`
- `backend/scripts/verification/verify_economic_readiness_overlay.py`
- `docs/specs/2026-03-24-mechanism-backed-quantification.md`
- `docs/specs/2026-04-14-economic-evidence-pipeline-lockdown.md`
- `docs/research/2026-04-14-economic-evidence-architecture-lockdown.md`
- `docs/poc/economic-analysis-boundary/`
- `docs/poc/economic-evidence-quality/`

## Current Verdict

The live economic-analysis path already contains literature-backed assumptions and deterministic gate logic. The next implementation must migrate and govern them; it must not create a second assumption/gate authority.

Canonical runtime today:

- `backend/services/llm/orchestrator.py::AnalysisPipeline.run`
- `backend/services/llm/orchestrator.py::_research_step`
- `backend/services/llm/orchestrator.py::_apply_wave1_quantification`
- `backend/services/llm/orchestrator.py::_apply_fail_closed_review_gates`
- `backend/services/legislation_research.py::LegislationResearchService.research`
- `backend/services/legislation_research.py::WAVE2_PASS_THROUGH_LITERATURE`
- `backend/services/legislation_research.py::WAVE2_ADOPTION_ANALOGS`
- `backend/services/legislation_research.py::_derive_pass_through_prerequisite`
- `backend/services/legislation_research.py::_derive_adoption_prerequisite`
- `backend/services/llm/evidence_gates.py::assess_sufficiency`
- `backend/schemas/analysis.py::SufficiencyBreakdown`
- `backend/schemas/analysis.py::ImpactGateSummary`

POC/contract candidate:

- `backend/services/economic_assumptions.py`:
  - `AssumptionRegistry`
  - `AssumptionProfile`
  - assumption profiles with `stale_after_days` (currently not consumed by runtime gating)
- `backend/schemas/economic_evidence.py`:
  - `EvidenceCard`, `ParameterCard`, `AssumptionCard`, `ModelCard`, `GateReport`
  - quality-stage taxonomy (`QualityGateStage`, `GateVerdict`) not yet wired into canonical `SufficiencyBreakdown` flow

Decision required by `bd-3wefe.11`:

1. Move runtime `WAVE2_*` values into versioned `AssumptionCard`/`ModelCard` records or explicitly document why a specific value remains runtime-local.
2. Enforce assumption staleness metadata in deterministic gating before quantification.
3. Ensure each quantitative output traces to source-bound parameter data, assumption/model cards, or fail-closed reasons.
4. Declare a single authoritative gate path: either wrap/project `SufficiencyBreakdown` into `GateReport`, or migrate in one direction with explicit deprecation.

## Inventory Template

Every assumption/literature entry carried forward must include:

| Field | Requirement |
| --- | --- |
| `assumption_id` | Stable ID suitable for `AssumptionCard` |
| `model_id` | Stable ID when assumption belongs to a reusable model |
| `runtime_path` | Exact file/symbol currently consuming it |
| `source_citation` | Paper/report/source URL or explicit `missing` |
| `source_date` | Publication or access date |
| `jurisdiction_scope` | geography/scope where applicable |
| `mechanism_family` | direct cost, compliance cost, supply effect, demand effect, take-up/adoption, pass-through, displacement, externality, other |
| `unit` | percent, dollars/unit, elasticity, multiplier, qualitative only, etc. |
| `range` | low/base/high when available |
| `applicability_tags` | policy domains and constraints |
| `stale_after_days` | staleness window or explicit no-staleness rationale |
| `confidence` | high/medium/low with reason |
| `decision_grade` | yes/no for quantitative analysis |
| `migration_action` | reuse, migrate, replace, retire, needs source |

## Runtime Economic Path Map (Source-Grounded)

| Layer | Canonical symbol | Role now | Notes |
| --- | --- | --- | --- |
| Research assembly | `backend/services/legislation_research.py::LegislationResearchService.research` | runtime | Builds `impact_candidates`, `parameter_candidates`, curated wave2 evidence, and a research sufficiency summary. |
| Wave2 pass-through | `backend/services/legislation_research.py::WAVE2_PASS_THROUGH_LITERATURE` and `_derive_pass_through_prerequisite` | runtime | Applies sector-cued pass-through rates and citations when tax/fee burden is detected. |
| Wave2 adoption | `backend/services/legislation_research.py::WAVE2_ADOPTION_ANALOGS` and `_derive_adoption_prerequisite` | runtime | Applies analog take-up and benefit values when eligibility/enrollment signals exist. |
| Pipeline orchestration | `backend/services/llm/orchestrator.py::AnalysisPipeline.run` | runtime | Persists canonical step outputs and invokes deterministic + LLM phases. |
| Deterministic sufficiency | `backend/services/llm/evidence_gates.py::assess_sufficiency` + `assess_impact_sufficiency` | runtime | Decides quantified vs qualitative path using retrieval, hierarchy, parameter, and validation gates. |
| Deterministic claim guard | `backend/services/llm/orchestrator.py::_apply_fail_closed_review_gates` | runtime | Blocks unsupported prose and unsupported quantified claims before final review pass. |
| Output contract | `backend/schemas/analysis.py::LegislationAnalysisResponse` and related models | runtime | Public/canonical analysis payload including `ImpactMode`, `ScenarioBounds`, `FailureCode`, and gate summaries. |
| Card schema candidates | `backend/schemas/economic_evidence.py::*Card`, `GateReport` | candidate | Strong contract types exist but are not yet canonical runtime persistence and gating authority. |
| Assumption registry candidate | `backend/services/economic_assumptions.py::AssumptionRegistry` | candidate | Structured and staleness-aware but currently disconnected from `AnalysisPipeline` runtime call path. |

## Known Runtime-Integrated Economic Assets

| Asset | Runtime path | Status | Required next action |
| --- | --- | --- | --- |
| Pass-through literature | `backend/services/legislation_research.py::WAVE2_PASS_THROUGH_LITERATURE` | runtime-authoritative constant | inventory citations/units/ranges; migrate to `AssumptionCard`/`ModelCard`; wire runtime lookup |
| Adoption analogs | `backend/services/legislation_research.py::WAVE2_ADOPTION_ANALOGS` | runtime-authoritative constant | inventory citations/coverage/applicability; migrate to assumption registry |
| Pass-through prerequisite derivation | `backend/services/legislation_research.py::_derive_pass_through_prerequisite` | runtime logic | preserve mechanism semantics when package cards are introduced |
| Adoption prerequisite derivation | `backend/services/legislation_research.py::_derive_adoption_prerequisite` | runtime logic | preserve mechanism semantics when package cards are introduced |
| Assumption registry | `backend/services/economic_assumptions.py::AssumptionRegistry` | POC/contract candidate | become runtime source or remain projection layer; no dual source of truth |

## Assumption/Literature Reconciliation Ledger

| assumption_id (proposed) | source (current) | mechanism_family | evidence scope | known range/unit | migration_action |
| --- | --- | --- | --- | --- | --- |
| `wave2.pass_through.housing.v1` | `WAVE2_PASS_THROUGH_LITERATURE["housing"]` | `pass_through_incidence` | academic literature; not bill-specific | `0.65` share (single point now) | migrate to `AssumptionCard`; add low/base/high bounds + applicability tags + stale policy |
| `wave2.pass_through.energy.v1` | `WAVE2_PASS_THROUGH_LITERATURE["energy"]` | `pass_through_incidence` | academic literature | `0.85` share | migrate to `AssumptionCard`; retain literature URL/excerpt and confidence |
| `wave2.pass_through.telecom.v1` | `WAVE2_PASS_THROUGH_LITERATURE["telecom"]` | `pass_through_incidence` | academic literature | `0.70` share | migrate to `AssumptionCard`; add explicit market-structure applicability |
| `wave2.adoption.rebate_program.v1` | `WAVE2_ADOPTION_ANALOGS["rebate_program"]` | `adoption_take_up` | curated analog benchmark | `take_up_rate=0.42`, `benefit_per_capita=750` | split into assumption card(s) + parameter defaults with source-bound constraints |
| `wave2.adoption.tax_credit_program.v1` | `WAVE2_ADOPTION_ANALOGS["tax_credit_program"]` | `adoption_take_up` | curated analog benchmark | `take_up_rate=0.58`, `benefit_per_capita=1200` | split into assumption card(s) + parameter defaults; enforce jurisdiction/applicability tags |
| `assumption_registry.direct_fiscal.annualization_factor.v1` | `AssumptionRegistry` | `direct_fiscal` | structured profile | low/base/high multiplier | keep as candidate; wire to runtime only when canonical selection/precedence is defined |
| `assumption_registry.compliance_cost.loaded_wage_multiplier.v1` | `AssumptionRegistry` | `compliance_cost` | structured profile | low/base/high multiplier | keep as candidate; avoid dual lookup with `WAVE2_*` until migration complete |

## Known Literature/Design Docs

- `docs/specs/2026-03-24-mechanism-backed-quantification.md`
- `docs/specs/2026-04-14-economic-evidence-pipeline-lockdown.md`
- `docs/research/2026-04-14-economic-evidence-architecture-lockdown.md`
- `docs/poc/economic-analysis-boundary/architecture_recommendation.md`
- `docs/poc/economic-evidence-quality/`

## Economic Quality Rubric

For `bd-3wefe.5`, `bd-3wefe.6`, and `bd-3wefe.8`, score each dimension 0/1/2. Require at least 11/14 and no critical zero in mechanism validity, parameter provenance, arithmetic integrity, or claim-evidence traceability.

| Dimension | Critical? | Pass bar |
| --- | --- | --- |
| Mechanism validity | yes | direct or indirect chain is causally coherent and policy-relevant |
| Parameter provenance coverage | yes | key numbers are source-bound, unit-checked, and reproducible |
| Assumption governance | no | applicability tags, version, confidence, and staleness are present |
| Model arithmetic integrity | yes | formula is transparent and low/base/high bounds are consistent |
| Uncertainty/sensitivity quality | no | final output explains drivers and sensitivity range |
| Claim-evidence traceability | yes | every quantitative claim traces to evidence or fails closed |
| Decision output quality | no | conclusion is usable while clearly stating constraints |

## Non-Negotiable Migration Rules

- Do not introduce a second authoritative assumption registry.
- Do not let hardcoded constants bypass staleness gates.
- Do not let LLM output invent quantitative values that are absent from evidence, parameter cards, or assumption cards.
- Do not treat general economic literature as jurisdiction-specific evidence unless applicability is explicit.
- Do not hide secondary research inside an LLM prompt; it must become a separately auditable evidence package.
