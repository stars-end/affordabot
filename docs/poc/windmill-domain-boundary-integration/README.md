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

## Live Windmill Manual Gate

Use the canonical live harness:

```bash
cd backend
poetry run python scripts/verification/verify_windmill_sanjose_live_gate.py \
  --run-mode stub-run
```

Live gate artifacts:

- `docs/poc/windmill-domain-boundary-integration/artifacts/sanjose_live_gate_report.json`
- `docs/poc/windmill-domain-boundary-integration/artifacts/sanjose_live_gate_report.md`

Live gate classification rules:

- `stub_orchestration_pass`: Windmill DAG + envelope path validated, but command path remains stub-backed.
- `full_product_pass`: Windmill DAG validated and storage/runtime evidence gates are satisfied.
- `read_only_surface_pass`: workspace/script/flow/job/schedule surfaces validated without triggering a flow run.
