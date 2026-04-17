# 2026-04-16 Data Moat Quality Gates

Feature-Key: bd-3wefe.20

## Objective

Harden the Affordabot data-moat iteration gates before any new POC is launched. This contract ensures that the epic/spec gates are precise enough that autonomous agents cannot stop at "architecture mechanics worked" or "economic analysis failed closed" without proving the real product goal.

The Affordabot product goal is to produce a **real data moat**: durable, auditable, source-grounded local-policy evidence packages from scraped and true structured sources. That package is useful input to downstream economic cost-of-living analysis.

The data moat is not "we found a document." The data moat is a policy-specific, source-grounded, lineage-aware, structured-plus-scraped evidence package with enough accuracy, completeness, and provenance that an economic analysis engine can safely decide whether to quantify, request secondary research, produce qualitative analysis, or fail closed.

Economic analysis is allowed to fail closed, but only after the upstream data package has been honestly classified as `analysis_ready`, `analysis_ready_with_gaps`, or `not_analysis_ready`.

## Standalone Data-Moat Metadata Contract

Each package and evidence card should carry explicit moat metadata, even when
economic handoff is not ready:

- `policy_family` / `policy_families`:
  `commercial_linkage_fee`, `parking_policy`, `housing_permits`,
  `business_compliance`, `meeting_action`, `zoning_land_use`,
  `procurement_contract`, `public_safety`, `general_governance`.
- `evidence_use`:
  `economic_parameter_source`, `policy_lineage_source`, `meeting_record`,
  `compliance_rule_source`, `permit_or_project_signal`, `background_context`.
- `economic_relevance`:
  `direct`, `indirect`, `contextual`, `none`, `unknown`.
- `moat_value_reason`: short structured reason describing why the evidence is
  durable and useful independently of immediate economic quantification.

This metadata is part of the product moat itself: it preserves policy lineage,
regulatory context, and reusable source grounding so future extraction and
analysis can improve without re-running discovery from scratch.

## Important Product Context: Cycle 25 Did Not Pass

**Cycle 25 did not pass the original product gates.** 

Honest verdict: 
`PASS_SCRAPED_ARTIFACT_AND_PACKAGE_MECHANICS_ONLY__STRUCTURED_MOAT_NOT_PROVEN__ECONOMIC_DECISION_GRADE_NOT_PROVEN`

Reasons:
- SearXNG/scraped path found and read a useful official artifact.
- Legistar Web API was mechanically live but economically shallow.
- CKAN/San Jose Open Data was not live-proven.
- Tavily rescued fee parameters, but Tavily is secondary search-derived evidence, not a true structured-source proof.
- The package mechanics/persistence/read model were useful, but the structured data moat was not proven.
- Economic analysis correctly failed closed in some places, but that does not prove the upstream data moat is real.

Future agents start here:
- **Data moat is the product objective; architecture is the means.**
- Cycle 25 was a mechanics/narrow scraped pass, not a full data-moat pass.
- The next POC must prove `decision_grade_data_moat`, or honestly classify the result as `evidence_ready_with_gaps`, `package_mechanics_only`, `fail`, or `blocked_hitl`.

## Corpus-Level Data Moat Gates

The package gates below are necessary but not sufficient for the next
super-reach goal. The next implementation pass targets
`local_government_data_moat_benchmark_v0`, defined in
[2026-04-17-local-government-data-moat-benchmark-v0.md](2026-04-17-local-government-data-moat-benchmark-v0.md).

San Jose remains a calibrated fixture, not the product boundary. Before any
architecture-lock claim, the corpus must be scored across multiple
jurisdictions, policy families, and source families.

Corpus result states:
- `decision_grade_corpus`: corpus gates pass and selected packages satisfy
  package/economic deep-dive gates.
- `corpus_ready_with_gaps`: corpus is official-source-grounded and valuable,
  but exact structured/economic/readiness gaps remain.
- `package_mechanics_only`: storage/read-model mechanics work, but corpus data
  substance is not proven.
- `fail`: corpus evidence contradicts the data-moat standard.
- `blocked_hitl`: only for real external or strategic blockers.

