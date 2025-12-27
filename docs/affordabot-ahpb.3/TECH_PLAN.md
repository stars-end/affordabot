# affordabot-ahpb.3 — API contract compatibility

## Goal
Define and enforce API contracts for Affordabot so frontend/backends don’t drift, and shared agent contracts can live in `llm-common`.

## Open Questions (Needs User Input)
- Which endpoints must be stable for MVP?
- Do we want OpenAPI-generated types, or shared JSON Schema artifacts from `llm-common`?

## Acceptance Criteria
- Canonical contract source is chosen and enforced in CI.

