# Plan Review: California Pipeline Truth Remediation

## 1. Does it address all critical issues in RAG?
**Yes.** The plan fixes both the ingestion side and the retrieval side of RAG.
*   **Write Side (Wave 2A / bd-tytc.3):** Mandates that official California bill text is actually downloaded and inserted into `raw_scrapes` so that it is chunked and embedded by the existing pipeline logic.
*   **Read Side (Wave 2B / bd-tytc.4):** Mandates that `AnalysisPipeline` uses the `PolicyAgent` research path, wires `LocalPgVectorBackend` to an actual embedder, enforces metadata filtering (jurisdiction), removes the silent fallback to mock documents in `RetrieverTool`, and fixes the `_research_step` interface mismatch that was dropping `EvidenceEnvelope` objects.

## 2. Does it address scraping?
**Yes.**
*   **Wave 2A (bd-tytc.3)** explicitly targets the California scraper. It mandates the use of OpenStates only for discovery, and mandates fetching the official bill text from the linked California legislature source rather than scraping useless summaries.

## 3. Does it address analytics (quantification)?
**Yes.**
*   **Wave 2C (bd-tytc.2)** removes the hallucination pressure. It makes the p10..p90 percentiles optional, introducing `research_incomplete`, `insufficient_evidence`, and `qualitative_only` states. This stops the pipeline from fabricating fake numbers when no fiscal notes are found.

## 4. Does it address visibility/observability?
**Yes.**
*   **Wave 3A (bd-tytc.5)** enforces "Honest Persistence and Telemetry". It normalizes the sufficiency telemetry (e.g., dynamically tracking `rag_chunks_retrieved` and `web_research_sources_found` from the `EvidenceEnvelope` items). It removes the fake "Virtual" embedding steps that were misleading operators, and strips destructive placeholders from the DB payload.

## 5. Does it address research & web search?
**Yes.**
*   **Wave 2B (bd-tytc.4)** unifies the legislation-analysis path with the `PolicyAgent` research loop. This guarantees that deep web searches for fiscal notes and committee analyses (via Z.ai) happen alongside local RAG retrieval, instead of bypassing research entirely.

## Are the Implementation Waves Correct?

The implementation wave structure is excellent and highly parallelizable:

*   **Wave 0 (Contract Lock):** Crucial step to get alignment before code changes.
*   **Wave 1 (Frontend Stop-Bleeding):** Can run immediately to stop the UI from lying to stakeholders while the backend is being repaired.
*   **Wave 2A (Scraping), 2B (RAG), and 2C (Schema):** These three are the core data repairs. They correctly identify that fixing scraping (2A) unblocks the RAG pipeline (2B), but the Schema repair (2C) can be worked on concurrently because it just defines the new Python/Pydantic payloads.
*   **Wave 3A (Observability) & 3B (Alerting) & 3C (Frontend):** Correctly sequenced *after* Wave 2 defines the new payload shapes.
*   **Wave 4 (Backfill/Tests):** The final capstone.

### Missing/Weak Link Check
There is one potential weakness in the wave plan summary provided: **Wave 3B (Deterministic Alerting / bd-tytc.8)** references `bd-tytc.8` and `OpenClaw/live monitor`. I need to verify if `bd-tytc.8` was actually documented in the main spec file we edited, because I do not recall seeing it in `2026-03-19-affordabot-california-pipeline-truth-remediation.md`.
