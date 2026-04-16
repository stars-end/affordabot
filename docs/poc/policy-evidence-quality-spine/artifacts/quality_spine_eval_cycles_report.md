# Policy Evidence Quality Spine Eval Cycles

- feature_key: `bd-3wefe.13`
- final_verdict: `fail`
- max_cycles: `25`

## Domain Progress

| Domain | Pass | Partial | Not proven | Fail | Total |
| --- | --- | --- | --- | --- | --- |
| data_moat | 3 | 2 | 0 | 1 | 6 |
| economic_analysis | 2 | 2 | 1 | 1 | 6 |
| manual_audit | 3 | 0 | 0 | 0 | 3 |

## Gate Status

| Gate | Domain | Severity | Status | Details |
| --- | --- | --- | --- | --- |
| D1 (source_catalog) | data_moat | blocking | pass | catalog_families=['legistar_web_api', 'san_jose_open_data_ckan'], complete_families=['legistar_web_api', 'san_jose_open_data_ckan'], free_ingestible=['legistar_web_api', 'san_jose_open_data_ckan'] |
| D2 (scraped_evidence_quality) | data_moat | blocking | pass | scraped/search=pass, reader=pass, selected_url=present |
| D3 (structured_evidence_quality) | data_moat | blocking | partial | scorecard indicates structured pass, but live cycle lacks structured source-family evidence |
| D4 (unified_package_identity) | data_moat | blocking | partial | scraped=pass, structured=partial, package_id=present, package_artifact=present, canonical_document_key=present, structured_sources=1 |
| D5 (storage_readback) | data_moat | blocking | pass | postgres=pass (package_row_linked_to_backend_run_id), minio=pass (all_artifact_refs_read_back), pgvector=pass (document_chunks_and_embeddings_present_with_derived_index_truth_role) |
| D6 (windmill_integration) | data_moat | blocking | fail | windmill job present but final_status=failed |
| E1 (mechanism_coverage) | economic_analysis | blocking | pass | mechanism_family_hint=fee_or_tax_pass_through, impact_mode_hint=pass_through_incidence |
| E2 (sufficiency_gate) | economic_analysis | blocking | pass | sufficiency=pass, economic_reasoning=pass |
| E3 (secondary_research_loop) | economic_analysis | blocking | partial | secondary_research_needed=true |
| E4 (canonical_llm_binding) | economic_analysis | blocking | not_proven | LLM narrative not proven (canonical_llm_run_id_missing; source=quality_spine_deterministic_lane). |
| E5 (decision_grade_quality) | economic_analysis | blocking | partial | decision_grade_verdict=not_decision_grade |
| E6 (admin_read_model) | economic_analysis | nonblocking | fail | analysis-status endpoint returned error |
| M1 (manual_data_audit) | manual_audit | blocking | pass | manual_data_audit_path=../docs/poc/policy-evidence-quality-spine/manual_audit_cycle_13_data_moat.md |
| M2 (manual_economic_audit) | manual_audit | blocking | pass | manual_economic_audit_path=../docs/poc/policy-evidence-quality-spine/manual_audit_cycle_13_economic_analysis.md |
| M3 (manual_gate_decision) | manual_audit | blocking | pass | manual_gate_decision_path=../docs/poc/policy-evidence-quality-spine/manual_gate_decision_cycle_13.md |

## Cycle 1 assessment

- artifact: `docs/poc/policy-evidence-quality-spine/artifacts/live_cycle_01_windmill_domain_run.json`
- status: `partial`
- reason: Cycle 1 is partial: selected evidence was economically insufficient, structured lane is not proven in this run, and admin/economic endpoint proof is missing.

## Recommended tweaks

- Capture successful live windmill_job_id and backend_run_id linkage in the same cycle.
- Capture and store /analysis-status endpoint response artifact for the cycle.
- Run structured-source enrichment in the live cycle and verify source-family provenance.
- Ensure scraped+structured inputs dedupe into the same package_id with canonical identity.
- Productize secondary-research loop and bind returned artifacts to the same package_id.
- Persist canonical LLM analysis run+step ids and bind to package_id.
- Meet decision-grade rubric with explicit assumptions, uncertainty, and bounded conclusion.

