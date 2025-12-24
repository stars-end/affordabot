# Dexter-LLM-Common Integration Plan
**ID:** dexter-llm-common-1220  
**Created:** 2025-12-20 15:05 PST  
**Updated:** 2025-12-20 15:13 PST

---

## Executive Summary

**Key Discovery:** llm-common `agents/` already implements 80% of the proposed Dexter port, including `ToolResult.source_urls` for provenance. Many Beads issues are **already complete or near-complete**.

**NEW (Second Pass):** Three modules are MISSING and can be fully, independently implemented:
1. `MessageHistory` - Multi-turn conversation memory (190 lines)
2. `formatToolResult()` - Provenance envelope helper
3. `LLM-based context selection` - Enhanced `selectRelevantContexts()`

---

## Part 1A: NEW Discoveries (Second Pass)

### 1. MessageHistory Class (MISSING from llm-common!)
**Source:** `dexter/src/utils/message-history.ts` (190 lines)

Key features:
- In-memory conversation history for multi-turn
- LLM-generated summaries per turn (`generateSummary()`)
- LLM-based relevance selection (`selectRelevantMessages()`)
- Caching of relevance results by query hash
- Separate formats for planning vs answer generation

**Fully self-contained:** Can be ported directly to `llm_common/agents/message_history.py`

### 2. formatToolResult() Helper (MISSING)
**Source:** `dexter/src/tools/types.ts` (13 lines)

```typescript
export function formatToolResult(data: unknown, sourceUrls?: string[]): string {
  const result: ToolResult = { data };
  if (sourceUrls?.length) {
    result.sourceUrls = sourceUrls;
  }
  return JSON.stringify(result);
}
```

**Purpose:** Standardizes provenance envelope across all tools.

### 3. Enhanced ToolContextManager (PARTIAL)
**Source:** `dexter/src/utils/context.ts` (263 lines)

Missing features in llm-common:
- `selectRelevantContexts()` - LLM-based context selection before answer
- `getToolDescription()` - Deterministic summary generation
- `hashQuery()` - Query-based context grouping

### 4. AgentCallbacks Protocol (PARTIAL)
**Source:** `dexter/src/agent/agent.ts:37-52`

llm-common has execution but not observability callbacks:
- `onIterationStart`, `onThinking`, `onToolCallsStart`
- `onToolCallComplete`, `onIterationComplete`
- `onAnswerStart`, `onAnswerStream`

### 5. Agent Loop (Complete Reference)
**Source:** `dexter/src/agent/agent.ts:119-252`

```typescript
// Core agent loop - port this pattern to Python
async run(query: string, messageHistory?: MessageHistory): Promise<string> {
  const summaries: ToolSummary[] = [];
  const queryId = this.toolContextManager.hashQuery(query);
  let finishReason: string | null = null;

  // Create finish tool
  const finishTool = createFinishTool((reason) => { finishReason = reason; });
  const allTools = [...TOOLS, finishTool];
  const toolSchemas = this.buildToolSchemas();

  // Select relevant conversation history (done once at start)
  let conversationContext: string | undefined;
  if (messageHistory?.hasMessages()) {
    const relevantMessages = await messageHistory.selectRelevantMessages(query);
    conversationContext = messageHistory.formatForPlanning(relevantMessages);
  }

  // Main loop
  for (let i = 0; i < this.maxIterations; i++) {
    this.callbacks.onIterationStart?.(i + 1);
    
    const response = await callLlm(userPrompt, { systemPrompt, tools: allTools });
    const thought = this.extractThought(response);
    if (thought) this.callbacks.onThinking?.(thought);
    
    const toolCalls = response.tool_calls || [];
    if (toolCalls.find(tc => tc.name === 'finish') || toolCalls.length === 0) break;
    
    // Execute tools in parallel
    const results = await Promise.all(toolCalls.map(async (tc) => {
      const result = await this.toolMap.get(tc.name)!.invoke(tc.args);
      return this.toolContextManager.saveAndGetSummary(tc.name, tc.args, result, queryId);
    }));
    
    summaries.push(...results.filter(Boolean));
    this.callbacks.onIterationComplete?.(i + 1);
  }

  return this.generateAnswer(query, queryId, messageHistory);
}
```

