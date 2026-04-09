# Municipal Coverage Expansion Plan (bd-iey6)

Date: 2026-04-02  
Repo: `affordabot`  
Primary objective: define a code-grounded municipal/county coverage matrix and a bounded first expansion pack that unblocks `bd-39cw` and `bd-fkr3`.

## 1) Ground Truth Used

This plan is grounded in:
- `backend/services/scraper/registry.py`
- `backend/services/scraper/san_jose.py`
- `backend/services/scraper/santa_clara_county.py`
- `backend/services/scraper/california_state.py`
- `backend/services/scraper/saratoga.py`
- `backend/services/scraper/nyc.py`
- `backend/services/scraper/city_scrapers_adapter.py`
- `backend/affordabot_scraper/spiders/sunnyvale_agendas.py`
- `backend/services/source_service.py`
- `backend/routers/sources.py`
- `docs/specs/2026-04-02-substrate-operator-readiness.md`
- `docs/specs/2026-04-02-substrate-storage-audit.md`

What this means right now:
- Substrate/operator path is proven for bounded manual runs.
- Municipal coverage quality is uneven: some lanes are live, some are mock, some are placeholders.
- Source inventory operations are available via `/admin/sources`, but coverage still depends on explicit source/provider expansion.

## 2) Coverage Matrix (Code-Grounded)

Legend:
- `Confidence`: `High`, `Medium`, `Low`
- `Pack A`: `Yes`, `Yes (conditional)`, `No`

| Jurisdiction | Current In-Code Coverage | Provider Family / Likely Fit | Target Asset Classes | Confidence / Rationale | Pack A |
|---|---|---|---|---|---|
| `san-jose` | Registry-backed scraper; Legistar API (`webapi.legistar.com/v1/sanjose`) with `/texts` fallback to attachments | Legistar API + hosted meeting artifacts; Municode is already a known adjacent lane | `meeting_details`, `agendas`, `minutes`, `agenda_packets`, `attachments`, `staff_reports`, `legislation`, `municipal_code` | `High` - strongest existing municipal control lane | Yes |
| `sanjose` | Alias to `san-jose` in registry | Same as `san-jose` | Same as `san-jose` | `High` - alias only; not separate expansion target | No |
| `san-jose-cityscrapers` | Registry entry exists; adapter flagged in code comments as "keep for later fix" | CityScrapers adapter path | `meeting_details`, `agendas`, `minutes` | `Low` - adapter lane present but explicitly unstable | No |
| `santa-clara-county` | Registry-backed scraper with Legistar API candidate (`sccgov`), mock fallback still present | Legistar API + hosted artifacts | `meeting_details`, `agendas`, `minutes`, `agenda_packets`, `attachments`, `staff_reports`, `legislation` | `Medium` - real API lane exists, but fallback behavior indicates reliability risk | Yes |
| `saratoga` | Registry-backed scraper currently returns mock content; points to AgendaCenter URL | CivicPlus/AgendaCenter style + PDF artifacts | `agendas`, `minutes`, `agenda_packets`, `attachments`, `staff_reports` | `Low` - in code, but currently mock-based | Yes |
| `california` | Registry-backed OpenStates discovery + official legislature text extraction path; no mock fallback for truth-critical lane | OpenStates + official legislature URLs | `legislation` (state lane only) | `High` - well-defined state flow, but state is secondary for moat | No (Pack A), Yes (secondary lane) |
| `nyc` | Registry-backed scraper currently mock | Legistar likely fit | `legislation`, `meeting_details`, `agendas`, `minutes` | `Low` - outside current municipal/county focus and currently mock | No |
| `sunnyvale` | Existing Scrapy spider `sunnyvale_agendas.py` for Legistar calendar, not yet in main registry | Legistar meeting calendar + artifacts | `meeting_details`, `agendas`, `minutes`, `agenda_packets`, `attachments` | `Medium` - concrete spider exists, but still labeled placeholder and not wired into main registry | Yes |
| `cupertino` | Not in code/registry yet | Likely Legistar/hosted meeting artifacts (unverified) | `meeting_details`, `agendas`, `minutes`, `agenda_packets`, `attachments`, `staff_reports` | `Low` - no code or source rows yet | Yes (conditional) |
| `palo-alto` | Not in code/registry yet | Likely Legistar or equivalent meeting platform (unverified) | `meeting_details`, `agendas`, `minutes`, `agenda_packets`, `attachments`, `staff_reports`, `municipal_code` | `Low` - no code or source rows yet | Yes (conditional) |
| `santa-clara-city` | Not in code/registry yet | Likely Legistar or equivalent meeting platform (unverified) | `meeting_details`, `agendas`, `minutes`, `agenda_packets`, `attachments`, `staff_reports`, `municipal_code` | `Low` - unverified provider fit | No |
| `mountain-view` | Not in code/registry yet | Likely Legistar or equivalent meeting platform (unverified) | `meeting_details`, `agendas`, `minutes`, `agenda_packets`, `attachments`, `staff_reports`, `municipal_code` | `Low` - unverified provider fit | No |
| `campbell` | Not in code/registry yet | Likely mixed meeting platform (unverified) | `meeting_details`, `agendas`, `minutes`, `agenda_packets`, `attachments` | `Low` - unverified | No |
| `milpitas` | Not in code/registry yet | Likely mixed meeting platform (unverified) | `meeting_details`, `agendas`, `minutes`, `agenda_packets`, `attachments` | `Low` - unverified | No |
| `san-mateo-county` | Not in code/registry yet | County meeting platform likely, provider unverified | `meeting_details`, `agendas`, `minutes`, `agenda_packets`, `attachments`, `staff_reports`, `legislation` | `Low` - unverified | No |
| `alameda-county` | Not in code/registry yet | County meeting platform likely, provider unverified | `meeting_details`, `agendas`, `minutes`, `agenda_packets`, `attachments`, `staff_reports`, `legislation` | `Low` - unverified | No |
| `san-francisco-city-county` | Not in code/registry yet | Distinct platform likely; provider unverified | `meeting_details`, `agendas`, `minutes`, `agenda_packets`, `attachments`, `staff_reports`, `legislation`, `municipal_code` | `Low` - unverified and likely custom edge cases | No |

