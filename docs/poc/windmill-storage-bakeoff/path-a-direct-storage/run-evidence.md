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