### 6. Context Selection (Complete Reference)
**Source:** `dexter/src/utils/context.ts:218-260`

```typescript
async selectRelevantContexts(query: string, availablePointers: ContextPointer[]): Promise<string[]> {
  if (availablePointers.length === 0) return [];

  const pointersInfo = availablePointers.map((ptr, i) => ({
    id: i,
    toolName: ptr.toolName,
    toolDescription: ptr.toolDescription,
    args: ptr.args,
  }));

  const prompt = `
    Original user query: "${query}"
    Available tool outputs:
    ${JSON.stringify(pointersInfo, null, 2)}
    
    Select which tool outputs are relevant for answering the query.
    Return { "context_ids": [0, 2, 5] } with IDs of relevant outputs.
  `;

  const response = await callLlm(prompt, {
    systemPrompt: CONTEXT_SELECTION_SYSTEM_PROMPT,
    outputSchema: SelectedContextsSchema,
  });

  return (response.context_ids || [])
    .filter(idx => idx >= 0 && idx < availablePointers.length)
    .map(idx => availablePointers[idx].filepath);
}
```

---

## Part 1B: Existing Infrastructure Gap Analysis

### llm-common/agents/ (Already Implemented)
| Component | File | Status | Dexter Equivalent |
|-----------|------|--------|-------------------|
| `TaskPlanner` | `planner.py` | ✅ Complete | `task-planner.ts` |
| `AgenticExecutor` | `executor.py` | ✅ Complete | `task-executor.ts` |
| `ToolContextManager` | `tool_context.py` | ✅ Complete | `utils/context.ts` |
| `ToolResult.source_urls` | `tools/__init__.py:55-61` | ✅ Complete | `ToolResult.sourceUrls` |
| `BaseTool` | `tools/__init__.py` | ✅ Complete | LangChain tools |
| `ToolRegistry` | `tools/__init__.py` | ✅ Complete | Dynamic tool binding |
| `AnswerSynthesizer` | `synthesizer.py` | ✅ Complete | `answer-generator.ts` |
| `ResearchAgent` | `research_agent.py` | ✅ Complete | `Agent` class |

### Prime-Radiant (Already Implemented)
| Component | File | Status |
|-----------|------|--------|
| `EvidenceItem` | `services/provenance/models.py` | ✅ Complete |
| `validate_citations()` | `services/provenance/validate.py` | ✅ Complete |
| `MetricResult.sources` | `packages/metrics_registry/types.py:116-125` | ✅ Complete |
| `MetricDefinition.evidence_*` | `types.py:53-57` | ✅ Complete |

### Affordabot (Gaps Identified)
| Component | Status | Gap |
|-----------|--------|-----|
| `ImpactEvidence` | ⚠️ Partial | Not unified with llm-common `ToolResult` |
| Research Tools (Z.ai) | ⚠️ Partial | Exists but not wrapped as `BaseTool` |
| Cost-of-Living prompts | ⚠️ Missing | Domain-specific prompts not ported |

---

## Part 2: Citations/Provenance Deep Dive

### Dexter Pattern (Source: `agent.ts:355-375`)
```typescript
// Tool results include sourceUrls
const sourceUrls = ctx.sourceUrls || [];
const sourceLine = sourceUrls.length > 0 
  ? `\nSource URLs: ${sourceUrls.join(', ')}` : '';

// Answer prompt includes citation requirement
allSources.length > 0 
  ? `Available sources for citation:\n${JSON.stringify(allSources)}` 
  : ''
```

### Prime-Radiant (MORE Advanced than Dexter!)
```python
# MetricDefinition with provenance fields (types.py:53-57)
evidence_kind: str = "internal"  # "internal", "url", "derived"
evidence_label: str = "Internal Data"
evidence_url_template: Optional[str] = None
propagate_upstream_evidence: bool = True

# Programmatic citation validation (validate.py)
def validate_citations(available: List[EvidenceItem], cited_ids: List[str]):
    available_ids = {s.id for s in available}
    return [cid for cid in cited_ids if cid not in available_ids]
```

