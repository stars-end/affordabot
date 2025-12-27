# affordabot-a242.12 — PolicyAgent orchestrator

## Goal
Define the orchestration boundary for PolicyAgent (planning → research → generate → review) with consistent artifact persistence and provenance.

## Acceptance Criteria
- Phase boundaries are explicit.
- Each phase reads selected context pointers (not raw blobs).
- Errors are recoverable and logged with enough context.

