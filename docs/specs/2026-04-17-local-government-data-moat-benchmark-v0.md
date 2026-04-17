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
6. Define the data moat as a standalone data product surface, not only an
   internal evidence package for the economic engine.

## Data Moat Product Surface

Affordabot's data moat can be valuable before a final cost-of-living analysis
is ready. The benchmark must therefore prove a product-consumable data surface.

A consumer of the moat should receive:

- normalized policy packages with stable package ids, jurisdiction ids,
  source ids, document ids, attachment ids, and structured row ids;
- source-grounded evidence cards with excerpts, structured fields, timestamps,
  hashes/storage refs where available, and officialness/source-of-truth labels;
- package classifications that distinguish `economic_analysis_ready`,
  `economic_handoff_candidate`, `secondary_research_needed`,
  `qualitative_only`, `stored_not_economic`, `not_policy_evidence`, and `fail`;
- provenance and freshness metadata sufficient to decide whether data can be
  trusted, refreshed, exported, or reused;
- query/export surfaces for corpus rows, packages, evidence cards,
  classifications, source-quality metrics, and handoff packets.

The product guarantees targeted by v0 are official-source dominance,
structured-plus-scraped lineage, normalized queryable fields, freshness/drift
detection, source licensing/export posture, and economic handoff
classification. The moat is the accumulated, refreshed, deduped,
source-grounded local-government corpus; the economic engine is a downstream
consumer of that corpus, not the only product surface.

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

The late Opus ultra-reach review raises the bar further. It agrees with the
corpus direction but says the v0 gates are still benchmark-sized, not moat-sized.
Before another implementation/eval cycle, this spec must also require:

1. freshness/cadence, historical backfill, cross-jurisdiction identity and
   dedupe, structured normalization/exportability, licensing/ToS posture,
   schema evolution, and coverage-of-known-policies gates;
2. official-source dominance thresholds that are strict enough to prevent
   external advocacy/news/vendor evidence from becoming the effective primary
   corpus;
3. true structured-source breadth that cannot be satisfied by Legistar metadata
   only or SearXNG plus PDFs;
4. stratified manual audit and a larger direct/indirect/secondary economic
   deep-dive quota;
5. a blind seed list and machine-readable taxonomy so ranker tuning cannot
   overfit the benchmark rows.

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

Ultra-reach benchmark target:

- 75 to 120 evidence packages, or a smaller first corpus pass that reports
  `corpus_ready_with_gaps` and cannot claim `decision_grade_corpus`.
- At least 6 jurisdictions, including at least 2 non-California jurisdictions
  to force taxonomy generalization.
- At least 8 policy families.
- At least 5 source families.
- At least 30 stratified manually sampled packages, or all packages if the
  first pass produces fewer than 30.
- At least 50 percent of corpus packages with at least 2 source families tied
  to the same canonical policy identity.
- No single jurisdiction may contribute more than 40 percent of the corpus for
  a `decision_grade_corpus` claim.
- At least 10 percent of the corpus must be valid `stored_not_economic` or
  `qualitative_only` policy evidence.
- At least 3 non-fee policy families must have structured extraction depth, not
  merely stored documents.
- At least 10 economic-handoff candidates.
- At least 6 economic deep dives:
  - at least 3 direct cost or fiscal/fee cases;
  - at least 2 indirect household cost-of-living mechanisms;
  - at least 1 secondary-research-required case;
  - at least 1 non-San-Jose deep dive;
  - at least 1 non-CLF policy-family deep dive.

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

Anti-tokenism rule: a jurisdiction does not count toward the 6-jurisdiction
floor unless it contributes at least 5 packages.

Composition rule: no single jurisdiction may contribute more than 40 percent of
packages for `decision_grade_corpus`; at least 10 percent of packages must be
valid `stored_not_economic` or `qualitative_only` policy evidence; and at least
3 non-fee policy families must have depth beyond document storage.

Fail if the run remains San Jose-only, California-only, Legistar-only,
CLF/fee-only, benchmark-sized while claiming ultra-reach, or single-source-family.

### C1 Official-Source Dominance Gate

Pass requires official primary-source dominance:

- at least 90 percent of manually audited P0/P1 packages;
- at least 85 percent corpus-wide;
- hard fail if audited or corpus-wide dominance is below 80 percent.

