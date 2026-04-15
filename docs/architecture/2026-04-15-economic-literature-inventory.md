# 2026-04-15 Economic Literature Inventory

Status: working draft for `bd-3wefe.11`

Purpose: prevent economic-analysis knowledge from being scattered across docs, constants, tests, and POC schemas. This file is the routing index for assumptions and literature already present in Affordabot.

## Freshness Contract

Treat this inventory as stale if any of these paths change:

- `backend/services/legislation_research.py`
- `backend/services/economic_assumptions.py`
- `backend/services/llm/orchestrator.py`
- `backend/services/llm/evidence_gates.py`
- `backend/schemas/analysis.py`
- `backend/schemas/economic_evidence.py`
- `docs/specs/2026-03-24-mechanism-backed-quantification.md`
- `docs/specs/2026-04-14-economic-evidence-pipeline-lockdown.md`
- `docs/research/2026-04-14-economic-evidence-architecture-lockdown.md`
- `docs/poc/economic-analysis-boundary/`
- `docs/poc/economic-evidence-quality/`

## Current Verdict

The live economic-analysis path already contains literature-backed assumptions. The next implementation must migrate and govern them; it must not design a new assumption system while leaving runtime constants behind.

Runtime-integrated today:

- `backend/services/legislation_research.py`:
  - `WAVE2_PASS_THROUGH_LITERATURE`
  - `WAVE2_ADOPTION_ANALOGS`
  - `_derive_pass_through_prerequisite(...)`
  - `_derive_adoption_prerequisite(...)`

POC/contract candidate:

- `backend/services/economic_assumptions.py`:
  - `AssumptionRegistry`
  - assumption profiles with `stale_after_days`

Decision required by `bd-3wefe.11`:

- Move runtime `WAVE2_*` values into versioned `AssumptionCard` / `ModelCard` records or explicitly document why a specific value remains runtime-local.
- Enforce staleness metadata in the package sufficiency gate.
- Ensure each quantitative output traces to a source-bound parameter, assumption card, model card, or fail-closed reason.

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

## Known Runtime-Integrated Assets

| Asset | Runtime path | Status | Required next action |
| --- | --- | --- | --- |
| Pass-through literature | `backend/services/legislation_research.py::WAVE2_PASS_THROUGH_LITERATURE` | runtime-authoritative constant | inventory citations/units/ranges; migrate to `AssumptionCard`/`ModelCard`; wire runtime lookup |
| Adoption analogs | `backend/services/legislation_research.py::WAVE2_ADOPTION_ANALOGS` | runtime-authoritative constant | inventory citations/coverage/applicability; migrate to assumption registry |
| Pass-through prerequisite derivation | `backend/services/legislation_research.py::_derive_pass_through_prerequisite` | runtime logic | preserve mechanism semantics when package cards are introduced |
| Adoption prerequisite derivation | `backend/services/legislation_research.py::_derive_adoption_prerequisite` | runtime logic | preserve mechanism semantics when package cards are introduced |
| Assumption registry | `backend/services/economic_assumptions.py::AssumptionRegistry` | POC/contract candidate | become runtime source or remain projection layer; no dual source of truth |

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
