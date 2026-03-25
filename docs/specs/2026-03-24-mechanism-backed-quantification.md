# Mechanism-Backed Quantification Implementation Spec

## Summary
Affordabot is moving from a fiscal-note-only quantification path to a mechanism-backed framework that can quantify official fiscal estimates and concrete compliance burdens without inventing numbers. This is an end-to-end pipeline change, not a prompt tweak. The pipeline must explicitly discover candidate impacts, resolve mode-specific parameters, deterministically gate quantification, persist parameter-level provenance, and expose compact operator proofs in Slack plus detailed canonical truth in admin/glassbox.

This spec is implementation-oriented. It incorporates:
- the empirical design from PR `#335`
- the pipeline propagation rewrite from PR `#336`
- consultant feedback on impact discovery, enforcement placement, and compliance-cost scope
- the product decision that pre-MVP data is provisional, so no backward-compatibility contract is required

## Problem
The current pipeline is intentionally conservative, but too narrow:
- quantification is mostly gated on the existence of fiscal-note-like numeric support
- research is optimized for bill text and fiscal analyses, not mechanism inputs
- deterministic gates do not understand modes or parameter completeness
- downstream truth surfaces assume flat percentile outputs instead of structured modeled parameters

That avoids fake precision, but it misses real, auditable cost-of-living effects from bills that impose:
- administrative reporting or filing burden
- training or recordkeeping labor burden
- concrete purchase/install/fee burdens

The founder wants broader quantification with strict fail-closed behavior and explicit uncertainty.

## Goals
- Quantify only when a real mechanism is identified and its required parameters are sourced.
- Support first-wave `direct_fiscal` and `compliance_cost`.
- Treat `compliance_cost` as both:
  - administrative labor burden
  - concrete non-labor substantive burden
- Insert deterministic pipeline steps for impact discovery, mode selection, parameter resolution, and parameter validation.
- Persist parameter-level provenance in the canonical truth path.
- Emit short debug Slack summaries for every pipeline run.
- Keep admin/glassbox as the detailed canonical audit surface.

## Non-Goals
- No Monte Carlo engine in Wave 1.
- No supply-shock / structural equilibrium quantification in Wave 1.
- No enabling `pass_through_incidence` or `adoption_take_up` without curated retrieval prerequisites.
- No backward-compatibility or legacy-read contract for pre-MVP provisional data.
- No multi-mode quantification for the same impact in Wave 1.

## Active Contract
This is an `ALL_IN_NOW` pre-MVP cutover.

Implications:
- legacy percentile fields and provisional quantified data do not constrain the implementation
- the new schema is the only required truth contract once the implementation lands
- there is no dual path, no read adapter requirement, and no staged coexistence period for dev/staging

## Current-State Assessment
Grounded in current repo structure:

- [orchestrator.py](backend/services/llm/orchestrator.py)
  - current sequence is roughly `ingestion_source -> research -> sufficiency_gate -> generate -> review -> refine? -> persistence`
  - there is no explicit impact discovery, mode selection, parameter resolution, or post-generation validation step

- [evidence_gates.py](backend/services/llm/evidence_gates.py)
  - `assess_sufficiency()` is deterministic but fiscal-note-centric
  - it does not validate per-mode parameter requirements or parameter-level provenance

- [legislation_research.py](backend/services/legislation_research.py)
  - research is oriented toward bill text, fiscal analyses, and official cost estimates
  - it does not yet deliberately retrieve population counts, wage baselines, or concrete unit-cost support for compliance modeling

- [analysis.py](backend/schemas/analysis.py)
  - `LegislationImpact` still uses `p10/p25/p50/p75/p90`
  - `LegislationAnalysisResponse` still uses `total_impact_p50`
  - there is no canonical `impact_mode`, `modeled_parameters`, or `scenario_bounds` structure

- [slack_summary.py](backend/services/slack_summary.py)
  - summaries assume a flat quantified/unquantified model
  - they do not yet show mode, dominant uncertainty, or fail-closed reason

