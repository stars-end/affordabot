# Data-Moat Workflow Pain-Point Review

Date: 2026-04-27
Status: Review package, no implementation dispatched
Related spec: `docs/specs/2026-04-27-data-moat-cycle-review-architecture.md`
Related Beads: `bd-cc6a4`, `bd-0si04`, `bd-dcq8f`, `bd-cwbxf`, `bd-n6h1c`

## Summary

The original two workflows surfaced the right product goal: broad local-government
coverage from both structured and scraped official data, reviewed over repeated
cycles and eventually usable by the economic analysis engine.

The first synthesis was directionally right but missed one major blocker:
Windmill-native runtime transparency was treated as supporting evidence rather
than a hard prerequisite. That is now corrected by `bd-cc6a4.8`.

The remaining risk is that implementation agents may still optimize individual
lanes instead of the repeated jurisdiction-pack loop. The primary loop should be
small-pack iteration: run structured + scraped lanes over a few jurisdictions,
measure quality, revise pipelines/source catalogs, and only then expand breadth.

## Original Workflow Pain Points

### Workflow 1: Structured Data Moat

Source context:

- `data_moat_takeover_handoff_2026-04-22.md`
- `2026-04-17-local-government-data-moat-benchmark-v0.md`
- `2026-04-16-data-moat-quality-gates.md`
- corpus scorecard/report artifacts from `feature-bd-3wefe.20-data-moat-gates`

Key pain points:

- `cataloged_intent` was too easy to mistake for proof.
- `orchestration_intent` was too easy to mistake for live Windmill proof.
- C2, C13, and C14 were explicitly not proven.
- San Jose/Legistar/CLF success risked becoming the implicit product boundary.
- Structured depth needed real public/free official sources, not search snippets
  or generated targets.
- Economic analysis readiness needed to stay visible without erasing standalone
  data-moat value.
- Manual audit passed, but manual audit was not a substitute for runtime proof.

Current coverage:

- `bd-0si04` addresses structured proof breadth/depth.
- `bd-cc6a4` now preserves the structured proof upgrade rule in the cycle report.
- `bd-cc6a4.8` makes Windmill runtime proof a hard prerequisite before report generation.
- The spec keeps economics as a downstream handoff gate, not the only product value.

Still weak or easy to miss:

- Structured source selection needs an explicit small-pack strategy, not only a
  corpus-scale ambition.
- We still need canonical cell identity shared across structured proofs,
  scraped cells, Windmill labels, storage artifacts, and admin review rows.
- We should avoid counting a jurisdiction as improved unless at least one
  source-family cell moves from intent/missing to live-proven or reason-coded blocked.
- C14 non-fee extraction depth remains easy to postpone behind structured API work.

### Workflow 2: Scraped / SearXNG / Unstructured Path

Source context:

- PR #411 research memo on OSS search alternatives.
- Current `AutoDiscoveryService`, `SearchDiscoveryService`, and round-1 benchmark helpers.
- Prior discussion around flaky Z.ai search behavior.

Key pain points:

- Z.ai structured web search returned HTTP 200 with empty results and cannot be
  trusted as the critical jurisdiction-to-keyword path.
- Existing discovery code still contains LLM-generated query paths and Z.ai-first
  search fallback patterns.
- SearXNG was recommended as first benchmark candidate, but SearXNG is still
  discovery only. It does not validate officialness or extraction quality.
- DuckDuckGo/Playwright fallback is useful as a dev escape hatch but not a
  robust production moat dependency.
- Official-source validation, source-family matching, and extractability need to
  be first-class outputs, not implicit search-result heuristics.

Current coverage:

- `bd-dcq8f` replaces Z.ai-dependent onboarding with deterministic profiles,
  source-family query templates, SearXNG retrieval, validators, extractability
  checks, and reason-coded missing cells.
- `bd-cwbxf` keeps OpenRouter/LLM enrichment advisory-only and downstream of a
  deterministic baseline.
- `bd-cc6a4` now requires scraped cells to expose official validation,
  extractability, stored/provenanced status, missing reason codes, and provider failures.

Still weak or easy to miss:

- We need baseline-vs-current query-template comparisons per jurisdiction/source
  family, not only provider-level benchmark metrics.
- The deterministic jurisdiction profile needs an owner and review surface; if
  it is wrong, all downstream search improves the wrong target.
- Provider health must be per cell/query, not only per run.
- Search-result quality and reader substance are separate gates; a good URL can
  still produce low-substance content.
- We need a clear policy for when to introduce official-root crawling
  (Scrapy+Meilisearch/YaCy) if SearXNG misses weak SEO jurisdictions.

## Missed Synthesis Gaps

### 1. Windmill Transparency Was Underweighted

Original synthesis said Windmill is evidence and admin is product truth. Correct,
but incomplete.

For the current blocker, Windmill-native transparency is not optional. Runs,
labels, dynamic `wm_labels`, job result envelopes, asset refs, resource refs,
logs, and run URLs are the cheapest way to see what changed while pipelines are
still moving.

Correction:

- `bd-cc6a4.2` now defines the Windmill-native transparency contract.
- `bd-cc6a4.8` now implements that instrumentation before cycle report generation.

### 2. The Unit Of Iteration Was Too Broad

The corpus target is broad, but the build loop should be small.

The right loop is:

- choose 3-6 jurisdictions;
- choose source families;
- run structured + scraped lanes;
- evaluate cells;
- revise source catalog/query templates/probes;
- repeat.

Broad corpus claims should follow repeated small-pack passes, not precede them.

