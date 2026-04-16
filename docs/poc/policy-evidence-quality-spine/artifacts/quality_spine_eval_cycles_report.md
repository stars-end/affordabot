# Policy Evidence Quality Spine Eval Cycles

- feature_key: `bd-3wefe.13`
- final_verdict: `partial`
- max_cycles: `10`

## Gate status

| Gate | Status | Details |
| --- | --- | --- |
| scraped_quality | pass | scraped/search=pass, reader=pass |
| structured_quality | not_proven | scorecard indicates structured pass, but live cycle lacks structured source-family evidence |
| unified_package | not_proven | scraped=pass, structured=not_proven, postgres=pass, minio=pass, pgvector=pass |
| postgres | pass | package_row_linked_to_backend_run_id |
| minio | pass | all_artifact_refs_read_back |
| pgvector | pass | document_chunks_and_embeddings_present_with_derived_index_truth_role |
| windmill | pass | live windmill flow run succeeded with concrete windmill_job_id |
| llm_narrative | not_proven | LLM narrative not proven (canonical_llm_run_id_missing; source=quality_spine_deterministic_lane). |
| economic_analysis | not_proven | analysis_status_endpoint=secondary_research_needed |
| admin_read_model | pass | analysis-status endpoint response captured |

## Cycle 1 assessment

- artifact: `docs/poc/policy-evidence-quality-spine/artifacts/live_cycle_01_windmill_domain_run.json`
- status: `partial`
- reason: Cycle 1 is partial: selected evidence was economically insufficient, structured lane is not proven in this run, and admin/economic endpoint proof is missing.

## Recommended tweaks

- Run a structured-source family in live cycle and verify provenance/storage joins.
- Ensure scraped+structured+storage gates pass in the same run with one package_id.
- Persist canonical LLM analysis run+step ids and bind to package_id.
- Improve quantitative evidence to pass economic analysis status endpoint.

## Cycle ledger

