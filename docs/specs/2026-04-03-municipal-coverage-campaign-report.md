# Municipal Coverage Campaign Report

Date: 2026-04-03
Beads: `bd-hfk0`, `bd-pd1s`, `bd-flci.1`
Base implementation for rerun: PR #367 (`5e358a6432a9088ae1dd813cefdf023e1b7544c2`)

## Execution Method

This campaign was executed against branch-local code in a worktree (PR #367 state), not the already-deployed Windmill/backend path.

Known-good execution form:

```bash
~/agent-skills/scripts/dx-load-railway-auth.sh -- \
  ~/agent-skills/scripts/dx-railway-run.sh \
    --project-id 1ed20f8a-aeb7-4de6-a02c-8851fff50d4e \
    --env dev \
    --service backend \
    -- bash -lc 'cd /tmp/agents/bd-flci.1/affordabot/backend && poetry run python - <<\"PY\"
import asyncio, json
from scripts.substrate.manual_expansion_runner import run_manual_substrate_expansion

manifest = {
    "run_label": "bd-flci-1-postfix-broad-pack-a",
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
    "notes": "post-fix rerun replacing pre-fix artifact",
}

print(json.dumps(asyncio.run(run_manual_substrate_expansion(manifest)), indent=2, default=str))
PY'
```

## Manifest

```json
{
  "run_label": "bd-flci-1-postfix-broad-pack-a",
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

## Grounded Artifacts

Pre-fix baseline (from PR #366 run lane):
- `run_id`: `manual-substrate-20260403T041421Z-831ef130`
- `status`: `partial_success`
- resolved targets: `11`
- raw scrapes created: `10`
- storage integrity: object storage `pass`, run coverage `warn`

Post-fix replacement artifact (fresh rerun from PR #367 state):
- `run_id`: `manual-substrate-20260403T131847Z-5a5c4bc8`
- `status`: `partial_success`
- inspection artifact:
  - `backend/scripts/substrate/artifacts/manual-substrate-20260403T131847Z-5a5c4bc8_substrate_inspection_report.json`

- resolved targets: `13`
- raw scrapes created: `13`
- content classes:
  - `html_text = 9`
  - `pdf_binary = 4`
- trust tiers:
  - `official_partner = 13`
- promotion states:
  - `durable_raw = 9`
  - `promoted_substrate = 4`
- storage integrity:
  - object storage `pass`
  - run coverage `pass`

By jurisdiction:

- `san-jose = 4`
- `santa-clara-county = 3`
- `saratoga = 3`
- `sunnyvale = 3`

By asset class:

- `meeting_details = 3`
- `agendas = 4`
- `minutes = 4`
- `municipal_code = 1`
- `agenda_packets = 1`

## Pre-fix vs Post-fix Delta

1. Coverage improved on the repaired branch-local rerun.
   - resolved targets: `11 -> 13`
   - raw scrapes created: `10 -> 13`
2. Trust and target quality are cleaner in the replacement run.
   - trust tiers: mixed (`official_partner` + `primary_government`) -> all `official_partner`
3. Run coverage integrity improved from warn to pass.
   - pre-fix had a target/row gap
   - post-fix shows `attempted_raw_capture_operations = 13` and `stamped_raw_scrapes_count = 13`

## Concrete Raw Examples

Promoted substrate examples:

- Sunnyvale agenda PDF:
  - `https://sunnyvaleca.legistar.com/View.ashx?M=A&amp;ID=1348618&amp;GUID=33794668-0DDD-42E1-8BCC-F606A61E3CF1`
  - `promotion_state = promoted_substrate`
  - `content_class = pdf_binary`
- Saratoga minutes PDF:
  - `https://www.saratoga.ca.us/AgendaCenter/ViewFile/Minutes/_03182026-1422`
  - `promotion_state = promoted_substrate`
  - `content_class = pdf_binary`

Durable raw examples:

- Sunnyvale minutes root fallback:
  - `https://sunnyvaleca.legistar.com/Calendar.aspx`
  - `promotion_state = durable_raw`
  - `content_class = html_text`
- Sunnyvale meeting detail:
  - `https://sunnyvaleca.legistar.com/MeetingDetail.aspx?ID=1348618&amp;GUID=33794668-0DDD-42E1-8BCC-F606A61E3CF1&amp;Options=info|&amp;Search=`
  - `promotion_state = durable_raw`
  - `content_class = html_text`

## What The Run Proved

1. The handler-aware Pack A expansion path is materially better than root-only capture.
   - The run produced real MeetingDetail and View.ashx targets, not only raw calendar/index roots.
2. Storage integrity remained truthful on the broader municipal set.
   - object storage check: `pass`
   - run coverage check: `pass`
3. The municipal/county substrate path is viable enough for repeated bounded manual use.
   - The fresh post-fix replacement artifact reproduces broad capture across four jurisdictions and promotes substantive PDFs without reopening framework questions.

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
- completed successfully from repaired PR #367 branch-local code
- fresh grounded artifact is `manual-substrate-20260403T131847Z-5a5c4bc8`
- this post-fix artifact supersedes the pre-fix artifact for Pack A broad municipal evidence

## Deferred

Deferred to future coverage work, not framework repair:

- expanding Pack A inventory to additional municipal asset classes
- adding richer county/code lanes where source coverage is still sparse
- improving ingest-mode/vector checks for a later capture-and-ingest sweep
