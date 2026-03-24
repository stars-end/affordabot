# Mechanism-Backed Quantification Specification

## 1. Problem Statement
Affordabot's current quantification path is intentionally conservative, but too narrow. After the recent truth-remediation work, the pipeline can reliably avoid fake numbers by requiring direct fiscal notes or official numeric estimates. That solved the hallucination problem, but it also blocks quantification for bills whose cost-of-living effects are real, causal, and economically analyzable through well-established mechanisms such as regulatory compliance burden, pass-through, or participation effects.

The founder requires a stricter but broader framework:
- quantify only when a real causal mechanism is identified
- quantify only when the required parameters are sourced and auditable
- propagate uncertainty explicitly without fake percentiles
- preserve end-to-end provenance from raw scrape to persisted output

This is not a generate-step enhancement. It is a whole-pipeline contract change affecting research, deterministic gates, generation, review, persistence, Slack, admin/glassbox, and verification.

## 2. Current-State Assessment
Grounded in current trunk and the existing PR `#335` baseline:

- [orchestrator.py](backend/services/llm/orchestrator.py)
  - Current step sequence is effectively `ingestion_source -> research -> sufficiency_gate -> generate -> review -> refine? -> persistence`.
  - There is no explicit `mode_selection`, `parameter_resolution`, or `parameter_validation` step.

- [evidence_gates.py](backend/services/llm/evidence_gates.py)
  - `assess_sufficiency()` is deterministic, but it is fiscal-note-centric.
  - It decides `quantification_eligible` primarily from Tier A evidence plus detected fiscal-note-style numeric support.
  - It has no concept of quantification modes, per-parameter validation, source hierarchies, or excerpt-as-gate.

- [legislation_research.py](backend/services/legislation_research.py)
  - Research retrieves bill text and bill-specific web results.
  - Query construction currently emphasizes fiscal impact analysis, committee analysis, and government cost estimates.
  - It does not yet deliberately retrieve parameter classes needed for mechanism-backed quantification such as BLS wages, CBP/QCEW counts, sector pass-through estimates, or take-up benchmarks.

- [analysis.py](backend/schemas/analysis.py)
  - `LegislationImpact` still uses `p10/p25/p50/p75/p90`.
  - `LegislationAnalysisResponse` still uses `total_impact_p50`.
  - There is no canonical representation for `impact_mode`, `modeled_parameters`, or `scenario_bounds`.

- [slack_summary.py](backend/services/slack_summary.py)
  - Slack proof builders assume the old flat quantified/unquantified model.
  - Current summaries do not explain mechanism, parameter gaps, or uncertainty drivers.

- [glass_box.py](backend/services/glass_box.py) and [admin.py](backend/routers/admin.py)
  - Canonical DB-backed truth path exists and is the correct audit surface.
  - Current responses expose flat run/analysis data, not parameter-level mechanism traces.

- [verify_pipeline_truth.py](backend/scripts/verification/verify_pipeline_truth.py)
  - Current verifier checks scrape, chunk presence, legislation truth fields, pipeline run presence, and persistence step presence.
  - It does not check mode selection, parameter sourcing, uncertainty construction, or post-generation validation.

## 3. Design Principles
1. **Mode-backed, not vibes-backed**
   - Every quantified impact must name a quantification mode.

2. **Deterministic gates before and after LLM generation**
   - LLMs may synthesize and narrate.
   - Deterministic code must validate mode selection, parameter completeness, and output integrity.

3. **Single-impact, single-mode in Wave 1**
   - Each quantified impact uses exactly one primary mode.
   - A bill may contain multiple impacts, but each impact remains single-mode.

4. **Fail closed on ambiguity**
   - If the mechanism is ambiguous, the parameters are missing, or the evidence is too contested, the system falls back to `qualitative_only`.