| Cycle | Status | Deploy SHA | Windmill Job | Backend Run | Package | Package Artifact | Selected URL | Reader Artifact | Provider | Mechanism | Impact Mode | Secondary Research | Quality Conclusion | Verdict | Next tweak |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | completed | 1f46d33f0ab5c03f90223dfd5d39a74eb6034eee | 019d94d2-81ef-1117-0353-4c40719876ed | 6695fe26-eaaf-47d1-9100-7eb861a7aa2f | pkg-sj-parking-minimum-amendment | - | https://sanjose.legistar.com/View.ashx?M=A&ID=1345653&GUID=CF0F61B5-1467-4299-B504-21A4ADD6FCFF | artifacts/2026-04-13.windmill-domain.v1/San Jose CA/meeting_minutes/reader_output/ae11ddffb6292d654ab990cddc9f169ce23868654ee623d07261ec553c81ed77.md | - | - | - | - | partial | partial | Run a structured-source family in live cycle and verify provenance/storage joins. |
| 2 | completed | 1f46d33f0ab5c03f90223dfd5d39a74eb6034eee | 019d94d7-1f8a-2755-6d12-4b8c20565081 | 2a6944e1-4c18-4265-b22e-4faa16d7c08b | pkg-sj-parking-minimum-amendment | - | https://sanjose.legistar.com/View.ashx?GUID=DEBFA654-8B86-447A-997C-5ED36892BE3C&ID=7810086&M=F | artifacts/2026-04-13.windmill-domain.v1/San Jose CA/meeting_minutes/reader_output/92e7e2d4aa29bfe9d552a09849d7d836cf167b0377a5f409c90519b299e7e76f.md | - | - | - | - | partial | partial | Run a structured-source family in live cycle and verify provenance/storage joins. |
| 3 | completed | 1f46d33f0ab5c03f90223dfd5d39a74eb6034eee | 019d94da-1547-48ec-9185-11b91651f5be | 498aff1e-3af9-4a28-9895-5058ffc92e21 | pkg-sj-parking-minimum-amendment | - | https://sanjose.legistar.com/View.ashx?M=F&ID=7810086&GUID=DEBFA654-8B86-447A-997C-5ED36892BE3C | artifacts/2026-04-13.windmill-domain.v1/San Jose CA/meeting_minutes/reader_output/ebadafaceba9d9d13d15d661559000beba0056f129d8e79e233c8c0f5f0ddca4.md | - | - | - | - | partial | partial | Run a structured-source family in live cycle and verify provenance/storage joins. |
| 4 | completed | 1f46d33f0ab5c03f90223dfd5d39a74eb6034eee | 019d94ec-e80e-0daf-3bb2-fdee2c6dce6a | f208078b-64af-4ef6-89b5-caaf5b0b8322 | pkg-ba380f24f5478f2590380e46 | minio://affordabot-artifacts/policy-evidence/packages/pkg-ba380f24f5478f2590380e46.json | https://sanjose.legistar.com/View.ashx?GUID=DEBFA654-8B86-447A-997C-5ED36892BE3C&ID=7810086&M=F | minio://affordabot-artifacts/artifacts/2026-04-13.windmill-domain.v1/San Jose CA/meeting_minutes/reader_output/92e7e2d4aa29bfe9d552a09849d7d836cf167b0377a5f409c90519b299e7e76f.md | - | fee_or_tax_pass_through | pass_through_incidence | True | secondary_research_needed | partial | Run a structured-source family in live cycle and verify provenance/storage joins. |
| 5 | completed | 1f46d33f0ab5c03f90223dfd5d39a74eb6034eee | 019d94f5-27d3-0de0-4f82-4d554d74234e | d611af15-4464-4eae-9e86-04b5dd438d27 | pkg-d90d67f6703d5e3d18593814 | minio://affordabot-artifacts/policy-evidence/packages/pkg-d90d67f6703d5e3d18593814.json | https://sanjose.legistar.com/View.ashx?M=F&ID=8758120&GUID=6C299331-91E9-48ED-B7A5-43601D63FBF6 | minio://affordabot-artifacts/artifacts/2026-04-13.windmill-domain.v1/San Jose CA/meeting_minutes/reader_output/71524d4b161bbf71c6145f0549351b0c4a9603630c5e8e7794fb77c552468dd3.md | - | fee_or_tax_pass_through | pass_through_incidence | True | secondary_research_needed | partial | Run a structured-source family in live cycle and verify provenance/storage joins. |
| 6 | completed | 1f46d33f0ab5c03f90223dfd5d39a74eb6034eee | 019d94f9-c6fa-9aab-f6e7-eca32b5b951f | f917d334-9dbc-4628-a6de-13a298c46692 | pkg-6f4ae5c23acc5ad4a09b686c | minio://affordabot-artifacts/policy-evidence/packages/pkg-6f4ae5c23acc5ad4a09b686c.json | https://www.huduser.gov/periodicals/cityscpe/vol8num1/ch4.pdf | minio://affordabot-artifacts/artifacts/2026-04-13.windmill-domain.v1/San Jose CA/economic_literature/reader_output/4dbf81f3a67ad8e4c8782b5ba6c2291992c16c2e0e480d1a78adaa441db8bd80.md | - | fee_or_tax_pass_through | pass_through_incidence | True | secondary_research_needed | partial | Run a structured-source family in live cycle and verify provenance/storage joins. |
| 7 | completed | 1f46d33f0ab5c03f90223dfd5d39a74eb6034eee | 019d94fb-dfaa-7681-7d6b-c1fb39f6ab49 | e1826ad9-cda9-4737-9c1d-316852460029 | pkg-10adcd7b63e6262425240b5b | minio://affordabot-artifacts/policy-evidence/packages/pkg-10adcd7b63e6262425240b5b.json | https://www.huduser.gov/periodicals/cityscpe/vol8num1/ch4.pdf | minio://affordabot-artifacts/artifacts/2026-04-13.windmill-domain.v1/San Jose CA/economic_literature/reader_output/4dbf81f3a67ad8e4c8782b5ba6c2291992c16c2e0e480d1a78adaa441db8bd80.md | - | fee_or_tax_pass_through | pass_through_incidence | True | secondary_research_needed | partial | Run a structured-source family in live cycle and verify provenance/storage joins. |
| 8 | not_executed | - | - | - | - | - | - | - | - | - | - | - | - | - | Run a structured-source family in live cycle and verify provenance/storage joins. |
| 9 | not_executed | - | - | - | - | - | - | - | - | - | - | - | - | - | Run a structured-source family in live cycle and verify provenance/storage joins. |
| 10 | not_executed | - | - | - | - | - | - | - | - | - | - | - | - | - | Run a structured-source family in live cycle and verify provenance/storage joins. |
