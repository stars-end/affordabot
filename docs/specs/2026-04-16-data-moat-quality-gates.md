# 2026-04-16 Data Moat Quality Gates

Feature-Key: bd-3wefe.20

## Objective

Harden the Affordabot data-moat iteration gates before any new POC is launched. This contract ensures that the epic/spec gates are precise enough that autonomous agents cannot stop at "architecture mechanics worked" or "economic analysis failed closed" without proving the real product goal.

The Affordabot product goal is to produce a **real data moat**: durable, auditable, source-grounded local-policy evidence packages from scraped and true structured sources. That package is useful input to downstream economic cost-of-living analysis.

Economic analysis is allowed to fail closed, but only after the upstream data package has been honestly classified as `analysis_ready`, `analysis_ready_with_gaps`, or `not_analysis_ready`.

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
- The next POC must prove structured-source economic depth or honestly classify it as `not_proven`.

## Data Moat Gates

These are hard gates before architecture lock. Do not allow `pass` from narrative claims alone. Every pass must cite artifact path, package id/run id where applicable, and the concrete evidence.

Result states:
- `pass`: concrete evidence satisfies the gate.
- `fail`: evidence contradicts the gate or quality is insufficient.
- `not_proven`: gate was not directly exercised or proof is indirect/unavailable.
- `blocked_hitl`: only for strategic decisions or missing external access that cannot be resolved non-destructively.

### D0 Source Catalog Gate

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

### D1 Scraped Primary Artifact Gate

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

### D2 True Structured Source Economic Depth Gate

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

### D3 Unified Package Identity And Provenance Gate

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

### D4 Storage And Readback Gate

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

### D5 Windmill Linkage Gate

Pass requires:
- current Windmill flow/run/job ids linked to package/run state;
- step sequence proves scraped and structured paths were orchestrated;
- retries/branching/failure states visible;
- Windmill owns orchestration only, not source semantics, ranking, assumptions, or economic conclusions.

Fail if:
- Windmill artifact is stale/stub-only while docs claim live proof;
- run ids are not bound to the current package;
- business logic lives in Windmill scripts.

### D6 Manual Data Audit Gate

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

### D7 Economic Handoff Gate

Pass requires the package to emit:
- `economic_handoff_quality`: `analysis_ready`, `analysis_ready_with_gaps`, or `not_analysis_ready`;
- named missing fields;
- parameter readiness;
- source support summary;
- assumption/model needs;
- unsupported-claim risk;
- whether direct and/or indirect analysis is plausible.

**Important:** This gate can pass with `analysis_ready_with_gaps` or `not_analysis_ready` if the classification is honest and source-grounded. Economic-analysis failure does not automatically fail the data-moat gate.

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

## Adaptive 25-Cycle Loop Contract

The next autonomous run has this contract:
- Up to 25 cycles are allowed.
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
