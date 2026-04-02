# Data Substrate Framework v1

## Status

Locked on April 3, 2026 from grounded San Jose substrate validation plus a
targeted hard-document OCR bakeoff.

This document is the current product contract for Affordabot's municipal data
substrate.

## Core Model

Affordabot stores municipal source data in three layers:

1. `captured_candidate`
   - captured but not yet durably preserved or trusted enough for the moat
2. `durable_raw`
   - durably preserved raw artifact with provenance
   - part of the moat layer
   - not necessarily analysis-ready
3. `promoted_substrate`
   - trusted, substantive, analysis-prioritized subset

## Truth Model

- `processed` is not authoritative
- `metadata.ingestion_truth` is authoritative for new rows
- missing `ingestion_truth` means `legacy_unknown`
- ingestion stages must truthfully distinguish:
  - `raw_captured`
  - `blob_stored`
  - `parsed`
  - `chunked`
  - `embedded`
  - `retrievable`

## Trust Model

Trust must be derived in this order:

1. explicit source metadata
2. official hostname/domain rules
3. conservative fallback

`sources.type` alone is not sufficient.

## Promotion Model

- preserve broadly into `durable_raw`
- promote narrowly into `promoted_substrate`
- rules first
- `glm-4.6v` only for ambiguous cases
- LLM failure never blocks raw preservation

## PDF Extraction Model

### Default

- `markitdown` is the default PDF-to-markdown path

Why:
- fast
- stable in the current backend runtime
- good enough on normal municipal PDFs

### Hard-Document Fallback

- `glm_ocr` is the selective hard-document fallback
- use it for image-heavy, table-heavy, or degraded PDFs where baseline output
  quality is weak

Why not default:
- materially slower than `markitdown`
- should be spent selectively, not on every PDF

### Rejected / Non-Default Paths

- `pymupdf4llm`
  - not available in the current backend runtime
  - keep non-default

## Z.ai Endpoint Contract

### Coding Endpoint

Use `https://api.z.ai/api/coding/paas/v4` for:
- `glm-4.6v`
- `glm-4.7`
- other chat/reasoning/coding-plan calls

### Non-Coding Endpoint

Use `https://api.z.ai/api/paas/v4/layout_parsing` for:
- `glm-ocr` only

This is the only model path that should use the non-coding endpoint in the
current framework.

## GLM-OCR Payload Contract

Live evidence showed:

- raw base64 was rejected
- `data:image/...;base64,...` worked
- `data:application/pdf;base64,...` worked on real municipal PDFs
- remote PDF URLs were inconsistent enough that we should not rely on them

So the stable backend contract is:

1. download the source artifact locally
2. send it as a `data:` URI
3. call `layout_parsing`

## Evidence Summary

### Grounded Validation Sweep

The substrate gate proved:

- official HTML meeting detail can become truthfully retrievable
- official PDF agenda can become truthfully retrievable
- official shell/index pages should remain `durable_raw`
- third-party pages should remain `captured_candidate`

### Hard-Document OCR Bakeoff

Artifact:
- `backend/scripts/substrate/artifacts/bd-z8qp.4_glm_ocr_bakeoff.json`

Observed:
- San Jose agenda:
  - `markitdown`: `0.943s`
  - `glm_ocr`: `5.581s`
- agenda packet front matter:
  - `markitdown`: `5.382s`
  - `glm_ocr`: `40.53s`

Interpretation:
- `markitdown` remains the right default
- `glm_ocr` is viable for harder docs and yielded useful structured snippets on
  selected packet/table-heavy front-matter pages in this bakeoff
- the latency/cost tradeoff makes it a fallback, not a universal parser
- current evidence does not yet establish broad output-quality superiority over
  `markitdown`

## Acceptance Gates

Framework acceptance remains:

1. substrate health inspection surface
2. grounded validation sweep
3. hard-document OCR bakeoff for OCR policy changes

## Expansion Rule

Do not widen jurisdiction breadth based on framework uncertainty anymore.

The framework itself is locked.

Breadth expansion is now a separate product/throughput decision and should be
gated on implementation capacity and quality, not on unresolved substrate
semantics.