- [glass_box.py](backend/services/glass_box.py) and [admin.py](backend/routers/admin.py)
  - the DB-backed audit path already exists and remains canonical
  - the payloads do not yet expose mechanism-trace detail

- [verify_pipeline_truth.py](backend/scripts/verification/verify_pipeline_truth.py)
  - current verification checks structural run truth
  - it does not yet check impact discovery, mode-aware gating, or parameter provenance

## Quantification Mode Taxonomy

### First-Wave Modes
1. `direct_fiscal`
   - official fiscal note, committee fiscal estimate, agency estimate, or equivalent government numeric source

2. `compliance_cost`
   - concrete burden imposed on regulated parties through:
     - administrative labor burden
     - substantive non-labor burden

### Second-Wave Modes
3. `pass_through_incidence`
   - price effects from taxes, fees, or business-cost pass-through

4. `adoption_take_up`
   - fiscal effects from eligible population, take-up, and per-participant costs or benefits

### Deferred Modes
5. `supply_shock`
   - structural equilibrium or elasticity-heavy market-wide effects
   - deferred until curated parameter infrastructure and later-wave modeling support exist

## Full Pipeline Contract
The implementation must use the following pipeline sequence:

1. `ingestion_source`
2. `chunk_index`
3. `research_discovery`
4. `impact_discovery`
5. `mode_selection`
6. `parameter_resolution`
7. `sufficiency_gate`
8. `generate`
9. `parameter_validation`
10. `review`
11. `refine` (optional)
12. `persistence`
13. `notify_debug`

### 1. ingestion_source
- unchanged as raw-source entry point
- must continue to persist:
  - source URL
  - source type
  - content hash
  - raw text presence

### 2. chunk_index
- structurally similar to today
- chunk metadata must remain provenance-friendly:
  - `bill_number`
  - `jurisdiction`
  - `document_id`
  - `source_url`
  - `source_type`
  - optional role hints such as `bill_text`, `fiscal_note`, `committee_analysis`, `agency_report`, `academic_literature`

### 3. research_discovery
- expands research into both evidence discovery and parameter discovery
- required outputs:
  - `rag_chunks`
  - `web_sources`
  - `evidence_envelopes`
  - `retrieval_coverage`
  - `coverage_gaps`
  - `candidate_mode_hints`
  - `parameter_candidates`
- `retrieval_coverage` must say whether the run searched for:
  - official fiscal notes
  - committee analyses
  - regulatory burden clues
  - population counts
  - wage benchmarks
  - concrete unit-cost support
  - take-up benchmarks
  - pass-through literature

### 4. impact_discovery
- new LLM-assisted but non-quantifying step
- purpose:
  - identify candidate cost-of-living impacts before deterministic mode logic runs
  - provide the entities that `mode_selection` and `parameter_resolution` iterate over
- required outputs per impact:
  - `impact_id`
  - `impact_description`
  - `relevant_clauses`
  - `evidence_refs`
  - `candidate_mode_hints`
  - `impact_scope`
- this step may identify candidate impacts, but it may not quantify them or invent parameters

### 5. mode_selection
- new deterministic step
- purpose:
  - choose one primary mode for each candidate impact
  - reject unsupported or ambiguous modes
- required outputs per impact:
  - `candidate_modes`
  - `selected_mode`
  - `rejected_modes`
  - `selection_rationale`
  - `ambiguity_status`
  - `composition_candidate`
- if ambiguity remains high, fail closed to `qualitative_only`

### 6. parameter_resolution
- new deterministic step
- purpose:
  - normalize required parameters for the selected mode
  - validate source hierarchy at the parameter level
- required outputs per impact:
  - `required_parameters`
  - `resolved_parameters`
  - `missing_parameters`
  - `source_hierarchy_status`
  - `excerpt_validation_status`
  - `literature_confidence`
  - `dominant_uncertainty_parameters`
