# Big‑Bang Shared Agent/Contract Unification (SEO-first Affordabot)

**Prime Radiant Epic:** `bd-yn9g`  
**Affordabot Epic:** `affordabot-ahpb`  
**llm-common Epic:** `llm-common-cmm`  

## 0) Purpose

Create a **full big‑bang rewrite specification** to standardize both products on **one shared agent/runtime contract layer** (via `llm-common`) while minimizing regressions and enabling parallel execution by remote agents (Jules).

This spec is designed for a solo developer managing multiple LLM agents: it prioritizes **clear contracts**, **minimized ambiguous integration surfaces**, and **low-cost regression detection**.

> **Canonical copy**: `prime-radiant-ai/docs/bd-yn9g/SPEC.md`.  
> This file is a **mirror** stored in `affordabot` so agents working in this repo have full context.

## 0.1 Jules Dispatch (Affordabot-specific)

Jules-ready packets live in `docs/bd-affordabot-ahpb/JULES_DISPATCH.md`. Use them to dispatch self-contained work with:
- explicit dependencies on llm-common primitives,
- explicit verification gates (`make verify-*`),
- and a strict feature-branch → PR → green checks → merge workflow.

## 1) MVP Stance (explicit)

**MVP = Structured-only advisor responses.**  
Streaming chat and tool-call visualization are explicitly **post‑MVP** unless needed for a user-facing requirement.

Rationale:
- Structured outputs are easier to validate, diff, regression-test, and safely render for financial advice.
- Streaming adds edge cases (partial output, reconnect, ordering, interruptions) that increase regression risk.

**Big-bang rewrite default:** remove Prime’s SSE/DeepChat path as part of the rewrite.  
If streaming is reintroduced post‑MVP, it must use a single shared event contract (llm-common), not a Prime-only fork.

## 2) Current State (baseline)

### Prime Radiant
- Frontend: **Vite + React Router + MUI** (`frontend/`)
- Advisor: structured endpoint (`/api/v2/advisor/analyze`) and a separate streaming endpoint (`/api/v2/chat/`) that is currently mock-only.
- UI contains multiple parallel “chat runtime” implementations (`AdvisorContext`, `useAdvisorSession`, `useSSEChat`).

### Affordabot
- Frontend: **Next.js** (`frontend/`) with its own UI patterns.
- Backend: FastAPI with a streaming chat router intended for PolicyAgent, but integration surfaces are inconsistent with llm-common APIs.

### llm-common
- Python shared layer for agent framework, tools, provenance, and UI-smoke agent.
- Version drift across repos/scripts is currently the #1 regression multiplier.

## 3) Target State (big-bang end state)

### 3.1 Target frontend stack (default)

Affordabot is **majority public + indexed** and must remain **Next.js** (SSR/SSG/ISR).

Unification target is not the frontend framework; it is:
- shared contracts + schemas (llm-common)
- shared agent primitives (ToolSelector, pointer store, provenance/evidence)
- shared verification strategy and regression harness

### 3.2 Target UX for MVP advisor

- Single “advisor session” UX, driven by a structured JSON response schema.
- Rendered sections: summary, insights, recommendations, confidence + limitations.
- Persisted conversation history (server-side), with a small client-side cache for responsiveness.

### 3.3 Optional post‑MVP extensions

- Streaming “progress events” (not raw advice text) to show tool activity and long-running steps.
- Tool-call UI (chips, approvals) and citations UI once provenance is stable and shared.

## 4) Architecture Decisions (recorded; open to change)

### Decision A: Design system
- **Default:** keep MUI to reduce migration lift and regressions.
- **Alternative:** migrate to shadcn/tailwind/Radix and consider assistant-ui (or use assistant-ui runtime/transport with MUI wrappers).

Tradeoff:
- MUI reduces migration cost (short term).
- assistant-ui can reduce long-term bespoke chat UX code, but its “starter” UX is Tailwind/shadcn-oriented; staying on MUI likely requires wrapper work and/or adopting only runtime/transport pieces.

### Decision B: Backend chat protocol
- **MVP:** structured JSON only.
- **Post‑MVP:** if streaming, standardize an event schema in llm-common (do not fork per repo).

### Decision C: Canonical contract source of truth
- **Canonical:** `llm-common` Python models (Pydantic) + generated JSON Schema artifacts (versioned).
- **Derived:** OpenAPI (helpful for docs/clients, but not the source of truth).
- **Frontend:** generated TypeScript types (or Zod guards) derived from the shared JSON Schema.

