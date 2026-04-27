# Affordabot Investigation: OpenRouter, z.ai, LiteLLM, llm-common, and OpenRouter Embeddings

Date: 2026-04-28  
Scope: `affordabot` only (`bd-9n1t2.21`)  
Mode: `qa_pass` (evidence-first, no architecture decision)

## Assignment Questions

1. Where does affordabot currently import/use `llm_common`?
2. Does affordabot use LiteLLM directly, indirectly, only as a dependency, or not at all?
3. Where are OpenRouter chat/completion paths configured?
4. Where are OpenRouter embedding paths configured, especially `qwen/qwen3-embedding-8b`?
5. Does affordabot rely on custom `OpenRouterClient`, OpenAI-compatible embeddings, LiteLLM `aembedding`, or multiple inconsistent paths?
6. What env vars are documented or required (`OPENROUTER_API_KEY`, `OPENROUTER_BASE_URL`, model names, site metadata)?
7. What is the safest next work that helps both affordabot and the llm-tldr replacement spike?
8. What should NOT be changed yet?

## Command Log (Exact Commands)

```bash
dx-worktree create bd-9n1t2.21 affordabot
bdx memories OpenRouter --json
bdx memories litellm --json
bdx search "OpenRouter" --label memory --status all --json
bdx search "LiteLLM" --label memory --status all --json
rg --files -g 'AGENTS.md' -g 'agents.md'
sed -n '1,220p' AGENTS.md
rg --files docs | rg 'architecture|BROWNFIELD_MAP|DATA_AND_STORAGE|WORKFLOWS_AND_PATTERNS|README'
sed -n '1,220p' docs/architecture/BROWNFIELD_MAP.md
sed -n '1,220p' docs/architecture/DATA_AND_STORAGE.md
sed -n '1,220p' docs/architecture/README.md
sed -n '1,220p' docs/architecture/WORKFLOWS_AND_PATTERNS.md
codex mcp list
rg -n --hidden --glob '!.git' -e 'llm_common|litellm|LiteLLM|openrouter|OPENROUTER|z\.ai|zai|OPENAI_BASE_URL|qwen/qwen3-embedding-8b|aembedding|embedding'
rg -n "from llm_common|import llm_common|llm_common\." backend --glob '!backend/tests/**'
rg -n "from litellm|import litellm|aembedding\(" backend --glob '!backend/tests/**'
rg -n "OPENROUTER|openrouter|qwen/qwen3-embedding-8b|OPENAI_BASE_URL|OPENAI_API_KEY|ZAI_API_KEY|site_url|site_name" backend --glob '!backend/tests/**'
rg -n "os\.getenv\(\"(OPENROUTER_API_KEY|OPENROUTER_BASE_URL|OPENAI_BASE_URL|OPENAI_API_KEY|ZAI_API_KEY|LLM_MODEL_[A-Z_]+|ZAI_SEARCH_ENDPOINT|WEB_SEARCH_[A-Z_]+|SEARXNG_[A-Z_]+|TAVILY_API_KEY|EXA_API_KEY|OPENROUTER_HTTP_REFERER|OPENROUTER_X_TITLE)" backend --glob '!backend/tests/**'
rg -n "OPENROUTER_BASE_URL|HTTP-Referer|X-Title|OPENROUTER_SITE_URL|OPENROUTER_SITE_NAME" backend docs --glob '!docs/**/artifacts/**'
rg --files-with-matches "from llm_common|import llm_common|llm_common\." backend/{agents,services,routers} backend/main.py | sort
rg --files-with-matches "from llm_common|import llm_common|llm_common\." backend/scripts/{cron,substrate,verification} | sort
nl -ba backend/pyproject.toml | sed -n '1,140p'
nl -ba backend/main.py | sed -n '150,320p'
nl -ba backend/services/llm/orchestrator.py | sed -n '1,340p'
nl -ba backend/services/llm/orchestrator.py | sed -n '1150,1225p'
nl -ba backend/services/llm/web_search_factory.py | sed -n '1,220p'
nl -ba backend/services/llm/web_search_factory.py | sed -n '460,620p'
nl -ba backend/services/pipeline/domain/bridge.py | sed -n '110,230p'
nl -ba backend/services/discovery/service.py | sed -n '1,220p'
nl -ba backend/services/auto_discovery_service.py | sed -n '1,240p'
nl -ba backend/services/discovery/search_discovery.py | sed -n '1,220p'
nl -ba backend/services/research/zai.py | sed -n '1,220p'
nl -ba backend/services/vector_backend_factory.py | sed -n '1,200p'
nl -ba backend/services/ingestion_service.py | sed -n '1,170p'
nl -ba backend/services/ingestion_service.py | sed -n '280,345p'
nl -ba backend/services/retrieval/local_pgvector.py | sed -n '1,230p'
nl -ba backend/services/retrieval/local_pgvector.py | sed -n '230,330p'
nl -ba backend/routers/admin.py | sed -n '1470,1545p'
nl -ba backend/routers/discovery.py | sed -n '1,220p'
nl -ba backend/scripts/cron/run_daily_scrape.py | sed -n '1,140p'
nl -ba backend/scripts/cron/run_rag_spiders.py | sed -n '90,170p'
nl -ba backend/scripts/cron/run_universal_harvester.py | sed -n '130,240p'
nl -ba backend/scripts/cron/run_discovery.py | sed -n '1,240p'
nl -ba backend/scripts/substrate/manual_capture.py | sed -n '240,320p'
nl -ba backend/scripts/substrate/manual_expansion_runner.py | sed -n '260,330p'
nl -ba backend/clients/web_reader_client.py | sed -n '1,180p'
nl -ba backend/clients/zai_layout_parsing_client.py | sed -n '1,130p'
nl -ba frontend/env.example | sed -n '1,220p'
```