5. **Canonical truth store stays the same**
   - Detailed provenance remains in `pipeline_steps`, `pipeline_runs.result`, and downstream persisted analysis structures.
   - Slack remains summary-only.
   - Admin/glassbox remains the detailed operator surface.

## 4. Quantification Mode Taxonomy

### 4.1 First-Wave Modes
1. `direct_fiscal`
   - Official fiscal note, CBO score, committee fiscal estimate, or agency cost estimate.

2. `compliance_cost`
   - Standard Cost Model style administrative/regulatory burden:
   - `Cost = Population × Frequency × Time × Wage`

### 4.2 Second-Wave Modes
3. `pass_through_incidence`
   - Consumer price effect from a tax, fee, or business cost shifted through a market.

4. `adoption_take_up`
   - Program fiscal effect from eligible population, take-up, and benefit/cost per participant.

### 4.3 Deferred Modes
5. `supply_shock`
   - Broad structural equilibrium or reduced-form elasticity adjustments with major regime-dependence risk.
   - Deferred until curated parameter infrastructure exists and Wave 1/2 modes are production-credible.

## 5. Full Pipeline Operating Contract
The current pipeline sequence is insufficient for mechanism-backed quantification. The required operating contract is:

1. `ingestion_source`
2. `chunk_index`
3. `research_discovery`
4. `mode_selection`
5. `parameter_resolution`
6. `sufficiency_gate`
7. `generate`
8. `parameter_validation`
9. `review`
10. `refine` (optional)
11. `persistence`
12. `notify_debug`

### 5.1 ingestion_source
- Unchanged as the raw-source entry point.
- Must continue to persist:
  - raw scrape id
  - source URL
  - content hash
  - source type
  - source text presence
- Mechanism-backed quantification is disallowed if raw-source provenance is incomplete.

### 5.2 chunk_index
- Structurally similar to today, but chunk metadata must remain parameter-provenance friendly.
- Minimum metadata:
  - `bill_number`
  - `jurisdiction`
  - `document_id`
  - `source_url`
  - `source_type`
- If available, chunk metadata should also carry a semantic role hint such as:
  - `bill_text`
  - `committee_analysis`
  - `fiscal_note`
  - `agency_report`
  - `academic_literature`

### 5.3 research_discovery
- Split the current generic research step into a richer output contract.
- Required outputs:
  - `rag_chunks`
  - `web_sources`
  - `evidence_envelopes`
  - `candidate_modes`
  - `parameter_candidates`
  - `retrieval_coverage`
  - `coverage_gaps`
- `retrieval_coverage` must explicitly record whether the run searched for:
  - official fiscal notes
  - committee analyses
  - regulatory burden clues
  - population counts
  - wage benchmarks
  - take-up benchmarks
  - pass-through literature

### 5.4 mode_selection
- New deterministic step.
- Purpose:
  - choose a primary mode for each candidate impact
  - reject unsupported or ambiguous modes
- Required outputs:
  - `candidate_modes`
  - `selected_mode`
  - `rejected_modes`
  - `selection_rationale`
  - `ambiguity_status`
  - `composition_candidate`
- Mode selection must run after research discovery but before quantification eligibility is decided.
- If ambiguity remains high, fail closed to `qualitative_only`.

### 5.5 parameter_resolution
- New deterministic step.
- Purpose:
  - normalize every required parameter for the selected mode into a canonical schema
  - validate source hierarchy at the parameter level
- Required outputs:
  - `required_parameters`
  - `resolved_parameters`
  - `missing_parameters`
  - `source_hierarchy_status`
  - `literature_confidence`
  - `excerpt_validation_status`
  - `dominant_uncertainty_parameters`
- If any required parameter is missing, the selected mode cannot proceed to quantification.

### 5.6 sufficiency_gate
- `assess_sufficiency()` must evolve from fiscal-note gating into mode-aware gating.
- This is a major deterministic rewrite, not a minor patch.
- Required outputs:
  - `selected_mode`
  - `quantification_eligible`
  - `sufficiency_state`
  - `gate_failures`
  - `parameter_validation_summary`
  - `retrieval_prerequisite_status`
