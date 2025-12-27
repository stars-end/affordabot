# affordabot-a242.11 — RetrieverTool (RAG)

## Goal
Expose a RAG retrieval tool that the agent can call deterministically (search corpus, fetch top-k chunks, return citations).

## Acceptance Criteria
- Tool schema is stable and documented.
- Retrieval is bounded (top-k, max tokens).
- Works with the current vector backend and passes `make verify*`.

