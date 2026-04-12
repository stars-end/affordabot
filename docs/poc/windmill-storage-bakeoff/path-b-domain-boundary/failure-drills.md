# Failure Drills

Date: 2026-04-12  
Runner: `backend/scripts/verification/windmill_bakeoff_domain_boundary.py`

## 1) SearXNG Failure Drill

Command:

```bash
/usr/bin/python3 backend/scripts/verification/windmill_bakeoff_domain_boundary.py --scenario source_failure --pretty --out docs/poc/windmill-storage-bakeoff/path-b-domain-boundary/artifacts/source_failure.json
```

Observed:

- Run `status=failed`
- `search_materialize.status=source_error`
- downstream steps did not execute
- storage counts remained zero

Why this matters:
- Transport failure is isolated at discovery step.
- No partial product records are created.

## 2) Reader Failure Drill

Command:

```bash
/usr/bin/python3 backend/scripts/verification/windmill_bakeoff_domain_boundary.py --scenario reader_failure --pretty --out docs/poc/windmill-storage-bakeoff/path-b-domain-boundary/artifacts/reader_failure.json
```

Observed:

- Run `status=failed`
- `search_materialize` and `freshness_gate` succeeded
- `read_fetch.status=reader_error`
- `index` and `analyze` did not execute

Why this matters:
- Reader errors fail before index/analyze.
- Prevents non-provenanced downstream outputs.

## 3) Storage Failure Drill

Command:

```bash
/usr/bin/python3 backend/scripts/verification/windmill_bakeoff_domain_boundary.py --scenario storage_failure --pretty --out docs/poc/windmill-storage-bakeoff/path-b-domain-boundary/artifacts/storage_failure.json
```

Observed:

- Run `status=failed`
- Failure at `index.status=storage_error`
- `read_fetch` succeeded (document + artifact present)
- `chunks=0`, `analyses=0`

Why this matters:
- Domain boundary prevents analysis from running after storage/index failure.
- Partial state remains inspectable but bounded.

## Assessment

Path B failure behavior is explicit and step-scoped. Windmill can orchestrate retries/branches,
while affordabot domain commands enforce product integrity before each transition.
