# POC #2: Current RAG Pipeline with OSS Web Search Swap

Generated: 2026-04-10 UTC

## Objective
Validate a prototype where the existing RAG research flow is kept intact while the web search dependency is swapped from Z.ai structured search to an OSS-hosted SearXNG-compatible endpoint.

## What changed since prior revision
- OSS client retries with exponential backoff and jitter for `429`/`503` and transient exceptions.
- Verification script now supports **live mode** via `--live-endpoint` and writes markdown reports via `--out`.
- Script now emits Saratoga-oriented relevance signals:
  - `official_domain_hits`
  - `saratoga_mention_hits`

## Execution (mock mode in this environment)
### Baseline run
```bash
python3 backend/scripts/verification/poc_rag_pipeline_oss_swap.py
```

### Saratoga jurisdiction run
```bash
python3 backend/scripts/verification/poc_rag_pipeline_oss_swap.py \
  --bill-id SR-2026-001 \
  --jurisdiction "Saratoga CA"
```

Observed output (Saratoga run):
```json
{
  "bill_id": "SR-2026-001",
  "jurisdiction": "Saratoga CA",
  "endpoint_mode": "mock",
  "rag_chunks": 1,
  "web_sources": 2,
  "evidence_envelopes": 2,
  "is_sufficient": true,
  "insufficiency_reason": null,
  "official_domain_hits": 1,
  "saratoga_mention_hits": 2
}
```

## Live Saratoga run command (for EPYC6)
```bash
python3 backend/scripts/verification/poc_rag_pipeline_oss_swap.py \
  --live-endpoint "http://<epyc6-searxng-host>:8080/search" \
  --bill-id "SR-2026-001" \
  --jurisdiction "Saratoga CA" \
  --out backend/artifacts/poc_rag_pipeline_oss_swap_saratoga_live.md
```

## Manual verification status
- Manual inspection performed for returned OSS-route fields and downstream contract metrics in mock mode.
- Outbound live public internet verification from this environment remains constrained by tunnel `403 Forbidden`; live-result QA should be run from EPYC6 with the command above.
