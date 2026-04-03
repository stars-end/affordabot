# Expanded Municipal Capture-And-Ingest Validation

Date: 2026-04-03
Beads: `bd-flci.5`  
Base implementation context: PR #372 (`3ee7616ab932e8668f1f84d10f85ecfa239d58cc`)

## Grounded Run Facts

Bounded `capture_and_ingest` validation run:

- `run_id`: `manual-substrate-20260403T134851Z-2f7ea3bf`
- `resolved_targets`: `52`
- `raw_scrapes_created`: `52`
- `retrievable_rows`: `52`
- promotion summary:
  - `durable_raw = 10`
  - `promoted_substrate = 42`
  - `captured_candidate = 0`
- storage integrity:
  - overall: `pass`
  - object storage check: `pass`
  - vector integrity check: `pass`
  - run coverage check: `pass`

## Remaining Unmatched Lanes Review

The unmatched lanes from this run are:

- `santa-clara-county / municipal_code`
- `saratoga / meeting_details`
- `saratoga / municipal_code`
- `sunnyvale / staff_reports`
- `sunnyvale / municipal_code`
- `cupertino / municipal_code`
- `mountain-view / municipal_code`
- `san-mateo-county / municipal_code`
- `san-francisco-city-county / municipal_code`
- `campbell / meeting_details`
- `campbell / municipal_code`

Assessment against current provider-family support in `manual_expansion_runner.py`:

- expected unsupported under current handlers:
  - all `municipal_code` lanes above, except `san-jose`, because only `municode` is defined for code and seeded for `san-jose`
  - `saratoga / meeting_details` because `agenda_center` currently supports `agenda`, `minutes`, `agenda_packet`, `attachment`, `staff_report` (not `meeting_detail`)
  - `sunnyvale / staff_reports` because `sunnyvale_agendas` currently supports `meeting_detail`, `agenda`, `minutes`, `agenda_packet`, `attachment` (not `staff_report`)
  - `campbell / meeting_details` because `campbell` is in the `agenda_center` family and inherits the same no-`meeting_detail` support

Conclusion: these are truthful unsupported lanes, not implementation defects.

## Defect Check Outcome

No narrow non-strategic defect was identified in this pass.

Reason:

- the unmatched set aligns with the explicit handler capability matrix and seeded source defaults in PR #372
- adding these lanes now would require either speculative source defaults or new provider behavior, both out of scope for this subtask

## Supported And Proven Lanes (Current Wave)

Supported and exercised lanes now include:

- Legistar family jurisdictions (`san-jose`, `santa-clara-county`, `sunnyvale`, `cupertino`, `mountain-view`, `san-mateo-county`, `san-francisco-city-county`) across:
  - `meeting_details`, `agendas`, `minutes`, `agenda_packets`, `attachments`
  - plus `staff_reports` where the handler family supports it
- AgendaCenter family jurisdictions (`saratoga`, `campbell`) across:
  - `agendas`, `minutes`, `agenda_packets`, `attachments`, `staff_reports`
- Municode lane:
  - `san-jose / municipal_code`

## Honest Next Frontier

The next frontier is adapter/provider-family expansion, not more default-row inflation.

Priority:

1. add new truthful municipal code adapters/families for non-`san-jose` jurisdictions
2. decide whether `meeting_details` should exist for AgendaCenter-family jurisdictions as a real model, not a forced mapping
3. only then widen jurisdiction count further