- quantification cannot proceed if any required parameter is missing

### 7. sufficiency_gate
- major deterministic rewrite of the current fiscal-note-centric gate
- required outputs:
  - `selected_mode`
  - `quantification_eligible`
  - `sufficiency_state`
  - `gate_failures`
  - `parameter_validation_summary`
  - `retrieval_prerequisite_status`
- the gate must validate:
  - source text presence
  - evidence presence
  - mode legitimacy
  - parameter completeness
  - source hierarchy compliance
  - excerpt-as-gate compliance
  - literature confidence constraints
  - anti-double-counting eligibility
  - uncertainty construction validity

### 8. generate
- generation may not choose a new mode
- it must consume:
  - discovered impacts
  - selected mode
  - validated parameters
  - scenario-construction rules
- required generated fields:
  - `impact_mode`
  - `modeled_parameters`
  - `scenario_bounds`
  - `mode_selection_rationale`
  - `component_breakdown`
  - `composition_note`

### 9. parameter_validation
- new deterministic post-generation step
- purpose:
  - verify generated output matches upstream validated inputs
  - verify arithmetic and schema invariants
  - verify scenario bounds vary only dominant parameters
  - verify narrative claims do not exceed evidence
- required outputs:
  - `schema_valid`
  - `arithmetic_valid`
  - `bound_construction_valid`
  - `claim_support_valid`
  - `validation_failures`
- control flow:
  - repairable arithmetic/schema defects may go through one refine attempt
  - missing-parameter, missing-source, and failed evidence-gate cases downgrade immediately to `qualitative_only`

### 10. review
- review remains useful for:
  - causal coherence
  - sign sanity
  - unit sanity
  - double-counting suspicion
  - uncertainty narrative sanity
- review is not the first enforcement layer

### 11. refine
- refine may revise:
  - explanation
  - causal framing
  - arithmetic presentation
- refine may not invent missing parameters or bypass deterministic failures

### 12. persistence
- persistence writes the new canonical schema only
- all provisional legacy percentile fields may be removed or replaced as part of the cutover
- every quantified impact must be reconstructable from:
  - selected mode
  - validated parameters
  - scenario-construction rule
  - cited evidence

### 13. notify_debug
- emit a short Slack summary for every pipeline run during the debug period
- Slack remains summary-only and links back to canonical truth surfaces

## Mode Definitions and Empirical Inputs

### direct_fiscal
- use when an official government estimate exists
- required parameter:
  - `fiscal_note_estimate`
- scenario construction:
  - `base = published value`
  - `low/high = official range if present`
  - otherwise `low = base = high`

### compliance_cost
- methodology:
  - Standard Cost Model style burden accounting, extended to include both labor burden and concrete non-labor burden
- subcomponents:
  - `administrative_labor_cost = population × frequency × time_burden × wage_rate`
  - `substantive_non_labor_cost = affected_units × unit_cost`
  - `total_compliance_cost = administrative_labor_cost + substantive_non_labor_cost`
- required administrative parameters when administrative labor burden is quantified:
  - `population`
  - `frequency`
  - `time_burden`
  - `wage_rate`
- required substantive parameters when non-labor burden is quantified:
  - `affected_units`
  - `unit_cost`
- source hierarchies:
  - `population` / `affected_units`
    1. bill text or fiscal note explicit count
    2. Census CBP or BLS QCEW establishment counts where applicable
    3. state registry, licensing, or administrative count
    4. fail closed
  - `wage_rate`
    1. bill-specific official wage basis if present
    2. BLS OEWS/OES
    3. fail closed
  - `unit_cost`
    1. bill text, fiscal note, or official implementation estimate explicitly naming the fee, purchase, install, or per-unit burden
    2. official agency schedule or cited government procurement/fee basis clearly tied to the mandate
    3. fail closed
- rules:
  - quantify administrative and substantive subcomponents separately
  - if only one subcomponent is supported, quantify only that subcomponent
  - do not infer capex or equipment costs from narrative alone
  - do not double-count the same burden as both labor and non-labor unless the bill clearly imposes both