## 3) Bounded First Expansion Pack Recommendation

Pack A is bounded to six municipal/county jurisdictions:

1. `san-jose` (control lane; must stay in every campaign)
2. `santa-clara-county`
3. `saratoga`
4. `sunnyvale`
5. `cupertino` (conditional on source/provider verification in `bd-fkr3`)
6. `palo-alto` (conditional on source/provider verification in `bd-fkr3`)

Pack A guardrails:
- If `cupertino` and/or `palo-alto` fail source/provider verification, do not substitute ad hoc one-off adapters in this wave.
- Keep Pack A at six max for this cycle; depth over count.
- Keep `california` as a secondary state lane under `bd-q20y` only.

Why this pack:
- It preserves one strong control (`san-jose`), includes one county lane, and adds one concrete new in-repo meeting lane (`sunnyvale`).
- It adds exactly two expansion candidates that can be verified quickly via source inventory without committing to unproven adapter work.

## 4) Municipal Primary, State Secondary Contract

Primary (municipal/county):
- Target outcome is broader municipal process coverage, not just more legislation rows.

Secondary (state):
- `california` remains active for legislation via OpenStates + official text.
- State expansion must not block municipal/county execution sequence.

## 5) Implementation Order (Feeds Downstream Tasks)

This is the execution order that directly unblocks downstream Beads tasks:

1. `bd-39cw` - Generalize provider families already present
- First focus: Legistar family normalization and hosted artifact handling used by `san-jose`, `santa-clara-county`, and `sunnyvale`.
- Keep cityscrapers adapter as non-critical until reliability is proven.

2. `bd-fkr3` - Expand source registry and trust coverage
- Add/verify jurisdiction + source rows for Pack A.
- Explicitly verify `cupertino` and `palo-alto` provider fit; if verification fails, mark out-of-pack for this cycle.

3. `bd-wqxe` - Implement Pack A municipal/county coverage
- Deliver asset coverage per jurisdiction using generalized provider family paths from `bd-39cw` and registry/trust inventory from `bd-fkr3`.

4. `bd-q20y` - Secondary state legislation lane
- Keep separate and parallel-safe after provider generalization.
- No cross-lane blocking on municipal/county core path.

5. `bd-hfk0` - Broad municipal campaign run
- Execute bounded Windmill manual campaign against implemented Pack A.
- Use inspection outputs to separate missing-source vs broken-path failures.

6. `bd-pd1s` - Repair findings and publish readiness verdict
- Fix non-strategic coverage defects from the campaign.
- Publish explicit readiness and remaining-gap report.

## 6) Validation Gates for This Plan

- `bd-39cw` and `bd-fkr3` are unblocked with a concrete jurisdiction/priority matrix.
- Pack A remains bounded and measurable (max six jurisdictions this cycle).
- Campaign success is judged by truthful substrate outputs and asset coverage, not jurisdiction count alone.
- Thin-evidence jurisdictions remain explicitly labeled `Low` confidence until source/provider verification is complete.

## Recommended First Task

- `bd-iey6` — Define municipal/county coverage matrix and first expansion pack

Why first:
- it converts “suggested jurisdictions” into an explicit, verified coverage matrix
- it prevents wasted effort on weak-fit jurisdictions
- it gives `dx-loop` or subagents a clean dependency root for the rest of the expansion program
