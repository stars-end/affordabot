# 2026-04-01 PDF -> Markdown POC (Substrate Lane)

## Scope
Grounded quick bakeoff for the substrate PDF parse path using one real municipal artifact:

- PDF: San Jose City Council agenda
- URL: `https://legistar.granicus.com/sanjose/meetings/2026/4/7616_A_City_Council_26-04-07_Agenda.pdf`
- Candidates:
  - [microsoft/markitdown](https://github.com/microsoft/markitdown)
  - [pymupdf/pymupdf4llm](https://github.com/pymupdf/pymupdf4llm)

## Observed Results (Real Artifact)
- `markitdown` output length: `37183` chars
- `pymupdf4llm` output length: `39348` chars

Qualitative observations:
- `markitdown` starts with clean plain text and low markdown noise.
- `pymupdf4llm` preserves stronger markdown structure (headers/layout), but includes image-omission marker lines.

## Recommendation
Default extractor: `markitdown`  
Fallback extractor: `pymupdf4llm`

Reasoning:
1. `markitdown` is a lower-risk default for broad backend rollout while still producing useful content for chunking/RAG.
2. `pymupdf4llm` remains an explicit fallback/alternative when structure fidelity is more important than output cleanliness.
3. Boundary design keeps the choice swappable without changing substrate ingestion internals.

## License / Dependency Caveats
- `pymupdf4llm` repository currently advertises `AGPL-3.0` and depends on PyMuPDF / MuPDF licensing terms. Treat as legal-review required before defaulting it in production.
- `markitdown` is currently the safer default path from a licensing posture for this repo lane.

## Implementation Hook
Boundary implemented in:
- `backend/services/pdf_markdown.py`

Interface behavior:
- Preferred extractor + optional fallback
- Clear error envelope when all extractors fail
- Optional-dependency imports (no hard dependency at import time)