Goal: eliminate “two definitions of the same payload” and stop silent frontend/backend drift.

### Decision D: Evidence/provenance shape (shared)
- Use a single shared evidence envelope (llm-common `Evidence` / `EvidenceEnvelope`).
- Citations reference evidence IDs (not raw URLs embedded ad hoc in model text).
- “Sources” UI renders from evidence items; text rendering can optionally include a “Sources” section.

### Decision E: Persistence model (shared)
- Persist **both**:
  - `response_json`: the full structured response payload (canonical)
  - `response_text`: a rendered human-readable summary (for UX/search/debug)
- Also persist:
  - `evidence_envelope` (or embed within `response_json`)
  - `schema_version` and `llm_common_version` to prevent “old rows break new UI”.

### Decision F: llm-common compatibility + pinning
- Apps pin `llm-common` by **tag** (no branch pins).
- Semver policy:
  - patch = bugfix only
  - minor = additive-only
  - major = breaking changes + migration notes

### Decision G: Failure mode policy (cross-repo)
- Required capabilities fail fast (startup/config error) rather than silently degrading.
- Optional capabilities degrade only behind explicit config (e.g., “no retrieval” mode).

### Decision H: Dexter patterns (what we actually reuse)
See `docs/bd-affordabot-ahpb/DEXTER_AUDIT.md` for the local Dexter snapshot audit and the specific “missed integration ideas” to fold into this rewrite.

### Decision I: Small-model tool selection (Dexter port)
- **Default tool-selection model:** `glm-4.5-air`
- Tool selection is a separate “model role” from synthesis.
- Tool selection must be schema-grounded (tool registry) and capped (≤5 tools) to reduce regressions.

### Decision J: AI chat UI framework (MVP vs post‑MVP)
**MVP + Post‑MVP default:** Vercel AI SDK hooks (`useChat`, `useObject`) + current UI rendering.

Rationale: the chat UX is not the differentiator; optimize for stability and maintainability. UI framework choice should follow a stable backend message/contract model, not drive it.

### Decision K: ToolSelector (explicit spec)
We will implement (in `llm-common`) a dedicated ToolSelector layer distinct from synthesis:
- **File/API:** `llm_common/agents/tool_selector.py` (exported from `llm_common.agents`)
- **Default model:** `glm-4.5-air` (configurable)
- **Output:** structured tool-call list (Pydantic model), with hard caps (≤5 calls)
- **Config:** env vars for model + fallback policy (names to be finalized in `llm-common-cmm.11`)

### Decision L: Tool selection fallback policy (safety-first)
Fallbacks must be bounded and safe (avoid “select all tools” behavior by default):
1. Retry once with a configured fallback model.
2. If still failing: fail closed with a structured error (no “run everything”).


## 5) Big‑Bang Cutover Strategy (minimize regressions)

### Approach
1. Build the “new unified frontend” in parallel (don’t edit the old affordabot Next.js UI in place).
2. Reach feature parity for MVP user journeys.
3. Add minimal contract + smoke tests.
4. Cut over behind a flag / separate deployment target.
5. Remove/deprecate the old frontend only after stability.

### MVP Journeys to preserve
- Auth/login → dashboard view
- “Ask Advisor” → structured response rendered
- Feedback submission (if present)

## 6) Regression Strategy (optimized for low verification cost)

### 6.1 Contract tests (cheap, high signal)
- Validate structured response schema (server-side and client-side type guard).
- Validate that required fields exist even on partial/empty portfolio.

### 6.2 E2E smoke tests (1–2 only)
- One happy-path test per product:
  - login (or auth stub) → ask advisor → see structured response sections.

### 6.3 GLM UI smoke agent (post-merge / periodic)
- Use existing `UISmokeAgent` stack to catch UI regressions across deployments.
- Treat as “broad net”, not a blocker for every PR.

### 6.4 Merge gates (CI/Railway) — required at milestones
- Prime: `make verify-local` (then `make verify-pr PR=<N>` for P0/P1 and multi-file); post-merge `make verify-dev`.
- Affordabot: `make verify-local` (then `make verify-pr PR=<N>` for P0/P1; `make verify-pr-lite` for docs/single-file); post-merge `make verify-dev`.
- Merge rule: CI must be green; Railway PR deploy checks must be green when present.

## 7) Workstreams and Beads Issues (Jules-dispatchable)

