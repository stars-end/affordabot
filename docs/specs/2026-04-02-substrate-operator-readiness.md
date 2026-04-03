# Substrate Operator Readiness Verdict (bd-17a1)

Date: 2026-04-02  
Repo: affordabot (`/tmp/agents/bd-5wd9/affordabot`)

## 1) Framework State: Locked

Verdict: locked for the manual substrate operator lane on this branch.

Grounding:
- Windmill manual flow contract is committed and exercised through the real flow surface.
- Typed flow input forwarding bug was corrected and operator path proof was rerun successfully (bd-81tt).

## 2) Storage Audit Outcome

Outcome: storage path is mapped and auditable, with integrity checks added on branch.

Grounding:
- Storage audit note: `docs/specs/2026-04-02-substrate-storage-audit.md`
- Branch hardening commit: `8e46ad4` (`feat: add storage integrity checks for manual substrate runs`)

## 3) Real Windmill Operator Proof Outcome (bd-81tt)

Outcome: operator path proved after typed input forwarding fix.

Evidence:
- Windmill job id: `019d4ff5-6b50-bd5a-9d62-16d8820bd844`
- Backend run_id: `manual-substrate-20260402T204937Z-13896267`
- Result: flow execution path ran through real Windmill surface and backend returned structured run output.

## 4) Broad Validation Run Outcome (bd-xv1j)

Outcome: bounded broad run completed with partial success and meaningful substrate writes.

Evidence:
- Windmill job id: `019d4ff8-0181-5101-b3ca-4b0dbf27eed6`
- Backend run_id: `manual-substrate-20260402T205227Z-2f479df7`
- Backend status: `partial_success`
- Capture summary: `raw_scrapes_created = 9`
- Ingestion summary: `retrievable = 9`
- Promotion summary: `durable_raw = 6`, `promoted_substrate = 3`, `captured_candidate = 0`

## 5) Manual Raw-Data Inspection Findings

Manual DB inspection matched run-reported counts:
- 9 raw rows for the broad run id
- content classes: `html_text = 4`, `pdf_binary = 1`, `plain_text = 4`
- trust tiers: `official_partner = 5`, `primary_government = 4`

## 6) Non-Strategic Defect Found and Fixed on Branch (bd-sdo3)

Defect:
- malformed quoted `SLACK_WEBHOOK_URL` values caused webhook send failures in trigger path.

Fix:
- commit `1b32183` (`fix: normalize malformed Slack webhook values in windmill trigger`)

Impact:
- defect was operational/noise-level; it did not invalidate substrate capture/ingestion/promotion outcomes.

## 7) Explicit Operator-Readiness Verdict

Verdict:
- repeated bounded manual operator use is ready after this branch merges.

Scope of readiness:
- real Windmill execution path proved
- storage path audited and hardened
- broad bounded run produced retrievable and promoted outputs with verifiable raw data

## 8) Residual Limits

Primary residual limit remains source coverage breadth outside San Jose:
- non-legislation assets (`meeting_details`, `agendas`, `municipal_code`) are still sparse for `california`, `saratoga`, and `santa-clara-county` in current source inventory.
- practical effect: broad runs may complete as `partial_success` with expected `no_matching_sources` failures outside stronger source areas.

