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

The second ultra-reach `dx-review` explicitly supports this target but makes
three items blocking before another implementation/eval cycle:

1. official-source dominance must be implemented through a central
   source/identity classification surface, not scattered heuristics;
2. freshness, source-shape drift, update-cadence drift, and last-successful
   refresh must be measured as moat durability signals;
3. the corpus matrix and scorecard schema must exist before another live run so
   the next cycle is not another San Jose vertical by accident.

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

Implementation requirement:

- official-source classification must be produced by one backend-owned
  source/identity service or ruleset;
- ranker, package builder, bridge/read model, corpus scorecard, and manual audit
  must consume the same classification result;
- every candidate must carry `source_officialness`,
  `source_of_truth_role`, `jurisdiction_match`, `policy_family_match`,
  `external_context_allowed`, and `primary_evidence_allowed`;
- external sources may be stored but must default to secondary context unless a
  documented promotion rule applies.

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

### C7 Freshness And Drift Durability Gate

Pass requires the corpus and every package to expose durability metadata:

- source cadence or expected update interval when known;
- `retrieved_at`;
- `source_published_at`, `meeting_date`, `adoption_date`, `effective_date`, or
  explicit `date_not_found`;
- last successful refresh for the same canonical source identity;
- source-shape version or schema fingerprint where available;
- `source_shape_changed` when expected fields, attachment structures, or portal
  layout change;
- `update_cadence_drift` when the source has not refreshed as expected;
- `stale_for_policy_use` when the source is too old for the package's stated
  use;
- next refresh recommendation.

Fail if stale, drifted, or source-shape-changed data can still produce a pass
without being surfaced in package status and the corpus scorecard.

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

This phase is the first executable task. It must finish before another live
Windmill/Railway eval cycle. Required fields:

- `corpus_row_id`;
- jurisdiction name, type, state/region, and canonical id;
- policy family and mechanism family;
- target query families;
- expected official source families;
- expected structured source families;
- known official domains/endpoints;
- economic mechanism plausibility;
- required package verdict floor;
- manual audit sampling priority;
- golden regression expectation.

### Phase 2: Official-Source Dominance

Improve query templates, source classification, ranking, and portal/external
demotion so official sources win primary selection. Private SearXNG remains the
primary low-cost discovery path.

This phase must add the central source/identity classification surface required
by C1. It should absorb or wrap existing officialness, jurisdiction, and policy
family heuristics so the ranker, builder, read model, corpus scorecard, and
manual audit use one decision.

### Phase 3: Structured Source Breadth

Ingest or explicitly catalog true structured API/raw sources across the corpus.
Legistar metadata may contribute identity/provenance, but it is not enough to
claim structured economic depth unless it materially improves the package.

### Phase 4: Unified Package Build And Storage

Create or reuse one `PolicyEvidencePackage` per corpus row. Prove Postgres,
MinIO, pgvector, Windmill run linkage, and admin/read-model visibility.

Packages must carry C7 freshness/drift fields into storage/readback and the
admin/read model. If the existing schema cannot carry these fields without
validator bloat, add a domain-level gate report or source-quality record rather
than forcing cross-field product logic into the Pydantic model.

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
- `docs/poc/policy-evidence-quality-spine/artifacts/source_identity_rules.json`
- `docs/poc/policy-evidence-quality-spine/artifacts/source_freshness_drift_scorecard.json`
- updated source catalog artifact;
- updated Beads notes and metadata.

## Recommended First Task

Do not run another live cycle first. Start by implementing the corpus matrix and
scorecard contract, then run the smallest real corpus pass that can expose
whether the dominant failure is official-source selection, structured-source
breadth, package identity, storage/readback, or economic handoff.

First implementation wave:

1. Build the corpus matrix and scorecard schema.
2. Centralize source/identity/officialness classification and wire it into
   ranker/package/read-model scoring.
3. Add freshness/drift durability gates and artifacts.
4. Only then run the first small real corpus pass and manual audit.

