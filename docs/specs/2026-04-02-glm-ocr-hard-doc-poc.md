# 2026-04-02 GLM-OCR Hard-Document POC

## Scope
Evaluate whether Z.ai `glm-ocr` should become an optional hard-document extractor in the substrate lane.

This wave adds:
- a minimal `ZaiLayoutParsingClient`
- an optional `glm_ocr` extractor in `backend/services/pdf_markdown.py`
- a grounded bakeoff script for two real municipal PDFs

## Source Reference
- Guide: [GLM-OCR overview](https://docs.z.ai/guides/vlm/glm-ocr)
- API reference: [POST /api/paas/v4/layout_parsing](https://docs.z.ai/api-reference/tools/layout-parsing)

## Working Assumptions
1. `file` accepts URL or raw base64 string.
2. `md_results` is the substrate-relevant output field.
3. We are evaluating `glm_ocr` as an optional hard-doc path, not changing the default extractor yet.

## Bakeoff Documents
- San Jose City Council agenda PDF
- San Jose Climate Adaptation and Resilience Plan PDF

## Acceptance
- client can call layout parsing successfully with the live backend `ZAI_API_KEY`
- bakeoff artifact captures:
  - success or failure
  - elapsed time
  - markdown length
  - preview text
- if `glm_ocr` clearly improves tougher docs without destabilizing the lane, it can be considered for v1.1

## Live Result
Artifact:
- `backend/scripts/substrate/artifacts/bd-z8qp.4_glm_ocr_bakeoff.json`

Observed on the live backend environment:
- `markitdown` succeeded on both real municipal PDFs
- `pymupdf4llm` was unavailable in the backend runtime (`dependency_missing`)
- `glm_ocr` reached the live API path but both calls failed with:
  - `429`
  - error code `1113`
  - message: `Insufficient balance or no resource package. Please recharge.`

Interpretation:
1. The adapter shape is valid enough to reach the real Z.ai OCR endpoint.
2. We do not currently have production-like evidence about OCR quality because the backend account is not provisioned for live GLM-OCR calls.
3. This is an account/resource blocker, not a Python integration blocker.

## Current Recommendation
- Keep `glm_ocr` as an optional, non-default extractor.
- Do not route substrate v1 traffic through it yet.
- If we provision GLM-OCR access later, rerun the same bakeoff artifact before promoting it into the hard-doc lane.
