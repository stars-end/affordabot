# Policy Evidence Package Windmill Orchestration POC

Feature key: `bd-3wefe.12`

This POC proves Windmill can orchestrate the policy evidence package path
without owning product logic.

## Scope

The flow models these backend command boundaries:

1. `fetch_scraped_candidates`
2. `fetch_structured_candidates`
3. `build_policy_evidence_package`
4. `persist_readback_boundary`
5. `evaluate_package_readiness`
6. `summarize_orchestration`

Windmill branches only on backend-authored readiness status.

This POC now proves two command-client lanes:

1. `command_client=stub` for deterministic orchestration contract checks.
2. `command_client=backend_endpoint` through a local backend-command HTTP surface
   used by the verifier (non-stub boundary proof without embedding product logic
   in Windmill).

## Files

- Windmill script: `ops/windmill/f/affordabot/policy_evidence_package_orchestration.py`
- Windmill script export: `ops/windmill/f/affordabot/policy_evidence_package_orchestration.script.yaml`
- Windmill flow export: `ops/windmill/f/affordabot/policy_evidence_package_orchestration__flow/flow.yaml`
- Tests: `backend/tests/ops/test_policy_evidence_package_windmill_orchestration.py`
- Verifier: `backend/scripts/verification/verify_policy_evidence_package_windmill_orchestration.py`
- Artifact JSON: `docs/poc/policy-evidence-package-windmill/artifacts/policy_evidence_package_windmill_orchestration_report.json`
- Artifact Markdown: `docs/poc/policy-evidence-package-windmill/artifacts/policy_evidence_package_windmill_orchestration_report.md`

## Boundary Contract

- Windmill owns retries, fanout/branching, and run-level status.
- Backend command outputs own `decision_reason`, `retry_class`, and package/gate semantics.
- Windmill carries through:
  - workspace/run/job/step ids
  - backend command ids
  - package id
  - storage refs
  - readiness + gate status
- No ranking rules, formulas, assumption selection, or final narrative logic in Windmill assets.

## Run

```bash
cd backend
poetry run pytest tests/ops/test_policy_evidence_package_windmill_orchestration.py
poetry run python scripts/verification/verify_policy_evidence_package_windmill_orchestration.py
```

The verifier includes a live Windmill dev smoke check. If non-interactive auth,
CLI access, or deployment is unavailable, it records a blocker and keeps the
local deterministic proof as the primary evidence.

Verifier output now distinguishes:

- deterministic stub path
- deterministic backend-endpoint path (local HTTP backend command surface)
- live Windmill dev surface (`workspace list`, `flow get`, and synchronous stub
  `flow run`)