### C0 Corpus Scope Gate

Pass requires the corpus to cover at least 3 jurisdictions, 5 policy families,
3 source families, and 30 to 50 evidence packages, or to document an exact
evidence-backed shortfall.

Fail if the proof remains San Jose-only, Legistar-only, CLF/fee-only, or
single-source-family.

### C1 Official-Source Dominance Gate

Pass requires at least 80 percent of manually audited packages to select an
official primary source: city, county, state, regulator, clerk, agenda system,
official open data portal, or official attachment.

Fail if external advocacy, news, vendor, nonprofit, or campaign sources win
primary selection without an explicit fail verdict or a narrow documented
source-of-truth promotion rule.

Pass also requires one backend-owned source/identity classification surface used
by ranking, package building, read models, corpus scorecards, and manual audit.
Every candidate must expose `source_officialness`, `source_of_truth_role`,
`jurisdiction_match`, `policy_family_match`, `external_context_allowed`, and
`primary_evidence_allowed`.

### C2 Source-Family Diversity Gate

Pass requires at least three source families in the corpus, including at least
one true structured API/raw source where available.

Fail if the corpus is effectively private SearXNG plus PDFs only, unless the
source catalog proves structured-source absence for the selected jurisdictions
and policy families.

### C3 Package Reusability Gate

Pass requires every package to carry standalone data-value classification:
`economic_analysis_ready`, `economic_handoff_candidate`,
`secondary_research_needed`, `qualitative_only`, `stored_not_economic`,
`not_policy_evidence`, or `fail`.

Packages can be data-moat assets even when not economic-ready if they are
official, source-grounded, deduped, stored, auditable, and correctly classified.

### C4 Economic Handoff Distribution Gate

Pass requires at least 5 packages to be plausible economic-handoff candidates
and at least 2 packages to reach deeper economic analysis or governed secondary
research proof.

Fail if the corpus has data value but the economic engine receives no clear
handoff packets, missing-parameter inventory, or recommended next action.

### C5 Manual Audit Sampling Gate

Pass requires orchestrator manual audit across jurisdictions, policy families,
and source families. The audit must inspect selected primary source,
officialness, source family, structured contribution, package identity,
storage/readback, data-moat classification, economic handoff classification,
and dominant failure class.

Fail if manual audit inspects only the best San Jose package.

### C6 Golden Regression Gate

Pass requires a reusable golden policy regression set with stable query inputs,
expected jurisdiction, expected policy family, selected source URL, package id,
verdict, and failure class.

Fail if future agents cannot rerun the scorecard and compare search, ranking,
reader, structured enrichment, or package quality.

### C7 Freshness And Drift Durability Gate

Pass requires corpus/package durability metrics:
- source cadence or expected update interval when known;
- retrieval timestamp;
- source publication, meeting, adoption, effective, or explicit unknown date;
- last successful refresh for the canonical source identity;
- schema or source-shape fingerprint where available;
- source-shape drift status;
- update-cadence drift status;
- stale-for-policy-use status;
- next refresh recommendation.

Fail if stale, drifted, source-shape-changed, or cadence-missing data can still
produce `decision_grade_corpus`, `corpus_ready_with_gaps`, or package-level pass
without visible caveats in the scorecard and read model.

## Package-Level Data Moat Gates

These are hard gates before architecture lock. Do not allow `pass` from narrative claims alone. Every pass must cite artifact path, package id/run id where applicable, and the concrete evidence.

Result states:
- `pass`: concrete evidence satisfies the gate.
- `fail`: evidence contradicts the gate or quality is insufficient.
- `not_proven`: gate was not directly exercised or proof is indirect/unavailable.
- `blocked_hitl`: only for strategic decisions or missing external access that cannot be resolved non-destructively.

Top-level data moat verdict:
- `fail`: source evidence is wrong, misleading, ungrounded, or unusable.
- `package_mechanics_only`: transport, storage, or admin visibility works, but evidence substance is not proved.
- `evidence_ready_with_gaps`: credible source-grounded package exists, but one or more lineage/source-family/economic-handoff gaps remain named.
- `economic_handoff_ready`: package is source-grounded and detailed enough for the economic engine to run or fail closed with machine-actionable reasons.
- `decision_grade_data_moat`: package is comprehensive, accurate, robust, and fit for direct or indirect economic analysis without hidden assumptions.

