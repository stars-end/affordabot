# Big‑Bang Frontend Stack Unification (Prime Stack)

**Prime Radiant Epic:** `bd-yn9g`  
**Affordabot Epic:** `affordabot-ahpb`  
**llm-common Epic:** `llm-common-cmm`  

## 0) Purpose

Create a **full big‑bang rewrite specification** to standardize both products on one frontend stack (current target: **Prime Radiant’s stack**) while minimizing regressions and enabling parallel execution by remote agents (Jules).

This spec is designed for a solo developer managing multiple LLM agents: it prioritizes **clear contracts**, **minimized ambiguous integration surfaces**, and **low-cost regression detection**.

> **Canonical copy**: `prime-radiant-ai/docs/bd-yn9g/SPEC.md`.  
> This file is a **mirror** stored in `affordabot` so agents working in this repo have full context.

## 1) MVP Stance (explicit)

**MVP = Structured-only advisor responses.**  
Streaming chat and tool-call visualization are explicitly **post‑MVP** unless needed for a user-facing requirement.

Rationale:
- Structured outputs are easier to validate, diff, regression-test, and safely render for financial advice.
- Streaming adds edge cases (partial output, reconnect, ordering, interruptions) that increase regression risk.

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

Both products use the **Prime Radiant frontend stack**:
- Vite + React Router (SPA)
- MUI (or a clearly-chosen alternative design system)
- One shared “advisor/chat runtime” module (thread state, persistence, error handling)

Affordabot adopts this stack (either in-repo or by extracting a shared frontend package).

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
- **Alternative:** migrate to shadcn/tailwind/Radix and consider assistant-ui.

Tradeoff:
- MUI reduces migration cost (short term).
- assistant-ui/shadcn potentially reduces long-term bespoke chat UX code, but requires re-theming + transport alignment.

### Decision B: Backend chat protocol
- **MVP:** structured JSON only.
- **Post‑MVP:** if streaming, standardize an event schema in llm-common (do not fork per repo).

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

## 7) Workstreams and Beads Issues (Jules-dispatchable)

### 7.1 llm-common workstream (contracts + release)
Epic: `llm-common-cmm`
- `llm-common-cmm.1` Docs: llm-common workstream spec
- `llm-common-cmm.2` Contract: ToolResult + provenance
- `llm-common-cmm.3` Contract: StreamEvent schema (optional / post‑MVP)
- `llm-common-cmm.4` Release + pinning plan (apps + scripts)

**Key deliverable:** a tagged llm-common release that both product repos pin to (no branch pins).

### 7.2 Prime Radiant workstream (canonical frontend + advisor contract)
Epic: `bd-yn9g`
- `bd-yn9g.1` Docs: canonical spec + mirrored copies
- `bd-yn9g.2` Frontend: unify chat runtime (structured MVP)
- `bd-yn9g.3` Backend/API: freeze advisor contract
- `bd-yn9g.4` Regression harness: minimal contract + E2E smoke test

### 7.3 Affordabot workstream (migrate to Prime stack)
Epic: `affordabot-ahpb`
- `affordabot-ahpb.1` Docs: affordabot migration plan + mirrored spec
- `affordabot-ahpb.2` Feature: build Prime-stack frontend inside affordabot
- `affordabot-ahpb.3` Task: align affordabot backend API contract to shared frontend
- `affordabot-ahpb.4` Regression harness: minimal contract + E2E smoke test

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