- dominant uncertainty defaults:
  - administrative branch:
    - `population`
    - `time_burden`
  - substantive branch:
    - `affected_units`
    - `unit_cost` only when the source itself provides a bounded range

### pass_through_incidence
- Wave 2 only
- required parameters:
  - `total_levied_cost`
  - `pass_through_rate`
  - `literature_confidence`
- schema remains open enough to capture supporting literature parameters when available
- blocked until curated sector-specific retrieval exists

### adoption_take_up
- Wave 2 only
- required parameters:
  - `eligible_population`
  - `take_up_rate`
  - `benefit_per_capita`
- grounded in participation / administrative-burden literature
- Bass diffusion is explicitly out of scope

## Research and Retrieval Contract

### Research is now two jobs
1. evidence discovery
2. parameter discovery

### Mode-aware retrieval expectations
- `direct_fiscal`
  - fiscal note
  - committee fiscal analysis
  - official agency estimate
- `compliance_cost`
  - affected population count
  - reporting / filing / training frequency
  - time burden clues
  - wage benchmark source
  - concrete per-unit fee / install / purchase burden
- `pass_through_incidence`
  - sector classification
  - statutory burden amount
  - sector-specific incidence literature
- `adoption_take_up`
  - eligible population
  - program analog
  - take-up benchmark
  - per-capita benefit/cost

### Retrieval prerequisites
- Wave 1:
  - `direct_fiscal` requires no new curated retrieval layer
  - `compliance_cost` can proceed with constrained source hierarchies plus official datasets
  - expectation: Wave 1 `compliance_cost` will often fail closed when bill text or official sources do not expose population, wage, or unit-cost support
- Wave 2:
  - `pass_through_incidence` blocked without curated literature retrieval
  - `adoption_take_up` blocked without curated take-up lookup

## Uncertainty Contract

### Replace flat percentiles
- drop `p10/p25/p50/p75/p90` as the new primary representation
- use `scenario_bounds = { low, base, high }`

### Dominant-parameter variation
- do not vary all parameters simultaneously
- only 1-2 dominant uncertainty parameters vary per quantified branch in Wave 1
- each bound must state:
  - which parameters varied
  - why they were chosen
  - what `low` and `high` mean

### Base estimate is primary
- `base` is the primary user-facing estimate
- `low/high` are sensitivity bounds, not probabilistic percentiles

## Fail-Closed Rules
The following deterministic rules are mandatory:

1. impact discovery gate
2. mode selection gate
3. missing parameter gate
4. excerpt-as-gate
5. population/affected-unit sourcing gate
6. missing literature gate
7. literature confidence gate
8. no bare bounds without modeled parameters
9. anti-double-counting gate
10. retrieval prerequisite gate
11. parameter-validation gate

### Failure taxonomy
Failure reasons must be explicit and machine-readable:
- `impact_discovery_failed`
- `mode_ambiguous`
- `parameter_missing`
- `parameter_unverifiable`
- `literature_contested`
- `retrieval_prerequisite_missing`
- `scenario_invalid`
- `composition_ambiguous`

These reasons should appear in:
- gate output
- Slack summary proof lines
- admin/glassbox traces
- verification diagnostics

## Canonical Persistence Contract

### Per-impact canonical fields
Each impact must persist:
- `impact_mode`
- `modeled_parameters`
- `scenario_bounds`
- `mode_selection_rationale`
- `component_breakdown`
- `composition_note`

### modeled_parameters schema
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

### component_breakdown schema
`compliance_cost` must support explicit subcomponents:

```json
{
  "administrative_labor_cost": {
    "enabled": true,
    "base": 0.0,
    "low": null,
    "high": null
  },
  "substantive_non_labor_cost": {
    "enabled": false,
    "base": null,
    "low": null,
    "high": null
  }
}
```

