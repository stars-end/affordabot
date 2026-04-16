# Policy Evidence Quality Spine Eval Cycles

- feature_key: `bd-3wefe.13`
- final_verdict: `partial`
- max_cycles: `25`

## Domain Progress

| Domain | Pass | Partial | Not proven | Fail | Total |
| --- | --- | --- | --- | --- | --- |
| data_moat | 4 | 1 | 1 | 0 | 6 |
| economic_analysis | 1 | 3 | 2 | 0 | 6 |
| manual_audit | 0 | 0 | 3 | 0 | 3 |

## Gate Status

| Gate | Domain | Severity | Status | Details |
| --- | --- | --- | --- | --- |
| D1 (source_catalog) | data_moat | blocking | pass | catalog_families=['legistar_web_api', 'san_jose_open_data_ckan'], complete_families=['legistar_web_api', 'san_jose_open_data_ckan'], free_ingestible=['legistar_web_api', 'san_jose_open_data_ckan'] |
| D2 (scraped_evidence_quality) | data_moat | blocking | pass | scraped/search=pass, reader=pass, selected_url=present |
| D3 (structured_evidence_quality) | data_moat | blocking | partial | scorecard indicates structured pass, but live cycle lacks structured source-family evidence |
| D4 (unified_package_identity) | data_moat | blocking | not_proven | scraped=pass, structured=partial, package_id=missing, package_artifact=missing, canonical_document_key=missing, structured_sources=0 |
| D5 (storage_readback) | data_moat | blocking | pass | postgres=pass (package_row_linked_to_backend_run_id), minio=pass (all_artifact_refs_read_back), pgvector=pass (document_chunks_and_embeddings_present_with_derived_index_truth_role) |
| D6 (windmill_integration) | data_moat | blocking | pass | live windmill flow run succeeded with concrete windmill_job_id, backend_run_id linked |
| E1 (mechanism_coverage) | economic_analysis | blocking | not_proven | mechanism_family_hint=missing, impact_mode_hint=missing |
| E2 (sufficiency_gate) | economic_analysis | blocking | partial | analysis_status_endpoint=secondary_research_needed |
| E3 (secondary_research_loop) | economic_analysis | blocking | partial | analysis_status confirms secondary_research_needed |
| E4 (canonical_llm_binding) | economic_analysis | blocking | not_proven | LLM narrative not proven (canonical_llm_run_id_missing; source=quality_spine_deterministic_lane). |
| E5 (decision_grade_quality) | economic_analysis | blocking | partial | decision_grade_verdict=not_decision_grade |
| E6 (admin_read_model) | economic_analysis | nonblocking | pass | analysis-status endpoint response captured |
| M1 (manual_data_audit) | manual_audit | blocking | not_proven | manual data audit markdown path missing |
| M2 (manual_economic_audit) | manual_audit | blocking | not_proven | manual economic audit markdown path missing |
| M3 (manual_gate_decision) | manual_audit | blocking | not_proven | manual gate decision markdown path missing |

## Cycle 1 assessment

- artifact: `docs/poc/policy-evidence-quality-spine/artifacts/live_cycle_01_windmill_domain_run.json`
- status: `partial`
- reason: Cycle 1 is partial: selected evidence was economically insufficient, structured lane is not proven in this run, and admin/economic endpoint proof is missing.

## Recommended tweaks

- Run structured-source enrichment in the live cycle and verify source-family provenance.
- Ensure scraped+structured inputs dedupe into the same package_id with canonical identity.
- Strengthen mechanism coverage to include both direct and indirect cost pathways in run_context.
- Raise sufficiency from partial/not_proven to pass using source-bound economic evidence.
- Productize secondary-research loop and bind returned artifacts to the same package_id.
- Persist canonical LLM analysis run+step ids and bind to package_id.
- Meet decision-grade rubric with explicit assumptions, uncertainty, and bounded conclusion.
- Write manual San Jose data moat audit markdown for this cycle.
- Write manual San Jose economic-analysis audit markdown for this cycle.
- Write explicit manual stop/continue gate decision markdown for this cycle.

## Cycle ledger