## Beads Memory Lookups (Required)

- `bdx memories OpenRouter --json` -> `{}`
- `bdx memories litellm --json` -> `{}`
- `bdx search "OpenRouter" --label memory --status all --json` -> `[]`
- `bdx search "LiteLLM" --label memory --status all --json` -> `[]`

Interpretation: no reusable Beads memory records currently found for these keywords in this lane.

## Files Inspected (Repo-Relative)

- `AGENTS.md`
- `docs/architecture/BROWNFIELD_MAP.md`
- `docs/architecture/DATA_AND_STORAGE.md`
- `docs/architecture/README.md`
- `docs/architecture/WORKFLOWS_AND_PATTERNS.md`
- `backend/pyproject.toml`
- `backend/main.py`
- `backend/routers/admin.py`
- `backend/routers/discovery.py`
- `backend/services/llm/orchestrator.py`
- `backend/services/llm/web_search_factory.py`
- `backend/services/pipeline/domain/bridge.py`
- `backend/services/discovery/service.py`
- `backend/services/auto_discovery_service.py`
- `backend/services/discovery/search_discovery.py`
- `backend/services/research/zai.py`
- `backend/services/ingestion_service.py`
- `backend/services/retrieval/local_pgvector.py`
- `backend/services/vector_backend_factory.py`
- `backend/scripts/cron/run_daily_scrape.py`
- `backend/scripts/cron/run_rag_spiders.py`
- `backend/scripts/cron/run_universal_harvester.py`
- `backend/scripts/cron/run_discovery.py`
- `backend/scripts/substrate/manual_capture.py`
- `backend/scripts/substrate/manual_expansion_runner.py`
- `backend/clients/web_reader_client.py`
- `backend/clients/zai_layout_parsing_client.py`
- `frontend/env.example`
- plus targeted `rg` over `backend/agents`, `backend/services`, `backend/routers`, and `backend/scripts`

## Current-State Map

### A) `llm_common` usage in affordabot

Runtime/backend imports are broad and structural (not just tests), including:

- Core LLM/search/provenance/retrieval contracts:
  - `backend/services/llm/orchestrator.py`
  - `backend/services/legislation_research.py`
  - `backend/services/ingestion_service.py`
  - `backend/services/retrieval/local_pgvector.py`
  - `backend/services/vector_backend_factory.py`
  - `backend/services/search_pipeline_service.py`
  - `backend/services/auto_discovery_service.py`
- Agent surfaces:
  - `backend/agents/policy_agent.py`
  - `backend/agents/tools/{zai_search.py,retriever.py,scraper.py,web_reader.py}`
- Runtime entrypoints:
  - `backend/main.py`
  - `backend/routers/discovery.py`
  - `backend/routers/chat.py`
- Operational scripts (cron/substrate/verification) also import `llm_common` heavily.

Package wiring:
- `backend/pyproject.toml` pins `llm-common` from git (`rev = d3d9e3c...`) and also includes `litellm` dependency.

### B) LiteLLM usage classification

