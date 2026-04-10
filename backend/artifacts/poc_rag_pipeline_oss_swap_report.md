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
- Added exponential backoff retries for OSS throttling/transient failures (`429`, `503`, and retryable exceptions).
- POC run used a local mock SearXNG endpoint (`/search?format=json`) to verify end-to-end behavior without external dependencies.

## Execution
### 1) Baseline run
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
  "first_web_source": "https://lao.ca.gov/mock-fiscal-analysis",
  "top_web_titles": [
    "Fiscal analysis for site:lao.ca.gov \"AB-123\" fiscal analysis",
    "Committee analysis for site:lao.ca.gov \"AB-123\" fiscal analysis"
  ]
}
```

### 2) Jurisdiction run (Saratoga CA)
Command:
```bash
python3 backend/scripts/verification/poc_rag_pipeline_oss_swap.py --bill-id SR-2026-001 --jurisdiction "Saratoga CA"
```

Output:
```json
{
  "rag_chunks": 1,
  "web_sources": 2,
  "evidence_envelopes": 2,
  "is_sufficient": true,
  "insufficiency_reason": null,
  "first_web_source": "https://lao.ca.gov/mock-fiscal-analysis",
  "top_web_titles": [
    "Fiscal analysis for Saratoga CA SR-2026-001 fiscal impact analysis",
    "Committee analysis for Saratoga CA SR-2026-001 fiscal impact analysis"
  ]
}
```

## Manual verification status
- Manual inspection performed on returned OSS-route payload fields (`title`, `url`, `content`) and downstream pipeline outputs (`web_sources`, `evidence_envelopes`, sufficiency).
- Outbound live internet search verification from this environment is currently constrained by tunnel `403 Forbidden`, so this report validates pipeline contract behavior with a local OSS-compatible endpoint rather than live public SearXNG traffic.

## Interpretation
- The pipeline successfully produced both internal and external evidence envelopes with OSS-backed web results.
- Sufficiency gate passed in this controlled scenario, indicating the swap can preserve downstream contract shape.
- Next validation step on EPYC6 host: point `OSS_WEB_SEARCH_ENDPOINT` at your running SearXNG instance and execute the same script in live mode for real-result QA.