- The gate must validate:
  - source text presence
  - evidence presence
  - mode legitimacy
  - parameter completeness
  - source hierarchy compliance
  - excerpt-as-gate compliance
  - literature confidence constraints
  - anti-double-counting eligibility
  - uncertainty construction validity

### 5.7 generate
- Generation may not choose a new mode on its own.
- It must consume:
  - selected mode
  - validated parameter set
  - scenario-construction rules
- Required generated fields:
  - `impact_mode`
  - `modeled_parameters`
  - `scenario_bounds`
  - `mode_selection_rationale`
  - `composition_note`
- Generation remains responsible for structured explanation, not for gate logic.

### 5.8 parameter_validation
- New deterministic post-generation step.
- Purpose:
  - verify generated output is consistent with upstream validated inputs
  - verify arithmetic and schema invariants
  - verify scenario bounds vary only dominant parameters
  - verify prose does not overclaim beyond the validated evidence
- Required outputs:
  - `schema_valid`
  - `arithmetic_valid`
  - `bound_construction_valid`
  - `claim_support_valid`
  - `validation_failures`
- If this step fails, the impact is downgraded to `qualitative_only` before persistence.

### 5.9 review
- Review remains valuable, but no longer carries the burden of deterministic enforcement.
- The reviewer checks:
  - mode appropriateness
  - causal coherence
  - double-counting risk
  - sign/unit sanity
  - uncertainty narrative sanity
- Review must not be the first place where missing parameters are discovered.

### 5.10 refine
- Refine may revise:
  - narrative explanation
  - causal chain
  - impact framing
- Refine may not invent missing parameters that failed deterministic validation.

### 5.11 persistence
- Persistence must store both:
  - backward-compatible summary truth fields
  - the new mechanism-backed structure
- Every persisted quantified impact must remain reconstructable from:
  - selected mode
  - validated parameters
  - scenario-construction rule
  - cited evidence

### 5.12 notify_debug
- During the debug period, a short Slack summary should emit for every pipeline run.
- Slack is not a second store; it is an operator proof layer with deep links back to canonical truth.

## 6. Mode Definitions and Empirical Inputs

### 6.1 direct_fiscal
- Use when an official government estimate exists.
- Required parameters:
  - `fiscal_note_estimate`
- Scenario construction:
  - `base` = published value
  - `low/high` = official range if present
  - otherwise `low = base = high`
- This mode is first-wave and backward-compatible with existing behavior.

### 6.2 compliance_cost
- Methodology: Standard Cost Model.
- Formula:
  - `Cost = Population × Frequency × Time × Wage`
- Required parameters:
  - `population`
  - `frequency`
  - `time_burden`
  - `wage_rate`
- Population source hierarchy:
  1. bill text / fiscal note explicit count
  2. Census CBP or BLS QCEW establishment counts
  3. state registry / licensing / administrative count
  4. fail closed
- Wage benchmark hierarchy:
  1. bill-specific official wage basis if present
  2. BLS OEWS/OES
  3. fail closed
- Overhead multiplier:
  - default US floor convention should be explicit and cited
- Dominant uncertainty defaults:
  - `population`
  - `time_burden`

### 6.3 pass_through_incidence
- Wave 2 only.
- Required parameters:
  - `total_levied_cost`
  - `pass_through_rate`
  - `literature_confidence`
- Requires curated sector-specific retrieval or lookup before activation.

### 6.4 adoption_take_up
- Wave 2 only.
- Required parameters:
  - `eligible_population`
  - `take_up_rate`
  - `benefit_per_capita`
- Take-up hierarchy:
  1. program-specific published administrative data
  2. defensible analogous program
  3. fail closed
- Bass diffusion is explicitly out of scope and must not appear in implementation.