- Direct code usage in `affordabot` runtime/scripts: **none found**.
  - No `import litellm`
  - No `from litellm import ...`
  - No `aembedding(` calls
- Dependency presence:
  - `backend/pyproject.toml` includes `litellm = ">=1.0.0"`.
  - `backend/poetry.lock` includes `litellm` resolved packages.
- Effective classification: **indirect usage through `llm_common` expectation**, not direct affordabot API calls.

### C) OpenRouter chat/completion configuration paths

1. Fallback LLM in core pipeline:
   - `backend/main.py` builds `OpenRouterClient` when `OPENROUTER_API_KEY` exists.
   - Fallback model from `LLM_MODEL_FALLBACK_OPENROUTER` else `openrouter/auto`.
   - `backend/services/llm/orchestrator.py` uses `fallback_llm.chat_completion(...)` on primary failure.

2. Discovery-classifier fallback path:
   - `backend/services/discovery/service.py` uses `instructor.from_openai(AsyncOpenAI(...))`.
   - Prefers Z.ai; falls back to OpenRouter (`base_url="https://openrouter.ai/api/v1"`) if only `OPENROUTER_API_KEY` exists.
   - Uses model `"x-ai/grok-4.1-fast:free"` by default in that fallback.

3. Admin introspection:
   - `backend/routers/admin.py` exposes configured status for Z.ai/OpenRouter model availability and fallback model id.

### D) OpenRouter embedding configuration paths (`qwen/qwen3-embedding-8b`)

Consistent model string appears in multiple runtime and script paths, all using OpenAI-compatible embedding client from `llm_common`:

- Core runtime:
  - `backend/main.py` (`OpenAIEmbeddingService`, base URL `https://openrouter.ai/api/v1`, model `qwen/qwen3-embedding-8b`, dimensions 4096)
  - `backend/services/pipeline/domain/bridge.py` (same)
- Cron/substrate operational paths:
  - `backend/scripts/cron/run_daily_scrape.py`
  - `backend/scripts/cron/run_rag_spiders.py`
  - `backend/scripts/cron/run_universal_harvester.py`
  - `backend/scripts/substrate/manual_capture.py`
  - `backend/scripts/substrate/manual_expansion_runner.py`
  - `backend/scripts/rerun_california_bills.py`

### E) Path consistency vs multiplicity

Observed patterns:

1. **`llm_common` provider client path** (chat):
   - `ZaiClient` primary + `OpenRouterClient` fallback (`main.py`, rerun script, orchestrator).

2. **OpenAI-compatible client path** (embeddings):
   - `llm_common.embeddings.openai.OpenAIEmbeddingService` hitting OpenRouter base URL.

3. **Direct AsyncOpenAI path (not via llm_common client wrappers)**:
   - `backend/services/discovery/service.py` (classifier)
   - `backend/clients/web_reader_client.py` and `backend/clients/zai_layout_parsing_client.py` are direct service clients (z.ai tool endpoints).

Conclusion: affordabot currently uses **multiple client pathways** (not a single abstraction boundary), but embedding path itself is consistently OpenAI-compatible + OpenRouter + qwen embedding model.

## Dependency and Env-Var Map

### Required/actively checked in runtime paths

- `ZAI_API_KEY`
  - Primary research/search/reasoning in multiple services.
- `OPENROUTER_API_KEY`
  - Enables fallback chat client and embedding generation in runtime/cron/substrate.
- `LLM_MODEL_RESEARCH` (default `glm-4.7`)
- `LLM_MODEL_GENERATE` (default `glm-4.7`)
- `LLM_MODEL_REVIEW` (default `glm-4.7`)
- `LLM_MODEL_FALLBACK_OPENROUTER` (default `openrouter/auto`)

### Search provider routing env vars (web_search_factory)

- `WEB_SEARCH_PROVIDER`
- `SEARXNG_SEARCH_ENDPOINT` / `WEB_SEARCH_SEARXNG_ENDPOINT` / `SEARXNG_ENDPOINT`
- `WEB_SEARCH_SEARXNG_TIMEOUT_S`
- `TAVILY_API_KEY`, `TAVILY_SEARCH_ENDPOINT`, `WEB_SEARCH_TAVILY_TIMEOUT_S`
- `EXA_API_KEY`, `EXA_SEARCH_ENDPOINT`, `WEB_SEARCH_EXA_TIMEOUT_S`, `WEB_SEARCH_EXA_USER_AGENT`
- `ZAI_SEARCH_ENDPOINT`
- `WEB_SEARCH_STRUCTURED_TIMEOUT_S`, `WEB_SEARCH_FALLBACK_TIMEOUT_S`

