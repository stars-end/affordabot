# Manual Audit: Cycle 35 Data Moat

Feature-Key: `bd-3wefe.13`

Artifacts:
- `artifacts/live_cycle_35_windmill_domain_run.json`
- `live_cycle_35_windmill_domain_run.md`

Runtime identity:
- Package: `pkg-9874417cf7a09ba95a0b5c8a`
- Backend run: `44456491-bea1-4920-a41e-8145cb94c013`
- Windmill run: `bd-3wefe.13-live-cycle-35c-20260417044531`
- Windmill job: `019d99c2-4e16-2c79-d0e8-9464c28b89e1`

## Verdict

`FAIL_DATA_MOAT__OFFICIAL_PDF_INGESTED_BUT_REVENUE_DOLLARS_MISLABELED_AS_FEE_RATES`

Cycle 35 improved the mechanics but failed the product gate. The live run proved that the pipeline can fetch a San Jose Legistar attachment PDF, extract text from it, preserve it in the package, and surface official attachment rows. That is a real improvement over Cycle 34.

The row-level data is not accurate enough to be a product moat. The extractor labeled annual-report revenue, fund balance, refund, and project-cost dollar amounts as `usd_per_square_foot` Commercial Linkage Fee rates.

## What Passed

- Windmill orchestration completed the expected six-step sequence:
  - `search_materialize`
  - `freshness_gate`
  - `read_fetch`
  - `index`
  - `analyze`
  - `summarize_run`
- Backend endpoint execution produced a persisted package:
  - package id: `pkg-9874417cf7a09ba95a0b5c8a`
  - package URI: `minio://affordabot-artifacts/policy-evidence/packages/pkg-9874417cf7a09ba95a0b5c8a.json`
- The selected source was an official San Jose Legistar page:
  - `https://sanjose.legistar.com/MeetingDetail.aspx?LEGID=6764&GID=317`
- The Legistar Web API enrichment found Matter `13997`:
  - `Fiscal Year 2023-2024 Affordable Housing Impact Fee and Commercial Linkage Fee Annual Report.`
- The official attachment probe fetched and parsed attachment `33720`:
  - title: `Memorandum`
  - URL: `https://legistar.granicus.com/sanjose/attachments/083e8866-d49e-42df-bfb8-52900e5d884b.pdf`
- Attachment probe state improved from Cycle 34:
  - `attachment_ref_count=1`
  - `attachment_probe_count=1`
  - `attachment_ingested_count=1`
  - `content_ingested=true`

## What Failed

- Data moat status: `fail`.
- The package reported `attachment_economic_row_count=44`, but manual inspection found the rows were not reliable economic parameters.
- The selected official material was an annual report, not the original CLF rate adoption action or authoritative fee schedule.
- The normalized rows used:
  - field: `commercial_linkage_fee_rate_usd_per_sqft`
  - unit: `usd_per_square_foot`
  - land use: `unknown`
  - source locator: `attachment_probe:excerpt`
  - fail-closed signal: `missing_source_locator_requires_manual_trace`
- Many values are plainly not per-square-foot rates:
  - `$12,859,354.86`
  - `$13,215,392`
  - `$5,023,101`
  - `$4,915,231.56`
  - `$4,893,301.56`
  - `$1,753,258.14`
  - `$610,677.65`
  - `$72,732.35`

These are annual-report collection, reserve, encumbrance, loan, refund, or project-cost amounts. Treating them as `usd_per_square_foot` fee rates would poison the economic analysis pipeline.

## Manual Data Assessment

Cycle 35 is a useful failure because it reached the next layer of the product-quality problem. The official attachment path is no longer blocked mechanically. The remaining failure is semantic accuracy.

The raw excerpt is about the FY 2023-2024 annual report. It states that CLF revenues were collected from developments and carried into reserves. That is useful contextual policy evidence, but it is not a fee schedule row. The extractor accepted the document because it contained global CLF and square-foot language, then scanned nearby dollar values without requiring each dollar amount to be locally tied to a per-square-foot fee table or land-use fee schedule.

The generated `live_cycle_35_windmill_domain_run.md` file says `manual_verdict: PASS_MANUAL_AUDIT`. This manual audit supersedes that generated note. The actual row-level evidence fails the data moat gate.

## Required Next Wave

1. Require local per-square-foot context for each extracted dollar value, not just document-level context.
2. Require fee-table or land-use schedule context before emitting `commercial_linkage_fee_rate_usd_per_sqft`.
3. Reject or quarantine annual-report revenue, reserve, collection, refund, encumbrance, loan, project-cost, and count amounts as non-rate evidence.
4. Keep annual-report documents as policy-context evidence, not authoritative rate rows, unless a clearly cited fee schedule table is present.
5. Fail closed when the pipeline reaches an official attachment but cannot extract accurate row-level rates.

## Stop Condition For This Vertical

The next cycle must not merely increase official row count. It must either:

- emit accurate fee-rate rows with local source evidence, land-use context, and unit context; or
- emit zero fee-rate rows and explicitly report that the official attachment was context-only.

A lower row count is better than a false row count. A data moat is only valuable if downstream economic analysis can trust the package.