## 7. Research and Retrieval Contract
Mechanism-backed quantification changes research upstream.

### 7.1 Research is now two jobs
1. evidence discovery
2. parameter discovery

### 7.2 Mode-aware retrieval expectations
- `direct_fiscal`
  - fiscal note
  - committee fiscal analysis
  - official agency estimate
- `compliance_cost`
  - affected population count
  - reporting / filing / training frequency
  - time burden clues
  - wage benchmark source
- `pass_through_incidence`
  - sector classification
  - statutory burden amount
  - sector-specific incidence literature
- `adoption_take_up`
  - eligible population
  - program analog
  - take-up benchmark
  - per-capita benefit/cost

### 7.3 Retrieval prerequisites
- Wave 1:
  - `direct_fiscal` requires no new curated retrieval layer
  - `compliance_cost` can proceed with constrained hierarchies plus official datasets
- Wave 2:
  - `pass_through_incidence` blocked without curated literature retrieval
  - `adoption_take_up` blocked without curated take-up lookup

## 8. Uncertainty Contract
The system must stop pretending to know percentiles it cannot justify.

### 8.1 Replace flat percentiles
- Drop `p10/p25/p50/p75/p90` as the primary mechanism-backed representation.
- Use `scenario_bounds = { low, base, high }`.

### 8.2 Dominant-parameter variation
- Do not vary all parameters simultaneously.
- Only 1-2 dominant uncertainty parameters vary in Wave 1.
- Each bound must state:
  - which parameters varied
  - why they were chosen
  - what `low` and `high` mean

### 8.3 Base estimate is primary
- `base` is the primary user-facing estimate when quantification is allowed.
- `low/high` are sensitivity bounds, not probabilistic percentiles.

## 9. Fail-Closed Rules
The following deterministic rules are mandatory:

1. missing parameter gate
2. excerpt-as-gate
3. population sourcing gate
4. missing literature gate
5. literature confidence gate
6. no bare bounds without modeled parameters
7. mode selection gate
8. anti-double-counting gate
9. retrieval prerequisite gate
10. parameter-validation gate

### 9.1 New failure taxonomy
Failure reasons should become explicit and machine-readable:
- `mode_ambiguous`
- `parameter_missing`
- `parameter_unverifiable`
- `literature_contested`
- `retrieval_prerequisite_missing`
- `scenario_invalid`
- `composition_ambiguous`
- `migration_backcompat_failure`

These should appear in:
- gate output
- Slack summary proof lines
- admin/glassbox traces
- verification diagnostics

## 10. Canonical Persistence and Backward Compatibility

### 10.1 Per-impact canonical fields
Each impact must persist:
- `impact_mode`
- `modeled_parameters`
- `scenario_bounds`
- `mode_selection_rationale`
- `composition_note`

### 10.2 modeled_parameters schema
Each parameter entry must include:
```json
{
  "base": 0.0,
  "low": null,
  "high": null,
  "is_dominant": false,
  "source_url": "",
  "excerpt": "",
  "source_type": "bill_text|fiscal_note|government_data|academic_literature|administrative_data|curated_lookup",
  "literature_confidence": null
}
```

### 10.3 Invariants
- `base` is always required
- `low/high` only appear for dominant parameters
- `scenario_bounds.low/high` must be mechanically reconstructable from `modeled_parameters`
- literature-backed parameters require both `source_url` and `excerpt`

### 10.4 Read/write compatibility contract
This change is breaking unless handled explicitly.

The implementation must define:
- what replaces `total_impact_p50`
- whether `quantification_eligible` remains a top-level truth field
- how existing persisted runs with percentile fields remain readable
- whether read adapters or one-time migrations are used

All of these read paths must be updated atomically:
- [analysis.py](backend/schemas/analysis.py)
- [verify_pipeline_truth.py](backend/scripts/verification/verify_pipeline_truth.py)
- [slack_summary.py](backend/services/slack_summary.py)
- [glass_box.py](backend/services/glass_box.py)
- [admin.py](backend/routers/admin.py)

