# affordabot-5at — Align agent trailers and CLI-only Beads

## Goal
Ensure every commit/PR is traceable to a Beads issue via `Feature-Key` trailers, and avoid silent drift.

## Acceptance Criteria
- Hooks/CI fail with a clear message when Feature-Key is missing.
- Beads JSONL auto-merge stays stable.

