# Broad Substrate Expansion Operationalization Plan

## Summary
- Operationalize the locked substrate framework across all active Affordabot ingestion entry points, add a dedicated manual Windmill expansion flow, add a post-run inspection surface, and use that stack to execute one bounded broad multi-jurisdiction manual run that is reviewed directly for moat quality.

## Problem
- The substrate framework is locked, but the system still mixes framework-complete paths with older raw-ingest paths.
- Affordabot's Windmill setup is currently a thin wrapper around fixed `/cron/*` endpoints and cannot run a parameterized broad substrate expansion job.
- There is no first-class post-run report that makes a broad manual run easy to inspect for raw-data usefulness, deny-path correctness, and promotion correctness.
- A broad multi-jurisdiction test is only meaningful after all involved ingest paths create substrate-consistent rows.

## Goals
- Migrate scheduled ingestion entry points onto the same framework-complete raw-capture contract.
- Add a dedicated unscheduled Windmill manual flow for broad substrate expansion.
- Add a post-run inspection report that makes manual review fast and truthful.
- Run one bounded broad multi-jurisdiction, multi-asset manual test after the migration is complete.

## Non-Goals
- Broad always-on rollout across many jurisdictions.
- Making `glm-ocr` the default PDF extractor.
- Reworking the full scheduled Windmill fleet before the manual path is proven.
- Introducing `glm-5v-turbo` anywhere in this lane.

## Active Contract
- Every new `raw_scrapes` row created by scheduled or manual substrate ingestion must carry framework-complete metadata at capture time:
  - `canonical_url`
  - `document_type`
  - `content_class`
  - `trust_tier`
  - `trust_host_classification`
  - `promotion_state`
  - `promotion_method`
  - `promotion_reason_category`
  - `promotion_policy_version`
  - `ingestion_truth`
- Scheduled jobs remain auth-gated and additive. They should be migrated onto the framework contract, not replaced with a dual path.
- Broad manual expansion runs must go through a dedicated unscheduled Windmill flow, not through overloaded fixed daily cron jobs.
- `markitdown` remains the default PDF path.
- `glm-ocr` remains a selective hard-doc fallback only, with:
  - non-coding `layout_parsing` endpoint
  - `ocr_mode = hard_doc_only`
- A broad manual run is valid only if the run is bounded, reproducible, and accompanied by a structured inspection report.

## Architecture / Design

### 1. Ingestion Convergence Target
- Reuse the substrate-aware metadata helpers already established in the framework lane rather than inventing new per-job shapes.
- The convergence target is the same capture-time substrate contract already used by the manual capture and promotion helpers.
- The following entry points must be brought onto that contract before the broad run:
  - `backend/scripts/cron/run_daily_scrape.py`
  - `backend/scripts/cron/run_rag_spiders.py`
  - `backend/scripts/cron/run_universal_harvester.py`

### 2. Windmill Manual Expansion Flow
- Add a new unscheduled flow under:
  - `ops/windmill/f/affordabot/manual_substrate_expansion.flow/flow.yaml`
- This should follow the Prime precedent from `manual_backfill_eod`: manual UI trigger, explicit input schema, no schedule file.
- The flow should call a dedicated backend endpoint via the shared-instance HTTP model, with the same auth/header pattern already used by Affordabot Windmill jobs.

### 3. Backend Manual Run Endpoint
- Add a dedicated auth-gated endpoint:
  - `POST /cron/manual-substrate-expansion`
- This endpoint is separate from the existing fixed `/cron/discovery`, `/cron/daily-scrape`, `/cron/rag-spiders`, and `/cron/universal-harvester` routes.
- It must accept a structured JSON body and return a structured run result instead of only a shell-script tail.

### 4. Exact Manual-Run Request Contract

```json
{
  "run_label": "broad-substrate-2026-04-02",
  "jurisdictions": ["san-jose", "sunnyvale", "santa-clara"],
  "asset_classes": [
    "meeting_details",
    "agendas",
    "minutes",
    "agenda_packets",
    "attachments",
    "staff_reports",
    "municipal_code",
    "legislation"
  ],
  "max_documents_per_source": 20,
  "run_mode": "capture_and_ingest",
  "ocr_mode": "hard_doc_only",
  "sample_size_per_bucket": 5,
  "notes": "Broad manual framework validation run"
}
```

Rules:
- `run_label`: required string, unique-enough operator label.
- `jurisdictions`: required non-empty list.
- `asset_classes`: required non-empty list from:
  - `meeting_details`
  - `agendas`
  - `minutes`
  - `agenda_packets`
  - `attachments`
  - `staff_reports`
  - `municipal_code`
  - `legislation`
- `max_documents_per_source`: required integer, bounded to `1..100`.
- `run_mode`: enum:
  - `capture_only`
  - `capture_and_ingest`
- `ocr_mode`: enum:
  - `off`
  - `hard_doc_only`
- `sample_size_per_bucket`: integer, bounded to `1..10`.
- `notes`: optional string.

Failure behavior:
- Unsupported jurisdiction or asset-class combinations must fail loudly in the endpoint response.
- The endpoint must return validation errors before any capture starts if the request is malformed.
- Partial success is allowed only if the response includes per-target failures.

### 5. Windmill Manual Flow Contract
- Flow summary:
  - `Manual Substrate Expansion`
- No schedule file.
- Concurrency:
  - `limit: 1`
  - key scoped to `affordabot-substrate`
- Shared-instance headers:
  - `Authorization: Bearer $CRON_SECRET`
  - `X-PR-CRON-SECRET: $CRON_SECRET`
  - `X-PR-CRON-SOURCE: windmill:f/affordabot/manual_substrate_expansion`