Required data-moat dimensions:
- comprehensive: policy lineage and expected source families are searched, linked, or explicitly marked missing.
- accurate: every extracted fact/parameter is quote-, page-, field-, or row-grounded with units and applicability context.
- robust: reruns, source drift, fallbacks, provider failures, and duplicated evidence cannot silently produce a false pass.
- fit for purpose: the package tells the economic engine what can be quantified, what needs secondary research, what is qualitative only, and what must be rejected.

Cycle 25 classification under this contract: `package_mechanics_only`.

### D0 Source Universe And Catalog Gate

Pass requires a canonical source catalog artifact with:
- source family;
- free/key/signup status;
- signup URL if key is needed;
- API/raw/scrape access method;
- jurisdiction coverage;
- policy-domain relevance;
- cadence/freshness;
- storage target;
- curation status;
- live_proven boolean;
- economic usefulness score;
- whether source is `true_structured`, `scraped_artifact`, `secondary_search_derived`, or `cataloged_unavailable`.

Fail if:
- unavailable CKAN/OpenData-style sources are marked integrated;
- search snippets are counted as true structured sources;
- source family breadth is claimed without live proof or explicit `cataloged-unavailable` evidence.

`not_proven` is the required state when a source family is cataloged but not exercised in the current package.

### D1 Policy Lineage Completeness Gate

Pass requires a package-level policy lineage graph, not a single artifact. For a local policy, the package must attempt and record:
- authoritative policy text: ordinance, resolution, bill, amendment, adopted text, staff draft, or fee schedule;
- meeting context: agenda item, minutes, vote/action record, event/body/item metadata;
- staff/economic context: staff report, fiscal impact memo, fee study, cost analysis, budget attachment, department memo, or impact statement;
- structured metadata: API/raw row tying event/body/item/date/jurisdiction/source identity;
- related artifacts: attachments, revisions, linked files, exhibits, implementation dates, and effective dates where available;
- negative evidence: searched source families that were not found or unavailable.

Pass does not require every possible document, but it requires the expected source families to be enumerated and either linked or explicitly marked missing with evidence.

Fail if:
- one artifact is treated as comprehensive without lineage search;
- staff/fiscal/economic context is absent and not marked as a named gap;
- the package cannot explain which source families were expected for the policy family;
- lineage claims are only LLM narrative without source records.

### D2 Scraped Primary Artifact Substance Gate

Pass requires:
- provider runtime provenance, not hardcoded provider labels;
- query family and provider used;
- top-N official artifact recall;
- first artifact rank;
- backend selected URL;
- portal-skip/ranker decisions;
- reader-substance result;
- real excerpt from read artifact;
- source URL and retrieval timestamp;
- extracted evidence cards;
- parameter cards when the primary artifact contains economic parameters;
- explicit fail-closed reason if no parameters are present.

Fail if:
- selected artifact is portal/menu/navigation content;
- reader-substance fails and the audit hides it behind aggregate pass;
- provider label is not runtime-derived;
- primary artifact contains fee/cost schedule but no structured cards are emitted.

### D3 True Structured Source Economic Depth Gate

Pass requires at least one true structured API/raw source linked to the same policy identity, jurisdiction, and time window that contributes one of:
- economically relevant facts/parameters; or
- policy identity/provenance/freshness/dedupe metadata that materially improves package quality.

True structured sources include API/raw/CSV/JSON-style sources such as Legistar API, OpenStates API, CKAN/Socrata/ArcGIS/OpenDataSoft/static CSV/raw files when live-proven. They do not include Tavily/Exa/SearXNG snippets.

Fail if:
- structured source is only diagnostic metadata and does not improve the package;
- structured source is unrelated/latest-event fallback rather than linked to the selected policy artifact;
- structured lane is passed because Tavily/Exa rescued parameters;
- source is cataloged but unavailable and still treated as integrated.

