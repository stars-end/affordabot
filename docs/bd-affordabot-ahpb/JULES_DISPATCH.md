# Jules Dispatch Packets (affordabot-ahpb)

Scope: **docs + Beads prep only** (no implementation in this PR).

This file is the “handoff sheet” for dispatching self-contained tasks to remote agents (Jules) in the Affordabot repo.

## 0) Non‑Negotiables (for every agent)

1. Work on a **feature branch** named `feature-<issue-id>` (example: `feature-affordabot-ahpb.10`).
2. Open a **PR early** (as soon as the scaffold compiles / tests start running).
3. Merge regularly (merge/rebase `origin/master` daily for multi-day work).
4. **Do not merge unless CI is green** and Railway PR checks are green at the milestone.
5. Every commit must include `Feature-Key: <issue-id or epic-id>`.
6. **No `.env` files**. Use `railway shell` for secrets/env access.

## 1) Verification Gates (Affordabot)

Use these as “merge blockers” at milestones:

- Local fast gate: `make verify-local`
- PR gate (P0/P1, multi-file): `make verify-pr PR=<N>`
- PR-lite (docs/single-file, P2+): `make verify-pr-lite`
- Post-merge dev gate (after landing on master): `make verify-dev`

## 2) What “Jules‑Ready” Means Here

An issue is Jules‑ready if it has:
- explicit dependencies (other Beads IDs),
- a clear file-level scope,
- acceptance criteria,
- a verification command list,
- and a “stop condition” (definition of done).

If any of those are missing, the first PR should be “docs-only: make Jules-ready”.

## 3) Workstream Split (do not blur boundaries)

- **llm-common** owns reusable primitives and shared contracts.
- **affordabot** owns research/policy domain tools and the research→generate→review pipeline, and must *consume* llm-common primitives.
- **prime-radiant-ai** owns the canonical frontend stack; Affordabot’s frontend migration should track it but not fork shared primitives.

Affordabot should not invent a second copy of:
tool selection helpers, evidence/provenance envelopes, context pointer stores, or message-history selection logic.

## 4) Jules‑Ready Packets

### Not Jules‑Ready (human decisions)

- `affordabot-ahpb.12` Decision: Affordabot frontend unification timing (MVP vs post‑MVP)

## 5) Fire-and-forget packet docs (read these first)

- `docs/bd-affordabot-ahpb/packets/affordabot-ahpb.10.md`
- `docs/bd-affordabot-ahpb/packets/affordabot-ahpb.11.md`

### Packet: `affordabot-ahpb.10` — TOOL_SELECTION_SMALL_MODEL_GLM_4_5_AIR

**Repo:** `affordabot`  
**Branch:** `feature-affordabot-ahpb.10`  
**Depends on:** `llm-common-cmm.11` (preferred), otherwise stub behind interface until llm-common lands  
**Goal:** Affordabot uses a dedicated small-model tool-selection step (default `glm-4.5-air`) that deterministically selects retrieval/research tools with schema-grounded prompts.

**Implementation approach (preferred):**
1. Adopt llm-common `ToolSelector` (or equivalent) as the only tool-selection mechanism.
2. Keep caps strict (`<= 5` tools) and make failures explicit (structured error + logs).

**Verification:**
- `make verify-local`
- If pipeline + API touched: `make verify-pr PR=<N>`

**Stop condition:**
- Tool routing no longer depends on the synthesis model and is isolated/configurable.

### Packet: `affordabot-ahpb.11` — CONTEXT_POINTER_STORE_AND_RELEVANCE_SELECTION

**Repo:** `affordabot`  
**Branch:** `feature-affordabot-ahpb.11`  
**Depends on:** `llm-common-cmm.12` (preferred), otherwise stub behind interface until llm-common lands  
**Goal:** Persist large research artifacts as pointers and run relevance selection at phase boundaries (before generation/review) to avoid prompt bloat and improve auditability.

**Implementation approach (preferred):**
1. Consume llm-common’s pointer store format and relevance selector (shared schema).
2. Ensure deterministic pointer summaries exist (for selection + admin visibility).
3. Wire selection into the research→generate→review pipeline so generation consumes only selected contexts.

**Verification:**
- `make verify-local`
- If multi-file / contract surface changes: `make verify-pr PR=<N>`

**Stop condition:**
- Generation/review steps no longer inject “all artifacts” into prompts.