## Implementation Work Packages

These are the implementation-ready work packages for the next session. They are
ordered so agents cannot accidentally run another narrow live cycle before the
benchmark shape exists.

### WP1: Corpus Matrix And Scorecard Contract

Owner: data-moat/runtime agent.

Inputs:

- this spec;
- `2026-04-16-data-moat-quality-gates.md`;
- current policy evidence quality-spine artifacts;
- source catalog artifacts and brownfield map.

Outputs:

- `local_government_corpus_matrix.json`;
- `local_government_corpus_scorecard.json`;
- `local_government_corpus_report.md`;
- schema or Pydantic/dataclass definitions if needed;
- validation command that can run without live infra against fixture rows.

Acceptance:

- matrix has 30 to 50 target rows, or a smaller seed set with explicit
  `corpus_ready_with_gaps` status and expansion backlog;
- rows cover the required jurisdiction, policy-family, and source-family axes;
- every row has expected official source families and expected structured
  sources or source-catalog absence;
- scorecard computes C0-C7 and per-package D0-D11/E handoff status;
- scorecard fails if manual-audit fields are missing for sampled rows.

### WP2: Central Source/Identity Classification

Owner: source-quality/ranker agent.

Inputs:

- Cycle 42/43 external-source failures;
- current ranker/source-family code;
- source catalog;
- corpus matrix official-source expectations.

Outputs:

- backend-owned source/identity classification module, service, or ruleset;
- one classification result consumed by ranker, builder, bridge/read model,
  scorecard, and audit;
- source identity rules artifact:
  `artifacts/source_identity_rules.json`;
- regression tests covering official San Jose/Legistar, non-Legistar official
  sources, state/regional official sources, advocacy PDFs, news, vendor pages,
  and ambiguous portals.

Acceptance:

- C1 cannot pass without this central classification result;
- external sources cannot be primary evidence by default;
- official source boost/demotion behavior is deterministic and test-covered;
- package/read-model output exposes why a source was official primary evidence,
  secondary context, or rejected.

### WP3: Freshness, Drift, And Durability Gates

Owner: package-quality/gates agent.

Inputs:

- D8 robustness gate;
- source catalog cadence/freshness fields;
- package storage/readback paths;
- prior stale/stub artifact issues.

Outputs:

- `source_freshness_drift_scorecard.json`;
- C7 corpus gate implementation;
- package/read-model fields or gate-report entries for source cadence,
  retrieved date, source date, last successful refresh, source-shape
  fingerprint, source-shape drift, update-cadence drift, stale-for-policy-use,
  and next refresh recommendation.

Acceptance:

- stale or drifted sources cannot silently pass;
- unavailable or shape-changed structured sources become `not_proven`, `fail`,
  or `cataloged_unavailable`, not `integrated`;
- durability fields are persisted or included in queryable gate reports;
- the admin/read model can display freshness/drift caveats without recomputing
  truth.

### WP4: First Small Corpus Pass And Manual Audit

Owner: orchestrator plus implementation agents.

Prerequisites:

- WP1 complete;
- WP2 complete enough to score official-source dominance;
- WP3 complete enough to score freshness/drift.

Outputs:

- first real corpus pass over a seed subset;
- `manual_audit_local_government_corpus.md`;
- `golden_policy_regression_set.md`;
- updated source catalog;
- Beads comment with package ids, run ids, corpus status, and next blockers.

Acceptance:

- manual audit samples multiple jurisdictions, policy families, and source
  families;
- every sampled package has source officialness, structured contribution,
  package identity, storage/readback, data-moat value classification, economic
  handoff classification, and dominant failure class;
- terminal state is one of `decision_grade_corpus`,
  `corpus_ready_with_gaps`, `package_mechanics_only`, `fail`, or
  `blocked_hitl`;
- if the result is not at least `corpus_ready_with_gaps`, the next blockers are
  implementation-specific, not narrative.
