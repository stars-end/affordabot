# affordabot-bok6 — Admin Console User Stories & UISmokeAgent Integration

## Goal
Maintain a story-driven verification suite for the admin console (UISmokeAgent + YAML stories) and keep it green in `make verify*`.

## Current Status
- Core admin story files exist under `docs/TESTING/STORIES/`.
- Verification runs as part of the pipeline; regressions should be logged as P0 bugs.

## Remaining Work
- Keep adding stories only when they catch real regressions (avoid bloat).
- Ensure story runner is stable without auth and with auth (when creds provided).