### Affordabot Application
Policy analysis requires stricter provenance than financial research:

| Use Case | Dexter | Prime Radiant | Affordabot (Target) |
|----------|--------|---------------|---------------------|
| Evidence type | URL only | `internal/url/derived` | `legislation/municipal_code/scraped/derived` |
| Validation | Prompt-only | Programmatic | Programmatic + Review step |
| Citation binding | Per-answer | Per-metric | Per-claim |

### Unified Provenance Model (llm-common)
```python
# Proposed: llm_common/agents/provenance.py
@dataclass
class EvidenceEnvelope:
    id: str
    kind: str  # "url", "internal", "legislation", "derived"
    label: str
    source_urls: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

# Extend existing ToolResult
@dataclass
class ToolResult:
    success: bool
    data: Any = None
    source_urls: list[str] = field(default_factory=list)  # Already exists!
    evidence: list[EvidenceEnvelope] = field(default_factory=list)  # NEW
    error: str | None = None
```

---

## Part 3: Jules-Ready Self-Contained Tasks

### Criteria for Jules Dispatch
- ✅ Self-contained (no cross-repo deps)
- ✅ Clear acceptance criteria
- ✅ Testable in isolation
- ✅ < 2 hours estimated

### Approved for Jules (8 tasks)

| Task | Repo | Scope | Est. |
|------|------|-------|------|
| `Add EvidenceEnvelope to llm-common` | llm-common | New file `agents/provenance.py` | 1h |
| `Extend ToolResult with evidence field` | llm-common | Modify `tools/__init__.py` | 30m |
| `Add validate_citations to llm-common` | llm-common | Port from prime-radiant | 1h |
| `Wrap Z.ai as BaseTool` | affordabot | New `tools/zai_search.py` | 1h |
| `Wrap Scraper as BaseTool` | affordabot | New `tools/scraper.py` | 1h |
| `Policy analysis prompts` | affordabot | New `prompts/policy.py` | 1.5h |
| `Port evidence validation` | prime-radiant | Use llm-common impl | 30m |
| `Close completed Beads issues` | both | Housekeeping | 30m |

---

## Part 4: llm-common vs Repo-Specific Boundaries

### llm-common (Domain-Agnostic Core)
```
llm_common/agents/
├── tools/
│   ├── __init__.py      # BaseTool, ToolResult, ToolRegistry ✅
│   └── provenance.py    # EvidenceEnvelope, validate_citations NEW
├── planner.py           # TaskPlanner ✅
├── executor.py          # AgenticExecutor ✅
├── tool_context.py      # ToolContextManager ✅
├── synthesizer.py       # AnswerSynthesizer ✅
└── schemas.py           # ExecutionPlan, ToolCall ✅
```

### Affordabot (Domain-Specific)
```
affordabot/backend/
├── agents/
│   ├── tools/
│   │   ├── zai_search.py       # Z.ai web search tool NEW
│   │   ├── scraper.py          # Universal scraper tool NEW
│   │   └── retriever.py        # RAG retriever tool NEW
│   ├── prompts/
│   │   └── policy.py           # Cost-of-living prompts NEW
│   └── policy_agent.py         # Domain-specific orchestration NEW
└── services/
    └── search_pipeline_service.py  # Wire agents ✅
```

### Prime-Radiant (Domain-Specific)
```
prime-radiant-ai/backend/
├── agents/
│   ├── tools/
│   │   └── metrics.py          # MetricsRegistry as tools
│   ├── prompts/
│   │   └── portfolio.py        # Finance prompts
│   └── financial_agent.py      # Domain orchestration
└── packages/
    └── metrics_registry/       # Keep, use llm-common provenance
```