`not_proven` is acceptable only when the source catalog explicitly shows no free/easily ingestible structured source exists for that specific policy family/jurisdiction/time window.

### D4 Extraction Accuracy And Citation Gate

Pass requires every economic evidence card and parameter card to be human-auditable. Each parameter card must include:
- source URL or structured row id;
- quote/excerpt, cell/field path, or attachment reference that contains the claimed value;
- page number, attachment id, row id, chunk id, or stable locator when available;
- raw value and normalized value;
- unit;
- denominator such as per square foot, per unit, per parcel, annual, one-time, percent, or household;
- category/applicability such as residential, commercial, citywide, district, project type, or exempt/non-exempt class;
- effective date, adoption date, or applicability date when present;
- parser/extractor confidence;
- ambiguity flag;
- unit sanity check;
- currency/number format sanity check.

Fail if:
- a parameter has no human-auditable citation;
- the source excerpt or row does not contain the claimed value;
- unit, denominator, category, geography, or applicability is missing when needed for analysis;
- malformed monetary values, such as `$18.706.00`, are not flagged;
- arithmetic uses an unresolved ambiguous parameter;
- an LLM summary is treated as source truth instead of source-grounded extraction.

Dual-reader extraction is not required for every value. It is required or must be escalated to manual audit when a value is high-impact, ambiguous, malformed, internally inconsistent, or used as a key economic-analysis driver.

### D5 Cross-Source Reconciliation Gate

Pass requires the package to reconcile overlapping facts across source families:
- primary artifact vs structured metadata;
- meeting/action record vs policy text;
- staff/fiscal/economic memo vs extracted fee/cost parameters;
- secondary-search-derived evidence vs authoritative sources.

For each overlapping fact, the package must record one of:
- `confirmed`: sources agree;
- `source_of_truth_selected`: sources differ but the authoritative source is named;
- `conflict_unresolved`: conflict blocks quantification or requires manual review;
- `not_applicable`: no overlapping source exists.

Fail if:
- secondary search overrides authoritative policy text without an explicit source-of-truth decision;
- a structured API "latest event" row is linked to the wrong policy artifact;
- conflicting values are averaged, merged, or silently overwritten;
- the economic engine receives reconciled-looking parameters that still have unresolved source conflict.

### D6 Unified Package Identity And Provenance Gate

Pass requires:
- scraped and structured inputs unify under one canonical package identity;
- canonical document/source keys are stable and jurisdiction-aware;
- evidence cards, parameter cards, assumption/model cards, and gate reports cite source artifacts or structured rows;
- duplicate lanes are deduped instead of double-counted;
- secondary-search-derived evidence is labeled as such and weighted separately;
- package has source hashes or stable storage refs where possible.

Fail if:
- scraped and structured evidence are parallel demo artifacts;
- Tavily secondary evidence is double-registered as scraped and structured;
- provenance stubs replace real excerpts/rows;
- epoch timestamps or degraded source tiers obscure authoritative sources.

### D7 Storage, Readback, And Replay Gate

Pass requires current-package proof for:
- Postgres package/read-model row;
- MinIO raw/intermediate/final artifact object refs and readback;
- pgvector derived chunk/index refs;
- idempotent replay or duplicate package handling;
- admin/read API visibility over the current package;
- direct vs indirect proof mode explicitly marked.

Fail if:
- direct probes fail but the docs claim direct storage pass;
- storage refs exist but readback was not exercised and proof mode is not marked indirect;
- MinIO/pgvector/Postgres are treated as proven from local fixture-only evidence.

### D8 Robustness, Fallback, And Regression Gate

Pass requires proof that the package is resilient to common failure modes:
- same policy rerun produces the same canonical package identity, or a documented version transition;
- source failure or provider fallback is exercised and correctly labeled;
- fallback evidence never becomes primary source proof unless promoted by a documented source-of-truth rule;
- unavailable sources cannot appear as `live_proven=true`;
- duplicated evidence does not produce duplicate parameter cards;
- source shape drift creates `source_shape_changed`, `not_proven`, or `fail`, not pass;
- at least one golden policy regression fixture validates search/ranking, reading, extraction, package build, gate verdict, and economic handoff classification.

