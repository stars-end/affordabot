# Manual Audit: Cycle 31 Data Moat

Feature-Key: `bd-3wefe.13`

Artifacts:
- `artifacts/live_cycle_31_windmill_domain_run.json`
- `artifacts/live_cycle_31_admin_analysis_status.json`
- `artifacts/live_cycle_31_policy_package_payload.json`

Runtime identity:
- Package: `pkg-611a55f6345123b02ef292c9`
- Backend run: `9941ff86-41ab-4005-9f36-f5b0a2c35d25`
- Windmill run: `bd-3wefe.13-live-cycle-31-20260417025026`
- Windmill scope job: `run_scope_pipeline:0:run_scope_pipeline`

## Verdict

`FAIL_DATA_MOAT__RUNTIME_READY`

Cycle 31 proves the deployed runtime can create, persist, read, and analyze a package, but it does not prove a defensible Affordabot data moat. The package is useful evidence for the next implementation wave because it exposes concrete failure modes:

- Scraped/search gate failed because the selected source was the official San Jose Commercial Linkage Fee page, not a concrete artifact.
- True structured economic rows remain unproven: `true_structured_row_count=0`.
- Attachment lineage improved materially, but attachment contents are not yet ingested or normalized.
- Economic parameters are present from the official CLF page, but they are not yet robust enough to claim artifact-grade, structured-corroborated moat data.

## What Passed

- Storage/read-back: pass via Postgres package row, MinIO package/read artifact refs, pgvector document ref, and `artifact_readback_status=proven`.
- Windmill/orchestration: pass with current run id and backend scope job bound to package state.
- LLM narrative binding: pass in the admin read model with canonical run and step ids.
- Private SearXNG runtime provenance: pass; runtime client was `OssSearxngWebSearchClient`, endpoint host `searxng-private.railway.internal:8080`.
- Reader substance: observed true on the selected CLF page.
- Attachment lineage: improved. The package now includes related Legistar attachment refs, including ordinance and resolution attachments.

## What Failed

- Selected URL: `https://www.sanjoseca.gov/your-government/departments-offices/housing/developers/commercial-linkage-fee`.
- Selected artifact family: `official_page`.
- Source quality status: `fail`.
- Source quality reason: `artifact_candidates_present_but_non_artifact_selected`.
- Data moat status: `fail`.
- Policy lineage score: `0.75`; authoritative policy text is still negative evidence.
- Normalized official economic rows: 9 in `package_payload.run_context`.
- True structured economic rows: 0.
- Missing true structured corroboration count: 2.
- Secondary search-derived row count: 1; correctly not authoritative.

## Manual Data Assessment

The data is relevant and official, but it is not yet moat-grade. The selected CLF page is a useful official source and includes current fee schedule values, but it is not a durable legislative artifact such as the resolution, ordinance, nexus study, staff memo, or fee schedule attachment. This means the package can answer some direct fee questions, but it is too brittle as a source-of-truth substrate.

The attachment refs are valuable because they identify the next high-leverage source set. However, refs alone are metadata; the moat requires fetching, reading, classifying, and normalizing the attachment contents. Until that happens, the structured lane is still mostly identity/provenance support rather than economic substance.

The current normalized-row implementation also needs correction. The row projection preserves nine rows, but reconciliation currently groups too coarsely and collapses the primary official evidence to two source-of-truth row keys. That weakens the audit trail and can hide table complexity.

## Required Next Wave

1. Prefer concrete official artifacts over official landing pages when artifact candidates exist, unless a page is explicitly classified as a maintained fee schedule and passes a separate fee-schedule gate.
2. Fetch/read Legistar related attachments, at minimum ordinance, resolution, memorandum, and likely fee/nexus-study families.
3. Normalize attachment-derived fee rows into true structured or official-attachment economic rows with source URL, attachment id, locator, raw value, normalized value, unit, land use, threshold, and date/status context.
4. Fix reconciliation row keys so repeated fee rows do not collapse across values, thresholds, payment timing, or source locator.
5. Keep Tavily/Exa secondary evidence non-authoritative unless corroborated by official primary/structured rows.

