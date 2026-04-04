# Legistar Calendar Expansion Notes

Date: 2026-04-03
Beads subtask: `bd-paba`

## Summary

This slice turns the seeded official Legistar calendar roots into direct candidate source rows for:

- `agenda`
- `minutes`

It stays inside the existing-family deepening strategy and avoids the custom-archive/provider-family decision surface.

## Why This Matters

`bd-knlg` seeded truthful official calendar roots. That alone is honest, but it does not yet give the bounded expansion runner direct `agenda` and `minutes` source rows.

This slice adds a Legistar calendar expander so the next campaign can work with direct document URLs under a reusable family.

## Output Shape

For each calendar row with available links, the expander emits:

- document URL
- document type (`agenda` or `minutes`)
- meeting name
- meeting date
- provider family metadata tied back to the source calendar root
