# Manual Audit: Cycle 33 Data Moat

Feature-Key: `bd-3wefe.13`

Artifacts:
- `artifacts/live_cycle_33_windmill_domain_run.json`
- `artifacts/live_cycle_33_admin_analysis_status.json`

Runtime identity:
- Package: `pkg-0a81eb50e4dfd03031500460`
- Backend run: `eed667bb-a067-49be-8709-644f509653de`
- Windmill run: `bd-3wefe.13-live-cycle-33-20260417034400`
- Windmill job: `019d998a-828c-2565-8c34-54f084a2d8fa`

## Verdict

`FAIL_DATA_MOAT__IDENTITY_REPAIRED_BUT_ARTIFACT_AND_STRUCTURED_DEPTH_MISSING`

Cycle 33 fixed the Cycle 32 false-positive class. The pipeline no longer selected the wrong-jurisdiction Los Altos HCD PDF. It selected a San Jose official source and the admin read model now exposes source-quality failure instead of passing artifact shape blindly.

This is not a data-moat pass. It is a measured improvement from a misleading wrong-jurisdiction package to a relevant but still shallow official-source package.

## What Improved

- Selected URL changed from a Los Altos HCD artifact to a San Jose official page: `https://www.sanjoseca.gov/Home/Components/News/News/1683/4765`.
- `identity_ready=true`, `policy_identity_ready=true`, and `jurisdiction_identity_ready=true`.
- `scraped/search` now fails instead of passing when the selected source does not meet artifact-quality threshold.
- `source_quality.selection_quality_status=fail`.
- Runtime/storage/Windmill/LLM binding are all live-proven from the admin read model:
  - storage/read-back: `pass`
  - Windmill/orchestration: `pass`
  - LLM narrative: `pass`
- The wrong-jurisdiction `$7.00` Los Altos parameter is gone from the economic parameter table.

## What Still Failed

- Selected artifact family: `official_page`.
- Source quality reason: `no_artifact_candidate_passed_quality_gate`.
- Scraped/search gate: `fail`.
- Data moat status: `fail`.
- True structured economic rows: `0`.
- Structured source coverage is still shallow:
  - Legistar Web API source is present for Matter 7526, but contributes metadata, not economic rows.
  - Tavily secondary search contributes the only fee parameter and remains search-derived, not structured-source proof.
- Economic handoff remains `not_analysis_ready`.
- Final recommended next action: `ingest_official_attachments`.

## Manual Data Assessment

The Cycle 33 package is credible but not moat-grade. It is now pointed at the correct jurisdiction and policy family, which is a necessary repair. But the package still relies on a San Jose official page plus a Tavily-derived fee snippet for the one resolved parameter. That is useful as an interim source, but it is not the durable data substrate the product needs.

The moat requires official artifacts and true structured rows. The next useful move is not more ranking-only work. It is attachment ingestion: fetch/read the Matter 7526 ordinance, resolution, memorandum, nexus/feasibility study, or fee schedule attachments; normalize their fee rows; and reconcile those rows against the maintained San Jose CLF page.

## Required Next Wave

1. Ingest official Legistar attachment content for Matter 7526, not only attachment refs or Matter metadata.
2. Promote attachment-derived official fee rows into authoritative structured/official-attachment rows.
3. Preserve row-level provenance: attachment id, URL, title, source family, locator, raw value, normalized value, unit, land use, threshold, payment timing, effective/adoption/final status.
4. Require at least one true structured or official-attachment economic row before `structured_depth_ready=true`.
5. Keep Tavily/Exa rows secondary-search-derived and non-authoritative unless corroborated by official attachment/source rows.
