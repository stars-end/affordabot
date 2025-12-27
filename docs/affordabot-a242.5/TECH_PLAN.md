# affordabot-a242.5 — llm-common agent gap unit tests

## Goal
Add focused unit tests around shared primitives adopted from `llm-common` to prevent regressions.

## Strategy
- Test shared behaviors at the boundaries you depend on (tool selection, context pointers, provenance envelope).
- Prefer golden fixtures for schema outputs.

