# 2026-04-17 Local Government Data Moat Benchmark v0

Feature-Key: `bd-3wefe`

## Summary

This spec upgrades the next Affordabot reach goal from a San Jose vertical
proof to a corpus-level data-moat benchmark.

San Jose remains a calibrated fixture because prior work has live Windmill,
private SearXNG, Legistar, storage, and manual-audit evidence. It is not the
product boundary. The product claim is broader: Affordabot can repeatedly build
official-source-dominant, durable, structured-plus-scraped local-government
evidence packages across jurisdictions and policy families, then classify each
package for economic-analysis handoff.

## Problem

The previous quality-spine cycles proved important mechanics and exposed real
data-quality failures:

- official CLF evidence can flow through the package/storage/read-model path;
- broad policy evidence can be classified as `stored_not_economic`;
- economic readiness and data-moat value must be separated;
- external advocacy PDFs can still outrank official sources in broad policy
  scenarios;
- San Jose/Legistar/CLF-specific tuning risks overfitting the architecture.

The next goal must therefore test whether the data moat generalizes beyond one
jurisdiction and one economic-fee vertical.

## Goals

1. Build a small real corpus, not a single cherry-picked vertical.
2. Preserve data value even when economic analysis is not ready.
3. Keep economic-analysis suitability visible through explicit handoff
   classification.
4. Measure official-source dominance, source-family diversity, structured
   enrichment, package reuse, storage/readback, Windmill linkage, and manual
   audit quality.
5. Produce reusable golden fixtures for future search/ranker/reader/package
   regression work.

## Non-Goals

- No architecture lock.
- No paid provider as primary.
- No migration of product logic into Windmill.
- No frontend recomputation of package or economic truth.
- No claim that every package must produce quantitative economic output.
- No use of Tavily, Exa, or SearXNG snippets as true structured-source proof.

## Active Contract

The next super-reach implementation target is:

`local_government_data_moat_benchmark_v0`

Required terminal states:

- `decision_grade_corpus`: corpus and selected economic deep dives satisfy the
  corpus gates plus package gates.
- `corpus_ready_with_gaps`: valuable official-source-dominant corpus exists,
  with exact missing structured/economic/readiness gaps.
- `package_mechanics_only`: transport/storage/read-model works, but corpus data
  substance does not pass and no non-destructive improvement path remains.
- `fail`: current architecture cannot satisfy the data-moat standard, with
  evidence.
- `blocked_hitl`: only for strategic or external blockers that cannot be fixed
  non-destructively.

Forbidden terminal states:

- San Jose-only pass.
- CLF/fee-row-only pass.
- "Windmill/storage/admin worked."
- "Economic analysis failed closed."
- "SearXNG found one PDF."
- "Tavily rescued the parameters."

## Corpus Scope

Minimum benchmark target:

- 30 to 50 evidence packages.
- At least 3 jurisdictions.
- At least 5 policy families.
- At least 3 source families.
- At least 20 manually sampled packages across the corpus, or all packages if
  the first pass produces fewer than 20.
- At least 5 economic-handoff candidates.
- At least 2 economic deep dives:
  - one direct cost or fiscal/fee case;
  - one indirect household cost-of-living or secondary-research case.

Jurisdiction archetypes:

- Legistar city: San Jose remains the primary calibrated fixture.
- Non-Legistar city or county: agenda PDFs, clerk site, custom civic portal, or
  open data portal.
- State or regional regulator: California state, county, BAAQMD/CARB-style
  regulator, or another official public body affecting local costs.

Policy-family targets:

- housing, permits, impact fees, development rules;
- parking, transportation demand management, streets, mobility;
- business licensing, compliance, inspections, local taxes/fees;
- utilities, building standards, electrification, air quality, energy;
- council actions, ordinances, resolutions, agenda items, minutes;
- code enforcement, permits, procurement, public safety, or general governance
  when the source is official and durable.

Source-family targets:

- private SearXNG scraped official HTML/PDF artifacts;
- Legistar or equivalent agenda/meeting API metadata;
- OpenStates or state API/raw data where relevant;
- CKAN, Socrata, ArcGIS, OpenDataSoft, static CSV/JSON/raw files where
  available;
- official PDFs/HTML/raw attachments;
- Tavily/Exa only as fallback, context, or secondary economic research.

## Corpus Gates

These corpus gates sit above the package-level D0-D11 gates in
`2026-04-16-data-moat-quality-gates.md`.

### C0 Corpus Scope Gate

Pass requires the benchmark to cover the required jurisdiction, policy-family,
source-family, package-count, and manual-audit scope, or to document an exact
evidence-backed shortfall.

Fail if the run remains San Jose-only, Legistar-only, CLF/fee-only, or
single-source-family.

### C1 Official-Source Dominance Gate