External advocacy, news, vendor, nonprofit, and campaign sources may be retained
as context, but they cannot satisfy primary evidence unless a documented
source-of-truth rule explicitly promotes them for a narrow use.

Secondary-search-derived primary selection is capped:

- Tavily/Exa-derived primary selection must be 0 percent in the audited sample;
- Tavily/Exa-derived primary selection must be at most 5 percent corpus-wide;
- SearXNG snippets are never primary evidence; SearXNG is discovery only.

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
- external-source promotions must be recorded in a machine-checked
  `external_source_promotion_register` with rule id, source URL, package id,
  reason, and reviewer/audit status; the scorecard must fail if promotions
  exceed the corpus cap or if any promotion lacks a rule id.

### C2 Source-Family Diversity Gate

Pass requires structured-source depth, not just source-family labels:

- at least 5 source families across the corpus;
- at least 2 true structured API/raw families, excluding secondary search;
- at least 1 non-Legistar structured source live-proven against the current
  corpus, such as OpenStates, CKAN, Socrata, ArcGIS, OpenDataSoft, or static
  CSV/JSON/raw files;
- structured-source coverage for at least 40 percent of
  policy-family-by-jurisdiction cells, or catalog-level absence evidence per
  uncovered cell.
- at least one true structured source live-proven for every counted
  non-primary jurisdiction, or exact infrastructure/source-catalog evidence for
  why that jurisdiction cannot yet count toward `decision_grade_corpus`.

Legistar metadata-only does not satisfy structured depth unless it contributes
normalized economic rows, policy-structure rows, effective-date rows, or
cross-source identity/freshness/dedupe signals that materially improve the
package.

Fail if the corpus is effectively private SearXNG plus PDFs plus shallow
Legistar metadata, unless the source catalog proves structured-source absence
for the selected jurisdictions and policy families.

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

The corpus scorecard must also reconcile package data-value classes with the
package-level D11 economic handoff quality:

| C3 data-value class | Required D11 handoff quality |
| --- | --- |
| `economic_analysis_ready` | `analysis_ready` |
| `economic_handoff_candidate` | `analysis_ready_with_gaps` or `analysis_ready` |
| `secondary_research_needed` | `analysis_ready_with_gaps` |
| `qualitative_only` | `not_analysis_ready` with qualitative reason |
| `stored_not_economic` | `not_analysis_ready` with non-economic value reason |
| `not_policy_evidence` | `not_analysis_ready` with false-positive reason |
| `fail` | `not_analysis_ready` or package `fail` |

Pass requires `handoff_taxonomy_reconciled=true` for every package row. Fail if
the same package can pass under C3 while D11 reports an incompatible state.

Implementation requirement: add a first-class package classification contract,
preferably `DataMoatPackageClassification`, with exactly the seven C3 classes.
The class must be schema-validated and emitted in package/read-model/scorecard
outputs; it must not remain a set of scattered booleans or inline conditionals.

`not_policy_evidence` is capped at 15 percent of the corpus. A higher share
means discovery or ranking is broken, not that the corpus is honestly filtered.
Every `not_policy_evidence` row must record whether it is off-topic, vendor,
news, advocacy, duplicate, wrong jurisdiction, or other.

### C4 Economic Handoff Distribution Gate

Pass requires at least 10 packages to be plausible economic-handoff candidates
and at least 6 packages to reach deeper economic analysis or governed
secondary-research proof:

- at least 3 direct-cost deep dives;
- at least 2 indirect-mechanism deep dives;
- at least 1 secondary-research-required deep dive;
- at least 1 non-San-Jose deep dive;
- at least 1 non-CLF policy-family deep dive.

Every deep dive must produce parameter/assumption/model-card artifacts that are
reusable by another corpus row, or explicitly mark why reuse is not possible.
Pass requires `model_card_reuse_count >= 1` for each recurring model family.

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

Sampling must be stratified:

- at least 30 manually audited packages, or all packages if fewer than 30 exist;
- at least 3 audited packages per counted jurisdiction;
- at least 2 audited packages per counted policy family;
- at least 2 audited packages per counted source family;
- at least 2 non-San-Jose jurisdictions must each contribute at least 5 audited
  or corpus packages before any pass claim.

