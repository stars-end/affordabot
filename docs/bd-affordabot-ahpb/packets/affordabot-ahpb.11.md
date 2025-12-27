# Packet: affordabot-ahpb.11 — Affordabot integrates pointer store + relevance selection (fire-and-forget)

Audience: senior engineer with good judgement and **no repo context**.

## Goal

Affordabot’s research→generate→review flow must avoid prompt bloat by:
- persisting large artifacts as pointers (llm-common pointer store),
- and selecting only relevant pointers before each generation/review step.

## Dependencies

- Hard dependency: `llm-common-cmm.12` merged and released as a tag that Affordabot pins.

## Scope (expected file touch list)

- `backend/agents/policy_agent.py` (or the actual pipeline entrypoint used for generation)
- any tool execution layer that currently writes artifacts inline into prompts

Out of scope:
- frontend unification (post-MVP decision)

## Required behavior

1. Tool outputs/artifacts are saved to `FileContextPointerStore`.
2. Before synthesis/generation, call `ContextRelevanceSelector.select(...)` and use only selected contexts.
3. Fail closed by default (do not inject all artifacts when selection fails).

## Config

Use llm-common env vars:
- `LLM_COMMON_POINTER_STORE_DIR` (recommended: `/tmp/affordabot/context` in server env)
- `LLM_COMMON_CONTEXT_SELECTION_MODEL`
- `LLM_COMMON_CONTEXT_SELECTION_MAX_POINTERS`
- `LLM_COMMON_CONTEXT_SELECTION_FAIL_CLOSED`

## Testing / verification

Required:
- `make verify-local`
- For multi-file / P0/P1: `make verify-pr PR=<N>`

## Acceptance criteria (reference)

Beads: `affordabot-ahpb.11`

