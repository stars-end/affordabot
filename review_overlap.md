# Analysis: Overlap between Affordabot PolicyAgent/Orchestrator and llm-common

Based on the review of the open questions and an inspection of `~/llm-common`, there is a significant, direct relationship between the two codebases. 

## 1. What's in `llm-common`?
The `llm-common` repository contains the core Agentic engine (`llm_common.agents.*`) that Affordabot's `PolicyAgent` relies on.
- **`AgenticExecutor`:** Executes parallel tool tasks (`llm_common/agents/executor.py`).
- **`ToolRegistry` / `BaseTool`:** The standard interface for `ZaiSearchTool`, `RetrieverTool`, and `ScraperTool` (`llm_common/agents/tools/__init__.py`).
- **`Evidence` / `EvidenceEnvelope`:** The canonical provenance schemas (`llm_common/agents/provenance.py`).
- **`TaskPlanner`:** Plans research iterations.

## 2. Where is the overlap?
The overlap occurs because Affordabot has **two parallel execution paths** for analyzing a bill:

1. **Path A (The Agentic Chat Path - `PolicyAgent`):** 
   - Lives in `backend/agents/policy_agent.py`.
   - Uses the rich `llm-common` tools (Planner, Executor, ContextManager).
   - Generates fully tracked `EvidenceEnvelope` items.
   - **Problem:** It's designed for open-ended queries (`async def analyze(query)`), not structured background bill processing.

2. **Path B (The Deterministic Pipeline - `AnalysisPipeline`):** 
   - Lives in `backend/services/llm/orchestrator.py`.
   - Used for the background, scheduled bill analysis (the California pipeline).
   - It *attempts* to call `PolicyAgent` via `_research_step`, but then flattens the rich provenance data down into a raw text prompt for generation, and throws away the `EvidenceEnvelope` tracking. 

## 3. Recommended Approach (Question 3)
The recommendation in the open questions is absolutely correct: **Option 2 (shared extracted legislation-research service)** is the right path.

*   **Why Option 1 fails:** Trying to shove the entire deterministic `AnalysisPipeline` (which must strictly output Pydantic `LegislationAnalysisResponse` schemas) into the `PolicyAgent` (which is designed for chat-style execution and returns a simple `answer: str` with sources) will destroy the strict schema contracts we need for the database.
*   **Why Option 2 works:** We should extract the *Research Phase* logic (planning the query, selecting tools, calling Z.ai/Retriever via `AgenticExecutor`, and gathering `EvidenceEnvelope` objects) into a shared `LegislationResearchService`. 
    *   `AnalysisPipeline` calls this service, gets `List[EvidenceEnvelope]`, and then uses deterministic LLM calls to generate the `LegislationAnalysisResponse`.
    *   `PolicyAgent` can also call this service if a user asks a chat question about a bill, preserving the same RAG logic.

## Summary of Decisions for the Final Plan
Based on the codebase analysis, the proposed answers to the open questions are completely sound:
1.  **Scope Control:** Platform-wide invalidation, but only California backfill in this epic.
2.  **Quantification Sources:** Enforce a strict "Tier A" requirement (official notes/reports) for outputting percentiles.
3.  **Architecture:** Build a shared extracted research service that leverages `llm-common`'s `AgenticExecutor` and `EvidenceEnvelope` contracts, which both the Chat Agent and the Background Pipeline will consume.