- Flow inputs must mirror the request contract fields above.
- The Windmill layer should remain a transport/orchestration layer, not a data-processing layer.

### 6. Exact Manual-Run Response Contract

```json
{
  "status": "succeeded",
  "run_id": "substrate-manual-20260402T221500Z",
  "run_label": "broad-substrate-2026-04-02",
  "requested": {
    "jurisdictions": ["san-jose", "sunnyvale", "santa-clara"],
    "asset_classes": ["agendas", "minutes", "municipal_code"],
    "max_documents_per_source": 20,
    "run_mode": "capture_and_ingest",
    "ocr_mode": "hard_doc_only",
    "sample_size_per_bucket": 5
  },
  "resolved_targets": {
    "count": 9,
    "by_jurisdiction": {"san-jose": 4, "sunnyvale": 2, "santa-clara": 3},
    "by_asset_class": {"agendas": 3, "minutes": 2, "municipal_code": 1}
  },
  "capture_summary": {
    "raw_scrapes_created": 74,
    "by_content_class": {"html_text": 31, "pdf_binary": 39, "binary_blob": 4},
    "by_trust_tier": {"primary_government": 58, "official_partner": 13, "non_official": 3}
  },
  "ingestion_summary": {
    "run_mode": "capture_and_ingest",
    "ocr_mode": "hard_doc_only",
    "ocr_fallback_invocations": 7,
    "by_stage": {"raw_captured": 74, "retrievable": 48, "parse_failed_no_text": 6}
  },
  "promotion_summary": {
    "captured_candidate": 6,
    "durable_raw": 49,
    "promoted_substrate": 19
  },
  "failures": [],
  "inspection_report": {
    "run_id": "substrate-manual-20260402T221500Z",
    "available": true
  }
}
```

Rules:
- `run_id` is required and becomes the join key for the inspection report.
- The response must include enough structured summary data to tell whether the run is worth inspecting further.
- The response must not rely on log tails as the primary contract.

### 7. Inspection Report Contract
- Add a post-run report surface keyed by `run_id`.
- Minimum report contents:
  - request manifest
  - resolved targets
  - counts by `promotion_state`
  - counts by `ingestion_truth.stage`
  - counts by `trust_tier` and `trust_host_classification`
  - top failure reasons
  - `ocr_fallback_invocations`
  - sample rows for:
    - `promoted_substrate`
    - `durable_raw`
    - `captured_candidate`
    - failed / non-retrievable rows
- Minimum sample fields:
  - `scrape_id`
  - `url`
  - `canonical_url`
  - `document_type`
  - `content_class`
  - `trust_tier`
  - `promotion_state`
  - `ingestion_truth.stage`
  - short preview / title
- The report may be exposed as:
  - a backend admin/report endpoint
  - or a script/runbook that queries the database by `run_id`
- For this lane, the key requirement is reviewability, not perfect UI polish.

## Execution Phases
1. Converge the scheduled ingestion paths onto framework-complete capture metadata.
2. Add the manual Windmill expansion flow and manifest-backed backend endpoint.
3. Add the post-run inspection/report surface keyed by `run_id`.
4. Execute one bounded broad manual run and review the resulting raw data and promotion outcomes directly.

## Beads Structure
- Epic: `bd-owqm`
- Child tasks:
  - `bd-owqm.1` — Migrate scheduled ingestion paths onto framework-complete substrate metadata
  - `bd-owqm.2` — Add manual Windmill substrate expansion flow and manifest-backed backend trigger
  - `bd-owqm.3` — Add post-run substrate inspection report for manual raw-data review
  - `bd-owqm.4` — Execute broad multi-jurisdiction substrate manual run and capture review findings

Blocking edges:
- `bd-owqm.2` blocks on `bd-owqm.1`
- `bd-owqm.3` blocks on `bd-owqm.1`
- `bd-owqm.4` blocks on `bd-owqm.2`
- `bd-owqm.4` blocks on `bd-owqm.3`

## Validation

### Code / Contract Gates
- Extend or add tests covering:
  - migrated scheduled ingestion metadata seeding
  - new `/cron/manual-substrate-expansion` auth and payload validation
  - Windmill flow contract for `manual_substrate_expansion`
  - inspection report generation keyed by `run_id`

### Runtime Gates
- `wmill sync push --workspace affordabot`
- successful manual trigger from Windmill UI using the new flow
- endpoint returns structured summary with `run_id`
- inspection report can be generated or retrieved for that `run_id`

### Human Review Gates
- broad run includes multiple jurisdictions and multiple asset classes
- raw data is directly inspectable
- official substantive docs land as `durable_raw` or `promoted_substrate`
- shell/index surfaces stay out of `promoted_substrate`
- non-official or third-party content stays in `captured_candidate` unless explicitly justified

## Risks / Rollback
- Risk: broad run evaluates a mixed old/new system.
  - Mitigation: `bd-owqm.1` must land first.
- Risk: Windmill manual trigger becomes another bespoke path.
  - Mitigation: keep it on the same auth/HTTP shared-instance pattern as the existing Affordabot Windmill stack.
- Risk: OCR adds latency/cost noise.
  - Mitigation: `ocr_mode = hard_doc_only` and bounded `max_documents_per_source`.
- Rollback:
  - the new manual flow is additive and unscheduled
  - existing scheduled flows stay live
  - if the manual path is not ready, the broad run simply does not proceed

## Recommended First Task
- Start with `bd-owqm.1`.
- Reason: the broad manual run is only meaningful if every participating ingest path writes framework-complete substrate metadata at capture time. Without that convergence, the manual test would be measuring migration drift instead of framework behavior.
