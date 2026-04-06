# 2026-04-06 Custom Archive Live Validation (bd-t4pz0.1)

## Objective

Run a bounded live validation for the new `custom_archive_document_center` family on affordabot/dev and confirm whether we can reach truthful live `agendas + minutes` for the targeted jurisdictions.

## Locked Scope

- Runtime target: Railway project `1ed20f8a-aeb7-4de6-a02c-8851fff50d4e`, environment `dev`, service `backend`
- Jurisdictions: `milpitas`, `alameda-county`
- Asset classes: `agendas`, `minutes`
- Run mode: `capture_and_ingest`
- OCR mode: `hard_doc_only`
- Max documents/source: `5`
- Sample size/bucket: `3`

## Corrected Runtime Target

The validated affordabot runtime target for this wave is:

- Project: `1ed20f8a-aeb7-4de6-a02c-8851fff50d4e` (`affordabot`)
- Environment: `dev`
- Service: `backend`
- In-container app root: `/app`
- Interpreter for this lane: `poetry run python`

## Chronological Blocker Burn-Down

1. **Wrong project context from worktree dx context**
   - The captured worktree context pointed to project `f0875753-5125-42d4-93c5-a04818e13dc6` (prime-radiant-ai), not affordabot.

2. **Stale prime-radiant-ai runtime mismatch**
   - Running substrate commands there failed because the container image did not match affordabot substrate code paths for this wave.

3. **Correct affordabot runtime established**
   - Switched to explicit Railway target: `1ed20f8a-aeb7-4de6-a02c-8851fff50d4e / dev / backend`.
   - Verified runtime root `/app` and successful dependency import with `poetry run python`.

4. **Missing jurisdictions in affordabot/dev DB**
   - Live DB check showed no jurisdiction rows for Milpitas/Alameda County.

5. **Targeted jurisdiction/source bootstrap**
   - Inserted or created the two jurisdictions and two source rows directly in-runtime for this wave.

6. **Rerun result reached**
   - Bounded rerun produced run id: `manual-substrate-20260406T175113Z-f63a06ca`.

## Exact Bootstrap Outcomes

- Milpitas jurisdiction inserted/ensured:
  - `2386deb1-d3b7-456c-bba9-cf23f15bcc36`
- Milpitas source inserted:
  - URL: `https://www.milpitas.gov/archive.aspx`
  - Source id: `66e5986d-349c-4f67-b576-97dfbfee8114`

- Alameda County jurisdiction inserted/ensured:
  - `6822c6cf-3d88-4653-b415-240dece49eb3`
- Alameda County source inserted:
  - URL: `https://apps.acgov.org/agenda_minutes_app/board/bos_calendar/ag_min.jsp`
  - Source id: `378094fa-7978-4293-9fa2-81538aa2c05d`

## Truthful Rerun Result Summary

Run:
- `run_id`: `manual-substrate-20260406T175113Z-f63a06ca`
- `run_label`: `custom-archive-live-validation-2026-04-06`
- `status`: `failed`

Operational summary:
- `resolved_targets.count`: `0`
- `capture_summary.raw_scrapes_created`: `0`
- `ingestion_summary.by_stage`: empty
- `promotion_summary.promoted_substrate`: `0`
- `inspection_report.available`: `true`
- `inspection_report.artifact_path`: `/app/scripts/substrate/artifacts/manual-substrate-20260406T175113Z-f63a06ca_substrate_inspection_report.json`

Failure summary:
- Milpitas
  - `agendas`: `no_matching_sources`
  - `minutes`: `no_matching_sources`
- Alameda County
  - `agendas`: `custom_archive_discovery_failed` + `no_matching_sources`
  - `minutes`: `custom_archive_discovery_failed` + `no_matching_sources`
  - Discovery failure detail: DNS resolution errors for official root URLs.

## Alameda Narrow Salvage Lane

Runtime fetch/discovery probes were executed for:

- `https://apps.acgov.org/agenda_minutes_app/board/bos_calendar/ag_min.jsp`
- `https://aspawebq.acgov.org/board/`
- `https://aspawebq.acgov.org/board/bos_calendar/ag_min.jsp`

Results:
- All three were non-fetchable from affordabot runtime (`<urlopen error [Errno -2] Name or service not known>`).
- Discovery candidate counts: `0` for all three URLs.
- No Alameda-only rerun was possible from this salvage lane because no official candidate root was reachable/discoverable from runtime.

## Verdict By Jurisdiction

- **Milpitas**
  - Source row is present in dev.
  - Current run still resolves zero discovered targets for `agendas/minutes` and reports `no_matching_sources`.

- **Alameda County**
  - Official known roots are unreachable from affordabot runtime DNS in this environment, including:
    - `apps.acgov.org` path
    - `aspawebq.acgov.org/board` variants
  - Result: discovery cannot proceed, therefore no live targets are resolved.

## Success Bar Result

The success bar for this wave was **NOT met**.

We did not reach truthful live `agendas + minutes` coverage for at least one targeted jurisdiction in affordabot/dev.

## Family Reusability Verdict

Nuanced verdict:
- **Code shape**: still looks reusable (`custom_archive_document_center` family abstraction remains coherent).
- **Live proof on affordabot/dev**: not yet proven for this wave due to:
  - zero discovered targets for Milpitas path in this run, and
  - Alameda official-root reachability failure from runtime DNS.

## Recommended Next Decisions (Tech Lead)

1. Authorize scoped expansion into a Milpitas-adjacent calendar/document-center family if desired.
2. Treat Alameda runtime DNS reachability for `apps.acgov.org`/`aspawebq.acgov.org` as an infra prerequisite before further live validation on Alameda.
3. Close this wave as not live-proven and roll findings into the next planning cycle.

