# Product Target: Cost-of-Living Analysis Archetype

Feature key: `bd-3wefe.13`  
Captured from founder-provided screenshot on `2026-04-16` during the data-moat/economic-analysis POC.

## Why This Matters

This is a target example for what Affordabot should eventually produce from the
data moat plus economic-analysis pipeline.

The example is not merely a link summary. It translates a local/regional policy
rule into household-relevant economic consequences using explicit mechanisms,
population scope, cost assumptions, and uncertainty.

## Example Shape

The screenshot describes a Bay Area natural-gas appliance rule and frames it as
a cost-of-living burden:

- Policy action: regional air-quality rule restricting replacement or purchase
  of traditional natural gas water heaters and furnaces over time.
- Jurisdiction/scope: Bay Area regional regulator and nearly three million
  households/housing units.
- Direct affected objects: water heaters, furnaces, HVAC systems.
- Direct compliance costs: equipment and labor ranges for heat-pump water
  heaters and HVAC conversion.
- Indirect/system costs: grid upgrades and utility infrastructure spending
  passed through to ratepayers.
- Household/economic conclusion: aggregate household burden and cost-of-living
  impact, with uncertainty rather than false precision.

## Target Pipeline Behavior

Affordabot should be able to produce this class of analysis from stored evidence:

1. Identify the policy rule and effective dates from official source material.
2. Determine who/what is affected:
   - households,
   - housing units,
   - businesses,
   - permits,
   - service providers,
   - infrastructure/ratepayer base.
3. Extract or research direct cost parameters:
   - equipment cost,
   - labor/installation cost,
   - fee/tax/rate,
   - required time/training/compliance burden,
   - affected unit count.
4. Build an indirect mechanism graph:
   - rule requirement -> compliance burden,
   - compliance burden -> capital/labor/supply effects,
   - utility/system cost -> ratepayer pass-through,
   - market or household channel -> cost-of-living impact.
5. Trigger secondary research when local policy evidence lacks economic
   parameters:
   - provider/query provenance,
   - source ranking,
   - reader output,
   - assumption applicability,
   - package linkage back to the policy package.
6. Produce a user-facing conclusion only when the evidence package can support
   it. Otherwise, fail closed with named missing parameters and assumptions.

## Data-Moat Requirements Implied By This Example

The data moat must capture more than economic rows:

- official rule text, agendas, minutes, staff reports, ordinances, attachments;
- regulator/jurisdiction identity and effective dates;
- affected asset classes and covered populations;
- structured source rows where available;
- raw and normalized policy evidence that may be sold or reused independently
  even before economic analysis is ready.

The economic pipeline then consumes this data package. It must not confuse
valuable stored local-government data with decision-grade economic analysis.

## Gate Implications

This archetype reinforces the split we are implementing:

- `stored_policy_evidence`: valuable, source-grounded local-government data.
- `economic_handoff_candidate`: stored evidence has direct or indirect economic
  signals worth modeling.
- `economic_analysis_ready`: the package has source-bound parameters,
  assumptions, model cards, arithmetic, and uncertainty sufficient for a
  decision-grade conclusion.

Economic analysis remains a required product gate, but the data moat may have
standalone product value before it reaches economic readiness.

## Acceptance Bar For Similar Outputs

A future Affordabot result in this style must include:

- policy source citations and dates;
- affected population/unit count with provenance;
- direct cost parameter table with units/ranges;
- indirect mechanism graph;
- assumption/model cards for pass-through, adoption, incidence, and timing;
- uncertainty/sensitivity ranges;
- explicit unsupported-claim rejection;
- final conclusion only when gates pass.

If any of those are missing, the product should show a useful evidence package
and a fail-closed economic-analysis state rather than inventing a conclusion.