Fail if:
- rerun identity changes without explanation;
- provider fallback hides primary-source failure;
- source drift or API-shape change silently drops attachments/fields while the gate still passes;
- there is no regression fixture covering a known hard policy case before claiming robustness.

### D9 Windmill Linkage Gate

Pass requires:
- current Windmill flow/run/job ids linked to package/run state;
- step sequence proves scraped and structured paths were orchestrated;
- retries/branching/failure states visible;
- Windmill owns orchestration only, not source semantics, ranking, assumptions, or economic conclusions.

Fail if:
- Windmill artifact is stale/stub-only while docs claim live proof;
- run ids are not bound to the current package;
- business logic lives in Windmill scripts.

### D10 Manual Data Audit Gate

Pass requires a human/orchestrator-readable audit artifact that manually inspects:
- raw scraped candidates;
- selected/read artifacts;
- structured rows;
- normalized evidence cards;
- parameter cards;
- provenance links;
- storage refs;
- package identity;
- whether data is credible, relevant, deduplicated, source-grounded, and useful for downstream economic analysis.

Fail if:
- audit only summarizes automated score JSON;
- audit does not inspect the actual package;
- audit omits why the package is or is not useful for economic analysis.

### D11 Economic Handoff Fitness Gate

Pass requires the package to emit:
- `economic_handoff_quality`: `analysis_ready`, `analysis_ready_with_gaps`, or `not_analysis_ready`;
- named missing fields;
- parameter readiness;
- source support summary;
- assumption/model needs;
- unsupported-claim risk;
- whether direct and/or indirect analysis is plausible.

The package must also emit:
- `mechanism_candidates`;
- `parameter_inventory`;
- `missing_parameters`;
- `assumption_needs`;
- `secondary_research_needs`;
- `unsupported_claim_risks`;
- `recommended_next_action`: `run_direct_analysis`, `run_secondary_research`, `qualitative_summary_only`, or `reject`.

**Important:** This gate can pass with `analysis_ready_with_gaps`, `qualitative_only`, or `not_analysis_ready` if the classification is honest and source-grounded. Economic-analysis failure does not automatically fail the data-moat gate.

Fail if:
- a qualitative-only policy is forced into fake quantification;
- missing indirect-cost parameters are not named;
- secondary research needs are hidden inside LLM context;
- the economic engine receives a package without explicit handoff quality.

## Decision-Grade Threshold

`decision_grade_data_moat` requires:
- D0 `pass`;
- D1 `pass` or `evidence_ready_with_gaps` with named missing lineage pieces;
- D2 `pass`;
- D3 `pass` or source-catalog-proven structured absence for the specific policy family;
- D4 `pass`;
- D5 `pass` or `not_applicable`;
- D6 `pass`;
- D7 `pass`;
- D8 `pass`;
- D9 `pass`;
- D10 `pass`;
- D11 `pass`.

The next 30-cycle run must end in one of these states:
- `decision_grade_corpus`: corpus gates C0-C7 pass and selected package-level
  deep dives satisfy the full D0-D11 and applicable E1-E5 standard.
- `corpus_ready_with_gaps`: credible corpus exists, but exact missing
  jurisdiction, policy-family, source-family, freshness/drift, or economic
  handoff gaps are documented.
- `decision_grade_data_moat`: an individual package satisfies the full
  package-level standard.
- `evidence_ready_with_gaps`: credible package exists, but exact missing lineage, structured-source, or economic-handoff gaps are documented.
- `fail`: current architecture cannot produce the required data moat without a strategic change, with evidence.
- `blocked_hitl`: only for real infra/API/key/vendor or architecture decisions that cannot be resolved non-destructively.

It must not end at `package_mechanics_only` unless all remaining cycles were exhausted with direct evidence that no non-destructive improvement path remains.

## Economic Analysis Gates

Downstream gates separate from the data moat gates.

### E1 Direct Mechanism Gate