Fail if manual audit inspects only the best San Jose package, only CLF packages,
or only packages already known to pass.

### C6 Golden Regression Gate

Pass requires the benchmark to produce a reusable golden set for future
regressions. Each row must include stable query inputs, expected jurisdiction,
expected policy family, selected source URL, package id, verdict, and failure
class.

The regression set must reference a versioned machine-readable taxonomy file for
jurisdictions, policy families, source families, handoff classes, and failure
classes. Golden rows must be versioned against that taxonomy.

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

### C8 Cross-Jurisdiction Identity And Dedupe Gate

Pass requires canonical source and policy identity across jurisdictions:

- jurisdiction-aware canonical keys for policy, source, document, attachment,
  meeting item, and structured row;
- state/regional policies referenced by multiple cities/counties deduped into
  one canonical source where appropriate, with local references preserved;
- superseded, amended, adopted, effective, and expired versions linked rather
  than overwritten;
- duplicate scraped/structured/secondary references counted once in package
  evidence while preserving lane provenance.

Fail if the same policy/source is stored as unrelated packages across
jurisdictions, if local and state/regional identities collapse incorrectly, or
if dedupe hides meaningful local applicability differences.

### C9 Structured Normalization And Exportability Gate

Pass requires the corpus to expose normalized, queryable fields that make the
data product consumable outside the current UI:

- currency, percent, count, date, and unit normalization;
- jurisdiction, geography, district, parcel/project, and applicability taxonomy
  fields where available;
- policy-family and mechanism-family taxonomy values;
- source and evidence type taxonomy values;
- effective/adoption/publication/retrieval dates or explicit unknown states;
- export artifact or API/read-model shape suitable for customer consumption;
- evidence-level provenance fields preserved in export.

Fail if the corpus can only be inspected through bespoke JSON blobs, if units
cannot be compared across rows, or if a customer cannot query/filter/export the
data product without re-running extraction logic.

### C9a Data Product Surface Gate

Pass requires the benchmark to document and exercise at least one concrete
consumer surface:

- backend read API endpoint or export artifact for corpus packages;
- stable schema for package, evidence, parameter/structured fact, source metric,
  classification, freshness, and handoff records;
- access-control assumptions for internal/admin vs future customer use;
- query examples for jurisdiction, policy family, source family, officialness,
  freshness, and classification.

Fail if the data moat is only inspectable through ad hoc local artifacts or
developer-only scripts.

### C10 Source Licensing, Robots, And ToS Gate

Pass requires every source family in the corpus to have a licensing/access
posture record:

- public-domain/open-data/license text when available;
- robots.txt or ToS posture for scraped sites where applicable;
- rate-limit and attribution notes;
- allowed storage/export posture;
- whether evidence can be redistributed, only stored internally, or only linked.

Fail if the corpus claims data-product readiness while source licensing,
robots/ToS, redistribution, or attribution posture is unknown for material
source families.

### C11 Schema Evolution And Package-Version Contract

Pass requires a versioned package/schema contract:

- package schema version;
- source taxonomy version;
- gate version;
- migration/backfill compatibility notes;
- field deprecation/addition rules;
- forward-compatible unknown-field handling;
- scorecard compatibility with prior corpus runs.

Fail if future package rows cannot be compared to current rows because schema,
taxonomy, or gate versions are implicit.

### C12 Coverage-Of-Known-Policies Gate

Pass requires evaluation against a seeded reference list of known policies, not
only discovered packages:

- at least one blind seed list held out from ranker/query tuning;
- reference policies with jurisdiction, policy family, expected official source
  family, expected structured source family where known, and expected economic
  handoff class;
- coverage percentage by jurisdiction and policy family;
- explicit missed-policy failure classes.

Fail if the corpus contains many packages but misses the seeded high-value
policies, or if the seed list is tuned after seeing ranker outcomes.

### C13 Windmill Batch Orchestration Gate

Pass requires corpus-level orchestration proof:

- every corpus row records `windmill_live`, `cli_only`, or `mixed` orchestration;
- every live row records Windmill flow/run/job ids linked to package ids;
- corpus scorecard reports orchestration share;
- `cli_only` rows are capped at 10 percent for any `decision_grade_corpus`
  claim.

