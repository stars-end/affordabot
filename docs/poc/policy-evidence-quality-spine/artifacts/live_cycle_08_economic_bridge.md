# Live Cycle 08 - Economic Analysis Bridge (`bd-3wefe.16`)

- date_utc: `2026-04-16`
- branch: `feature-bd-2agbe.1`
- scope: package-to-economic-analysis bridge only (no source-ingestion changes)
- owner: `bd-3wefe.16`

## Inputs

- Prior live baseline:
  - `live_cycle_07_admin_analysis_status.json`
  - `quality_spine_live_storage_probe.json`
  - `policy_evidence_quality_spine_cycle_learning_report.md`
- Existing canonical code path reused:
  - `AnalysisPipeline` + `LegislationResearchService`
  - `PolicyEvidenceQualitySpineEconomicsService` endpoint projection

## Tweak Set

1. Extended backend-authored economic read model to include explicit trace payload:
   - `economic_trace.mechanism_graph`
   - `economic_trace.direct_indirect_classification`
   - `economic_trace.parameter_table`
   - `economic_trace.assumption_cards`
   - `economic_trace.model_cards`
   - `economic_trace.arithmetic_integrity`
   - `economic_trace.sensitivity_range`
   - `economic_trace.uncertainty_notes`
2. Added governed secondary-research contract surface:
   - `secondary_research.status`
   - `secondary_research.request_contract` (package-linked request shape)
   - `secondary_research.output_contract` (required auditable fields)
3. Added canonical-analysis binding diagnostics:
   - `canonical_analysis_binding.status` (`bound` or `not_proven`)
   - blocker and missing code path when unbound
   - source artifact refs tied to `package_id`
4. Strengthened mechanism classification fallback for indirect paths when model cards are missing but parameter semantics indicate indirect mode (`take_up`, `pass_through`, `incidence`, `adoption`).

## Files Changed

- `backend/services/pipeline/policy_evidence_quality_spine_economics.py`
- `backend/tests/services/pipeline/test_policy_evidence_quality_spine_economics.py`

## Verification

- `poetry run pytest tests/services/pipeline/test_policy_evidence_quality_spine_economics.py -q`
  - result: `23 passed`
- `poetry run pytest tests/routers/test_admin_pipeline_read_model.py -q`
  - result: `10 passed`

## E-Gate Delta (Cycle 07 -> Cycle 08)

- `E1 mechanism validity`: unchanged gate logic; added explicit endpoint trace visibility.
- `E2 direct/indirect classification`: improved fallback classification for secondary/indirect cases without model cards.
- `E3 secondary-research loop`: improved from implicit failure signal to explicit request/output contract with package linkage.
- `E4 canonical analysis binding`: improved from generic `LLM narrative not_proven` to precise `canonical_analysis_binding` diagnostics and missing code path.
- `E5 unsupported-claim rejection`: unchanged semantics; now surfaced within `economic_trace` and `economic_output`.
- `E6 user-facing conclusion quality`: unchanged fail-closed semantics; no new quantified claims permitted without decision-grade gates.

## Gate B (Manual Economic Audit) Status

- status: `not_executed_in_this_cycle`
- reason: this cycle was code bridge hardening and deterministic/unit verification only.
- manual audit requirement remains: run against latest live San Jose package and inspect:
  - mechanism graph correctness,
  - parameter provenance,
  - assumption/model card governance,
  - arithmetic/sensitivity traceability,
  - secondary-research request/output linkage,
  - canonical-analysis binding status.

## Remaining Blockers

1. Live `analysis_history`/canonical analysis run binding to `package_id` remains `not_proven`.
2. Secondary-research contract exists but live orchestration consumption path is not yet proven in this cycle.
3. Decision-grade San Jose indirect result still requires additional source-bound parameters and governed assumptions.
