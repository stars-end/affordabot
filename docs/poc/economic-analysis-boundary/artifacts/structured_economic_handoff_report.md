# Structured Economic Handoff Boundary POC

- feature_key: `bd-2agbe.10`
- poc_version: `2026-04-14.structured-economic-handoff.v1`
- generated_at: `2026-04-14T17:17:51.808794+00:00`
- mode: `replay`

## Gate Outcomes

| case_id | expected | final_verdict | blocking_gate |
| --- | --- | --- | --- |
| case_direct_fiscal_quantified_pass | quantified_pass | quantified_pass | none |
| case_local_control_fail_closed_insufficient | fail_closed | fail_closed | parameterization |

## Canonical Code Paths

- Canonical pipeline orchestration and step execution: `backend/services/llm/orchestrator.py:205-211,256-268,633-658,666-676,1020-1049,2283-2373`
- Research service evidence envelopes + sufficiency: `backend/services/legislation_research.py:213-219,260-280,299-330,665-721,723-741`
- Deterministic evidence gate logic: `backend/services/llm/evidence_gates.py:1-5,211-247,249-260`
- Assumption registry applicability constraints: `backend/services/economic_assumptions.py:23-25,61-92,166-187`
- Structured economic artifact contracts: `backend/schemas/economic_evidence.py:45-55,68-83,84-112,114-134,136-164,173-195`
- Pipeline step persistence for audit/read-model: `backend/services/audit/logger.py:16-21,63-66,91-100`
- Pipeline run persistence table writes: `backend/db/postgres_client.py:253-267,278-289`
- Storage path raw_scrapes -> object -> chunks -> pgvector: `backend/services/ingestion_service.py:240-262,269-278,374-407`
- pgvector retrieval contract and filter semantics: `backend/services/retrieval/local_pgvector.py:20-28,64-73,84-91,169-176,214-220`
- Admin/glassbox read model + evidence endpoints: `backend/routers/admin.py:866-879,1268-1305,1346-1364,1373-1403`
- Frontend pipeline status/admin operator links: `frontend/src/components/admin/PipelineStatusPanel.tsx:32-38,58-66,107-115,199-215,219-230`
- Boundary options A/B/C source spec: `docs/specs/2026-04-14-economic-evidence-pipeline-lockdown.md:30-49`

## Boundary Recommendation

- recommended_option: `option_a`
- rationale: Boundary proof supports Windmill DAG control with backend-owned domain gates/contracts; avoid Option C for core economics.
- Windmill should own schedule/fanout/retry/branch orchestration and write only run metadata references.
- Backend should own evidence-card extraction, parameterization, assumptions, quantification, and fail-closed sufficiency decisions.
- Postgres should remain the canonical run/step/read-model store; pgvector should remain retrieval substrate; MinIO should store raw/reader artifacts by URI reference.
- Frontend/admin should remain read-only over backend-authored run/step/evidence models.

## Recommended Contract Extensions

- `backend/services/llm/orchestrator.py`: Emit structured artifact ids (EvidenceCard/ParameterCard/AssumptionCard/ModelCard) into pipeline step outputs and run result payload.
- `backend/routers/admin.py`: Extend /pipeline/runs/{run_id}/evidence to include parameter and assumption provenance, not only analysis citations.
- `backend/db/postgres_client.py`: Persist contract_version and artifact-count metrics on pipeline_runs for deterministic dashboard gating.
- `frontend/src/components/admin/PipelineStatusPanel.tsx`: Show gate-level blocking stage and structured artifact counts for operator audit decisions.

## Evidence Quality

- Replay-mode quantification is deterministic contract proof, not live production proof. Railway-dev rollout still requires live source/read/analysis runs with persisted artifact audits.
- Required before Railway-dev rollout: at least one live multi-jurisdiction run proving gate-by-gate parity with replay plus persistence-read-model integrity.