Requires:
- direct fiscal/fee/cost-change mechanism;
- parameter table with units;
- source-bound evidence;
- arithmetic trace;
- uncertainty/sensitivity;
- final user-facing conclusion or explicit fail-closed reason.

### E2 Indirect Mechanism Gate

Requires:
- mechanism graph (e.g., regulation -> cost/supply/channel -> price/incidence -> household effect);
- parameter needs;
- assumption/model cards;
- evidence support;
- sensitivity range;
- unsupported-claim rejection.

### E3 Secondary Research Loop Gate

Requires:
- economic analyzer identifies missing parameter;
- governed secondary search/read package is created;
- provider/query provenance is stored;
- reader output is stored;
- assumptions cite secondary artifacts;
- rerun binds secondary package to original package.

Fail if:
- secondary research exists only as hidden LLM context;
- Tavily snippets are treated as structured-source proof rather than secondary evidence.

### E4 Canonical Analysis Binding Gate

Requires:
- analysis run id;
- package id;
- source artifacts;
- assumption/model cards;
- secondary package refs;
- final conclusion;
- rejected unsupported claims.

### E5 Decision-Grade Output Gate

Decision-grade requires:
- source-bound parameters;
- model/assumption provenance;
- uncertainty/sensitivity;
- arithmetic trace;
- no hidden assumptions;
- clear household/cost-of-living conclusion.

If missing, the result must be `qualitative_only`, `secondary_research_needed`, or `fail_closed`, not overclaimed.

## Adaptive 30-Cycle Loop Contract

The next autonomous run has this contract:
- Up to 30 cycles are allowed.
- Cycles are adaptive, not preallocated.
- Every cycle must do at least one of:
  - improve a measured data-moat gate;
  - improve economic-handoff quality;
  - prove a blocker with direct evidence;
  - broaden source/jurisdiction coverage after narrow gates pass.
- Cycles 8+ must not be diagnosis-only unless they prove a blocker that changes the next implementation move.
- Every cycle artifact must include:
  - cycle number;
  - hypothesis;
  - gate targeted;
  - commands/run ids;
  - code/config/data tweaks;
  - package id/run id;
  - before/after scorecard;
  - manual audit status if applicable;
  - stop/continue decision;
  - next targeted tweak.

### Early Stop Conditions
Stop early only if:
- all required data-moat gates pass;
- remaining failures are explicit strategic HITL decisions;
- repeated cycles prove a blocker with high-quality evidence and no non-destructive improvement path remains.

### Forbidden Stop Conditions
- "architecture mechanics worked";
- "we identified the blockers";
- "economic analysis failed closed";
- "storage/read model visible" without data substance.

## Review Issue Coverage

This v3 gate contract explicitly addresses the latest GLM-5.1 and Gemini review concerns.

### GLM-5.1 Coverage

- PR #438 routing/findability is preserved through architecture README, POC README, dependency lockdown spec, and this gate contract.
- Cycle 25 remains explicitly classified as `package_mechanics_only`, not a data-moat pass.
- True structured-source proof is separated from Tavily/Exa/SearXNG secondary or scraped evidence.
- Future cycles must cite artifact paths, package ids/run ids, and concrete evidence for each `pass`.
- Economic-analysis failure is allowed only after the package emits an honest economic handoff classification.

### Gemini Coverage

- Comprehensive: D1 requires a policy lineage graph covering authoritative text, meeting context, staff/fiscal/economic context, structured metadata, related artifacts, and negative evidence.
- Accurate: D4 requires quote/page/row grounding, raw and normalized value, units, denominator, applicability, dates, ambiguity flags, confidence, and unit/currency sanity checks.
- Robust: D8 requires rerun identity stability, fallback labeling, unavailable-source handling, source-shape drift classification, duplicate control, and a golden policy regression fixture.
- Fit for purpose: D11 requires economic handoff quality, mechanism candidates, parameter inventory, missing parameters, assumption needs, secondary-research needs, unsupported-claim risks, and recommended next action.
- Qualitative policies: D11 allows `qualitative_only` as an honest handoff outcome when the package is source-rich but cannot support quantification.
