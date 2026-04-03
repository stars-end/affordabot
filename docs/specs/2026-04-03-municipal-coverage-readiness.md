# Municipal Coverage Readiness

Date: 2026-04-03
Beads: `bd-pd1s`, `bd-flci.1`, `bd-flci.3`, `bd-flci.5`

## Verdict

The municipal substrate wave is operator-ready for repeated bounded `capture_and_ingest` use under current provider families.

This verdict is grounded by:

- Pack A post-fix baseline rerun:
  - `run_id = manual-substrate-20260403T131847Z-5a5c4bc8`
- expanded bounded ingest validation:
  - `run_id = manual-substrate-20260403T134851Z-2f7ea3bf`
  - `resolved_targets = 52`
  - `raw_scrapes_created = 52`
  - `retrievable_rows = 52`
  - promotion summary:
    - `durable_raw = 10`
    - `promoted_substrate = 42`
    - `captured_candidate = 0`
  - storage integrity:
    - overall `pass`
    - object storage `pass`
    - vector integrity `pass`
    - run coverage `pass`

## Proven Coverage Surface

Current proven provider-family surface:

- Legistar-family municipal/county lanes:
  - `meeting_details`, `agendas`, `minutes`, `agenda_packets`, `attachments`
  - plus `staff_reports` where seeded and handler-supported
- AgendaCenter-family municipal lanes:
  - `agendas`, `minutes`, `agenda_packets`, `attachments`, `staff_reports`
- Municode municipal code lane:
  - `san-jose / municipal_code`

## Truthful Unsupported Lanes

The following unmatched lanes from the 52-target run are expected under current handler/source support and are not defects:

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

## Repair Decision For `bd-flci.5`

No code repair was made in this subtask.

Reason:

- the unmatched set maps directly to unsupported lanes in the current handler matrix (`legistar_calendar`, `sunnyvale_agendas`, `agenda_center`, `municode`) and seeded defaults
- adding those lanes now would be speculative coverage inflation, not a non-strategic fix

## Next Honest Frontier

The next frontier is new truthful adapter/family work, not more defaults under current families:

1. municipal code expansion beyond `san-jose` (`municode` is currently single-jurisdiction)
2. explicit decision on whether AgendaCenter-family jurisdictions should have first-class `meeting_details`
3. then broaden jurisdiction count further under newly supported families
