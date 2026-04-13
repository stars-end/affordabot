# Windmill Domain Boundary Local Integration

This POC verifies the local integration chain for `bd-9qjof.6`:

`Windmill-shaped orchestration -> coarse domain commands -> in-memory state surfaces -> run artifact`

## Scope

- Deterministic local run only (no external network or storage calls).
- Uses `domain_package` mode in the Windmill orchestration script.
- Proves:
  - happy San Jose meeting-minutes run
  - rerun idempotency behavior
  - stale-blocked short-circuit behavior
  - windmill envelope metadata propagation into domain command responses
  - no direct canonical storage API usage in Windmill orchestration layer

## Run

```bash
cd backend
poetry run python scripts/verification/verify_windmill_domain_boundary_local_integration.py
```

Artifacts are written to:

- `docs/poc/windmill-domain-boundary-integration/artifacts/local_integration_report.json`
- `docs/poc/windmill-domain-boundary-integration/artifacts/local_integration_report.md`
