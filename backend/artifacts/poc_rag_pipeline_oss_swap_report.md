# POC #2: Current RAG Pipeline with OSS Web Search Swap

Generated: 2026-04-10 UTC

## Objective
Validate a prototype where the existing RAG research flow is kept intact while the web search dependency is swapped from Z.ai structured search to an OSS-hosted SearXNG-compatible endpoint.

## What stayed the same
- `LegislationResearchService` orchestration and sufficiency logic.
- Retrieval-first then web-research flow.
- Evidence envelope construction and result scoring path.

## What changed
- Web search client swapped to `OssSearxngWebSearchClient`.
- POC run used a local mock SearXNG endpoint (`/search?format=json`) to verify end-to-end behavior without external dependencies.

## Execution
Command:
```bash
python3 backend/scripts/verification/poc_rag_pipeline_oss_swap.py
```

Output:
```json
{
  "rag_chunks": 1,
  "web_sources": 2,
  "evidence_envelopes": 2,
  "is_sufficient": true,
  "insufficiency_reason": null,
  "first_web_source": "https://lao.ca.gov/mock-fiscal-analysis"
}
```

## Interpretation
- The pipeline successfully produced both internal and external evidence envelopes with OSS-backed web results.
- Sufficiency gate passed in this controlled scenario, indicating the swap can preserve downstream contract shape.
- This does **not** validate live EPYC6 network behavior yet; it validates that the pipeline contract remains stable when the search backend is swapped.
