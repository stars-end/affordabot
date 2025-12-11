# Dexter Integration Plan: Agentic Orchestration for Affordabot

## 1. Overview & Objective
Transform Affordabot's legislative analysis pipeline from a linear script (`AnalysisPipeline`) into a robust, agentic system by porting the proven architecture of **Dexter** (Typescript agent). This will enable:
- **Dynamic Research**: Intelligent queries to Z.ai/Universal Scraper based on intermediate findings.
- **Complex Reasoning**: Multi-step task planning and execution for thorough "Research -> Generate -> Review" cycles.
- **Unified Architecture**: Sharing core agent implementation between `affordabot` and `prime-radiant-ai` via `llm-common`.
- **Full Observability**: Admin Dashboard visibility into agent thought processes, tool usage, and context states.

## 2. Architecture: The "Dexter Pattern"

We will replicate Dexter's "Planner-Executor" pattern in Python, adapted for our specific "Research -> Generate -> Review" domain.

### Core Components to Port
1.  **`ToolContextManager` (The Brain's Working Memory)**
    *   **Role**: Manages the LLM context window. Decides what tool outputs to keep, summarize, or discard.
    *   **Port Target**: `llm_common.agent.context_manager.ToolContextManager`
    *   **Features**:
        *   Filesystem-backed persistence (for resumability).
        *   Smart context pruning (Token counting).
        *   "Keep/Discard" logic for tool results.

2.  **`TaskPlanner` (The Strategist)**
    *   **Role**: Breaks high-level objectives (e.g., "Analyze SB-123") into granular, dependency-aware steps.
    *   **Port Target**: `llm_common.agent.planner.TaskPlanner`
    *   **Inputs**: Bill text, Jurisdiction config, System Prompts.
    *   **Outputs**: A JSON-structured plan (DAG or ordered list).

3.  **`TaskExecutor` (The Doer)**
    *   **Role**: Executes individual steps from the plan using available tools.
    *   **Port Target**: `llm_common.agent.executor.TaskExecutor`
    *   **Loop**: `Think -> Act -> Observe -> Context Update`.

4.  **`Agent` (The Orchestrator)**
    *   **Role**: Wires the components together.
    *   **Port Target**: `llm_common.agent.core.Agent`

## 3. Tool Ecosystem (~/llm-common)

We will wrap existing services as standard **Tools** compatible with the Agent.

*   **`WebSearchTool`**: Wraps `ZaiSearchClient` (already in `llm-common`).
*   **`UniversalScraperTool`**: New tool to query `PostgresDB` (`raw_scrapes` table) for existing content.
*   **`WebReaderTool`**: Wraps `WebReader` (Playwright/trafilatura) for deep reading of URLs found during research.
*   **`KnowledgeBaseTool`**: Wraps `PgVectorBackend` for semantic search over historical analysis/legislation.

## 4. Workstreams & Phases

### Phase A: Core Agent Framework (llm-common)
*   **Task**: Implement `ToolContextManager`, `TaskPlanner`, `TaskExecutor` in `llm_common/agent/`.
*   **Goal**: Generic, project-agnostic agent framework.
*   **Outcome**: Unit-tested Python implementation of Dexter's core logic.

### Phase B: Tool Implementation & Integration
*   **Task**: Wrap Z.ai, Scraper, and VectorDB as `BaseTool` implementations.
*   **Task**: Implement `AffordabotAgent` in `backend/services/llm/agent.py` using `llm-common` framework.
*   **Goal**: The Agent "knows" how to do research.

### Phase C: AnalysisPipeline Refactor
*   **Task**: Replace the hardcoded `AnalysisPipeline.run()` logic with `Agent.run_task()`.
*   **Task**: Map "Research" step to an Agent execution loop focused on information gathering.
*   **Task**: Map "Generate" step to an Agent execution loop focused on synthesis.
*   **Task**: Map "Review" step to a Critic Agent loop.

### Phase D: Admin Dashboard Integration
*   **Task**: Expose Agent internal steps (thoughts, tool calls) to `admin_tasks` table.
*   **Task**: Update Admin UI to visualize the Agent's "Thought Trace" (not just final output).
*   **Goal**: "Glass Box" AI - admins see exactly *why* the agent concluded X about a bill.

## 5. Implementation Details (Python)

### Folder Structure
```
llm-common/
  src/
    agent/
      __init__.py
      core.py          # Agent class
      planner.py       # TaskPlanner
      executor.py      # TaskExecutor
      context.py       # ToolContextManager
      tools/
        base.py        # BaseTool protocol
        search.py      # WebSearchTool
        retrieval.py   # RAG tools
```

### Context Manager Logic (Simplified Port)
```python
class ToolContextManager:
    def add_result(self, tool_name, result):
        # Save full result to disk (JSON/Text)
        # Add summary to active LLM context
        pass
        
    def get_messages(self) -> List[Message]:
        # Return pruned conversation history + active tool context
        pass
```

## 6. Execution Strategy
1.  **Start with Phase A**: Build the engine in `llm-common`. This benefits `prime-radiant-ai` immediately.
2.  **Mock Integration**: Verify the Python Agent works with simple mock tools.
3.  **Pipeline Swap**: Swap the old `AnalysisPipeline` logic with the new Agent logic behind a feature flag (`ENABLE_AGENTIC_PIPELINE`).

## 7. Success Metrics
*   **Resiliency**: Agent recovers from empty search results by trying alternative queries (automatic retry).
*   **Depth**: Research includes citations from multiple sources (Universal Scraper + Z.ai).
*   **Transparency**: Admin UI shows the exact search queries used.
