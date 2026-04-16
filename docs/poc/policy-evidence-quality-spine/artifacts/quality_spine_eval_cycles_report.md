# Policy Evidence Quality Spine Eval Cycles

- feature_key: `bd-3wefe.13`
- final_verdict: `partial`
- max_cycles: `10`

## Gate status

| Gate | Status | Details |
| --- | --- | --- |
| scraped_quality | pass | scraped/search=pass, reader=pass |
| structured_quality | not_proven | scorecard indicates structured pass, but live cycle lacks structured source-family evidence |
| unified_package | not_proven | scraped=pass, structured=not_proven, postgres=not_proven, minio=not_proven, pgvector=not_proven |
| postgres | not_proven | offline_mode_no_live_postgres_probe |
| minio | not_proven | offline_mode_no_live_minio_probe |
| pgvector | not_proven | offline_mode_no_live_document_chunks_probe |
| windmill | pass | live windmill flow run succeeded with concrete windmill_job_id |
| llm_narrative | not_proven | LLM narrative not proven (canonical_llm_run_id_missing; source=quality_spine_deterministic_lane). |
| economic_analysis | pass | sufficiency=pass, economic_reasoning=pass |
| admin_read_model | not_proven | economic analysis status endpoint artifact missing |

## Cycle 1 assessment

- artifact: `docs/poc/policy-evidence-quality-spine/artifacts/live_cycle_01_windmill_domain_run.json`
- status: `partial`
- reason: Cycle 1 is partial: selected evidence was economically insufficient, structured lane is not proven in this run, and admin/economic endpoint proof is missing.

## Recommended tweaks

- Run a structured-source family in live cycle and verify provenance/storage joins.
- Ensure scraped+structured+storage gates pass in the same run with one package_id.
- Persist and verify policy_evidence_packages row linked to exact backend_run_id.
- Repair MinIO object readback for current run artifact_refs.
- Verify document_chunks + embeddings tied to the same document_id from run refs.
- Persist canonical LLM analysis run+step ids and bind to package_id.
- Capture and store /analysis-status endpoint response artifact for the cycle.

## Cycle ledger

| Cycle | Status | Deploy SHA | Windmill Job | Backend Run | Package | Selected URL | Artifact URI | Verdict | Next tweak |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | completed | 735022f74ebddc0064717b59921a99bd9950f893 | 019d94d2-81ef-1117-0353-4c40719876ed | 6695fe26-eaaf-47d1-9100-7eb861a7aa2f | pkg-sj-parking-minimum-amendment | https://sanjose.legistar.com/View.ashx?M=A&ID=1345653&GUID=CF0F61B5-1467-4299-B504-21A4ADD6FCFF | artifacts/2026-04-13.windmill-domain.v1/San Jose CA/meeting_minutes/reader_output/ae11ddffb6292d654ab990cddc9f169ce23868654ee623d07261ec553c81ed77.md | partial | Run a structured-source family in live cycle and verify provenance/storage joins. |
| 2 | not_executed | - | - | - | - | - | - | - | Run a structured-source family in live cycle and verify provenance/storage joins. |
| 3 | not_executed | - | - | - | - | - | - | - | Run a structured-source family in live cycle and verify provenance/storage joins. |
| 4 | not_executed | - | - | - | - | - | - | - | Run a structured-source family in live cycle and verify provenance/storage joins. |
| 5 | not_executed | - | - | - | - | - | - | - | Run a structured-source family in live cycle and verify provenance/storage joins. |
| 6 | not_executed | - | - | - | - | - | - | - | Run a structured-source family in live cycle and verify provenance/storage joins. |
| 7 | not_executed | - | - | - | - | - | - | - | Run a structured-source family in live cycle and verify provenance/storage joins. |
| 8 | not_executed | - | - | - | - | - | - | - | Run a structured-source family in live cycle and verify provenance/storage joins. |
| 9 | not_executed | - | - | - | - | - | - | - | Run a structured-source family in live cycle and verify provenance/storage joins. |
| 10 | not_executed | - | - | - | - | - | - | - | Run a structured-source family in live cycle and verify provenance/storage joins. |
