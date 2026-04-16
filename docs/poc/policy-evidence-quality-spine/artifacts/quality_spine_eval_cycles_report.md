# Policy Evidence Quality Spine Eval Cycles

- feature_key: `bd-3wefe.13`
- final_verdict: `fail`
- max_cycles: `30`

## Domain Progress

| Domain | Pass | Partial | Not proven | Fail | Total |
| --- | --- | --- | --- | --- | --- |
| data_moat | 4 | 1 | 1 | 0 | 6 |
| economic_analysis | 1 | 1 | 3 | 1 | 6 |
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
| E2 (sufficiency_gate) | economic_analysis | blocking | pass | sufficiency=pass, economic_reasoning=pass |
| E3 (secondary_research_loop) | economic_analysis | blocking | not_proven | secondary research signal missing from run_context |
| E4 (canonical_llm_binding) | economic_analysis | blocking | not_proven | LLM narrative not proven (canonical_llm_run_id_missing; source=quality_spine_deterministic_lane). |
| E5 (decision_grade_quality) | economic_analysis | blocking | partial | decision_grade_verdict=not_decision_grade |
| E6 (admin_read_model) | economic_analysis | nonblocking | fail | analysis-status endpoint returned error |
| M1 (manual_data_audit) | manual_audit | blocking | not_proven | manual data audit markdown path missing |
| M2 (manual_economic_audit) | manual_audit | blocking | not_proven | manual economic audit markdown path missing |
| M3 (manual_gate_decision) | manual_audit | blocking | not_proven | manual gate decision markdown path missing |

## Cycle 1 assessment

- artifact: `docs/poc/policy-evidence-quality-spine/artifacts/live_cycle_01_windmill_domain_run.json`
- status: `partial`
- reason: Cycle 1 is partial: selected evidence was economically insufficient, structured lane is not proven in this run, and admin/economic endpoint proof is missing.

## Recommended tweaks

- Capture and store /analysis-status endpoint response artifact for the cycle.
- Run structured-source enrichment in the live cycle and verify source-family provenance.
- Ensure scraped+structured inputs dedupe into the same package_id with canonical identity.
- Strengthen mechanism coverage to include both direct and indirect cost pathways in run_context.
- Productize secondary-research loop and bind returned artifacts to the same package_id.
- Persist canonical LLM analysis run+step ids and bind to package_id.
- Meet decision-grade rubric with explicit assumptions, uncertainty, and bounded conclusion.
- Write manual San Jose data moat audit markdown for this cycle.
- Write manual San Jose economic-analysis audit markdown for this cycle.
- Write explicit manual stop/continue gate decision markdown for this cycle.

## Cycle ledger

