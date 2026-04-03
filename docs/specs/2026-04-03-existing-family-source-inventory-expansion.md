# Existing-Family Source Inventory Expansion

Date: 2026-04-03
Beads subtask: `bd-knlg`

## Summary

This slice expands the explicit source inventory for the next deep-coverage substrate wave.

It intentionally adds truthful official Legistar calendar roots for the next target jurisdictions instead of pretending those roots are already direct agenda or minutes documents.

## Jurisdictions

- `san-jose`
- `sunnyvale`
- `cupertino`
- `mountain-view`
- `san-mateo-county`

## Truth Boundary

Each seeded source is:

- an official calendar root
- classified as `provider_family=legistar_calendar`
- marked with `document_type=meeting_calendar`
- annotated with `supported_asset_classes=["agendas", "minutes"]`

This keeps the inventory honest:

- it does not claim direct agenda/minutes rows already exist in `sources`
- it does define the exact official roots the next adapter/discovery step should use to materialize truthful `agendas + minutes`

## Why This Slice

The next wave is optimized for existing-family deepening rather than speculative breadth.

These jurisdictions give a clearer path to truthful `agendas + minutes` under a reusable family than the deferred custom-archive jurisdictions.
