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

## Updated Live Result
Artifact:
- `backend/scripts/substrate/artifacts/bd-z8qp.4_glm_ocr_bakeoff.json`

Observed on the live backend environment after account recharge and payload correction:
- `markitdown` succeeded on both real municipal PDFs
- `glm_ocr` also succeeded on both real municipal PDFs when local files were sent
  as `data:` URIs instead of raw base64
- live contract details:
  - raw base64 payloads were rejected with `1214`
  - `data:image/...;base64,...` worked
  - `data:application/pdf;base64,...` also worked for real municipal PDFs
  - direct remote PDF URLs remained inconsistent, so the stable backend path is
    local download -> `data:` URI -> `layout_parsing`

Interpretation:
1. `glm_ocr` is now proven usable in the backend substrate lane.
2. The stable implementation path is local artifact -> `data:` URI, not raw
   base64 and not reliance on remote PDF URL fetches.
3. `glm_ocr` improves layout fidelity on tougher packet front matter, but it is
   materially slower than `markitdown`.

## Current Recommendation
- Keep `glm_ocr` as an optional, non-default hard-doc extractor.
- Keep `markitdown` as the default PDF path for normal municipal documents.
- Use `glm_ocr` selectively for image-heavy, table-heavy, or otherwise degraded
  PDFs where baseline extraction quality is weak.
