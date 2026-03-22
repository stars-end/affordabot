## Final External Review Prompts Execution

To confirm the plan's alignment, the provided external review prompts cover all angles:
1. **Backend/Data-Truth Architecture Reviewer:** Focuses on the RAG pipeline write/read paths, provenance preservation (using `llm-common`), and the use of the shared extracted legislation-research service to maintain schema contracts without losing the `EvidenceEnvelope`.
2. **Frontend/Product-Truth Reviewer:** Focuses on Data Gap Summary UI and rendering nullable percentiles safely so no "fake scores" appear.
3. **Systems/Ops/Control-Plane Reviewer:** Verifies the role of Windmill (scheduler only), deterministic alerts (`bd-tytc.8`), and the canonical `/api/admin` + Glass Box trace layer.

The recommendations exactly match the required fixes to prevent the system from lying to operators. The overlapping implementations between `Affordabot` and `llm-common` demonstrate that Option 2 (a shared, extracted service that leverages `llm-common`'s robust Agentic tools without forcing `AnalysisPipeline` into a chat flow) is the only way to save the RAG pipeline's integrity.
