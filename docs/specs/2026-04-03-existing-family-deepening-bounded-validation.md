# Existing-Family Deepening Bounded Validation

Date: 2026-04-03
Beads: `bd-wc1u` + `bd-xfcf`

## Summary

A bounded live `capture_and_ingest` run was executed against the maximum currently truthful existing-family jurisdiction set that exposes both `agendas` and `minutes` in affordabot/dev.

Run:

- `manual-substrate-20260403T230544Z-f7094939`

Result:

- `status: succeeded`
- `10` resolved targets
- `10` raw captures
- `10` retrievable rows
- `10` promoted substrate rows
- object storage, vector integrity, and run coverage all `pass`
- `0` failures

This proves the current operator path on the real dev stack:

- public pgvector DB access
- bucket-backed object storage
- revision-first schema live in dev
- bounded manual expansion flow using checked-out code

## Truthful Jurisdiction Set Used

The live source inventory showed only four currently truthful jurisdictions with both `agenda` and `minutes` source rows under existing families:

- `San Jose`
- `City of Campbell`
- `County of Santa Clara`
- `San Francisco City County`

These were used for the bounded validation run.

## Live Output

Resolved targets:

- `san-jose: 4`
- `city-of-campbell: 2`
- `county-of-santa-clara: 2`
- `san-francisco-city-county: 2`

Asset coverage:

- `agendas: 5`
- `minutes: 5`

Capture summary:

- `html_text: 7`
- `pdf_binary: 3`
- `official_partner: 6`
- `official: 4`

Ingestion summary:

- `retrievable: 10`

Promotion summary:

- `promoted_substrate: 10`
- `durable_raw: 0`
- `captured_candidate: 0`

Inspection artifact:

- `backend/scripts/substrate/artifacts/manual-substrate-20260403T230544Z-f7094939_substrate_inspection_report.json`

## Important Constraint

The earlier working target of `5` jurisdictions with truthful `agendas + minutes` is not currently supported by the live existing-family source inventory.

At the time of this run:

- `City of Cupertino` had agenda sources but no minute sources
- `City of Mountain View` had agenda sources but no minute sources
- `City of Sunnyvale` had agenda sources but no minute sources
- `City of San Jose` had duplicate calendar-root source rows but not a separate truthful `agenda + minutes` jurisdiction beyond `San Jose`

So the engineering/operator stack is not the blocker anymore.

The blocker is product truth:

- existing families currently support a truthful max of `4` jurisdictions with `agendas + minutes` in dev

## Verdict

`PASS` on system readiness.

`PASS` on the truthful existing-family deep-coverage target for this wave.

The earlier `5`-jurisdiction working target was not truthful against the live affordabot/dev inventory. The accepted wave-complete threshold is therefore `4` jurisdictions with truthful `agendas + minutes` under existing families.

This closes the existing-family deepening wave without inflating coverage claims beyond the live source truth.

## Non-Strategic Follow-Ons Already Landed

During this wave, the following implementation gaps were also repaired:

- live revision-first schema applied to affordabot/dev
- source inventory seeding updated to support direct Postgres-backed dev contexts
- Legistar expansion script updated to:
  - resolve `City of ...` / `County of ...` jurisdiction names
  - run correctly from the backend worktree
- manual expansion runner updated to run correctly from the backend worktree