| Cycle | Status | Verdict | Decision | Windmill Job | Backend Run | Package | Artifacts | Gate deltas | Next tweak |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | completed | partial | continue_prove_remaining | 019d94d2-81ef-1117-0353-4c40719876ed | 6695fe26-eaaf-47d1-9100-7eb861a7aa2f | pkg-sj-parking-minimum-amendment | 1 | 0 | Run structured-source enrichment in the live cycle and verify source-family provenance. |
| 2 | completed | partial | continue_prove_remaining | 019d94d7-1f8a-2755-6d12-4b8c20565081 | 2a6944e1-4c18-4265-b22e-4faa16d7c08b | pkg-sj-parking-minimum-amendment | 1 | 0 | Run structured-source enrichment in the live cycle and verify source-family provenance. |
| 3 | completed | partial | continue_prove_remaining | 019d94da-1547-48ec-9185-11b91651f5be | 498aff1e-3af9-4a28-9895-5058ffc92e21 | pkg-sj-parking-minimum-amendment | 1 | 0 | Run structured-source enrichment in the live cycle and verify source-family provenance. |
| 4 | completed | partial | continue_prove_remaining | 019d94ec-e80e-0daf-3bb2-fdee2c6dce6a | f208078b-64af-4ef6-89b5-caaf5b0b8322 | pkg-ba380f24f5478f2590380e46 | 1 | 2 | Run structured-source enrichment in the live cycle and verify source-family provenance. |
| 5 | completed | partial | continue_prove_remaining | 019d94f5-27d3-0de0-4f82-4d554d74234e | d611af15-4464-4eae-9e86-04b5dd438d27 | pkg-d90d67f6703d5e3d18593814 | 1 | 0 | Run structured-source enrichment in the live cycle and verify source-family provenance. |
| 6 | completed | partial | continue_prove_remaining | 019d94f9-c6fa-9aab-f6e7-eca32b5b951f | f917d334-9dbc-4628-a6de-13a298c46692 | pkg-6f4ae5c23acc5ad4a09b686c | 1 | 0 | Run structured-source enrichment in the live cycle and verify source-family provenance. |
| 7 | completed | partial | continue_prove_remaining | 019d94fb-dfaa-7681-7d6b-c1fb39f6ab49 | e1826ad9-cda9-4737-9c1d-316852460029 | pkg-10adcd7b63e6262425240b5b | 1 | 0 | Run structured-source enrichment in the live cycle and verify source-family provenance. |
| 8 | not_executed | - | continue | - | - | - | 0 | 0 | Run structured-source enrichment in the live cycle and verify source-family provenance. |
| 9 | not_executed | - | continue | - | - | - | 0 | 0 | Run structured-source enrichment in the live cycle and verify source-family provenance. |
| 10 | not_executed | - | continue | - | - | - | 0 | 0 | Run structured-source enrichment in the live cycle and verify source-family provenance. |
| 11 | not_executed | - | continue | - | - | - | 0 | 0 | Run structured-source enrichment in the live cycle and verify source-family provenance. |
| 12 | not_executed | - | continue | - | - | - | 0 | 0 | Run structured-source enrichment in the live cycle and verify source-family provenance. |
| 13 | not_executed | - | continue | - | - | - | 0 | 0 | Run structured-source enrichment in the live cycle and verify source-family provenance. |
| 14 | not_executed | - | continue | - | - | - | 0 | 0 | Run structured-source enrichment in the live cycle and verify source-family provenance. |
| 15 | not_executed | - | continue | - | - | - | 0 | 0 | Run structured-source enrichment in the live cycle and verify source-family provenance. |
| 16 | not_executed | - | continue | - | - | - | 0 | 0 | Run structured-source enrichment in the live cycle and verify source-family provenance. |
| 17 | not_executed | - | continue | - | - | - | 0 | 0 | Run structured-source enrichment in the live cycle and verify source-family provenance. |
| 18 | not_executed | - | continue | - | - | - | 0 | 0 | Run structured-source enrichment in the live cycle and verify source-family provenance. |
| 19 | not_executed | - | continue | - | - | - | 0 | 0 | Run structured-source enrichment in the live cycle and verify source-family provenance. |
| 20 | not_executed | - | continue | - | - | - | 0 | 0 | Run structured-source enrichment in the live cycle and verify source-family provenance. |
| 21 | not_executed | - | continue | - | - | - | 0 | 0 | Run structured-source enrichment in the live cycle and verify source-family provenance. |
| 22 | not_executed | - | continue | - | - | - | 0 | 0 | Run structured-source enrichment in the live cycle and verify source-family provenance. |
| 23 | not_executed | - | continue | - | - | - | 0 | 0 | Run structured-source enrichment in the live cycle and verify source-family provenance. |
| 24 | not_executed | - | continue | - | - | - | 0 | 0 | Run structured-source enrichment in the live cycle and verify source-family provenance. |
| 25 | not_executed | - | continue | - | - | - | 0 | 0 | Run structured-source enrichment in the live cycle and verify source-family provenance. |
