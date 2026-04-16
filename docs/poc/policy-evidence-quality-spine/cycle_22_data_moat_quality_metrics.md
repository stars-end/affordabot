# Cycle 22: Data Moat Selected-Artifact Quality Metrics

Feature-Key: bd-3wefe.13

## Goal

Make Gate A harder to falsely pass by surfacing selected-artifact/provider quality
signals directly in the package and admin read model.

Cycle 20 showed the core issue: the run selected an official page while stronger
artifact-style fee schedule URLs existed in the result universe. Before this cycle,
manual auditors had to inspect raw package JSON and command-step payloads to see
that quality mismatch.

## Tweak Implemented

The runtime bridge now writes `source_quality_metrics` into package payload
`run_context` (and top-level package payload mirror), including:

- top-N recall proxy (`top_n_window`, `top_n_official_recall_count`, `top_n_artifact_recall_count`)
- selected candidate details (`url`, `rank`, `artifact_grade`, `official_domain`)
- selected artifact family (`artifact`, `official_page`, `portal`, `external_page`)
- reader substance observation for the selected candidate
- secondary structured/search numeric rescue signal
- provider summary and provider candidate metrics

Admin read model now:

1. Synthesizes matrix `rows` from package `source_quality_metrics` when runtime
   rows are absent, so scraped/search gate scoring can evaluate selected-artifact
   quality instead of defaulting to opaque not-proven.
2. Returns a dedicated `source_quality` object in endpoint response so auditors
   can verify quality status without opening raw package payload JSON.

## Why This Improves Gate A

This closes the URL-only blind spot.

- Old behavior: scraped provenance URL existed -> audit depended on manual JSON
  spelunking.
- New behavior: selected-artifact/provider quality is explicit and testable.
  If selected candidate is an official page while artifact-grade candidates are
  present, `scraped/search` can now fail with a concrete reason.

That enforces stricter selected-artifact quality while preserving fail-closed
economic output semantics.

## Test Coverage

Added/updated tests verify:

- bridge persists source-quality metrics to package run context
- bridge exposes the “artifact exists but official page selected” condition
- admin endpoint keeps scraped/search gate `not_proven` when metrics are missing
- admin endpoint surfaces `source_quality` metrics and marks scraped/search `fail`
  when selected candidate is non-artifact despite artifact recall in top-N

## Follow-Up

Run a live cycle after deployment and capture:

- `source_quality` block from admin endpoint
- scraped/search gate status + reason
- selected candidate family versus top-N artifact recall

That live check should become part of the recurring Gate A manual audit checklist.
