# Admin Pipeline Frontend Ownership Map (bd-bupjb.2)

Date: 2026-04-13  
Feature-Key: `bd-bupjb`

## Surface Ownership

1. Audit Trace pages own pipeline run debugging:
   - run list (`/admin/audits/trace`)
   - run detail (`/admin/audits/trace/[id]`)
   - step-level prompt/response inspection
   - analysis output and citation inspection

2. Substrate Explorer owns substrate ingestion debugging:
   - substrate run list and summary
   - failure buckets
   - raw row filtering and row detail inspection
   - it must not treat substrate/manual run ids as pipeline run UUIDs

3. Pipeline Status panel owns jurisdiction/source-family health:
   - freshness status and policy windows
   - coverage counts and latest analysis readiness
   - operator alerts and refresh action
   - optional link to Audit Trace run only when a real `pipeline_run_id` is present in backend status payload

4. Scrape Manager and Analysis Lab remain separate operational surfaces:
   - Scrape Manager: scrape trigger + scrape task execution tracking
   - Analysis Lab: analysis workflow/operator tooling

## Consolidation Rules Applied

- Removed duplicate run-detail/steps/evidence rendering from `PipelineStatusPanel`.
- Stopped `SubstrateExplorer` from passing selected substrate run id into pipeline run endpoints.
- Kept Pipeline Status focused on jurisdiction/source-family status and refresh controls.