### Hybrid Integration Pattern
```python
# affordabot/backend/agents/tools/zai_search.py
from llm_common.agents.tools import BaseTool, ToolMetadata, ToolResult
from llm_common.agents.provenance import EvidenceEnvelope

class ZaiSearchTool(BaseTool):
    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="zai_search",
            description="Search web via Z.ai for policy research",
            parameters=[...]
        )
    
    async def execute(self, **kwargs) -> ToolResult:
        results = await self.client.search(kwargs["query"])
        return ToolResult(
            success=True,
            data=results,
            source_urls=[r.url for r in results],
            evidence=[
                EvidenceEnvelope(
                    id=str(uuid4()),
                    kind="url",
                    label="Web Search",
                    source_urls=[r.url for r in results]
                )
            ]
        )
```

---

## Part 5: Beads Issue Reconciliation

### Issues to CLOSE (Already Implemented)
| ID | Title | Reason |
|----|-------|--------|
| `affordabot-3q2.3.1` | TaskPlanner & AgenticExecutor | ✅ Already in llm-common |
| `affordabot-q4x` | Port Dexter Context | ✅ `ToolContextManager` exists |
| `affordabot-mil` | Dexter-style Orchestration | ✅ `AgenticExecutor` exists |

### Issues to REDUCE Scope
| ID | Title | New Scope |
|----|-------|-----------|
| `affordabot-3q2.3` | Port Dexter Agent Core | Only: add `EvidenceEnvelope` |
| `affordabot-1mz` | DEXTER_REFRESH | Only: integration verification |
| `affordabot-s3q` | Research Tools | Only: wrap as `BaseTool` |

### Issues to KEEP (New Work Required)
| ID | Title | Scope |
|----|-------|-------|
| `affordabot-3q2.3.2` | Cost of Living Integration | Domain prompts + verification |
| `affordabot-9g6` | Admin Dashboard + Dexter | Wire policy_agent to UI |

---

## Part 6: Fully Self-Contained Implementations

These modules have **complete specifications** and can be implemented independently:

### A. MessageHistory (llm-common) — Jules Ready ✅
**Port:** `dexter/src/utils/message-history.ts` → `llm_common/agents/message_history.py`

```python
# Target: llm_common/agents/message_history.py (~150 lines)
class MessageHistory:
    """Multi-turn conversation memory with LLM-based summarization."""
    
    async def add_message(self, query: str, answer: str) -> None:
        """Add turn with auto-generated summary."""
    
    async def select_relevant_messages(self, current_query: str) -> list[Message]:
        """LLM-selects relevant prior turns for context."""
    
    def format_for_planning(self, messages: list[Message]) -> str:
        """Lightweight format: queries + summaries only."""
    
    def format_for_answer(self, messages: list[Message]) -> str:
        """Full format: queries + complete answers."""
```

**Acceptance Criteria:**
- [ ] Port all methods from Dexter
- [ ] Use `llm_common.LLMClient` for summarization
- [ ] Add unit tests with mocked LLM
- [ ] Export from `__init__.py`

---

### B. Enhanced ToolContextManager (llm-common) — Jules Ready ✅
**Enhance:** `llm_common/agents/tool_context.py`

```python
# Add to existing ToolContextManager:

async def select_relevant_contexts(
    self, query: str, pointers: list[ContextPointer]
) -> list[str]:
    """LLM-based selection of relevant contexts for answer generation."""

def get_tool_description(self, tool_name: str, args: dict) -> str:
    """Deterministic summary: 'AAPL income statements (quarterly) - 4 periods'."""

def hash_query(self, query: str) -> str:
    """MD5 hash for query-based context grouping."""
```

**Acceptance Criteria:**
- [ ] Add 3 methods to existing class
- [ ] Match Dexter behavior exactly
- [ ] Add unit tests

---

### C. AgentCallbacks Protocol (llm-common) — Jules Ready ✅
**New file:** `llm_common/agents/callbacks.py`

