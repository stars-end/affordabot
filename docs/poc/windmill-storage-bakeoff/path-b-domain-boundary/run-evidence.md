# Run Evidence

Date: 2026-04-12  
Feature key: `bd-jxclm.15` (Beads reconciliation pending infra repair)  
Path: `B / affordabot_domain_boundary`

## Commands

```bash
/usr/bin/python3 backend/scripts/verification/windmill_bakeoff_domain_boundary.py --help
/usr/bin/python3 backend/scripts/verification/windmill_bakeoff_domain_boundary.py --scenario happy_rerun --pretty --out docs/poc/windmill-storage-bakeoff/path-b-domain-boundary/artifacts/happy_rerun.json
/usr/bin/python3 backend/scripts/verification/windmill_bakeoff_domain_boundary.py --scenario source_failure --pretty --out docs/poc/windmill-storage-bakeoff/path-b-domain-boundary/artifacts/source_failure.json
/usr/bin/python3 backend/scripts/verification/windmill_bakeoff_domain_boundary.py --scenario reader_failure --pretty --out docs/poc/windmill-storage-bakeoff/path-b-domain-boundary/artifacts/reader_failure.json
/usr/bin/python3 backend/scripts/verification/windmill_bakeoff_domain_boundary.py --scenario storage_failure --pretty --out docs/poc/windmill-storage-bakeoff/path-b-domain-boundary/artifacts/storage_failure.json
/usr/bin/python3 backend/scripts/verification/windmill_bakeoff_domain_boundary.py --scenario stale_usable --pretty --out docs/poc/windmill-storage-bakeoff/path-b-domain-boundary/artifacts/stale_usable.json
/usr/bin/python3 backend/scripts/verification/windmill_bakeoff_domain_boundary.py --scenario stale_blocked --pretty --out docs/poc/windmill-storage-bakeoff/path-b-domain-boundary/artifacts/stale_blocked.json
/usr/bin/python3 -m unittest backend/tests/verification/test_windmill_bakeoff_domain_boundary.py
```

## Outcome Summary

- `--help`: pass
- Happy path first run: `status=succeeded`
- Rerun/idempotency: `status=succeeded` with no duplicate writes
- Source failure drill: `status=failed` with `search_materialize:source_error`
- Reader failure drill: `status=failed` with `read_fetch:reader_error`
- Storage failure drill: `status=failed` with `index:storage_error`
- Stale usable drill: `status=succeeded` with `freshness_gate:stale_but_usable`
- Stale blocked drill: `status=failed` with `freshness_gate:stale_blocked`
- Narrow tests: pass (`Ran 3 tests ... OK`)

## Key Evidence

From `happy_rerun.json`:

- First run:
  - `canonical_document_key`: `san-jose-ca::a653e7debe31e650`
  - `artifact_ref`: `minio://affordabot-artifacts/San_Jose_CA/ecf092f9a92f34b1.md`
  - `chunks_created`: `5`
  - `analysis_id`: `analysis-ebbbe7e0f3aeac41` (`reused=false`)
- Rerun:
  - same `canonical_document_key`
  - same `artifact_ref`
  - `chunks_created`: `0`
  - same `analysis_id` with `reused=true`

Interpretation: idempotency is preserved across document identity, artifacts, chunks, and analysis.

## Live Infra Blockers

- None for deterministic contract validation.
- Live Windmill/SearXNG/Z.ai credentials were intentionally not used under current safety constraints.

## Windmill Export Evidence

The Path B orchestration shape is committed as reviewable repo code:

- `ops/windmill/f/affordabot/pipeline_daily_refresh_domain_boundary.py`
- `ops/windmill/f/affordabot/pipeline_daily_refresh_domain_boundary.script.yaml`
- `ops/windmill/f/affordabot/pipeline_daily_refresh_domain_boundary__flow/flow.yaml`
