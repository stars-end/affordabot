# Mechanism-Backed Quantification Specification

## 1. Problem Statement
Affordabot's current quantification strategy is too narrow. While the recent pipeline truth remediation (bd-tytc) successfully eliminated fake numbers by enforcing strict evidence gates, it inadvertently under-quantifies bills whose economic effects are real but indirect. The current pipeline fundamentally expects explicit "fiscal notes" or direct cost estimates in the text. The founder explicitly requires "mechanism-backed quantification" to model indirect effects—such as compliance costs, pass-through incidence, and adoption rates—grounded in real economic literature and empirical parameter classes, while still maintaining strict "no fake precision" fail-closed rules.

## 2. Current-State Assessment
Grounded in the current trunk (`b557c2098193f558fab61ed9144773e24870b657`):
- **Orchestrator (`backend/services/llm/orchestrator.py`)**: Uses `LegislationResearchService` to fetch evidence, then forces outputs into a generic, falsely-precise `p10/p25/p50/p75/p90` array if quantified.
- **Evidence Gates**: `assess_sufficiency` completely blocks quantification (`quantification_eligible = False`) if direct fiscal notes or official numeric estimates are missing.
- **Observability**: `GlassBoxService` and `/api/admin` APIs expose `pipeline_runs` containing a flat analysis payload without tracking *how* numbers were derived (the mechanism) or what parameters were used.
- **Slack Summary (`backend/services/slack_summary.py`)**: Emits a brief summary per run, noting `sufficiency_state` and whether the bill is `quantification_eligible`, but lacks mechanism insight.

## 3. Recommended Quantification Mode Taxonomy
To expand safely, we must replace the single generic pathway with specific, mechanically sound quantification modes backed by established economic methodologies.

### Recommended for First-Wave Implementation
1. **`direct_fiscal`**: Straightforward extraction of official government cost estimates (formalizing the current capability).
2. **`compliance_cost`**: Calculating direct regulatory burden on businesses or residents based on the Standard Cost Model (SCM).

### Recommended for Second-Wave Implementation
3. **`pass_through_incidence`**: Calculating how much of a new corporate tax, fee, or cost is passed on to consumers.
4. **`adoption_take_up`**: Calculating the impact of an opt-in program based on eligibility and historical take-up rates.

### Deferred (Out of Scope)
5. **`supply_shock`**: General equilibrium effects and elasticity-driven price changes across entire markets (e.g., housing elasticity) are too complex for LLM derivation without a dedicated dynamic scoring model. Attempting this now risks massive hallucination.

---

## 4. Empirical Parameters and Literature by Mode

To prevent "hand-wavy" modes, Affordabot must extract and cite specific empirical parameters corresponding to established economic literature.

### A. Compliance Cost Mode
**Methodology**: Based on the **Standard Cost Model (SCM)**, the international benchmark used by the OECD for quantifying administrative and regulatory burdens.
**Core Empirical Formula**: `Cost = Population (P) × Frequency (F) × Time (T) × Wage (W)`
**Required Parameters**:
- `population`: Number of affected entities (businesses, residents).
- `frequency`: How often the compliance task occurs per year.
- `time_burden`: Hours required per task.
- `wage_rate`: Hourly labor cost (must include an overhead multiplier, empirically benchmarked at 1.25x to 1.33x in literature).
**Literature/Sources**: Bureau of Labor Statistics (OEWS wage data), O*NET (task data), Regulatory Impact Statements (RIS).

### B. Pass-Through Incidence Mode (Wave 2)
**Methodology**: Based on structural incidence models, notably **Weyl and Fabinger (2013, Journal of Political Economy)**.
**Core Empirical Formula**: `ΔP = ρ × ΔT` (Price Change = Pass-Through Rate × Tax/Cost Change).
**Required Parameters**:
- `total_levied_cost`: The initial statutory burden or tax amount.
- `pass_through_rate` ($\rho$): The percentage of the cost shifted to consumers.
**Literature/Sources**: Must cite empirical tax incidence literature specific to the sector. (e.g., Retail/Gasoline often sees $\rho \approx 0.7 - 1.0$; Corporate Tax shifting to labor $\rho \approx 0.3 - 0.7$ per Arulampalam et al. 2012).

### C. Adoption / Take-up Mode (Wave 2)
**Methodology**: Based on utility-based discrete choice models (e.g., Currie 2006) and the **Bass Diffusion Model**.
**Required Parameters**:
- `eligible_population`: Total number of people qualifying for the policy.
- `take_up_rate`: The fraction of the eligible population expected to participate.
- `benefit_per_capita`: The value or cost per participating individual.
**Literature/Sources**: Historical administrative records (SNAP/Medicaid uptake rates), think tank reports (e.g., Urban Institute, CBO baselines).

---

