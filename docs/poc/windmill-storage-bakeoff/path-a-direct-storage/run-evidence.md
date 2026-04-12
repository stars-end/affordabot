# Path A Run Evidence

Contract version: `2026-04-12.windmill-storage-bakeoff.v1`
Architecture path: `windmill_direct_storage`

## First Run

- status: `succeeded`
- reason: `completed`
- search results: `3`
- objects total: `3`
- chunks total: `1`
- documents total: `1`
- analyses total: `1`

## Rerun (Idempotency)

- status: `succeeded`
- reason: `completed`
- objects total: `3`
- chunks total: `1`
- documents total: `1`
- analyses total: `1`

Idempotency assertion:
- canonical documents should remain stable across rerun with same idempotency key
- vector chunks should be reused rather than duplicated
- analysis row should be upserted by idempotency key

Computed checks:
- documents stable: `True`
- chunks stable: `True`
- analyses stable: `True`
- overall idempotent: `True`

## Freshness Gate Drills

- stale usable status: `succeeded`
- stale usable alert count: `1`
- stale usable freshness step: `stale_but_usable`
- stale blocked status: `stale_blocked`
- stale blocked reason: `age_hours=96.00`
- stale blocked terminal freshness step: `stale_blocked`

## Windmill Mapping Limitation

The committed flow export is Windmill-shaped, but Path A execution still concentrates
most domain-like behavior in one script implementation. This proves direct-storage viability,
not full Windmill-native step decomposition. A truly maximal Windmill implementation would
require step-level storage context handoff or more granular scripts, which shifts more domain
invariants into Windmill code.
