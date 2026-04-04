# Fail-Fast New-Family Wave With Parallel UX QA

Date: 2026-04-04

## Summary

This spec defines the next affordabot execution wave after the completion of the existing-family deepening, revision-first hardening, viewer MVP, and Bucket cleanup outcomes.

The wave runs two lanes in parallel:

1. option 1: new reusable provider-family unlocks for deeper truthful local-government coverage
2. option 2: founder UX QA and bounded usability hardening for the admin/substrate viewer

Option 1 is attempted through `dx-loop` first under a hard fail-fast contract. If the loop misses early health signals, the same spec is handed immediately to a `gpt-5.3-codex` implementation lane.

Option 2 runs in parallel as a bounded `gpt-5.3-codex` QA lane using `agent-browser` first and Playwright only if a deterministic regression is worth encoding after the UX issues are known.

## Problem

The current moat wave is complete, but the next growth step is not “more of the same.”

The remaining high-value jurisdictions most likely require a new reusable provider-family pattern rather than more defaults under the existing families. At the same time, the founder-facing inspection surface is now good enough to dogfood seriously, and that dogfood can reduce cognitive load before the next larger expansion.

`dx-loop` also still has product trust debt. The next wave should improve the product moat while turning `dx-loop` failures into bounded QA evidence rather than letting them silently consume schedule.

## Goals

- unlock one clearly reusable new provider family
- bias toward truthful `agendas + minutes` coverage, not shallow breadth
- keep `dx-loop` off the irreversible critical path by using a hard fail-fast wrapper
- run a real founder UX QA lane in parallel against the current admin/substrate surface
- convert any `dx-loop` failure into a detailed dogfood log and explicit next verdict

## Non-Goals

- broad admin-platform redesign
- generic observability work
- broad Playwright coverage before the UX flow is stable
- municipal code as the primary success condition
- more existing-family deepening as the primary objective

## Active Contract

This wave succeeds only if all of the following are true:

1. one new provider family is proven on at least one jurisdiction and is clearly reusable
2. the implementation path does not stall product progress if `dx-loop` fails
3. the founder UX QA lane produces concrete usability findings or a clear “no critical UX blockers” verdict
4. a dx-loop dogfood artifact is published regardless of whether the loop succeeds or fails

## Recommended Defaults To Lock

These are the recommended defaults for the next dispatch:

- primary new family target:
  - custom archive / document-center family
- first target jurisdictions:
  - `Palo Alto`
  - `Milpitas`
  - `Alameda County`
- success bar for the family:
  - truthful `agendas + minutes`
  - not a one-off scraper
  - implementation shape is clearly reusable
- UX QA scope:
  - run list
  - failure buckets
  - raw row detail
  - artifact preview discovery only if it is already reachable without broadening scope
- browser tool:
  - `agent-browser` first
  - Playwright only after the flow is stable enough for deterministic coverage

## Architecture / Design

### Lane A: Option 1

Option 1 is the moat-critical lane. It follows this contract:

1. write or refine the implementation spec for the chosen new family
2. dispatch `dx-loop` once against that exact spec
3. fail fast if any early-health contract is violated
4. on failure, dispatch the same scope to `gpt-5.3-codex`
5. keep the same acceptance criteria regardless of execution surface

### Lane B: Option 2

Option 2 is a bounded QA lane, not a broad feature wave.

The QA worker should:

- verify founder-critical tasks using the current `/admin` substrate viewer
- focus on:
  - “what worked or failed in this run?”
  - “can I inspect the raw row without SQL?”
  - “is the failure reasoning easy to follow?”
- use `agent-browser` for exploratory/manual verification
- propose only bounded product fixes, not generic admin rework

## dx-loop Fail-Fast Contract

Terminate `dx-loop` and fall back to `gpt-5.3-codex` if any of the following occur:

- missing wave state
- no first real task materialization
- status/explain disagreement
- no code artifact, PR artifact, or execution artifact by the first checkpoint
- wave stall without progress evidence
- false-success symptom:
  - success claim without meaningful implementation or review artifact

Operational rule:

- the fallback worker replaces `dx-loop`
- the fallback does not run concurrently on the same implementation slice

## Execution Phases

### Phase 1: Lock Contract

- choose the first new family target
- define the strict dx-loop fail-fast contract
- define the exact scope of the UX QA lane

### Phase 2: Parallel Start

- Lane A: option 1 through `dx-loop`
- Lane B: option 2 through `gpt-5.3-codex` + `agent-browser`

### Phase 3: Fail-Fast Branch

- if Lane A loop is healthy, keep it running
- if Lane A fails the contract, stop it and hand the same scope to `gpt-5.3-codex`

### Phase 4: Closeout

- publish implementation verdict for the new family
- publish UX QA findings
- publish detailed dx-loop dogfood log
- recommend whether `dx-loop` gained any requalification signal

## Beads Structure

- `BEADS_EPIC`: `bd-ft8ng`
- `bd-ggreu`: lock new-family target and dx-loop fail-fast contract
- `bd-zuy8x`: execute option 1 via dx-loop first with gpt-5.3-codex fallback
- `bd-0xo86`: run parallel founder UX QA lane for option 2
- `bd-mf1fw`: publish dx-loop dogfood log and next-wave verdict

## Blocking Edges

- `bd-zuy8x` blocks on `bd-ggreu`
- `bd-0xo86` blocks on `bd-ggreu`
- `bd-mf1fw` blocks on `bd-zuy8x`
- `bd-mf1fw` blocks on `bd-0xo86`

## Validation Gates

- new family gate:
  - at least one jurisdiction reaches truthful `agendas + minutes`
  - source path is auditable
  - adapter shape is reusable
- dx-loop gate:
  - loop either produces real progress artifacts or fails fast with a QA log
- founder QA gate:
  - run list, failure buckets, and raw row detail can be navigated without SQL
  - major usability blockers are explicitly documented
- closeout gate:
  - one next-wave verdict memo exists with product and DX conclusions

## Risks / Rollback

### Risk: dx-loop wastes schedule

Mitigation:

- hard fail-fast contract
- immediate handoff to `gpt-5.3-codex`

### Risk: new family degenerates into a one-off scraper

Mitigation:

- do not call the wave a success unless the family shape is clearly reusable

### Risk: UX QA expands into broad internal-tool work

Mitigation:

- limit QA to founder-critical workflows already agreed in the current admin surface

## Strategic HITL Surface

The minimum med-high risk decisions that still need explicit founder lock are:

1. confirm the first new-family target family:
   - recommendation: custom archive / document-center family
2. confirm the first target jurisdiction set:
   - recommendation: `Palo Alto`, `Milpitas`, `Alameda County`
3. confirm whether artifact preview remains out of scope for the option 2 lane unless surfaced as a severe usability blocker:
   - recommendation: yes

## Recommended First Task

- `FIRST_TASK`: `bd-ggreu`

Why:

- both parallel lanes depend on a single clear target family and a locked fail-fast contract
- if those are vague, both the loop lane and the QA lane can drift