Pass requires at least 80 percent of manually audited packages to select an
official primary source: city, county, state, regulator, clerk, agenda system,
official open data portal, or official attachment.

External advocacy, news, vendor, nonprofit, and campaign sources may be retained
as context, but they cannot satisfy primary evidence unless a documented
source-of-truth rule explicitly promotes them for a narrow use.

Fail if external sources win primary selection without a hard failure verdict.

### C2 Source-Family Diversity Gate

Pass requires at least three source families in the corpus, including at least
one true structured API/raw source where available.

Fail if the corpus is effectively private SearXNG plus PDFs only, unless the
source catalog proves structured-source absence for the selected jurisdictions
and policy families.

### C3 Package Reusability Gate

Pass requires each package to have standalone data value classification:

- `economic_analysis_ready`;
- `economic_handoff_candidate`;
- `secondary_research_needed`;
- `qualitative_only`;
- `stored_not_economic`;
- `not_policy_evidence`;
- `fail`.

Packages can pass as data-moat assets even when not economic-ready if they are
official, source-grounded, deduped, stored, auditable, and correctly classified.

### C4 Economic Handoff Distribution Gate

Pass requires at least 5 packages to be plausible economic-handoff candidates
and at least 2 packages to reach deeper economic analysis or governed
secondary-research proof.

Fail if the corpus has data value but the economic engine receives no clear
handoff packets, no missing-parameter inventory, and no recommended next action.

### C5 Manual Audit Sampling Gate

Pass requires orchestrator manual audit across jurisdictions, policy families,
and source families. The audit must include at least:

- selected primary source;
- source officialness;
- source-family type;
- structured-source contribution;
- package identity;
- storage/readback evidence;
- data-moat value classification;
- economic handoff classification;
- dominant failure class.

Fail if manual audit inspects only the best San Jose package.

### C6 Golden Regression Gate

Pass requires the benchmark to produce a reusable golden set for future
regressions. Each row must include stable query inputs, expected jurisdiction,
expected policy family, selected source URL, package id, verdict, and failure
class.

Fail if future agents cannot rerun the scorecard and compare whether search,
ranking, reader, structured enrichment, or package quality improved.

## Package Gates

Every package must still be evaluated by the D0-D11 data-moat gates and E1-E5
economic-analysis gates where applicable. The corpus can contain packages that
are `stored_not_economic` or `qualitative_only`, but those packages must be
honestly classified and must not be counted as economic-analysis-ready.

## Implementation Phases

### Phase 1: Corpus Matrix Contract

Define the machine-readable corpus matrix schema and seed target rows:
jurisdiction, policy family, query family, expected source families, structured
source candidates, and economic mechanism plausibility.

### Phase 2: Official-Source Dominance

Improve query templates, source classification, ranking, and portal/external
demotion so official sources win primary selection. Private SearXNG remains the
primary low-cost discovery path.

### Phase 3: Structured Source Breadth

Ingest or explicitly catalog true structured API/raw sources across the corpus.
Legistar metadata may contribute identity/provenance, but it is not enough to
claim structured economic depth unless it materially improves the package.

### Phase 4: Unified Package Build And Storage

Create or reuse one `PolicyEvidencePackage` per corpus row. Prove Postgres,
MinIO, pgvector, Windmill run linkage, and admin/read-model visibility.

### Phase 5: Economic Handoff Classification

Classify every package for economic handoff. Promote only eligible packages into
direct analysis, indirect analysis, or secondary-research package generation.

### Phase 6: Manual Audit And Review Packet

Produce corpus scorecards, manual audit docs, golden regression artifacts, and a
review packet for `dx-review` and external consultants.

## Beads Updates

The current `bd-3wefe.13` San Jose quality-spine POC should be revised to
become the corpus-level benchmark task. San Jose stays as one golden fixture.

`bd-3wefe.8` architecture review must depend on corpus-level evidence, not only
on one vertical package.

## Validation

Required artifacts:

- `docs/specs/2026-04-17-local-government-data-moat-benchmark-v0.md`
- `docs/poc/policy-evidence-quality-spine/artifacts/local_government_corpus_matrix.json`
- `docs/poc/policy-evidence-quality-spine/artifacts/local_government_corpus_scorecard.json`
- `docs/poc/policy-evidence-quality-spine/local_government_corpus_report.md`
- `docs/poc/policy-evidence-quality-spine/manual_audit_local_government_corpus.md`
- `docs/poc/policy-evidence-quality-spine/golden_policy_regression_set.md`
- updated source catalog artifact;
- updated Beads notes and metadata.

## Recommended First Task

Do not run another live cycle first. Start by implementing the corpus matrix and
scorecard contract, then run the smallest real corpus pass that can expose
whether the dominant failure is official-source selection, structured-source
breadth, package identity, storage/readback, or economic handoff.
