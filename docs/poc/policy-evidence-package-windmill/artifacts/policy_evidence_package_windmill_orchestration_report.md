# Policy Evidence Package Windmill Orchestration Report

## Status
- local_status: `passed`
- local_stub_status: `passed`
- local_backend_endpoint_status: `passed`
- live_status: `blocked_backend_endpoint_route_mismatch`

## Steps Proven
- `fetch_scraped_candidates`
- `fetch_structured_candidates`
- `build_policy_evidence_package`
- `persist_readback_boundary`
- `evaluate_package_readiness`
- `summarize_orchestration`

## Boundary Assertions
- `windmill_owns_orchestration_only`
- `backend_command_ids_preserved`
- `windmill_run_job_step_refs_preserved`
- `package_id_storage_refs_gate_status_preserved`
- `branch_on_backend_authored_readiness_only`

## Stub Happy Path
- status: `succeeded`
- package_id: `pkg-local-happy`
- readiness: `ready`
- gate_status: `quantified`
- decision_reason: `package_ready_for_economic_handoff`
- retry_class: `none`

## Stub Blocked Path
- status: `blocked`
- package_id: `pkg-local-blocked`
- readiness: `blocked`
- gate_status: `insufficient_evidence`
- decision_reason: `package_not_ready_for_economic_handoff`
- retry_class: `retry_after_new_evidence`

## Local Backend Endpoint Path
- status: `succeeded`
- command_client: `backend_endpoint`
- event_count: `6`
- command_names_seen: `fetch_scraped_candidates,fetch_structured_candidates,build_policy_evidence_package,persist_readback_boundary,evaluate_package_readiness,summarize_orchestration`

## Contract Alignment
- policy_evidence_backend_path: `/cron/pipeline/policy-evidence/command`
- policy_evidence_backend_route_present: `False`
- domain_boundary_backend_path: `/cron/pipeline/domain/run-scope`
- domain_boundary_backend_route_present: `True`
- route_mismatch: `True`
- authoritative_live_product_flow: `f/affordabot/pipeline_daily_refresh_domain_boundary__flow`

## Authoritative Live Evidence
- flow_path: `f/affordabot/pipeline_daily_refresh_domain_boundary__flow`
- idempotency_key: `bd-3wefe.13-live-domain-backend-2026-04-15-r1`
- status: `succeeded_with_alerts`
- warning: `top z.ai reader candidates returned provider 500; fallback transcript materialized; sufficiency_state=Insufficient`

## Live Windmill Surface Probe
- commands: `windmill-cli workspace list (read-only), windmill-cli flow get f/affordabot/policy_evidence_package_orchestration__flow (read-only), windmill-cli flow run f/affordabot/policy_evidence_package_orchestration__flow (stub, synchronous)`
- live_status: `passed_stub_flow_run`
- blocker: `None`
- verifier_live_status: `blocked_backend_endpoint_route_mismatch`

## Open Gaps
- policy-evidence stub flow pass is not authoritative for full live product proof
- route mismatch: policy-evidence backend endpoint path is not a live backend route
- treat latest domain-boundary live run as proof-with-warning, not clean data-quality pass
- run storage verifier in Railway dev with DATABASE_URL and MinIO env available
- connect resulting package to canonical analysis output and admin/frontend read model
