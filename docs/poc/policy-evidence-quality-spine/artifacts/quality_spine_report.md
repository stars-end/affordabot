# Policy Evidence Quality Spine Economic Report

- feature_key: `bd-3wefe.13`
- report_version: `2026-04-15.policy-evidence-quality-spine-economics.v1`
- generated_at: `2026-04-15T18:56:05.883214+00:00`
- matrix_mode: `agent_a_horizontal_matrix`
- matrix_path: `docs/poc/policy-evidence-quality-spine/artifacts/horizontal_matrix.json`
- overall_verdict: `partial`
- vertical_package_id: `pkg-sj-parking-minimum-amendment`
- sufficiency_readiness: `economic_handoff_ready`

## Failure taxonomy

| Category | Status | Evidence |
| --- | --- | --- |
| scraped/search | pass | Selected artifact has provider-quality support (provider=private_searxng, status=strong, reason=artifact_top2). |
| reader | pass | Reader substance passed and reader artifact refs present. |
| structured-source | pass | Structured source provenance attached. |
| identity/dedupe | pass | Canonical document key present for dedupe/identity join. |
| storage/read-back | not_proven | Deterministic in-memory readback is proven, but non-memory Postgres/MinIO storage proof is not provided. |
| Windmill/orchestration | not_proven | Historical Windmill stub proof exists but is not valid for current vertical package. |
| sufficiency gate | pass | readiness=economic_handoff_ready |
| economic reasoning | pass | Mechanism model cards and source-bound parameter/assumption inputs are present. |
| LLM narrative | not_proven | LLM narrative not proven (canonical_llm_run_id_missing; source=quality_spine_deterministic_lane). |
| frontend/read-model auditability | pass | Read-model payload is display-only and does not recompute economic truth. |

## Vertical economic output

- mechanism_type: `direct`
- quantified: `True`
- unsupported_claim_rejection: `none`

### User-facing conclusion

Package is quantified-ready for canonical economic analysis handoff; the low/base/high range is source-bound and auditable.

## Read-model/admin audit output

- frontend_requires_recomputation: `False`
- admin_requires_recomputation: `False`
- canonical_analysis_adapter: `policy_package_projection_into_canonical_analysis`
- llm_narrative_proof_status: `not_proven`
- llm_narrative_proof_blocker: `canonical_llm_run_id_missing_or_not_executed`
