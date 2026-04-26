# Expanded New-Family Wave With Substrate Story Pack And dx-loop QA Evidence

Date: 2026-04-04

## Summary

This spec expands the next affordabot execution wave beyond the earlier fail-fast new-family plan.

The wave now has three explicit outcomes under one contract:

1. unlock one reusable new provider family for truthful local-government coverage
2. establish a canonical affordabot executable story pack for the merged substrate viewer MVP
3. produce a detailed `dx-loop` dogfood artifact as a byproduct of real product work, not a synthetic benchmark

The `uismoke` engine refactor remains out of scope for this epic. That work belongs to a separate `~/llm-common` lane coordinated with this one.

## Problem

The previous wave completed revision-first hardening, viewer MVP, existing-family deepening, and Bucket cleanup. The next moat step is not another Legistar-style depth pass; it is a reusable new family unlock.

But affordabot's current executable story pack still reflects the older admin-console surface in `docs/TESTING/STORIES/README.md` rather than the newly merged founder-critical substrate viewer flows.

If the new-family wave runs without upgrading the executable story pack, affordabot product progress and affordabot testing truth will diverge. If `dx-loop` is exercised without a clear fail-fast contract and an artifact expectation, we also lose the chance to turn real product work into useful DX dogfood.

## Goals

- prove one clearly reusable new provider family on real municipal data
- keep the primary moat target focused on truthful `agendas + minutes`
- promote affordabot substrate viewer flows into the canonical executable repo-local story pack
- preserve Playwright-backed deterministic gating through `uismoke`, not ad hoc one-off scripts
- generate a detailed `dx-loop` QA log for the real product lane

## Non-Goals

- `uismoke` core engine refactor inside `~/llm-common`
- broad admin-console redesign
- artifact preview expansion as a primary product goal
- turning `agent-browser` into the core `uismoke` backend
- municipal code as a primary coverage target

## Active Contract

This wave is complete only if all of the following are true:

1. a custom archive / document-center family is proven on at least one jurisdiction and is clearly reusable
2. the affordabot executable story pack covers:
   - run list
   - failure buckets
   - raw row detail
3. the new story pack is wired into the existing affordabot verification surface rather than living as a sidecar experiment
4. `dx-loop` either produces real progress artifacts or fails fast and hands off cleanly to `gpt-5.3-codex`
5. a detailed `dx-loop` dogfood log is published for the `dx-loop` agent

## Locked Decisions

The following med-high risk decisions are locked for this wave:

- new family target:
  - custom archive / document-center family
- first jurisdiction set:
  - `Palo Alto`
  - `Milpitas`
  - `Alameda County`
- success standard for the family:
  - truthful `agendas + minutes`
  - clearly reusable adapter shape
  - no one-off scraper counted as success
- affordabot executable product-test scope:
  - run list
  - failure buckets
  - raw row detail
- artifact preview policy:
  - out of scope unless it appears as a severe usability blocker during QA
- `dx-loop` role:
  - first attempt only
  - hard fail-fast fallback to `gpt-5.3-codex`
- `dx-loop` dogfood policy:
  - detailed QA log is required regardless of success or failure

## Architecture / Design

### Lane A: Product-Critical New Family Unlock

This lane implements the new family under a fail-fast execution wrapper:

1. attempt the implementation through `dx-loop`
2. terminate on the agreed fail-fast conditions
3. hand the exact same scope to `gpt-5.3-codex` if the loop falters
4. keep acceptance criteria identical regardless of execution surface

### Lane B: Affordabot Story-Pack Promotion

This lane upgrades affordabot's repo-local testing truth so it matches the current product:

- define a canonical substrate viewer story pack under `docs/TESTING/STORIES/`
- keep stories repo-local to affordabot
- wire them into existing affordabot Make targets
- align the executable pack with the merged substrate viewer MVP

### Lane C: Founder UX QA + dx-loop Evidence

This lane uses the upgraded story pack and the current UI surface to produce:

- a founder UX verdict for the substrate viewer MVP
- bounded usability findings
- a detailed `dx-loop` dogfood artifact for the control-plane team

## dx-loop Fail-Fast Contract

Terminate `dx-loop` and switch to `gpt-5.3-codex` if any of the following occur:

- missing wave state
- no first real task materialization
- status/explain disagreement
- no code, PR, or execution artifact by the first checkpoint
- wave stall without progress evidence
- false-success symptom where completion is claimed without meaningful implementation or review artifact

Operational rule:

- the fallback worker replaces `dx-loop`
- the fallback does not run concurrently on the same implementation slice

## Execution Phases

### Phase 1: Lock And Seed

- finalize new family target and jurisdictions
- finalize fail-fast contract and QA artifact expectation
- define affordabot substrate story-pack boundaries

### Phase 2: Parallel Start

- Lane A: new-family implementation through `dx-loop`
- Lane B: affordabot substrate story-pack implementation

### Phase 3: Product QA And Fallback

- if Lane A is healthy, continue it
- if Lane A stalls, dispatch `gpt-5.3-codex` fallback
- run founder UX QA against the updated substrate story pack

### Phase 4: Closeout

- publish new-family verdict
- publish substrate story-pack verification verdict
- publish detailed `dx-loop` dogfood log for control-plane follow-up

## Beads Structure

- epic: expanded new-family wave with substrate story pack and `dx-loop` QA evidence
- feature 1: lock execution contract and story-pack scope
- feature 2: execute new-family unlock via `dx-loop` first with codex fallback
- feature 3: implement affordabot substrate executable story pack and makefile wiring
- feature 4: run founder UX QA and capture `dx-loop` evidence log
- feature 5: publish closeout verdict across product and DX lanes

## Validation

### New Family Gate

- at least one target jurisdiction reaches truthful `agendas + minutes`
- source path is auditable
- adapter shape is clearly reusable

### Story-Pack Gate

- canonical executable affordabot stories cover run list, failure buckets, and raw row detail
- affordabot Make targets invoke the updated story pack
- the story pack is treated as executable product truth, not an abandoned sidecar

### Founder QA Gate

- the founder can inspect run list, failure buckets, and raw row detail without SQL
- critical usability blockers are either fixed or explicitly documented

### dx-loop Gate

- loop either produces real artifacts or fails fast with a detailed QA log
- the detailed QA log is ready to hand to the `dx-loop` agent

## Risks / Rollback

### Risk: new family degrades into bespoke scraping

Mitigation:
- success requires a reusable adapter shape

### Risk: story-pack work becomes generic QA sprawl

Mitigation:
- keep the executable scope limited to the substrate viewer MVP

### Risk: `dx-loop` burns schedule

Mitigation:
- hard fail-fast contract and immediate `gpt-5.3-codex` replacement

## Recommended First Task

Start with the execution-contract task.

Why:
- it locks the precise product target, the precise testing surface, and the fail-fast swap conditions before parallel work starts
- both the new-family lane and the story-pack lane depend on those boundaries being explicit