Fail if 30 to 120 packages are produced by ad hoc CLI runs while claiming the
pipeline is reproducible as a live data-moat product.

### C14 Policy-Family Extraction Depth Gate

Pass requires policy-family-specific extraction beyond fee schedules:

- extraction templates for at least 3 non-fee policy families, such as zoning
  amendments, affordable-housing mandates, short-term-rental regulations,
  parking/TDM rules, business licensing/compliance, permits/inspections, or
  meeting-action lineage;
- at least 2 non-fee policy families exercised in live packages;
- extracted structured facts must include applicability, effective date or
  explicit unknown date, jurisdiction/geography, source locator, and policy
  action type;
- `stored_not_economic` packages must still preserve useful structured facts
  when the policy is not immediately quantifiable.

Fail if corpus depth remains CLF/fee/rate-shaped while other policy families
are only stored as raw documents.

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
- golden regression expectation;
- blind-seed flag and tuning/evaluation split;
- known-policy reference id when applicable;
- expected licensing/ToS posture;
- schema/taxonomy versions.

The matrix must separate a ranker/query tuning cohort from a held-out blind
evaluation cohort. Do not tune ranking/query templates on held-out rows.

This phase must also split infrastructure readiness from corpus scoring. A
matrix row cannot count toward corpus pass until its source-family
infrastructure lane is explicitly `live_integrated`, `cataloged_unavailable`,
or `blocked_hitl`.

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

The first corpus pass must live-prove at least one non-Legistar structured
source or end in `corpus_ready_with_gaps` with exact access/source-family gaps.
The implementation wave must also wire at least one non-San-Jose structured
source into runtime enrichment, not only the source catalog. Candidate lanes
include OpenStates, California LegInfo/raw files, Socrata, CKAN, ArcGIS,
OpenDataSoft, or static CSV/JSON/raw files.

### Phase 3a: Policy-Family Extraction Templates

Add extraction templates for at least 3 non-fee policy families before claiming
corpus depth. The first pass should exercise at least 2 of them live. Templates
should produce structured facts even when economic analysis is not ready.

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

The deep-dive subset must satisfy the C4 quota. Economic analysis is not the
dominant focus of this session, but Product B cannot remain represented by two
San-Jose-only examples.

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
- `docs/poc/policy-evidence-quality-spine/artifacts/corpus_taxonomy_v1.json`
- `docs/poc/policy-evidence-quality-spine/artifacts/local_government_corpus_matrix.json`
- `docs/poc/policy-evidence-quality-spine/artifacts/local_government_corpus_scorecard.json`
- `docs/poc/policy-evidence-quality-spine/local_government_corpus_report.md`
- `docs/poc/policy-evidence-quality-spine/manual_audit_local_government_corpus.md`
- `docs/poc/policy-evidence-quality-spine/golden_policy_regression_set.md`
- `docs/poc/policy-evidence-quality-spine/artifacts/source_identity_rules.json`
- `docs/poc/policy-evidence-quality-spine/artifacts/source_freshness_drift_scorecard.json`
- `docs/poc/policy-evidence-quality-spine/artifacts/external_source_promotion_register.json`
- `docs/poc/policy-evidence-quality-spine/artifacts/known_policy_reference_list.json`
- `docs/poc/policy-evidence-quality-spine/artifacts/source_licensing_tos_register.json`
- `docs/poc/policy-evidence-quality-spine/artifacts/package_schema_version_contract.json`
- `docs/poc/policy-evidence-quality-spine/artifacts/corpus_windmill_orchestration_scorecard.json`
- `docs/poc/policy-evidence-quality-spine/artifacts/data_product_surface_contract.json`
- `docs/poc/policy-evidence-quality-spine/artifacts/non_fee_extraction_templates.json`
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
3. Add freshness/drift, identity/dedupe, normalization/exportability,
   licensing/ToS, schema-version, known-policy coverage, and Windmill batch
   orchestration gates.
4. Create the taxonomy and blind seed list.
5. Add the first-class data-moat package classification contract.
6. Wire at least one non-San-Jose structured source into runtime enrichment.
7. Add non-fee extraction templates.
8. Only then run the first small real corpus pass and manual audit.

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