```python
# Target: llm_common/agents/callbacks.py (~50 lines)
from dataclasses import dataclass
from typing import Callable, Any, Protocol

@dataclass
class ToolCallInfo:
    name: str
    args: dict[str, Any]

@dataclass
class ToolCallResult:
    name: str
    args: dict[str, Any]
    summary: str
    success: bool

class AgentCallbacks(Protocol):
    on_iteration_start: Callable[[int], None] | None
    on_thinking: Callable[[str], None] | None
    on_tool_calls_start: Callable[[list[ToolCallInfo]], None] | None
    on_tool_call_complete: Callable[[ToolCallResult], None] | None
    on_iteration_complete: Callable[[int], None] | None
    on_answer_start: Callable[[], None] | None
    on_answer_stream: Callable[[Any], None] | None
```

**Acceptance Criteria:**
- [ ] Create callbacks protocol
- [ ] Wire into `AgenticExecutor`
- [ ] Export from `__init__.py`

---

## Part 7: Recommended Workflow

### Phase 1: Foundation (Days 1-2) — Jules Parallel
```
Jules 1 (llm-common):
├── Add EvidenceEnvelope to agents/provenance.py
├── Extend ToolResult with evidence field
└── Add validate_citations, get_valid_citations

Jules 2 (affordabot):
├── Create agents/tools/zai_search.py (BaseTool wrapper)
├── Create agents/tools/scraper.py (BaseTool wrapper)
└── Create agents/prompts/policy.py
```

### Phase 2: Integration (Days 3-4) — Human/Agent
```
├── Wire PolicyAgent into SearchPipelineService
├── Update Glass Box UI to show evidence
├── Verify E2E with cost-of-living query
└── Close Beads issues
```

### Phase 3: Prime-Radiant Sync (Day 5)
```
├── Replace local provenance with llm-common types
├── Verify MetricResult.sources compatibility
└── Update llm-common to v0.5.0
```

---

## Part 7: Decision Required

1. **Approve issue closures** for already-implemented work?
2. **Dispatch Jules tasks** for parallel execution?
3. **Confirm llm-common v0.5.0 release** after Phase 1?

---

## Part 8: Frontend/UI Integration Track (NEW)

> **How Deep Chat UI workflow fits with this plan**

### 8.1 Relationship to Backend Work

The Dexter-LLM-Common plan (Parts 1-7) focuses on **backend agent infrastructure**:
- `llm_common/agents/` - Core agent patterns
- `EvidenceEnvelope` - Provenance model
- Jules parallel tasks - Backend tools

The **UI workflow** (Deep Chat) is the **consumer** of this infrastructure:

```
┌─────────────────────────────────────────────────────────────┐
│                    Full Integration Stack                    │
├─────────────────────────────────────────────────────────────┤
│  FRONTEND (Deep Chat)                                        │
│  └─── /api/chat SSE endpoint                                │
│       └─── AgenticExecutor (Phase 1-2 work)                 │
│            └─── BaseTool wrappers (Jules tasks)             │
│                 └─── EvidenceEnvelope (Part 3)              │
│                      └─── ToolResult.source_urls (existing) │
└─────────────────────────────────────────────────────────────┘
```

### 8.2 Sequencing: Backend Before Frontend

**UI depends on backend being ready:**

| UI Feature | Backend Dependency |
|------------|-------------------|
| Streaming responses | `AgenticExecutor` async generator |
| Provenance display | `EvidenceEnvelope` from ToolResult |
| Tool call visualization | `AgentCallbacks` protocol |
| Multi-turn memory | `MessageHistory` class |

**Therefore:** Backend Phase 1-2 should run **first or parallel** with UI prototyping.

### 8.3 Updated Timeline (Integrated)