## 11. Operator Surfaces

### 11.1 Slack summary contract
Slack becomes a short debug proof for every run during the debug period.

Minimum summary content:
- run identity
- selected mode or `qualitative_only`
- quantification decision
- base estimate if quantified
- dominant uncertainty parameters
- fail-closed reason if blocked
- deep links to:
  - `/admin/audits/trace/{run_id}`
  - `/admin/bill-truth/{jurisdiction}/{bill_id}`

### 11.2 Admin / Glassbox contract
Admin/glassbox must become the detailed mechanism trace surface.

Required additions:
- selected mode
- rejected modes
- gate failures
- validation failures
- modeled parameters
- source hierarchy details
- dominant uncertainty parameters
- scenario derivation summary

The detailed trace must make it easy to answer:
- where did this number come from?
- which parameter drove the range?
- which rule blocked quantification?

## 12. Verification and Test Contract
The definition of a healthy pipeline run changes.

### 12.1 New verifier expectations
[verify_pipeline_truth.py](backend/scripts/verification/verify_pipeline_truth.py) must eventually check:
- mode selected or explicitly failed closed
- parameter resolution executed
- required parameters resolved or explicitly missing
- sufficiency gate used mode-aware logic
- parameter validation executed
- persisted impacts conform to the new schema
- admin/glassbox can expose mechanism-backed truth

### 12.2 Required tests
1. unit tests for mode selection
2. unit tests for ambiguity fail-closed behavior
3. unit tests for per-parameter validation
4. unit tests for dominant-parameter scenario construction
5. integration tests for direct_fiscal
6. integration tests for compliance_cost
7. backward-compatibility tests for old persisted runs
8. Slack summary tests for mode-aware proofs
9. admin/glassbox serialization tests for mechanism trace payloads

## 13. Phased Execution Plan

### 13.1 Current spec repair task
- `bd-hvji.10`
  - mechanism-backed quantification spec
- `bd-hvji.10.1`
  - pipeline propagation spec for mechanism-backed quantification

### 13.2 Next implementation tasks
- `bd-hvji.11`
  - mechanism-backed quantification pipeline sequence and schema contract
  - purpose:
    - add `mode_selection`, `parameter_resolution`, `parameter_validation`
    - define backward-compatibility contract

- `bd-hvji.12`
  - update Slack, admin, glassbox, and verification for mechanism-backed quantification
  - dependency:
    - blocks on `bd-hvji.11`

- `bd-hvji.13`
  - implement Wave 1 `direct_fiscal` and `compliance_cost` pipeline changes
  - dependency:
    - blocks on `bd-hvji.11`

- `bd-hvji.14`
  - run full mechanism-backed quantification pipeline audit
  - dependency:
    - blocks on `bd-hvji.12`
    - blocks on `bd-hvji.13`

- `bd-hvji.15`
  - build curated retrieval prerequisites for Wave 2 quantification modes
  - dependencies:
    - blocks on `bd-hvji.11`

### 13.3 Recommended rollout order
1. `bd-hvji.11`
2. `bd-hvji.12` and `bd-hvji.13` in parallel if the write scopes stay clean
3. `bd-hvji.14`
4. `bd-hvji.15` when Wave 2 is ready

## 14. Non-Goals and Explicit Deferrals
- no Monte Carlo engine in Wave 1
- no full equilibrium/supply-shock quantification in Wave 1
- no multi-mode quantification for the same impact in Wave 1
- no enabling of Wave 2 modes without curated retrieval prerequisites

## 15. Implementation Readiness Statement
After this spec update:
- the economics design is defined
- the full pipeline propagation contract is defined
- the operator-surface and verification impacts are defined
- the implementation work is split into concrete Beads tasks with dependencies

Implementation should begin only from this fuller pipeline contract, not from the earlier economics-only framing.
