# Dexter Integration: The "Agentic Core" (affordabot-1mz)

## Objective
Port the `dexter-ts` (TypeScript) agent architecture to `llm-common` (Python) to power Affordabot's "Trust" pillar.
We preserve the **logic** (Planner/Executor separation) but adapt the **implementation** to our Python stack.

## Architecture: The "Two-Step" Pattern
We will implement two core classes in `llm-common`:

### 1. `TaskPlanner` (The "Brain")
*   **Source**: `dexter/src/agent/task-planner.ts`
*   **Logic**:
    1.  Accepts user query.
    2.  Uses LLM (via `instructor` or JSON mode) to generate a structured `ExecutionPlan`.
    3.  Output Schema: `List[PlannedTask]` where each task has `subtasks`.
*   **Python Implementation**:
    *   Use Pydantic models for `ExecutionPlan` and `PlannedTask`.
    *   Prompt: Port `getPlanningSystemPrompt` from Dexter.

### 2. `AgenticExecutor` (The "Hands")
*   **Source**: `dexter/src/agent/task-executor.ts`
*   **Logic**:
    1.  Iterates through `PlannedTask`s.
    2.  For each task, asks LLM to map `subtasks` -> `ToolCall`s.
    3.  Executes tools in parallel.
    4.  Saves context to `ToolContextManager`.
*   **Python Implementation**:
    *   Use `ToolRegistry` (existing in `llm-common`) for tool definitions.
    *   Implement `ToolContextManager` to cache results to disk (Glass Box requirement).

## Deliverables
1.  `llm_common/agents/planner.py`: The `TaskPlanner` class.
2.  `llm_common/agents/executor.py`: The `AgenticExecutor` class.
3.  `llm_common/agents/context.py`: `ToolContextManager`.
4.  **Integration**: `affordabot/backend/services/llm/pipeline.py` uses these classes to run the "Deep Research" flow.

## Verification
*   **Unit Tests**: Mock LLM responses to verify Plan -> Execution flow.
*   **E2E**: `make e2e` runs a "Trust" query and verifies the `execution_plan` is generated and tools are called.
