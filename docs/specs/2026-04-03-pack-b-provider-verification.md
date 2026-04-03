# Pack B Provider Verification

Date: 2026-04-03  
Beads: `bd-flci.3`  
Base: PR #371 (`17159d11ff4e128670ec1c45b5d6f1ab94152e33`)

## Objective

Apply the next jurisdiction wave using only provider families already supported by the current substrate/manual expansion implementation.

Allowed families in scope:
- `legistar_calendar`
- `agenda_center`
- `municode` (only when municipal code roots are clearly supported and obvious)

## Added In This Wave

1. `cupertino`  
Provider fit: Legistar calendar family  
Handler: `legistar_calendar`  
Asset lanes: `meeting_details`, `agendas`, `minutes`, `agenda_packets`, `attachments`, `staff_reports`

2. `mountain-view`  
Provider fit: Legistar calendar family  
Handler: `legistar_calendar`  
Asset lanes: `meeting_details`, `agendas`, `minutes`, `agenda_packets`, `attachments`, `staff_reports`

3. `san-mateo-county`  
Provider fit: Legistar calendar family  
Handler: `legistar_calendar`  
Asset lanes: `meeting_details`, `agendas`, `minutes`, `agenda_packets`, `attachments`, `staff_reports`

4. `san-francisco-city-county`  
Provider fit: Legistar calendar family  
Handler: `legistar_calendar`  
Asset lanes: `meeting_details`, `agendas`, `minutes`, `agenda_packets`, `attachments`, `staff_reports`

5. `campbell`  
Provider fit: AgendaCenter family  
Handler: `agenda_center`  
Asset lanes: `agendas`, `minutes`, `agenda_packets`, `attachments`, `staff_reports`

## Deferred In This Wave

1. `palo-alto`  
Reason: current source pattern is a custom archive/file style and does not map cleanly to the existing handler families without a bespoke adapter.

2. `milpitas`  
Reason: current site pattern aligns with CivicEngage-style calendar/document-center behavior that is not represented as a first-class handler family in the current implementation.

3. `alameda-county`  
Reason: current board/agenda-minutes application pattern does not cleanly map to existing Legistar/AgendaCenter handler assumptions without one-off handling.

## Municipal Code Decision

No new Pack B municipal code roots were added in this patch.

Reason:
- keep this wave strict to verified handler-family parity
- avoid speculative `municode` assumptions for newly added jurisdictions
- preserve truthful coverage over jurisdiction count

## Code Manifest

Changes in this wave are centered on:
- Pack B source defaults for manual substrate expansion
- matching seed inventory entries
- tests proving only supported handler families are used
- explicit deferred-jurisdiction guardrails