## Cycle ledger

| Cycle | Status | Verdict | Decision | Windmill Job | Backend Run | Package | Artifacts | Gate deltas | Next tweak |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | not_executed | - | continue | - | - | - | 0 | 0 | Capture successful live windmill_job_id and backend_run_id linkage in the same cycle. |
| 2 | not_executed | - | continue | - | - | - | 0 | 0 | Capture successful live windmill_job_id and backend_run_id linkage in the same cycle. |
| 3 | not_executed | - | continue | - | - | - | 0 | 0 | Capture successful live windmill_job_id and backend_run_id linkage in the same cycle. |
| 4 | not_executed | - | continue | - | - | - | 0 | 0 | Capture successful live windmill_job_id and backend_run_id linkage in the same cycle. |
| 5 | not_executed | - | continue | - | - | - | 0 | 0 | Capture successful live windmill_job_id and backend_run_id linkage in the same cycle. |
| 6 | not_executed | - | continue | - | - | - | 0 | 0 | Capture successful live windmill_job_id and backend_run_id linkage in the same cycle. |
| 7 | not_executed | - | continue | - | - | - | 0 | 0 | Capture successful live windmill_job_id and backend_run_id linkage in the same cycle. |
| 8 | not_executed | - | continue | - | - | - | 0 | 0 | Capture successful live windmill_job_id and backend_run_id linkage in the same cycle. |
| 9 | not_executed | - | continue | - | - | - | 0 | 0 | Capture successful live windmill_job_id and backend_run_id linkage in the same cycle. |
| 10 | not_executed | - | continue | - | - | - | 0 | 0 | Capture successful live windmill_job_id and backend_run_id linkage in the same cycle. |
| 11 | not_executed | - | continue | - | - | - | 0 | 0 | Capture successful live windmill_job_id and backend_run_id linkage in the same cycle. |
| 12 | not_executed | - | continue | - | - | - | 0 | 0 | Capture successful live windmill_job_id and backend_run_id linkage in the same cycle. |
| 13 | completed | fail | continue_fix_failed_gate | 019d9571-ba10-6e09-4355-3cc297c83d5a | 848c36e6-54e2-49c2-9906-9206ede90787 | pkg-02457f6abdab43aaa78cdc44 | 1 | 0 | Capture successful live windmill_job_id and backend_run_id linkage in the same cycle. |
| 14 | not_executed | - | continue | - | - | - | 0 | 0 | Capture successful live windmill_job_id and backend_run_id linkage in the same cycle. |
| 15 | not_executed | - | continue | - | - | - | 0 | 0 | Capture successful live windmill_job_id and backend_run_id linkage in the same cycle. |
| 16 | not_executed | - | continue | - | - | - | 0 | 0 | Capture successful live windmill_job_id and backend_run_id linkage in the same cycle. |
| 17 | not_executed | - | continue | - | - | - | 0 | 0 | Capture successful live windmill_job_id and backend_run_id linkage in the same cycle. |
| 18 | not_executed | - | continue | - | - | - | 0 | 0 | Capture successful live windmill_job_id and backend_run_id linkage in the same cycle. |
| 19 | not_executed | - | continue | - | - | - | 0 | 0 | Capture successful live windmill_job_id and backend_run_id linkage in the same cycle. |
| 20 | not_executed | - | continue | - | - | - | 0 | 0 | Capture successful live windmill_job_id and backend_run_id linkage in the same cycle. |
| 21 | not_executed | - | continue | - | - | - | 0 | 0 | Capture successful live windmill_job_id and backend_run_id linkage in the same cycle. |
| 22 | not_executed | - | continue | - | - | - | 0 | 0 | Capture successful live windmill_job_id and backend_run_id linkage in the same cycle. |
| 23 | not_executed | - | continue | - | - | - | 0 | 0 | Capture successful live windmill_job_id and backend_run_id linkage in the same cycle. |
| 24 | not_executed | - | continue | - | - | - | 0 | 0 | Capture successful live windmill_job_id and backend_run_id linkage in the same cycle. |
| 25 | not_executed | - | continue | - | - | - | 0 | 0 | Capture successful live windmill_job_id and backend_run_id linkage in the same cycle. |