```
Week 1: Foundation
┌──────────────────────────────────────────────────────────────┐
│ Backend (Jules Parallel)          │ Frontend (Prime-Radiant) │
├───────────────────────────────────┼──────────────────────────┤
│ Day 1-2:                          │ Day 1-2:                 │
│ • EvidenceEnvelope (llm-common)   │ • Deep Chat prototype    │
│ • Extend ToolResult               │ • MUI theme bridge       │
│ • validate_citations()            │ • Mock SSE endpoint      │
├───────────────────────────────────┼──────────────────────────┤
│ Day 3-4:                          │ Day 3-4:                 │
│ • ZaiSearchTool (affordabot)      │ • Wire real SSE endpoint │
│ • ScraperTool (affordabot)        │ • Provenance HTML        │
│ • policy.py prompts               │ • Test with real agent   │
└───────────────────────────────────┴──────────────────────────┘

Week 2: Integration
┌──────────────────────────────────────────────────────────────┐
│ Backend                           │ Frontend                 │
├───────────────────────────────────┼──────────────────────────┤
│ Day 5-6:                          │ Day 5-6:                 │
│ • MessageHistory (llm-common)     │ • Multi-turn UI          │
│ • AgentCallbacks (llm-common)     │ • Thinking indicator     │
│ • PolicyAgent (affordabot)        │ • Tool call display      │
├───────────────────────────────────┼──────────────────────────┤
│ Day 7:                            │ Day 7:                   │
│ • E2E verification                │ • Shared component       │
│ • Close Beads issues              │ • Port to affordabot     │
└───────────────────────────────────┴──────────────────────────┘

Week 3: Stack Migration + Polish
┌──────────────────────────────────────────────────────────────┐
│ affordabot Migration              │ UI Finalization          │
├───────────────────────────────────┼──────────────────────────┤
│ • Vite + MUI setup                │ • Shared AgentChat       │
│ • Port Next.js pages              │ • Theme consistency      │
│ • Update routing                  │ • Glass Box integration  │
└───────────────────────────────────┴──────────────────────────┘
```

### 8.4 SSE Endpoint: Bridge Point

**This is where backend and frontend meet:**

```python
# backend/api/routes/chat.py (NEW - Week 1 Day 3)
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from llm_common.agents.executor import AgenticExecutor
from llm_common.agents.callbacks import AgentCallbacks

router = APIRouter()

@router.post("/api/chat")
async def chat(request: ChatRequest):
    callbacks = StreamingCallbacks()  # Implements AgentCallbacks
    executor = AgenticExecutor(tools=TOOLS, callbacks=callbacks)
    
    async def generate():
        async for event in executor.run_stream(request.messages):
            yield f"data: {json.dumps({
                'type': event.type,  # 'thinking', 'tool_call', 'text', 'sources'
                'text': event.text,
                'sources': [e.dict() for e in event.evidence]  # EvidenceEnvelope!
            })}\n\n"
    
    return StreamingResponse(generate(), media_type="text/event-stream")
```

### 8.5 Deep Chat Handler: UI Integration

```typescript
// frontend/src/components/AgentChat.tsx (NEW - Week 1 Day 1-2)
chatRef.current.connect = {
  handler: (body, signals) => {
    fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ messages: conversationHistory }),
    }).then(async response => {
      const reader = response.body.getReader();
      signals.onOpen();
      
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        
        const event = JSON.parse(decoder.decode(value).replace('data: ', ''));
        
        switch (event.type) {
          case 'thinking':
            setThinkingText(event.text);  // Show thinking indicator
            break;
          case 'tool_call':
            setToolCalls(prev => [...prev, event]);  // Show tool usage
            break;
          case 'text':
            signals.onResponse({ text: event.text });  // Stream to bubble
            break;
          case 'sources':
            setSources(event.sources);  // Store for provenance panel
            break;
        }
      }
      signals.onClose();
    });
  }
};
```

### 8.6 Feature Dependencies Matrix

| UI Feature | Backend Component | Status |
|------------|-------------------|--------|
| Basic streaming | `AgenticExecutor` | ✅ Exists |
| Provenance panel | `EvidenceEnvelope` | 📋 Part 3 |
| Thinking indicator | `AgentCallbacks.on_thinking` | 📋 Part 6C |
| Tool call display | `AgentCallbacks.on_tool_call` | 📋 Part 6C |
| Multi-turn memory | `MessageHistory` | 📋 Part 6A |
| Context selection | `selectRelevantContexts` | 📋 Part 6B |

### 8.7 Effort Summary

