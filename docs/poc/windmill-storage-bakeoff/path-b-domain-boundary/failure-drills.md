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

## 4) Stale Gate Drill (`stale_but_usable`)

Command:

```bash
/usr/bin/python3 backend/scripts/verification/windmill_bakeoff_domain_boundary.py --scenario stale_usable --pretty --out docs/poc/windmill-storage-bakeoff/path-b-domain-boundary/artifacts/stale_usable.json
```

Observed:

- Run `status=succeeded`
- `freshness_gate.status=stale_but_usable`
- Alert emitted: `freshness_gate:stale_but_usable`
- `read_fetch/index/analyze` continue

Why this matters:
- Staleness can degrade gracefully with explicit alerting.
- Supports "use yesterday's data" behavior while retaining traceability.

## 5) Stale Gate Drill (`stale_blocked`)

Command:

```bash
/usr/bin/python3 backend/scripts/verification/windmill_bakeoff_domain_boundary.py --scenario stale_blocked --pretty --out docs/poc/windmill-storage-bakeoff/path-b-domain-boundary/artifacts/stale_blocked.json
```

Observed:

- Run `status=failed`
- `freshness_gate.status=stale_blocked`
- Pipeline stops before `read_fetch`

Why this matters:
- Fail-closed behavior is explicit at the freshness boundary.
- Prevents stale evidence from flowing into analysis.

## Assessment

Path B failure behavior is explicit and step-scoped. Windmill can orchestrate retries/branches,
while affordabot domain commands enforce product integrity before each transition.
