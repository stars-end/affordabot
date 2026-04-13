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
  --run-mode stub-run \
  --stale-drill-statuses stale_but_usable,stale_blocked \
  --idempotent-rerun
```

Backend endpoint mode (only when backend endpoint + auth are configured):

```bash
cd backend
poetry run python scripts/verification/verify_windmill_sanjose_live_gate.py \
  --run-mode backend-endpoint-run \
  --stale-drill-statuses stale_but_usable,stale_blocked \
  --idempotent-rerun \
  --database-url "$DATABASE_URL"
```

Standalone provider bakeoff (read-only):

```bash
cd backend
poetry run python scripts/verification/verify_search_provider_bakeoff.py
```

Live gate artifacts:

- `docs/poc/windmill-domain-boundary-integration/artifacts/sanjose_live_gate_report.json`
- `docs/poc/windmill-domain-boundary-integration/artifacts/sanjose_live_gate_report.md`
- `docs/poc/windmill-domain-boundary-integration/artifacts/search_provider_bakeoff_report.json`

Live gate classification rules:

- `stub_orchestration_pass`: Windmill DAG + envelope path validated, but command path remains stub-backed.
- `backend_bridge_surface_ready`: backend endpoint configuration + local mock probe validated, but live storage-backed execution is still unproven.
- `full_product_pass`: Windmill DAG validated and storage/runtime evidence gates are satisfied.
- `read_only_surface_pass`: workspace/script/flow/job/schedule surfaces validated without triggering a flow run.
- `blocked`: run requested a mode requiring unavailable auth/runtime inputs.

`backend_endpoint` is now an explicit command-client mode in the Windmill flow
and script, but it is opt-in and fail-closed. The live default remains `stub`.
The endpoint contract is backend-owned at `/cron/pipeline/domain/run-scope`;
Windmill resolves backend URL and cron auth through workspace vars when that
mode is explicitly enabled.
