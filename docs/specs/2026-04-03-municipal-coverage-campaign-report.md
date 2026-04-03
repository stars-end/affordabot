# Municipal Coverage Campaign Report

Date: 2026-04-03
Beads: `bd-hfk0`, `bd-pd1s`
Base implementation: PR #366 (`f62131a3932e3a65a25cbc1a3f6caed47e43b006`)

## Execution Method

This campaign was executed against branch-local code in a worktree, not the already-deployed Windmill/backend path.

Known-good execution form:

```bash
~/agent-skills/scripts/dx-load-railway-auth.sh -- \
  ~/agent-skills/scripts/dx-railway-run.sh \
    --project-id 1ed20f8a-aeb7-4de6-a02c-8851fff50d4e \
    --env dev \
    --service backend \
    -- bash -lc 'cd /tmp/agents/bd-hfk0/affordabot/backend && poetry run python - <<\"PY\"
import asyncio, json
from scripts.substrate.manual_expansion_runner import run_manual_substrate_expansion

manifest = {
    "run_label": "bd-hfk0-broad-pack-a",
    "jurisdictions": ["san-jose", "santa-clara-county", "saratoga", "sunnyvale"],
    "asset_classes": [
        "meeting_details",
        "agendas",
        "minutes",
        "municipal_code",
        "agenda_packets",
        "attachments",
        "staff_reports",
    ],
    "max_documents_per_source": 1,
    "run_mode": "capture_only",
    "ocr_mode": "off",
    "sample_size_per_bucket": 2,
    "notes": "broad municipal bounded validation",
}

print(json.dumps(asyncio.run(run_manual_substrate_expansion(manifest)), indent=2, default=str))
PY'
```

## Manifest

```json
{
  "run_label": "bd-hfk0-broad-pack-a",
  "jurisdictions": ["san-jose", "santa-clara-county", "saratoga", "sunnyvale"],
  "asset_classes": [
    "meeting_details",
    "agendas",
    "minutes",
    "municipal_code",
    "agenda_packets",
    "attachments",
    "staff_reports"
  ],
  "max_documents_per_source": 1,
  "run_mode": "capture_only",
  "ocr_mode": "off",
  "sample_size_per_bucket": 2
}
```

## Grounded Run Result

- `run_id`: `manual-substrate-20260403T041421Z-831ef130`
- `status`: `partial_success`
- inspection artifact:
  - `backend/scripts/substrate/artifacts/manual-substrate-20260403T041421Z-831ef130_substrate_inspection_report.json`

Summary:

- resolved targets: `11`
- raw scrapes created: `10`
- content classes:
  - `html_text = 7`
  - `pdf_binary = 3`
- trust tiers:
  - `official_partner = 8`
  - `primary_government = 2`
- promotion states:
  - `durable_raw = 7`
  - `promoted_substrate = 3`

By jurisdiction:

- `san-jose = 4`
- `santa-clara-county = 1`
- `saratoga = 3`
- `sunnyvale = 3`

By asset class:

- `meeting_details = 2`
- `agendas = 3`
- `minutes = 4`
- `municipal_code = 1`
- `agenda_packets = 1`

## Concrete Raw Examples

Promoted substrate examples:

- Saratoga minutes PDF:
  - `https://www.saratoga.ca.us/AgendaCenter/ViewFile/Minutes/_03182026-1422`
  - `promotion_state = promoted_substrate`
  - `content_class = pdf_binary`
- San Jose minutes PDF:
  - `https://sanjose.legistar.com/View.ashx?M=M&amp;ID=1403430&amp;GUID=8E51628F-E53B-44EB-925E-4C4E5D41A8E7`
  - `promotion_state = promoted_substrate`
  - `content_class = pdf_binary`

Durable raw examples:

- Sunnyvale meeting detail:
  - `https://sunnyvaleca.legistar.com/MeetingDetail.aspx?ID=1348618&amp;GUID=33794668-0DDD-42E1-8BCC-F606A61E3CF1&amp;Options=info|&amp;Search=`
  - `promotion_state = durable_raw`
  - `content_class = html_text`
- Sunnyvale minutes root fallback:
  - `https://sunnyvaleca.legistar.com/Calendar.aspx`
  - `promotion_state = durable_raw`
  - `content_class = html_text`

## What The Run Proved

1. The handler-aware Pack A expansion path is materially better than root-only capture.
   - The run produced real MeetingDetail and View.ashx targets, not only raw calendar/index roots.
2. Storage integrity remained truthful on the broader municipal set.
   - object storage check: `pass`
   - run coverage check: `warn` because one attempted target did not stamp a raw row
3. The municipal/county substrate path is viable enough for repeated bounded manual use.
   - It captured across four jurisdictions and promoted substantive PDFs without reopening framework questions.

## Failure Buckets

Expected sparse-coverage buckets:

- many `no_matching_sources` results for unsupported Pack A asset/jurisdiction combinations
- examples:
  - `san-jose / attachments`
  - `santa-clara-county / municipal_code`
  - `saratoga / staff_reports`
  - `sunnyvale / agenda_packets`

Concrete defects found during this campaign:

1. `upsert_source()` accepted dict metadata and passed it directly to asyncpg JSONB bindings on the clean branch.
2. URL-first source upsert semantics collapsed same-root municipal lanes (`Calendar.aspx`) into a single surviving source row.
3. Sunnyvale agenda selection admitted a known 403 page:
   - `https://www.sunnyvale.ca.gov/your-government/governance/city-council/pending-council-agendas`

## Repair Outcome

`bd-pd1s` addresses the concrete defects above by:

- serializing dict/list metadata before source upsert
- making source upsert identity document-type aware so same URL can coexist across distinct municipal asset lanes
- filtering Sunnyvale handler candidates so the known 403 non-Legistar agenda page is not selected as the winning target

Post-fix rerun note:

- a fresh rerun from the repaired `bd-pd1s` worktree was attempted via the same Railway dev command lane
- Railway CLI returned a transient rate-limit response (`You are being ratelimited. Please try again later`)
- because the failure was external to the substrate code, the grounded run above remains the last complete campaign artifact for this pass

## Deferred

Deferred to future coverage work, not framework repair:

- expanding Pack A inventory to additional municipal asset classes
- adding richer county/code lanes where source coverage is still sparse
- improving ingest-mode/vector checks for a later capture-and-ingest sweep
