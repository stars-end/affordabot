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
5. **`supply_shock`**: General equilibrium effects and elasticity-driven price changes across entire markets (e.g., housing elasticity). **Deferral rationale**: Full CGE/dynamic scoring requires structural model choices (Solow-type, OLG, DSGE) that introduce ideological and parametric controversy (see CBO's practice of running 2+ models and bracketing results). Reduced-form GE corrections exist for specific channels (e.g., Saiz 2010 metro-level housing supply elasticities, Dube 2019 minimum-wage employment elasticities, Ramey 2019 fiscal multiplier ranges), but integrating them requires curated empirical lookup infrastructure that does not yet exist in the pipeline. **Intermediate path for future waves**: where credible reduced-form GE estimates exist in the literature (housing supply, employment effects of minimum wage, fiscal multipliers), they can be incorporated as mode-specific adjustment factors without a full CGE model. This is the approach recommended by Chetty's (2009) "sufficient statistics" framework for welfare analysis. **Implementation gate**: supply_shock should not be attempted until (a) a curated parameter store for sector-specific elasticities exists, and (b) the Wave 2 modes have been validated in production.

### 3.1 Mode Selection Mechanism

**Single-bill, single-mode assignment (Wave 1)**. Each bill-impact pair is assigned exactly one quantification mode. The orchestrator selects the mode using the following precedence rules:

1. **If an official fiscal note, CBO score, or government cost estimate exists** → `direct_fiscal`.
2. **If the bill imposes a new regulatory obligation with identifiable compliance activities on a defined population** → `compliance_cost`.
3. **If the bill levies a tax, fee, or cost on businesses that is plausibly shifted to consumers** → `pass_through_incidence` (Wave 2 only).
4. **If the bill creates or modifies an opt-in benefit program** → `adoption_take_up` (Wave 2 only).
5. **If none of the above conditions are met with sufficient evidence** → `qualitative_only` (fail closed).

**Ambiguity resolution**: If a bill plausibly fits multiple modes (e.g., a new licensing fee that is both a compliance cost and a potential pass-through to consumers), the orchestrator MUST select the mode for which it has the strongest evidence support. It MUST NOT attempt to combine modes or produce multiple quantified impacts from different modes for the same bill-impact pair in Wave 1.

**Multi-mode composition (future design)**. A single bill may have multiple *distinct* impacts (e.g., a bill that both creates a licensing regime AND establishes a subsidy program). Each distinct impact may be assigned a different mode. However, the same dollar flow MUST NOT be double-counted across modes. Multi-impact composition is permitted only when the impacts are economically independent (i.e., the compliance cost of the licensing regime and the fiscal cost of the subsidy program do not overlap). The orchestrator must emit a `composition_note` field when multiple impacts are quantified for the same bill, explaining why they are independent.

**Fail-closed on ambiguity**: If the orchestrator cannot determine the correct mode with high confidence, or if the available evidence supports multiple modes roughly equally, the bill fails closed to `qualitative_only`. Emitting a quantified impact under the wrong mode is worse than emitting no quantified impact.

---

## 4. Empirical Parameters and Literature by Mode

To prevent "hand-wavy" modes, Affordabot must extract and cite specific empirical parameters corresponding to established economic literature.

### A. Compliance Cost Mode
**Methodology**: Based on the **Standard Cost Model (SCM)**, the methodology adopted by the OECD (2004, 2014) as the recommended approach for measuring administrative and regulatory burdens across member countries. Originally developed by the Dutch Ministry of Finance / SIRA Consulting in the late 1990s; also adopted by the European Commission for its Administrative Burden Reduction Programme (2007).
**Core Empirical Formula**: `Cost = Population (P) × Frequency (F) × Time (T) × Wage (W)`
This is the canonical simplification of the full SCM formula: `Cost_per_IO = (Internal_time × Internal_tariff + External_costs + Out_of_pocket) × Population × Frequency`. The simplified form omits external costs and out-of-pocket costs, which are secondary components for most regulatory obligations. The simplification is standard in the literature when the primary burden is internal staff time.
**Required Parameters**:
- `population`: Number of affected entities (businesses, residents).
- `frequency`: How often the compliance task occurs per year.
- `time_burden`: Hours required per task.
- `wage_rate`: Hourly labor cost. Must include an overhead multiplier to reflect total employer cost. The 1.25x multiplier is a convention from European SCM practice (mandatory social contributions). The 1.33x multiplier is closer to US mandatory employer costs. Both are conservative — BLS Employer Costs for Employee Compensation (ECEC) data shows actual total compensation overhead in the US is closer to 1.40x for private industry. Implementations SHOULD default to 1.33x for US jurisdictions and note this is a convention, not an empirically derived constant.

**Population Sourcing Hierarchy** (required — fail closed if no source is available):
1. **Bill text or accompanying fiscal note**: explicit count of affected entities stated in legislation or official analysis.
2. **Census County Business Patterns (CBP)** or **BLS Quarterly Census of Employment and Wages (QCEW)**: for business-affecting regulations, use NAICS-code-filtered establishment counts at the relevant geographic level.
3. **State licensing/regulatory registry**: for regulations targeting licensed professions or permitted activities, use the count from the relevant state agency's public registry or administrative data.
4. **Fail closed**: If none of the above sources yields a defensible population count, the mode fails closed to `qualitative_only`. The orchestrator MUST NOT estimate or hallucinate a population figure.

**Literature/Sources**: Bureau of Labor Statistics (OES wage data — the standard US source per OMB Circular A-4 for regulatory cost wage inputs), BLS ECEC (for overhead/benefits ratios), O*NET (task data), Regulatory Impact Statements (RIS), OECD SCM Manual (2004), OECD Regulatory Compliance Cost Assessment Guidance (2014).

**Known SCM limitations** (per Torriti 2007, Wegrich 2009, OECD 2014): SCM measures administrative/paperwork burden only, not substantive compliance costs (behavioral changes). The "normally efficient business" assumption introduces subjectivity. Population and frequency estimates may be unreliable. The model is static and does not capture learning/adaptation effects. These limitations are acceptable for Wave 1 because Affordabot's target is a first-order cost estimate with transparent parameters, not a comprehensive regulatory impact assessment.

### B. Pass-Through Incidence Mode (Wave 2)
**Methodology**: Based on structural incidence models, notably **Weyl and Fabinger (2013, Journal of Political Economy)**. The Weyl-Fabinger framework defines ρ as dp*/dt (the derivative of equilibrium price with respect to the tax). Under perfect competition, ρ = 1/(1 + η_D/η_S). Under imperfect competition, ρ depends on demand curvature and competitive conduct.
**Core Empirical Formula**: `ΔP = ρ × ΔT` (Price Change = Pass-Through Rate × Tax/Cost Change).
This is a valid local/marginal approximation. For large discrete tax changes, accuracy depends on the linearity of the pass-through function. ρ is not a constant — it varies with market concentration, demand curvature, supply elasticity, and tax magnitude.
**Required Parameters**:
- `total_levied_cost`: The initial statutory burden or tax amount.
- `pass_through_rate` (ρ): The fraction of the cost shifted to consumers.
- `literature_confidence`: One of `high`, `moderate`, or `contested`. Required for each parameter sourced from economic literature.

**Literature confidence classification**:
- `high`: Multiple well-identified empirical studies with consistent findings and no major methodological controversy (e.g., gasoline tax pass-through: Chouinard & Perloff 2004, Doyle & Samphantharak 2008, Marion & Muehlegger 2011 — clustering around ρ ≈ 0.7–1.0).
- `moderate`: Empirical estimates exist but show meaningful heterogeneity by context, or the study populations may not match the target jurisdiction (e.g., retail sales tax pass-through: Besley & Rosen 1999 found over-shifting (ρ > 1.0) for more than half of goods examined).
- `contested`: The literature itself is actively disputed, estimates span a wide range, or meta-analyses have identified publication bias (e.g., corporate tax incidence on labor: Knaisch & Poeschel 2024 meta-regression found substantial publication bias; after correction, the average effect may be near zero, vs. published point estimates of ρ ≈ 0.3–0.7).

**Fail-closed on contested literature**: If `literature_confidence` is `contested`, the scenario_bounds MUST use the widest defensible range from the literature and the impact summary MUST flag the contested status. If the range is so wide as to be uninformative (e.g., ρ spanning 0.0–0.8), the mode SHOULD fail closed to `qualitative_only`.

**Important caveats** (per Fullerton & Metcalf 2002, Handbook of Public Economics):
- Over-shifting (ρ > 1.0) is theoretically expected and empirically observed in imperfectly competitive markets. The model must not cap ρ at 1.0.
- Pass-through is often asymmetric — tax increases and decreases may not pass through equally (Doyle & Samphantharak 2008).
- Time horizon matters: short-run and long-run incidence can differ substantially.
- Local market conditions dominate; national-average ρ may be misleading for specific jurisdictions.

**Literature/Sources**: Must cite empirical tax incidence literature specific to the sector and, where possible, the geographic context. General references: Weyl & Fabinger (2013, JPE), Fullerton & Metcalf (2002), Besley & Rosen (1999, NTJ). Sector-specific: gasoline (Chouinard & Perloff 2004, Doyle & Samphantharak 2008), corporate (Arulampalam et al. 2012 — European Economic Review, not Econometrica; note Knaisch & Poeschel 2024 meta-analysis concerns).

**Wave 2 retrieval prerequisite**: This mode MUST NOT be enabled until a curated retrieval pipeline for sector-specific empirical pass-through literature is operational. The current general-purpose web search is insufficient to reliably surface the correct empirical estimates for a given tax type and sector. Implementation of this mode is gated on: (a) a curated index of pass-through studies organized by tax type, sector, and geography, or (b) a validated RAG pipeline that can retrieve and cite specific empirical estimates with provenance. Without this infrastructure, the LLM will anchor on training-data priors rather than current, context-appropriate literature.

### C. Adoption / Take-up Mode (Wave 2)
**Methodology**: Based on the program participation/take-up literature, including Currie (2006, in Auerbach, Card & Quigley eds., *Public Policy and the Income Distribution*), Moffitt (1983, "An Economic Model of Welfare Stigma," *American Economic Review*), and Herd & Moynihan (2019, *Administrative Burden*).

**Why not Bass Diffusion**: The Bass Diffusion Model was designed for consumer durable adoption (TVs, phones) where: (a) all potential adopters eventually purchase, (b) market potential is fixed, and (c) imitation/word-of-mouth drives the S-curve. Government program take-up violates all three assumptions: take-up reaches a steady-state ceiling well below 100% (SNAP plateaus ~82-84%, EITC ~78-80%), eligible populations shift with economic conditions and policy changes, and enrollment is driven primarily by administrative design and outreach rather than peer imitation. The program participation literature uses cost-benefit participation models, administrative burden frameworks, and microsimulation — not diffusion models.

**Core Empirical Formula**: `Fiscal_Impact = eligible_population × take_up_rate × benefit_per_capita`
This is a reasonable first-order approximation used by CBO and state fiscal offices. Known limitations: (a) take_up_rate is endogenous to benefit generosity and administrative design, not a fixed parameter; (b) benefit_per_capita is heterogeneous across the enrolled population; (c) the formula omits administrative costs (typically 5-15% of benefit outlays), crowd-out of existing coverage, and cross-program interaction effects. These limitations are acceptable for Wave 1 back-of-envelope estimation with transparent parameters.

**Required Parameters**:
- `eligible_population`: Total number of people qualifying for the policy.
- `take_up_rate`: The fraction of the eligible population expected to participate. Must be sourced from published take-up data (see sourcing hierarchy below), not LLM-generated estimates.
- `benefit_per_capita`: The value or cost per participating individual.

**Take-up rate sourcing hierarchy** (required — fail closed if no source is available):
1. **Program-specific published take-up data**: USDA FNS participation rates (SNAP — the gold standard, published annually with state-level breakdowns), IRS EITC participation rate estimates (published by state), CMS enrollment data (Medicaid/CHIP).
2. **CBO baseline projections**: CBO publishes enrollment/caseload projections for selected programs up to 3x/year. Note: CBO publishes enrollment projections, not explicit take-up rates — deriving a rate requires separately estimating the eligible population.
3. **Analogous program take-up data**: If the bill creates a novel program, use take-up rates from the most structurally similar existing program, with explicit justification for the analogy and a wider uncertainty band.
4. **Fail closed**: If no published take-up data or defensible analogy exists, the mode fails closed to `qualitative_only`. The LLM MUST NOT generate take-up rate estimates from first principles.

**Key empirical reference points** (for calibrating reasonableness, not for direct application):
| Program | Take-up Rate | Source |
|---------|-------------|--------|
| SNAP | ~82-84% | USDA FNS (FY 2015-2017) |
| EITC (with children) | ~78-81% | IRS (TY 2022) |
| EITC (childless) | ~56% | IRS (TY 2022) |
| Medicaid (children) | ~91% | Census ACS / PMC (2015-2019) |
| Medicaid (adults) | ~71% | Census ACS / PMC (2015-2019) |
| Section 8 | ~25% of eligible | NLIHC (supply-constrained, not demand-side) |

**Literature/Sources**: Currie (2006), Moffitt (1983, AER), Herd & Moynihan (2019), Ko & Moffitt (2022, IZA — updated take-up survey), Bhargava & Manoli (2015 — information/simplification effects on EITC take-up), USDA FNS participation rate reports, IRS EITC Central, CBO baseline projections for selected programs, HHS ASPE cross-program participation briefs.

**Wave 2 retrieval prerequisite**: This mode MUST NOT be enabled until a curated lookup table of published take-up rates by program type is available in the pipeline. The most practical approach is a maintained table sourced from FNS, IRS, CMS, and ASPE reports, rather than relying on real-time LLM retrieval of these figures.

---

## 5. Uncertainty Model Requirements

The current `p10..p90` array implies a continuous probability distribution that the LLM cannot actually compute, leading to fake precision.

### 5.1 Replacing p10..p90 with Scenario Bounds
Affordabot must move to discrete **Scenario Bounds (`low`, `base`, `high`)** at the impact level. A Monte Carlo-ready parameter distribution is overkill for Wave 1 given the quality of input data.

### 5.2 Definitions
- **`base`**: The single most defensible point estimate given available evidence. For parameters sourced from published data (BLS wages, FNS take-up rates), this is the published figure. For parameters derived from bill text (population, frequency), this is the literal number stated or the most direct inference.
- **`low`**: A plausible lower bound representing a scenario where the 1-2 most uncertain parameters take conservative values. This is NOT the 10th percentile of a distribution — it is the estimate under a specific, stated "things go better than expected" assumption. The assumption must be named.
- **`high`**: A plausible upper bound representing a scenario where the 1-2 most uncertain parameters take adverse values. Same constraint: the assumption must be named.

### 5.3 Dominant-Parameter Variation (Avoiding Corners-of-the-Box)
**The naive approach of setting all parameters simultaneously to their extreme values is a well-documented antipattern** (Morgan & Henrion 1990, *Uncertainty*; Saltelli et al. 2004; EPA 2009 modeling guidance; NRC 2009). If n independent parameters each sit at their 10th/90th percentile, the probability of the corner scenario is 0.1^n — astronomically improbable for n > 2. The resulting range is uninformatively wide and implicitly assumes perfect positive correlation among all parameters.

**Wave 1 design: dominant-parameter variation.** Instead of varying all parameters:
1. The orchestrator identifies the **1-2 parameters with the greatest uncertainty** for each mode. These are the "dominant uncertainty parameters."
2. `low` and `high` scenario bounds are computed by varying ONLY the dominant parameters while holding all others at their `base` values.
3. The `scenario_bounds` object MUST include a `dominant_parameters` array naming which parameters were varied and why.

**Per-mode dominant parameters (defaults, overridable by evidence)**:
| Mode | Typical dominant parameter(s) | Rationale |
|------|------------------------------|-----------|
| `direct_fiscal` | The fiscal note figure itself (see §5.5) | Single-source estimate; uncertainty is in the source, not in a formula |
| `compliance_cost` | `population`, `time_burden` | Wage and frequency are typically well-sourced; affected population and time-per-task are the most uncertain SCM inputs (OECD 2014) |
| `pass_through_incidence` | `pass_through_rate` (ρ) | The empirical pass-through rate dominates uncertainty in most tax incidence analyses |
| `adoption_take_up` | `take_up_rate`, `eligible_population` | Benefit amount is usually legislatively specified; participation and eligibility are uncertain |

### 5.4 LLM-Generated Parameter Ranges: Epistemological Constraints
LLM-produced low/base/high estimates are defensible ONLY when used as **literature synthesis** — i.e., the LLM is summarizing published ranges from fiscal notes, CBO reports, and academic sources. They are NOT defensible as calibrated probability estimates or expert elicitation (per Kadavath et al. 2022 on LLM calibration limitations, Halawi et al. 2024 on LLM forecasting).

**Binding constraints on LLM-generated ranges**:
1. Every parameter range MUST cite at least one source (the `source_url` and `excerpt` fields — see §7).
2. Ranges must be labeled as "literature-derived," not "model-estimated."
3. If the LLM cannot cite a source for a low/high bound, it MUST use the base value only (i.e., no uncertainty band for that parameter). Single-value parameters are honest; invented ranges are not.
4. `excerpt` is a **gate**, not merely a persistence field: if a literature-backed parameter has no excerpt from the cited source, the parameter fails validation and the mode fails closed. This prevents citation of sources the LLM has not actually read or verified.

### 5.5 Direct Fiscal Mode and Scenario Bounds
A single-number fiscal note maps into scenario_bounds as follows:
- `base`: The fiscal note figure as stated.
- `low` and `high`: If the fiscal note source provides a range, use it. If CBO or the issuing agency provides sensitivity analysis, use the stated alternatives. If only a single point estimate exists, set `low = base` and `high = base` (i.e., a zero-width band). **A single-point fiscal note with no stated uncertainty should be represented honestly as a single point, not artificially widened.** The `dominant_parameters` array is empty in this case, and a `note` field should state: "Single-point fiscal note; no uncertainty decomposition available."

### 5.6 Relationship to OMB Circular A-4
This design is consistent with OMB Circular A-4 (2023 revision) guidance for rules with annual effects below $200M (qualitative discussion of uncertainty) and $200M-$1B (sensitivity analysis with alternative scenarios). The dominant-parameter variation approach is a principled sensitivity analysis. Full Monte Carlo (encouraged by A-4 for >$1B rules) remains a non-goal for Wave 1 but is not precluded by this schema design.

## 6. Fail-Closed Rules to Prevent Fake Precision
To guarantee truthfulness, the orchestrator's evidence gates must enforce the following:

1. **Missing Parameter Gate**: If any mode's required parameters (as defined in §4) cannot be populated with a cited source, the mode fails closed to `qualitative_only`. This applies to ALL modes, not only compliance_cost.
2. **Excerpt-as-Gate**: For every literature-backed parameter (pass_through_rate, take_up_rate, and any parameter not derived from bill text or a single official source), the `excerpt` field is a **validation gate**, not merely a persistence field. If the LLM cites a source but cannot provide a verbatim excerpt from that source supporting the parameter value, the parameter fails validation and the mode fails closed. This prevents hallucinated citations — a known LLM failure mode.
3. **Population Sourcing Gate**: The `population` parameter in compliance_cost mode must be sourced from the hierarchy defined in §4A. No other parameter substitutes for a missing population count.
4. **Missing Literature Gate (Wave 2)**: For `pass_through_incidence`, the evidence payload MUST contain a URL or explicit citation to an empirical study validating the `pass_through_rate` for the relevant sector. Generic "80%" without sector-specific grounding is blocked. For `adoption_take_up`, the `take_up_rate` must be sourced from published participation data per the hierarchy in §4C.
5. **Literature Confidence Gate (Wave 2)**: If `literature_confidence` is `contested` and the resulting scenario_bounds range is wider than 3x (high/low ratio > 3.0), the mode SHOULD fail closed to `qualitative_only` with an explanation that the empirical basis is too uncertain for a defensible quantified estimate.
6. **No Bare Percentiles/Bounds**: No numeric bounds may be emitted without a populated `modeled_parameters` dictionary clearly explaining the arithmetic. The `scenario_bounds` must name the `dominant_parameters` that were varied.
7. **Mode Selection Gate**: The orchestrator must select a mode per the precedence rules in §3.1. If no mode can be selected with high confidence, the bill fails closed to `qualitative_only`. The orchestrator MUST NOT default to a mode simply because it is available.
8. **Anti-Double-Counting Gate**: If multiple impacts are quantified for the same bill, the orchestrator must verify they are economically independent (§3.1). If independence cannot be established, only the single highest-evidence impact is quantified; others fail closed to `qualitative_only`.

## 7. Canonical Persistence Design
How modeled assumptions and evidence must be represented in the database:

**`pipeline_steps` (`generate` step)**:
The `output_result` JSON must replace flat arrays with:
- `impact_mode`: string enum (`direct_fiscal`, `compliance_cost`, `pass_through_incidence`, `adoption_take_up`, `qualitative_only`)
- `scenario_bounds`: `{ "low": float, "base": float, "high": float, "dominant_parameters": [string], "note": string | null }`
- `modeled_parameters`: dict mapping parameter names to the schema below
- `mode_selection_rationale`: string (brief explanation of why this mode was chosen per §3.1)
- `composition_note`: string | null (required when multiple impacts are quantified for the same bill)

**`modeled_parameters` entry schema** (resolving value vs. low/base/high inconsistency):
Each parameter entry has this structure:
```json
{
  "base": float,           // REQUIRED: the point estimate used in the base scenario
  "low": float | null,     // OPTIONAL: value used in the low scenario (only for dominant uncertainty parameters)
  "high": float | null,    // OPTIONAL: value used in the high scenario (only for dominant uncertainty parameters)
  "is_dominant": boolean,  // whether this parameter is varied in scenario analysis
  "source_url": string,    // REQUIRED: URL or citation reference
  "excerpt": string,       // REQUIRED for literature-backed params (gate, not just persistence — see §5.4, §6)
  "source_type": string,   // one of: "bill_text", "fiscal_note", "government_data", "academic_literature", "administrative_data"
  "literature_confidence": string | null  // one of: "high", "moderate", "contested" (required for academic_literature source_type)
}
```

**Schema invariants**:
- `base` is always present and always a single float.
- `low` and `high` are non-null ONLY when `is_dominant` is true.
- When `is_dominant` is false, the parameter is held at `base` in all scenarios.
- `excerpt` is required (non-empty string) when `source_type` is `academic_literature` or `government_data`. It may be null for `bill_text` where the parameter is a literal number from the legislation.
- `literature_confidence` is required when `source_type` is `academic_literature`. It is null otherwise.
- The `scenario_bounds.low` value equals the formula output when all dominant parameters are at their `low` values and all non-dominant parameters are at `base`. Same for `scenario_bounds.high`.

**`pipeline_runs.result` & Downstream Storage (`legislation` / `impacts`)**:
Update the `LegislationImpact` schema to include:
- `impact_mode`: string
- `modeled_parameters`: JSONB (conforming to the schema above)
- `scenario_bounds`: JSONB (conforming to the schema above)
- `mode_selection_rationale`: string

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

**Non-Goals (Wave 1)**:
- Building a local Python Monte Carlo engine. The dominant-parameter variation approach (§5.3) is the v1 uncertainty design.
- Full general equilibrium / dynamic scoring. Deferred per §3 with explicit implementation gates.
- Multi-mode composition for a single bill-impact pair (§3.1). Wave 1 is single-mode-per-impact only.

**Resolved Design Questions**:
- Mode selection mechanism: defined in §3.1 with precedence rules and fail-closed on ambiguity.
- Take-up modeling grounding: Bass Diffusion removed; replaced with participation/administrative-burden literature (§4C).
- Compliance-cost population sourcing: explicit hierarchy in §4A.
- Uncertainty corners-of-the-box: replaced with dominant-parameter variation (§5.3).
- Schema consistency: resolved with unified parameter schema (§7).
- Excerpt-as-gate: defined in §5.4 and §6.

**Open Questions (to be resolved before or during implementation)**:
- **Baseline data indexing**: How to systematically index standard baseline data (BLS wages, CBO baselines, FNS take-up rates) so the LLM does not web-search them per-run. Recommendation: a static curated lookup table for Wave 1 parameters (OES wages by SOC code, ECEC overhead ratios). This is a prerequisite for production reliability but not a spec design question.
- **Wave 2 retrieval infrastructure**: The curated retrieval pipelines for empirical literature (pass-through studies, take-up data) are explicitly gated as prerequisites in §4B and §4C. The specific retrieval architecture (RAG index, curated table, or hybrid) is an implementation decision.
- **Heckman-class concerns on regime dependence**: Reduced-form elasticities estimated under one policy regime may not transfer to a different regime (the Lucas/Marschak critique). For Wave 1 modes (direct_fiscal, compliance_cost), this is not material — SCM parameters are micro-level and regime-independent. For Wave 2 modes, this concern is real: pass-through rates estimated from small state-level tax changes may not apply to large federal changes. The spec addresses this partially through literature_confidence and contested-literature fail-closed rules (§6), but implementations should monitor for this class of error.
- **Over-shifting in pass-through mode**: The current schema allows ρ > 1.0, which is correct. But presenting an over-shifted estimate (consumers bear more than 100% of the tax) to non-economist end users requires careful UX framing. This is a frontend/communication concern, not a spec design issue.

## 12. Acceptance Criteria for Future Implementation
- [ ] `LegislationImpact` schema drops `p10..p90` in favor of `scenario_bounds`, `impact_mode`, and `modeled_parameters`.
- [ ] Orchestrator explicitly supports `direct_fiscal` and `compliance_cost` modes.
- [ ] Sufficiency gates deterministically fail closed if a mode's required parameters are not backed by cited evidence.
- [ ] Slack summaries output the `impact_mode` and failure reasons if parameters are missing.
- [ ] `/api/admin/pipeline-runs` surfaces the extracted parameters for auditability.