### 7.1 llm-common workstream (contracts + release)
Epic: `llm-common-cmm`
- `llm-common-cmm.1` Docs: llm-common workstream spec
- `llm-common-cmm.2` Contract: ToolResult + provenance
- `llm-common-cmm.3` Contract: StreamEvent schema (optional / post‑MVP)
- `llm-common-cmm.4` Release + pinning plan (apps + scripts)
- `llm-common-cmm.5` Docs: Dexter audit refresh + rewrite spec updates (this PR)
- `llm-common-cmm.6` Chore: version/tag alignment
- `llm-common-cmm.7` Task: publish JSON Schema artifacts in releases
- `llm-common-cmm.8` Task: MessageHistory helper (Dexter-style)
- `llm-common-cmm.9` Docs: bundle Dexter ports (glm-4.5-air tool selection, context pointers, message history)
- `llm-common-cmm.10` Feature: Dexter ports bundle (llm-common primitives)
- `llm-common-cmm.11` Task: tool selection helper + model config (glm-4.5-air default)
- `llm-common-cmm.12` Task: context pointer store + relevance selection library

**Key deliverable:** a tagged llm-common release that both product repos pin to (no branch pins).

### 7.2 Prime Radiant workstream (canonical frontend + advisor contract)
Epic: `bd-yn9g`
- `bd-yn9g.1` Docs: canonical spec + mirrored copies
- `bd-yn9g.2` Frontend: unify chat runtime (structured MVP)
- `bd-yn9g.3` Backend/API: freeze advisor contract
- `bd-yn9g.4` Regression harness: minimal contract + E2E smoke test
- `bd-yn9g.5` Docs: Dexter audit refresh + rewrite spec updates (this PR)
- `bd-yn9g.6` Task: pin llm-common to tag
- `bd-yn9g.7` Task: remove SSE/DeepChat path (MVP structured-only)
- `bd-yn9g.8` Task: evidence envelope contract + UI
- `bd-yn9g.9` Docs: bundle Dexter ports (glm-4.5-air tool selection, context pointers, message history)
- `bd-yn9g.10` Feature: Dexter ports bundle (Prime integration)
- `bd-yn9g.11` Task: tool selection small model (glm-4.5-air)
- `bd-yn9g.12` Task: context pointer store + relevance selection

### 7.3 Affordabot workstream (SEO-first Next.js frontend)
Epic: `affordabot-ahpb`
- `affordabot-ahpb.1` Docs: affordabot migration plan + mirrored spec
- `affordabot-ahpb.2` Feature: build Prime-stack frontend inside affordabot (**DEPRECATED**; Affordabot remains Next.js due to majority-public SEO needs)
- `affordabot-ahpb.3` Task: align affordabot backend API contract to shared frontend
- `affordabot-ahpb.4` Regression harness: minimal contract + E2E smoke test
- `affordabot-ahpb.5` Docs: Dexter audit refresh + rewrite spec updates (this PR)
- `affordabot-ahpb.6` Task: frontend-v2 baseline + cutover plan (**DEPRECATED**; do not deprecate Next frontend)
- `affordabot-ahpb.7` Task: provenance envelope contract (EvidenceEnvelope + evidence-id citations)
- `affordabot-ahpb.8` Docs: bundle Dexter ports (glm-4.5-air tool selection, context pointers, message history)
- `affordabot-ahpb.9` Feature: Dexter ports bundle (Affordabot integration)
- `affordabot-ahpb.10` Task: tool selection small model (glm-4.5-air)
- `affordabot-ahpb.11` Task: context pointer store + relevance selection

Jules-ready: `affordabot-ahpb.10`, `affordabot-ahpb.11` (see `docs/bd-affordabot-ahpb/JULES_DISPATCH.md`)

## 8) Cross‑Repo Dependency Map (documented; not enforceable in Beads DB)

Hard dependencies:
1. `llm-common-cmm.4` (release + pinning) should land **before** major implementation work in `bd-yn9g.2` and `affordabot-ahpb.2`.

Soft dependencies:
- Provenance contract (`llm-common-cmm.2`) before any post‑MVP citations UI.

## 9) Open Questions (need explicit decisions before implementation)

1. Do we keep MUI long-term, or migrate to a unified shadcn/tailwind design system?
2. Do we want one monorepo shared UI package, or cross-repo copy + later extraction?
3. Auth strategy for unified frontend:
   - shared Clerk config across both products?
   - or product-specific auth adapters?
4. Are there any affordabot-specific UI workflows that must survive the big‑bang cutover (admin pages, scraping workflows)?