### Invariants
- `base` is always required
- `low/high` only appear for dominant parameters
- `scenario_bounds.low/high` must be mechanically reconstructable from `modeled_parameters` and `component_breakdown`
- literature-backed parameters require both `source_url` and `excerpt`
- there is no legacy-read requirement for pre-MVP provisional data

## Operator Surfaces

### Slack summary contract
Slack becomes a short debug proof for every run.

Minimum content:
- run identity
- selected mode or `qualitative_only`
- quantification decision
- base estimate if quantified
- dominant uncertainty parameters
- fail-closed reason if blocked
- deep links to:
  - `/admin/audits/trace/{run_id}`
  - `/admin/bill-truth/{jurisdiction}/{bill_id}`

### Admin / Glassbox contract
Admin/glassbox must expose:
- discovered impacts
- selected mode
- rejected modes
- gate failures
- validation failures
- modeled parameters
- source hierarchy details
- dominant uncertainty parameters
- scenario derivation summary
- compliance subcomponent breakdown where applicable

The trace must make it easy to answer:
- where did this number come from?
- which parameter drove the range?
- which deterministic rule blocked quantification?

## Validation

### Verifier expectations
[verify_pipeline_truth.py](backend/scripts/verification/verify_pipeline_truth.py) must eventually check:
- impact discovery executed
- mode selected or explicitly failed closed
- parameter resolution executed
- required parameters resolved or explicitly missing
- sufficiency gate used mode-aware logic
- parameter validation executed
- persisted impacts conform to the new schema
- admin/glassbox can expose mechanism-backed truth

### Sequential prefix-testing methodology
The implementation must support sequential prefix testing of the pipeline so operators can inspect:
- step `1`
- steps `1+2`
- steps `1+2+3`
- ...
- steps `1+2+...+N`

This is a required testing/debugging methodology, not an optional convenience.

#### Prefix-run harness contract
The orchestrator must support a test/debug execution mode with controls equivalent to:
- `start_at_step`
- `stop_after_step`
- `reuse_prior_step_outputs`
- `fixture_mode`
- `run_label`

Prefix runs must:
- persist to the normal `pipeline_runs` table
- persist per-step data to the normal `pipeline_steps` table
- remain visible in admin/glassbox
- emit a Slack debug summary when `notify_debug` is reached or when the prefix run stops early in debug mode

Prefix runs must not require a second audit store or bespoke sidecar artifact format.

#### Required per-prefix assertions
The implementation must define deterministic expectations for each prefix boundary:

1. after `ingestion_source`
- raw source provenance is present or explicitly missing

2. after `chunk_index`
- chunk metadata exists and is provenance-compatible

3. after `research_discovery`
- retrieval coverage and coverage gaps are explicit
- parameter candidates and mode hints are inspectable

4. after `impact_discovery`
- candidate impacts exist with clause references and evidence refs
- no quantified values or invented parameters appear yet

5. after `mode_selection`
- each candidate impact has either one selected mode or an explicit fail-closed reason

6. after `parameter_resolution`
- required parameters are partitioned into resolved vs. missing
- source hierarchy status and excerpt validation status are explicit

7. after `sufficiency_gate`
- gate failures and quantification eligibility are machine-readable

8. after `generate`
- generated payload matches the new schema shape but is not treated as trusted until parameter validation succeeds

9. after `parameter_validation`
- arithmetic, schema, bound-construction, and claim-support checks are explicit
- repairable vs. structural failures are distinguishable

10. after `review` / `refine`
- review comments are inspectable without replacing deterministic gate truth

11. after `persistence`
- persisted canonical truth matches the validated payload

12. after `notify_debug`
- Slack one-line proof matches the step truth exposed in admin/glassbox

#### Required inspection surfaces for every prefix run
Every prefix run must be inspectable through all three of:
- DB truth:
  - `pipeline_runs`
  - `pipeline_steps`
- admin/glassbox:
  - per-step input/output inspection
  - mechanism-trace visibility where applicable