## 5. Uncertainty Model Requirements

The current `p10..p90` array implies a continuous probability distribution that the LLM cannot actually compute, leading to fake precision.

**Minimum Acceptable Representation: Scenario Bands**
Affordabot must move to discrete **Scenario Bands (`low`, `base`, `high`)**.
- A Monte Carlo-ready parameter distribution is overkill for Wave 1.
- Instead, the LLM will output a `modeled_parameters` dictionary where each parameter can have a `low`, `base`, and `high` estimate (e.g., `wage_rate`: `{"base": 25.00}`).
- The final `scenario_bounds` for the impact are the deterministic product of these discrete parameter sets.

## 6. Fail-Closed Rules to Prevent Fake Precision
To guarantee truthfulness, the orchestrator's evidence gates must enforce the following:
1. **Missing Parameter Gate**: If `compliance_cost` is chosen, but the LLM cannot cite a specific source for the `wage_rate` or the `population`, the mode fails closed to `qualitative_only`.
2. **Missing Literature Gate (Wave 2)**: For `pass_through_incidence`, the evidence payload MUST contain a URL or explicit citation to an economic literature source validating the `pass_through_rate`. Guessing "80%" is unsupported speculation and will be blocked.
3. **No Bare Percentiles/Bounds**: No numeric bounds may be emitted without a populated `modeled_parameters` dictionary clearly explaining the arithmetic.

## 7. Canonical Persistence Design
How modeled assumptions and evidence must be represented in the database:

**`pipeline_steps` (`generate` step)**:
The `output_result` JSON must replace flat arrays with:
- `impact_mode`: string (e.g., `compliance_cost`)
- `scenario_bounds`: `{ "low": float, "base": float, "high": float }`
- `modeled_parameters`: dict mapping parameter names (e.g., `wage_rate`) to `{ "value": float, "source_url": string, "excerpt": string }`.

**`pipeline_runs.result` & Downstream Storage (`legislation` / `impacts`)**:
Update the `LegislationImpact` schema to include:
- `impact_mode`: string
- `modeled_parameters`: JSONB
- `scenario_bounds`: JSONB

## 8. Slack Summary Design for Every Run
Update `backend/services/slack_summary.py` (`_build_generate_proof` and `_build_persistence_proof`) to report the mechanism.
- *Current*: `Generate: 2 impacts, sufficiency 'sufficient', quantification eligible.`
- **New Requirement**: `Generate: 2 impacts (Mode: compliance_cost). Bounds: base=$50/yr. Sufficiency: 'sufficient'.`
- *If degraded*: `Generate: 0 impacts quantified. Failed closed: missing 'wage_rate' parameter for compliance_cost.`

## 9. Admin/Glassbox Design Requirements
The Glass Box (`routers/admin.py` and frontend admin views) must expose the full modeled provenance to maintain trust.
- The `pipeline_runs/{id}` endpoint must return the `modeled_parameters` and the chosen `impact_mode`.
- The UI must render a "Mechanism Trace" table showing: `Parameter Name` → `Assumed Value` → `Evidence Excerpt` → `URL`.
- This ensures that if a compliance cost looks wrong, an admin can instantly see if the LLM hallucinated the hourly wage or the population size.

## 10. Phased Implementation Sequence
- **Batch 1 (Next Implementation Wave)**:
  - Update `LegislationImpact` schema to support `impact_mode`, `scenario_bounds`, and `modeled_parameters`.
  - Implement orchestrator prompt changes and sufficiency gates for `direct_fiscal` and `compliance_cost` modes.
  - Update Slack summaries and Glassbox API.
- **Batch 2 (Future)**:
  - Add specific retrieval pipelines tuned for economic literature (e.g., NBER, CBO) to unlock `pass_through_incidence` and `adoption_take_up`.

## 11. Open Questions / Explicit Non-Goals
- **Non-Goal**: Building a local Python Monte Carlo engine. We rely on the LLM to multiply the discrete Low/Base/High parameter sets for now.
- **Open Question**: How to systematically index standard baseline data (like BLS wages or CBO baselines) so the LLM doesn't have to web-search them via general search tools every time? (Recommendation: A static internal RAG index for baseline economic parameters).

## 12. Acceptance Criteria for Future Implementation
- [ ] `LegislationImpact` schema drops `p10..p90` in favor of `scenario_bounds`, `impact_mode`, and `modeled_parameters`.
- [ ] Orchestrator explicitly supports `direct_fiscal` and `compliance_cost` modes.
- [ ] Sufficiency gates deterministically fail closed if a mode's required parameters are not backed by cited evidence.
- [ ] Slack summaries output the `impact_mode` and failure reasons if parameters are missing.
- [ ] `/api/admin/pipeline-runs` surfaces the extracted parameters for auditability.