| Track | Week 1 | Week 2 | Week 3 | Total |
|-------|--------|--------|--------|-------|
| Backend (llm-common) | 8h | 6h | 2h | 16h |
| Backend (affordabot) | 4h | 4h | - | 8h |
| Frontend (Deep Chat) | 6h | 4h | 2h | 12h |
| Stack Migration | - | - | 8h | 8h |
| **Total** | **18h** | **14h** | **12h** | **44h** |

### 8.8 Jules Task Alignment

**Backend Jules tasks (Part 3) unblocked by:**
- Nothing - can start immediately

**Frontend work blocked by:**
- Part 3 (`EvidenceEnvelope`) for provenance display
- Part 6C (`AgentCallbacks`) for thinking/tool indicators
- Part 6A (`MessageHistory`) for multi-turn

**Recommended:** Start Jules backend tasks + Deep Chat prototype in parallel.

---

## Part 9: Testing and Verification Strategy

### 9.1 Existing Test Infrastructure

| Repo | Test Files | Framework | Targets |
|------|------------|-----------|---------|
| **llm-common** | 9 | pytest, pytest-asyncio | `poetry run pytest` |
| **affordabot** | 21 | pytest + Playwright | `make test`, `make e2e`, `make ci-lite` |
| **prime-radiant** | 42 | pytest + Playwright | `make test`, `make test-e2e`, `make ci-lite` |

### 9.2 Testing Tiers

```
Tier 1: Unit Tests (Fast, Mocked)
├── llm-common: agents/, tools/, provenance
├── affordabot: services/*, routers/*
└── prime-radiant: services/*, unit/*

Tier 2: Integration Tests (DB + Services)
├── llm-common: N/A (no DB)
├── affordabot: test_integration_flows.py
└── prime-radiant: tests/integration/*

Tier 3: E2E Tests (Full Stack)
├── llm-common: N/A
├── affordabot: Playwright (frontend/)
└── prime-radiant: Playwright (frontend/)
```

### 9.3 Component-Specific Tests (NEW Work)

#### A. llm-common Tests (Part 3, 6)

```python
# tests/agents/test_provenance.py (NEW)
def test_evidence_envelope_creation():
    """EvidenceEnvelope has required fields."""
    
def test_tool_result_with_evidence():
    """ToolResult can include evidence list."""

def test_validate_citations_finds_invalid():
    """validate_citations returns invalid IDs."""

# tests/agents/test_message_history.py (NEW)
@pytest.mark.asyncio
async def test_message_history_add_and_retrieve():
    """Messages are stored and retrievable."""

@pytest.mark.asyncio
async def test_select_relevant_messages(mock_llm):
    """LLM-based selection returns subset."""

# tests/agents/test_callbacks.py (NEW)
def test_agent_callbacks_protocol():
    """AgentCallbacks protocol is implementable."""

def test_executor_calls_callbacks(mock_callbacks):
    """AgenticExecutor invokes all callback hooks."""
```

**Command:** `cd llm-common && poetry run pytest tests/agents/ -v`

#### B. affordabot Tests (Part 4)

```python
# tests/services/llm/test_policy_agent.py (NEW)
@pytest.mark.asyncio
async def test_policy_agent_uses_tools(mock_tools):
    """PolicyAgent invokes registered tools."""

@pytest.mark.asyncio
async def test_policy_agent_returns_evidence():
    """PolicyAgent responses include EvidenceEnvelope."""

# tests/tools/test_zai_search.py (NEW)
@pytest.mark.asyncio
async def test_zai_search_tool_returns_urls(mock_zai):
    """ZaiSearchTool populates source_urls."""

# tests/routers/test_chat_endpoint.py (NEW)
@pytest.mark.asyncio
async def test_chat_endpoint_streams(test_client):
    """POST /api/chat returns SSE stream."""
```

**Command:** `cd affordabot/backend && poetry run pytest tests/ -v`

#### C. prime-radiant Tests (Part 5)