### Not found in active runtime code

- `OPENROUTER_BASE_URL` (only appears in long-form planning docs)
- OpenRouter site metadata headers/vars (`OPENROUTER_SITE_URL`, `OPENROUTER_SITE_NAME`, `HTTP-Referer`, `X-Title`) not used in active backend runtime code.

### Embedding/env behavior note

Embedding setup is often conditional:
- Some paths fail closed when key missing.
- Some paths use a mock embedding service (4096 vector) when `OPENROUTER_API_KEY` missing.

## Direct vs Indirect LiteLLM Usage

- Direct in affordabot code: **no evidence**.
- Indirect: **likely yes via `llm-common` internals** (dependency declared; affordabot consumes `llm_common` clients/interfaces heavily).
- Operational implication: replacing `llm-common` with custom clients in affordabot is high-risk without first mapping which `llm_common` interfaces are contract-critical.

## OpenRouter Chat vs Embedding Paths

- Chat/completion:
  - OpenRouter used as **fallback** provider via `OpenRouterClient` for orchestrator flow.
  - Also used in discovery classifier fallback through direct AsyncOpenAI adapter.
- Embeddings:
  - OpenRouter used as **primary configured embedding endpoint when key exists**, with model `qwen/qwen3-embedding-8b`, dimensions 4096.
  - Implemented through `llm_common` OpenAI-compatible embedding service across runtime + scripts.

## Evidence-Backed Gaps/Risks

1. Client-boundary fragmentation risk:
   - Mixed use of `llm_common` provider wrappers, direct `AsyncOpenAI`+`instructor`, and bespoke service clients.
2. Config drift risk:
   - OpenRouter base URL hardcoded in many files; no single env-driven `OPENROUTER_BASE_URL`.
3. Runtime/script divergence risk:
   - Core runtime and cron/substrate scripts each initialize embeddings independently.
4. Litellm decision risk:
   - Since affordabot does not call LiteLLM directly, a LiteLLM-vs-custom decision made at affordabot layer can miss true dependency locus (`llm-common` contracts).
5. Evidence quality risk for env docs:
   - Env requirements are spread across code and historical docs; no single authoritative runtime env contract file was found in this pass.

## Recommendations (Affordabot Only)

### ALL_IN_NOW

1. Produce an affordabot-only interface inventory for `llm_common` touchpoints (no implementation changes):
   - Enumerate concrete symbols used (LLM clients, embeddings, retrieval, WebSearchClient, agent/provenance types).
   - Mark each as runtime-critical vs script-only.
   - This directly de-risks the llm-tldr replacement spike by clarifying what must be preserved at call sites.

2. Add one investigation follow-up doc/table that normalizes current OpenRouter usage points (chat fallback vs embeddings, runtime vs script):
   - Keep behavior unchanged.
   - Goal is evidence alignment before any client refactor.

### DEFER_TO_P2_PLUS

1. Consolidate repeated embedding client construction into one affordabot helper/factory.
2. Introduce env-driven `OPENROUTER_BASE_URL` (with default current value) after dependency mapping.
3. Normalize discovery classifier path onto a single client boundary (currently mixed direct AsyncOpenAI and llm_common patterns).

### CLOSE_AS_NOT_WORTH_IT (for now)

1. Any immediate migration of affordabot runtime from `llm_common` to bespoke clients before cross-repo contract mapping.
2. Any LiteLLM-first refactor inside affordabot alone (direct usage is absent here).
3. Any model/provider switch without proving parity on pipeline/retrieval/provenance contracts.

## Implications for grepai/OpenRouter llm-tldr Semantic Spike

Affordabot evidence suggests the spike should treat `llm_common` interface compatibility as the primary contract surface, not LiteLLM API compatibility. The highest-value next step is to map and freeze affordabot call-site contracts (LLM/search/retrieval/embedding/provenance) so the spike can test replacements behind those contracts. OpenRouter embeddings (`qwen/qwen3-embedding-8b`, 4096-dim) are deeply threaded through runtime and scripts; this path should be treated as a stability anchor during experimentation.

## Tool Routing Exception

`llm-tldr` was available in MCP config but both required first calls timed out (`semantic` and `status`, each at 120s). Fallback proceeded with bounded targeted `rg` and direct file inspection.