- Slack:
  - short operator proof with deep links back to canonical truth

#### Step-owned implementation responsibility
- `bd-hvji.11` must add the prefix-run harness and step stop/start controls
- `bd-hvji.12` must make Slack, admin/glassbox, and `verify_pipeline_truth.py` understand prefix runs and partial-step traces
- `bd-hvji.14` must use the prefix-run methodology as part of the full post-implementation audit

### Required tests
1. unit tests for impact discovery output shape
2. unit tests for mode selection
3. unit tests for ambiguity fail-closed behavior
4. unit tests for per-parameter validation
5. unit tests for compliance subcomponent arithmetic
6. unit tests for dominant-parameter scenario construction
7. integration tests for `direct_fiscal`
8. integration tests for `compliance_cost`
9. prefix-run tests for `stop_after_step` at every major pipeline boundary
10. prefix-run tests for `reuse_prior_step_outputs`
11. Slack summary tests for mode-aware proofs, including partial prefix runs
12. admin/glassbox serialization tests for mechanism trace payloads and prefix-run visibility
13. verifier tests for mechanism-backed step coverage and partial-run diagnostics

## Risks
- Wave 1 `compliance_cost` may fail closed frequently until BLS/CBP-backed retrieval is richer.
- Impact discovery introduces a new pre-quantification LLM step that must stay tightly scoped.
- Pre-MVP cutover simplifies implementation, but it means provisional old data can be discarded.
- Administrative and substantive compliance branches raise double-counting risk unless the gate stays strict.

## Beads Structure

### Epic
- `bd-hvji`
  - existing umbrella epic

### Current planning/spec task
- `bd-hvji.16`
  - mechanism-backed quantification full pipeline contract spec
  - purpose:
    - capture the final end-to-end implementation contract before execution

### Implementation tasks
- `bd-hvji.11`
  - title target:
    - `Implement impact discovery, pipeline sequence, and pre-MVP schema cutover`
  - purpose:
    - add `impact_discovery`, `mode_selection`, `parameter_resolution`, and `parameter_validation`
    - cut over schemas from percentile-era structures to the new canonical contract

- `bd-hvji.12`
  - title target:
    - `Update Slack admin glassbox and verifier for mechanism-backed quantification`
  - purpose:
    - update Slack proofs, admin/glassbox payloads, and `verify_pipeline_truth.py`
  - dependency:
    - blocks on `bd-hvji.11`

- `bd-hvji.13`
  - title target:
    - `Implement Wave 1 direct_fiscal and compliance_cost quantification`
  - purpose:
    - implement `direct_fiscal`
    - implement `compliance_cost` with both administrative labor and substantive non-labor branches
  - dependency:
    - blocks on `bd-hvji.11`

- `bd-hvji.14`
  - title target:
    - `Run full mechanism-backed quantification pipeline audit`
  - purpose:
    - audit the full pipeline after the implementation lands
  - dependencies:
    - blocks on `bd-hvji.12`
    - blocks on `bd-hvji.13`

- `bd-hvji.15`
  - title target:
    - `Build curated retrieval prerequisites for Wave 2 quantification modes`
  - purpose:
    - add curated parameter and literature retrieval needed before enabling `pass_through_incidence` and `adoption_take_up`
  - dependency:
    - blocks on `bd-hvji.11`

## Recommended First Task
`bd-hvji.11` should go first.

Why:
- it creates the missing impact entities and deterministic gate surfaces that every downstream change depends on
- it resolves the current pipeline chicken-and-egg problem
- it establishes the canonical schema before Slack/admin/verifier and mode implementations build on top

## Implementation Readiness Statement
Implementation can start once the Beads task metadata is aligned to this spec. The architecture is now explicit on:
- where impacts are identified
- where modes are selected
- where parameters are resolved
- where deterministic enforcement occurs
- how `compliance_cost` includes both administrative labor and substantive non-labor burden
- how the pre-MVP cutover removes backward-compatibility requirements