### 3. Shared Cell Identity Was Implicit

Structured proof rows, scraped cells, Windmill labels, provider failures, storage
artifacts, and admin review rows all need to join on the same identity.

Recommended identity:

```text
cycle_id + jurisdiction_id + source_family + policy_family + lane + stage
```

Without this, agents will build parallel artifacts that are hard to compare.

### 4. Source Catalog Revision Was Not Prominent Enough

Pipeline iteration is not only code iteration. The official-source catalog,
jurisdiction profile, source-family ontology, and known official roots must be
reviewable and revisable.

If a source family fails for a jurisdiction, the report should distinguish:

- no source known yet;
- source exists but unavailable;
- source exists but schema changed;
- source exists but extractor missing;
- source exists but search did not find it;
- source exists but reader/extractor failed;
- source exists but not economically useful.

### 5. C14 Non-Fee Depth Could Still Be Deferred Forever

The structured path naturally gravitates toward easy APIs and fee-like rows.
The product moat needs non-fee depth too: zoning, permits, inspections,
parking/TDM, meeting-action lineage, business licensing, and housing mandates.

`bd-0si04` covers this partly, but implementation review should explicitly ask
whether each cycle improved non-fee extraction depth or just added more
catalog/provenance metadata.

### 6. LLM Enrichment Needs A Measured Uplift Contract

The current LLM-enrichment epic is correctly non-critical. The missed point is
that enrichment should be evaluated only against weak/missing deterministic
cells.

Do not evaluate enrichment by "did it produce plausible ideas." Evaluate it by:

- official_validated delta;
- extractable delta;
- stored/provenanced delta;
- cost and latency;
- false-positive rate;
- provider failure rate.

### 7. Admin Route Health Is A Real Blocker, Not UI Polish

`bd-n6h1c.7` remains a prerequisite. If existing admin routes/proxies are
mismatched, data-moat UI work will either rely on mocks or invent a second
surface.

This blocks `bd-cc6a4.4` by design.

## Updated Blocker Map

| Blocker | Status | Beads Coverage | Remaining Risk |
| --- | --- | --- | --- |
| Structured intent vs live proof | Covered | `bd-0si04`, `bd-cc6a4.3` | Need multiple real official sources, not one proof row. |
| Windmill intent vs live proof | Strengthened | `bd-cc6a4.2`, `bd-cc6a4.8`, `bd-cc6a4.6` | Need live/recorded labels and run URLs, not just schema. |
| Z.ai flaky search | Covered for critical path | `bd-dcq8f` | Current legacy code still has Z.ai-first paths until implementation lands. |
| Jurisdiction-to-keywords reliability | Covered but fragile | `bd-dcq8f.1` | Jurisdiction profile/source-family ontology needs HITL review. |
| Official-source validation | Covered | `bd-dcq8f.3` | Must be consumed by report/admin, not isolated test helpers. |
| Extractability/storage proof | Partly covered | `bd-dcq8f.4`, `bd-cc6a4.6` | Need per-cell stored/provenanced state. |
| Non-fee extraction depth | Partly covered | `bd-0si04.4`, `bd-cc6a4.6` | Must not be crowded out by easy structured APIs. |
| Economic handoff visibility | Covered | `bd-cc6a4.3`, `bd-cc6a4.5` | Need blockers surfaced without downgrading stored data value. |
| Admin route/proxy mismatch | Covered | `bd-n6h1c.7` -> `bd-cc6a4.4` | Must close before UI implementation. |
| Per-cycle transparency | Strengthened | `bd-cc6a4.8` -> `bd-cc6a4.3` | Need Windmill labels/envelopes before report generator. |
| Source catalog revision loop | Weak | Spec update only | Consider adding a later task if early cycles show catalog churn. |
| Official-root crawler/index lane | Deferred | `bd-dcq8f.5` decision, PR #411 round 2 | Might become P1 if weak-SEO jurisdictions fail SearXNG. |

## Recommended Implementation Priority

1. Complete `bd-cc6a4.1`, `bd-cc6a4.2`, and `bd-cc6a4.8` before any cycle report generator work.
2. Run `bd-dcq8f.1` early so jurisdiction profiles and source-family query templates are visible for review.
3. Run `bd-0si04.1` early in parallel or immediately after so structured target selection is reviewable before coding probes.
4. Do not start `bd-cc6a4.3` until Windmill evidence envelopes exist.
5. Do not start `bd-cc6a4.5` until `bd-n6h1c.7` closes and backend payloads exist.
6. Treat `bd-cwbxf` as P2 until deterministic scraped baseline misses are measured.

## What Would Make Future Cycles Easier

- A single jurisdiction-pack manifest used by structured probes, scraped queries,
  Windmill labels, cycle reports, and admin review.
- A source-catalog diff view: added/removed/changed official roots and structured endpoints.
- Per-cell reason codes with stable enum values.
- A captured `cycle_evidence_envelope` for every Windmill step that can be
  replayed into the report generator in tests.
- A baseline-vs-current quality table for query templates and structured probes.
- A "do not expand breadth" rule when the same blocker repeats for two cycles.

## Bottom Line

The revised architecture now addresses the biggest missed blocker:
Windmill-native transparency must be proven before custom cycle reports and
admin UI.

The next most important guardrail is to keep implementation centered on small
jurisdiction-pack iteration. The goal is not a beautiful dashboard or a giant
generated corpus. The goal is repeated improvement in structured and scraped
official data coverage, with each cycle showing exactly which cells improved,
regressed, remained missing, or need pipeline/source-catalog revision.