| Cycle | Status | Verdict | Decision | Windmill Job | Backend Run | Package | Artifacts | Gate deltas | Next tweak |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | completed | partial | continue_prove_remaining | 019d94d2-81ef-1117-0353-4c40719876ed | 6695fe26-eaaf-47d1-9100-7eb861a7aa2f | pkg-sj-parking-minimum-amendment | 1 | 0 | Capture and store /analysis-status endpoint response artifact for the cycle. |
| 2 | completed | partial | continue_prove_remaining | 019d94d7-1f8a-2755-6d12-4b8c20565081 | 2a6944e1-4c18-4265-b22e-4faa16d7c08b | pkg-sj-parking-minimum-amendment | 1 | 0 | Capture and store /analysis-status endpoint response artifact for the cycle. |
| 3 | completed | partial | continue_prove_remaining | 019d94da-1547-48ec-9185-11b91651f5be | 498aff1e-3af9-4a28-9895-5058ffc92e21 | pkg-sj-parking-minimum-amendment | 1 | 0 | Capture and store /analysis-status endpoint response artifact for the cycle. |
| 4 | completed | partial | continue_prove_remaining | 019d94ec-e80e-0daf-3bb2-fdee2c6dce6a | f208078b-64af-4ef6-89b5-caaf5b0b8322 | pkg-ba380f24f5478f2590380e46 | 1 | 3 | Capture and store /analysis-status endpoint response artifact for the cycle. |
| 5 | completed | partial | continue_prove_remaining | 019d94f5-27d3-0de0-4f82-4d554d74234e | d611af15-4464-4eae-9e86-04b5dd438d27 | pkg-d90d67f6703d5e3d18593814 | 1 | 0 | Capture and store /analysis-status endpoint response artifact for the cycle. |
| 6 | completed | partial | continue_prove_remaining | 019d94f9-c6fa-9aab-f6e7-eca32b5b951f | f917d334-9dbc-4628-a6de-13a298c46692 | pkg-6f4ae5c23acc5ad4a09b686c | 1 | 0 | Capture and store /analysis-status endpoint response artifact for the cycle. |
| 7 | completed | partial | continue_prove_remaining | 019d94fb-dfaa-7681-7d6b-c1fb39f6ab49 | e1826ad9-cda9-4737-9c1d-316852460029 | pkg-10adcd7b63e6262425240b5b | 1 | 0 | Capture and store /analysis-status endpoint response artifact for the cycle. |
| 8 | not_executed | - | continue | - | - | - | 0 | 0 | Capture and store /analysis-status endpoint response artifact for the cycle. |
| 9 | not_executed | - | continue | - | - | - | 0 | 0 | Capture and store /analysis-status endpoint response artifact for the cycle. |
| 10 | completed | partial | continue_prove_remaining | 019d9557-11b4-9cea-38fa-818cd959f02e | - | pkg-sj-parking-minimum-amendment | 1 | 4 | Capture and store /analysis-status endpoint response artifact for the cycle. |
| 11 | completed | partial | continue_prove_remaining | 019d955c-74e6-353f-705c-c21c6bca4366 | 085ff7ce-eb4d-4df6-9df2-7ba488c904ae | pkg-d04e8a67cc9bb4eac46e4d9a | 1 | 4 | Capture and store /analysis-status endpoint response artifact for the cycle. |
| 12 | completed | partial | continue_prove_remaining | 019d956c-95d7-449c-3fb9-1fdbe2f00613 | - | pkg-sj-parking-minimum-amendment | 1 | 4 | Capture and store /analysis-status endpoint response artifact for the cycle. |
| 13 | completed | partial | continue_prove_remaining | 019d9571-ba10-6e09-4355-3cc297c83d5a | 848c36e6-54e2-49c2-9906-9206ede90787 | pkg-02457f6abdab43aaa78cdc44 | 1 | 4 | Capture and store /analysis-status endpoint response artifact for the cycle. |
| 14 | completed | partial | continue_prove_remaining | 019d957d-b9c3-9ebc-5db4-32ef156b4e47 | 651818df-05d7-4a98-ab5a-b5047ce7fe47 | pkg-3da784731acec1a985cc33cd | 1 | 0 | Capture and store /analysis-status endpoint response artifact for the cycle. |
| 15 | completed | partial | continue_prove_remaining | 019d9580-63c1-d7d9-cf9e-ffc9b86f05d0 | 24e1de76-9661-41fd-a966-ce57ae258fe1 | pkg-0a7f8f1524ffb9e56b8cb209 | 1 | 0 | Capture and store /analysis-status endpoint response artifact for the cycle. |
| 16 | completed | partial | continue_prove_remaining | 019d9582-79a1-3eae-3a58-6421b3d023cd | b84123ad-8169-43aa-ae7d-c7791d492be4 | pkg-bcb4c43d8dd83845f1b6dc3a | 1 | 0 | Capture and store /analysis-status endpoint response artifact for the cycle. |
| 17 | not_executed | - | continue | - | - | - | 0 | 0 | Capture and store /analysis-status endpoint response artifact for the cycle. |
| 18 | completed | partial | continue_prove_remaining | 019d958d-2c51-5e21-f010-3fb74a514e3b | 82bc5cc6-c666-400f-84e9-feb7351065cc | pkg-efa6e50f77c3b9690dc3d2a8 | 1 | 0 | Capture and store /analysis-status endpoint response artifact for the cycle. |
| 19 | not_executed | - | continue | - | - | - | 0 | 0 | Capture and store /analysis-status endpoint response artifact for the cycle. |
| 20 | completed | partial | continue_prove_remaining | 019d9595-fd9c-b4b8-7030-6262102a228a | a599344a-ca06-4d4b-85cf-4e1f47cf15d8 | pkg-189ea06455b12e96370c5ebd | 1 | 0 | Capture and store /analysis-status endpoint response artifact for the cycle. |
| 21 | not_executed | - | continue | - | - | - | 0 | 0 | Capture and store /analysis-status endpoint response artifact for the cycle. |
| 22 | not_executed | - | continue | - | - | - | 0 | 0 | Capture and store /analysis-status endpoint response artifact for the cycle. |
| 23 | not_executed | - | continue | - | - | - | 0 | 0 | Capture and store /analysis-status endpoint response artifact for the cycle. |
| 24 | not_executed | - | continue | - | - | - | 0 | 0 | Capture and store /analysis-status endpoint response artifact for the cycle. |
| 25 | completed | partial | continue_prove_remaining | 019d95b8-d449-8788-17de-731d14e99b4f | f6a83207-80e4-4783-b749-ceafe7900a33 | pkg-eff1f08d25da562b87954c2a | 1 | 0 | Capture and store /analysis-status endpoint response artifact for the cycle. |
| 26 | not_executed | - | continue | - | - | - | 0 | 0 | Capture and store /analysis-status endpoint response artifact for the cycle. |
| 27 | not_executed | - | continue | - | - | - | 0 | 0 | Capture and store /analysis-status endpoint response artifact for the cycle. |
| 28 | not_executed | - | continue | - | - | - | 0 | 0 | Capture and store /analysis-status endpoint response artifact for the cycle. |
| 29 | not_executed | - | continue | - | - | - | 0 | 0 | Capture and store /analysis-status endpoint response artifact for the cycle. |
| 30 | not_executed | - | continue | - | - | - | 0 | 0 | Capture and store /analysis-status endpoint response artifact for the cycle. |