```python
# tests/unit/test_provenance_migration.py (NEW)
def test_metric_result_uses_llm_common_evidence():
    """MetricResult.sources maps to EvidenceEnvelope."""

# tests/e2e/test_chat_ui.py (NEW - Playwright)
async def test_chat_sends_and_receives(page):
    """Deep Chat component sends message and displays response."""

async def test_provenance_panel_shows_sources(page):
    """Sources panel appears after response with citations."""
```

**Command:** `cd prime-radiant-ai && make test`

### 9.4 Integration Verification Matrix

| Scenario | Test Location | Backend Components | Frontend Components |
|----------|---------------|-------------------|---------------------|
| Tool returns provenance | llm-common unit | `ToolResult.evidence` | - |
| Agent uses tool | affordabot unit | `PolicyAgent` + `BaseTool` | - |
| SSE streams correctly | affordabot integration | `/api/chat` endpoint | - |
| Chat UI renders stream | prime-radiant e2e | Backend stub | Deep Chat |
| Sources display | prime-radiant e2e | Real backend | SourcesPanel |

### 9.5 Cross-Repo Verification

```bash
# Step 1: llm-common (foundation)
cd ~/llm-common
poetry run pytest tests/agents/ -v
# ✅ All 15+ agent tests pass

# Step 2: affordabot (consumer)
cd ~/affordabot/backend
poetry run pytest tests/services/llm/ -v
poetry run pytest tests/routers/test_chat_endpoint.py -v
# ✅ PolicyAgent + SSE endpoint tests pass

# Step 3: prime-radiant (consumer)
cd ~/prime-radiant-ai
make ci-lite
# ✅ Unit tests + lint pass

# Step 4: E2E (full stack)
cd ~/prime-radiant-ai
make test-e2e
# ✅ Playwright tests pass
```

### 9.6 CI Pipeline Integration

```yaml
# .github/workflows/ci.yml (all 3 repos have this)

# llm-common CI
- name: Run tests
  run: poetry run pytest tests/ -v --cov=llm_common

# affordabot CI
- name: Backend tests
  run: cd backend && poetry run pytest tests/ -v

# prime-radiant CI
- name: CI Lite (lint + unit)
  run: make ci-lite
- name: E2E tests
  run: make smoke-e2e  # or full test-e2e
```

### 9.7 Verification Checkpoints

| Checkpoint | Trigger | Acceptance Criteria |
|------------|---------|---------------------|
| **CP1: llm-common** | Part 3, 6 complete | 66+ tests pass, new 15+ pass |
| **CP2: affordabot backend** | Part 4 complete | All pytest pass |
| **CP3: SSE endpoint** | Part 8.4 complete | Manual curl + unit test |
| **CP4: Deep Chat prototype** | Part 8.5 complete | Manual UI test |
| **CP5: Integration** | Week 2 Day 7 | E2E Playwright pass |
| **CP6: Stack migration** | Week 3 complete | affordabot CI green |

### 9.8 Manual Verification Steps

```bash
# Deep Chat smoke test (Week 1 Day 3)
cd prime-radiant-ai
make dev  # Start frontend + backend
# Open http://localhost:5173/chat
# 1. Type "What is the current price of AAPL?"
# 2. Verify streaming response appears
# 3. Verify sources panel populates

# PolicyAgent smoke test (Week 2)
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "What are San Jose housing policies?"}]}' \
  --no-buffer
# Verify SSE chunks with type: thinking, tool_call, text, sources
```

### 9.9 Test Effort Estimate

| Repo | New Tests | Effort |
|------|-----------|--------|
| llm-common | ~15 tests | 4h |
| affordabot | ~10 tests | 3h |
| prime-radiant | ~5 tests + 2 e2e | 3h |
| **Total** | **~30 tests** | **10h** |

---

1. **Approve issue closures** for already-implemented work?
2. **Dispatch Jules tasks** for parallel backend execution?
3. **Confirm llm-common v0.5.0 release** after Phase 1?
4. **NEW: Confirm parallel UI track** with Deep Chat prototyping?
5. **NEW: Confirm stack migration timing** (Week 3)?
