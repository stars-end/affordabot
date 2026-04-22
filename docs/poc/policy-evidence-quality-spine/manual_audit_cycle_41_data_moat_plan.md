# Manual Audit Plan: Cycle 41 Broad Local-Policy Moat

Feature key: `bd-3wefe.13`
Scope: prove Affordabot can capture and persist useful San Jose local-policy evidence for a non-CLF policy family without forcing economic-analysis readiness.

## Goal

Validate that a live-gate run can produce a policy evidence package with:

1. non-CLF `source_family` and scenario/query configuration,
2. selected/read official artifact identity,
3. package identity and provenance links,
4. storage/admin references when the live runtime can expose them,
5. explicit classification as useful local policy evidence, even if `economic_handoff_ready=false`.

## Recommended Scenario

- `--policy-scenario parking_policy`
- Allowed alternates:
  - `housing_permits`
  - `business_compliance`
  - `meeting_actions`

## Run Checklist

1. Execute harness with the selected non-CLF scenario.
2. Confirm `policy_evidence_capture.requested_policy_scope` records:
   - `scenario`
   - `jurisdiction`
   - `source_family`
   - `search_query`
   - `analysis_question`
3. Confirm `policy_evidence_capture.selected_read_artifact` records:
   - selected artifact URL/title
   - `reader_output_ref` and `raw_scrape_ids` when present.
4. Confirm `policy_evidence_capture.package_identity` records:
   - `package_id`, or explicit absence if package was not produced,
   - storage/admin refs from DB probe (`content_artifact_ids`, `pipeline_command_ids`) when available.
5. Confirm semantics classification:
   - `observed_useful_local_policy_evidence=true` for successful broad moat capture,
   - `classification=useful_local_policy_evidence_not_economic_ready` when package evidence is useful but economic handoff remains blocked.

## Pass/Fail Rules

- PASS (broad moat evidence capture):
  - selected artifact and provenance are present,
  - package/storage/admin references are present or explicitly unavailable due to runtime probe limits,
  - semantics classification is one of:
    - `useful_local_policy_evidence_not_economic_ready`
    - `useful_local_policy_evidence`
    - `economic_handoff_ready`
- FAIL:
  - scenario/source family not captured,
  - selected artifact cannot be identified,
  - no provenance/storage references and no explicit runtime limitation recorded,
  - semantics remains `not_proven`.

## Audit Notes Template

- Scenario:
- Source family:
- Selected artifact URL:
- Reader output ref:
- Package ID:
- Storage refs:
- Semantics classification:
- Observed economic handoff ready:
- Manual verdict: `PASS_BROAD_LOCAL_POLICY_MOAT` or `FAIL_BROAD_LOCAL_POLICY_MOAT`
