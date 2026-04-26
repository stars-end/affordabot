# Expanded New-Family Wave Closeout

Date: 2026-04-04
Epic: `bd-t4pz0`

## Summary

This wave combined three bounded outcomes:

1. prove one reusable new provider family for truthful `agendas + minutes`
2. promote the substrate viewer MVP into affordabot's canonical executable story pack
3. capture real `dx-loop` dogfood evidence from product work instead of a synthetic benchmark

The implementation lanes completed under separate PRs:

- planning + fail-fast contract: `#393`
- affordabot substrate story pack: `#394`
- custom archive / document-center family: `#395`
- founder UX QA memo: `#396`

## Outcome 1: New Family Unlock

`#395` implements a reusable `custom_archive_document_center` family shape.

Grounded result:

- truthful root inventory rows added for:
  - `Milpitas`
  - `Alameda County`
- first-pass `Palo Alto` was deliberately excluded because this wave did not yet establish a stable truthful official root
- bounded manual expansion now supports two reusable extraction modes:
  - generic anchor extraction
  - CivicPlus archive option expansion via `Archive.aspx?AMID=...&ADID=...`

Why this counts:

- it is not a one-off scraper
- it preserves the truthful `agendas + minutes` standard
- it creates a clearly reusable family shape for other archive / document-center jurisdictions

## Outcome 2: Affordabot Story-Pack Promotion

`#394` promotes the merged substrate viewer MVP into affordabot's canonical repo-local executable story pack.

Grounded result:

- canonical deterministic substrate stories added for:
  - `substrate_run_list`
  - `substrate_failure_buckets`
  - `substrate_raw_row_detail`
- stable `data-testid` hooks were added to the substrate viewer surface
- `make verify-gate` now targets the founder-critical substrate stories instead of the stale older admin-default set
- `docs/TESTING/STORIES/README.md` now describes the substrate viewer pack as the current founder-critical executable truth

Why this matters:

- product truth and test truth now point at the same founder workflow
- the substrate viewer is no longer treated like an unowned sidecar

## Outcome 3: dx-loop Dogfood Evidence

The wave honored the fail-fast contract.

Observed first-step outcome:

- `dx-loop status --beads-id bd-epyeg`
- `dx-loop explain --beads-id bd-epyeg`

Both returned:

```text
Wave state not found for bd-epyeg
Known persisted waves: 1 (run `dx-loop status` to list).
```

Interpretation:

- this satisfied the locked fail-fast trigger `missing wave state`
- `dx-loop` was not allowed to stay on the critical path after that point
- the product lane cleanly fell back to `gpt-5.3-codex`

Current dogfood verdict:

- `dx-loop` did not qualify as the execution surface for this wave
- the fallback handoff preserved product progress
- the evidence should be handed back to the `dx-loop` control-plane lane as a concrete repro, not a vague reliability complaint

## Validation Snapshot

Grounded checks completed in this wave:

- `#393`: PR checks green after adding the fail-fast evidence log
- `#394`: PR checks green
- `#395`: manifest coverage pass confirmed locally; CI status tracked separately on the PR
- `pytest -q backend/tests/test_substrate_source_inventory_manifest.py` passed on the new-family branch
- `python -m py_compile backend/scripts/substrate/manual_expansion_runner.py backend/tests/test_manual_expansion_runner.py` passed on the new-family branch

## Founder UX QA

`#396` completed the bounded dogfood pass against affordabot dev:

- target URL: `https://frontend-dev-5093.up.railway.app/admin`
- auth path: signed `x-test-user` bypass cookie
- tool: `agent-browser`
- scope:
  - run list
  - failure buckets
  - raw row detail

Verdict:

- `pass-with-gaps`

Grounded outcome:

- run list is usable without SQL
- failure buckets are usable without SQL and show an explicit empty state on healthy runs
- raw row detail is usable without SQL and exposes URL, source URL, storage URI, document ID, trust tier, ingestion stage, content preview, and metadata JSON

Evidence:

- `/tmp/agent-browser-dogfood/screenshots/substrate-admin-dashboard.png`
- `/tmp/agent-browser-dogfood/screenshots/substrate-tab.png`
- `/tmp/agent-browser-dogfood/screenshots/substrate-row-detail.png`

Non-blocking gap:

- manual QA entry friction is higher than expected because plain `x-test-user=admin` no longer works
- the current frontend middleware requires a signed `v1.<payload>.<sig>` cookie
- this gap was confirmed directly in the manual QA lane and is now being repaired in the verification helper path

## Verdict

Current product verdict:

- new-family lane: pass
- story-pack lane: pass
- founder UX lane: pass-with-gaps
- `dx-loop` lane: fail-fast fallback behaved correctly

This wave should be treated as complete.

The only remaining gap is operational QA auth friction, not a blocker in the locked founder-critical substrate flows.

## Remaining Follow-Up

Not blocking this wave:

- promote or merge `#394` and `#395` after final review/CI confirmation
- merge `#396` if you want the QA memo preserved in-repo
- feed the concrete `dx-loop` wave-state failure back to the `dx-loop` agent
- merge the verification-helper signed-cookie fix on `#394`
- decide whether the next moat wave should prioritize:
  - more new-family unlocks
  - founder/operator UX deepening
  - revision-history UX deepening
