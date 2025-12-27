# Packet: affordabot-ahpb.10 — Affordabot integrates ToolSelector (fire-and-forget)

Audience: senior engineer with good judgement and **no repo context**.

## Goal

Affordabot must route tools using a dedicated small-model **ToolSelector** (default `glm-4.5-air`) by consuming the shared llm-common implementation (`llm-common-cmm.11`), not duplicating selection logic locally.

## Dependencies

- Hard dependency: `llm-common-cmm.11` merged and released as a tag that Affordabot pins.

## Current integration reality (important)

Affordabot’s `PolicyAgent` code is currently out-of-sync with llm-common APIs:
- Uses `TaskPlanner.create_plan(...)` but llm-common planner is `TaskPlanner.plan(...)`.
- References `self.registry.tools` but llm-common `ToolRegistry` stores tools internally (`_tools`) and exposes `list_tools()` / `get_tools_schema()`.

Treat this task as “make Affordabot compile/run against the pinned llm-common release,” not “paper over mismatches.”

## Scope (expected file touch list)

- `backend/agents/policy_agent.py` (planning + execution wiring)
- `backend/routers/chat.py` only if dependency injection must change

Out of scope:
- Any frontend rewrite/unification (tracked separately; `affordabot-ahpb.12`)

## Required behavior

1. Planning uses llm-common `TaskPlanner.plan(...)` (not `create_plan`).
2. Tool selection uses llm-common `ToolSelector` (from `llm-common-cmm.11`) either:
   - indirectly via llm-common `AgenticExecutor` (preferred), or
   - explicitly wired in Affordabot if executor is not updated upstream.
3. Default tool-selection model is `glm-4.5-air` (override via env vars).
4. Max tool calls capped (≤ 5).
5. Fallback policy bounded and safe (no “select all tools” default).

## Config

Use llm-common env vars (do not invent new names):
- `LLM_COMMON_TOOL_SELECTION_MODEL`
- `LLM_COMMON_TOOL_SELECTION_FALLBACK_MODEL`
- `LLM_COMMON_TOOL_SELECTION_MAX_CALLS`
- `LLM_COMMON_TOOL_SELECTION_TIMEOUT_S`
- `LLM_COMMON_TOOL_SELECTION_FAIL_CLOSED`

## Testing / verification

Required:
- `make verify-local`
- For multi-file / P0/P1: `make verify-pr PR=<N>`

Note: if `master` CI is red, fix that first or merge discipline breaks.

## Acceptance criteria (reference)

Beads: `affordabot-ahpb.10`