- matrix has 75 to 120 target rows, or a smaller seed set with explicit
  `corpus_ready_with_gaps` status and expansion backlog;
- rows cover the required jurisdiction, policy-family, and source-family axes;
- rows include at least 6 jurisdictions, 8 policy families, 5 source families,
  tuning/evaluation split, and blind-seed identifiers;
- every row has expected official source families and expected structured
  sources or source-catalog absence;
- scorecard computes C0-C14 and per-package D0-D11/E handoff status;
- scorecard reconciles C3 data-value class with D11 handoff quality;
- matrix distinguishes infrastructure milestones from corpus package rows;
- data product surface and export/read API expectations are included;
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
- official-source dominance thresholds are computed corpus-wide and for the
  audited sample;
- Tavily/Exa primary selection caps are enforced;
- every external primary-source promotion is recorded in the promotion register;
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
- C8-C13 corpus gate skeletons or scorecard checks where this work package owns
  shared source/package durability metadata;
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

### WP4: Taxonomy, Coverage, Export, Licensing, And Schema Contract

Owner: data-product contract agent.

Inputs:

- this spec;
- current source catalog;
- package/read-model contract;
- economic handoff taxonomy.

Outputs:

- `corpus_taxonomy_v1.json`;
- `known_policy_reference_list.json`;
- `source_licensing_tos_register.json`;
- `package_schema_version_contract.json`;
- `data_product_surface_contract.json`;
- export/read-model schema notes for normalized corpus fields.

Acceptance:

- taxonomy includes jurisdiction, policy-family, source-family, handoff-class,
  failure-class, unit, geography, and mechanism-family values;
- known-policy reference list includes blind held-out rows;
- licensing/ToS register covers every material source family in the seed corpus;
- package/schema/gate/taxonomy versions are explicit in scorecard rows;
- consumer-facing query/export/read-model contract is documented;
- C8-C12 and C9a cannot pass without these artifacts.

### WP5: Non-San-Jose Structured Runtime And Non-Fee Extraction Depth

Owner: structured-source/extraction agent.

Inputs:

- current `StructuredSourceEnricher` and source catalog;
- corpus matrix non-primary jurisdictions;
- source taxonomy;
- non-fee policy-family list.

Outputs:

- at least one non-San-Jose structured source wired into runtime enrichment;
- `non_fee_extraction_templates.json`;
- tests or fixture validations for at least 3 non-fee policy-family templates;
- live or dev-real package proof for at least 2 non-fee policy families when
  possible.

Acceptance:

- structured enrichment is no longer San-Jose-only;
- at least one non-Legistar true structured source is live-proven or the corpus
  state is `corpus_ready_with_gaps` with exact blocker evidence;
- extraction depth is not only CLF/fee/rate-shaped;
- `stored_not_economic` packages can preserve structured facts useful as a data
  product even when economic handoff is not ready.

### WP6: First Small Corpus Pass And Manual Audit

Owner: orchestrator plus implementation agents.

Prerequisites:

- WP1 complete;
- WP2 complete enough to score official-source dominance;
- WP3 complete enough to score freshness/drift.
- WP4 complete enough to score taxonomy, licensing, schema, and known-policy
  coverage.
- WP5 complete enough to prove non-San-Jose structured runtime and non-fee
  extraction depth, or to report exact blockers.

Outputs:

- first real corpus pass over a seed subset;
- `manual_audit_local_government_corpus.md`;
- `golden_policy_regression_set.md`;
- updated source catalog;
- Beads comment with package ids, run ids, corpus status, and next blockers.

Acceptance:

- manual audit samples multiple jurisdictions, policy families, and source
  families;
- manual audit is stratified by jurisdiction, policy family, source family, and
  tuning vs blind-evaluation split;
- every sampled package has source officialness, structured contribution,
  package identity, storage/readback, data-moat value classification, economic
  handoff classification, and dominant failure class;
- terminal state is one of `decision_grade_corpus`,
  `corpus_ready_with_gaps`, `package_mechanics_only`, `fail`, or
  `blocked_hitl`;
- if the result is not at least `corpus_ready_with_gaps`, the next blockers are
  implementation-specific, not narrative.
