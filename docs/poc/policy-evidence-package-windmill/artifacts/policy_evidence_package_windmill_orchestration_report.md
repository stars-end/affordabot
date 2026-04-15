# Policy Evidence Package Windmill Orchestration Report

## Status
- local_status: `passed`
- live_status: `passed_read_only_smoke`

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

## Happy Path
- status: `succeeded`
- package_id: `pkg-local-happy`
- readiness: `ready`
- gate_status: `quantified`
- decision_reason: `package_ready_for_economic_handoff`
- retry_class: `none`

## Blocked Path
- status: `blocked`
- package_id: `pkg-local-blocked`
- readiness: `blocked`
- gate_status: `insufficient_evidence`
- decision_reason: `package_not_ready_for_economic_handoff`
- retry_class: `retry_after_new_evidence`

## Live Windmill Smoke
- command: `windmill-cli workspace list (read-only)`
- live_status: `passed_read_only_smoke`
- blocker: `None`

## Open Gaps
- bd-3wefe.10: storage durability, readback atomicity, replay semantics
- bd-3wefe.5: economic sufficiency gate over packaged evidence
- bd-3wefe.6: direct/indirect/secondary research analysis quality cases
