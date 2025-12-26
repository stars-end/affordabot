# Dexter Audit (Local `~/dexter`, 2025-12)

**Audited repo:** `~/dexter`  
**Audited commit:** `1ba02db47d5d8647de6f3f2eb17eae0a93d07cef` (“Add insider trades tool”)  
**Goal of this audit:** Extract low-effort, high-leverage patterns we can reuse in the `affordabot-ahpb` big-bang rewrite to reduce regressions and long-term maintenance.

This audit is “what the code actually does today” (not what the README claims).

## 1) High-Level Architecture (What Dexter Actually Implements)

Dexter is a small TypeScript agent + terminal UI (Ink) that runs a 4-phase pipeline:

1. **Understand**: Extract `intent` + `entities` via structured output (`zod` schema).
2. **Plan**: Create a small task graph (2–5 tasks) with:
   - `taskType`: `use_tools` (fetch) vs `reason` (LLM synthesis)
   - `dependsOn`: explicit dependencies so tasks can run in parallel when possible
3. **Execute**:
   - For `use_tools` tasks: select tools with a small model (`gpt-5-mini`), execute tools in parallel, persist tool outputs to disk as contexts.
   - For `reason` tasks: run an LLM prompt consuming previous contexts and task outputs.
4. **Answer**: Stream a final answer and append a “Sources” section if data was used.

Key files:
- `src/agent/task-executor.ts`: dependency-aware task scheduling + parallel execution.
- `src/agent/tool-executor.ts`: tool selection (`gpt-5-mini`) and tool invocation.
- `src/utils/context.ts`: context persistence and provenance extraction.
- `src/utils/message-history.ts`: conversation memory summarization + relevance selection.

## 2) The Most Valuable Pattern: Evidence Plumbing by Construction

Dexter’s “evidence” is minimal but consistent:
- Tools can return `{ data, sourceUrls }` (as a JSON string).
- The context persistence layer extracts and stores `sourceUrls` as metadata.
- The final answer is prompt-contractually required to list “Sources” when data was used.

This is not enough for Affordabot’s trust requirements by itself, but it’s a good backbone:
- it makes provenance a first-class data path rather than a “remember to cite” prompt.

## 3) Conversation Memory (Cheap, Useful, Reusable)

Dexter’s `MessageHistory` pattern is worth copying:
- each answer gets a short summary
- future turns select relevant summaries via structured output
- the agent injects only selected turns into planning/understanding

For Affordabot, this is attractive because it avoids embedding infrastructure while still keeping multi-turn context manageable.

## 4) Reality Checks / Gaps (Important for Reuse)

1. **Context selection exists but is unused**:
   - `ToolContextManager.selectRelevantContexts(...)` exists but is never called.
   - reason tasks currently consume all tool contexts for the query.
2. **No programmatic citation validation** (prompt-only sources policy).
3. **Answer generation is coupled to streaming UI** (`Agent.run()` returns empty string and relies on a callback stream).

## 5) What We Should Reuse in `affordabot-ahpb`

### 5.1 Tool result envelope → unify around llm-common EvidenceEnvelope

Affordabot already uses `llm_common.agents.provenance.EvidenceEnvelope` in several tools.
The big-bang rewrite should strengthen this by making it an invariant:
- every retrieval/research tool returns a structured evidence envelope
- citations/claims reference evidence IDs

### 5.2 Context pointer store for large artifacts

Affordabot has large research artifacts (scrapes, chunks, analyses). Dexter’s context persistence suggests:
- store raw artifacts separately
- keep pointers + summaries in the “active prompt context”

### 5.3 Small-model tool selection

Dexter’s “small model chooses tools” is a practical forcing function to reduce cost and increase predictability.

## 6) Tracking

This audit is intended to directly influence:
- `docs/bd-affordabot-ahpb/SPEC.md` (affordabot workstream spec)
- the canonical spec in Prime: `prime-radiant-ai/docs/bd-yn9g/SPEC.md`

