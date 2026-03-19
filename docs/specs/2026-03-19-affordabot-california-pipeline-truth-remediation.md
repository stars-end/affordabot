# Affordabot California Pipeline Truth Remediation

Date: 2026-03-19
Status: Proposed
Beads Epic: `bd-tytc`
Planning Task: `bd-tytc.1`
Audit Input: `bd-hvji.1`

## Executive Verdict

The California legislation path is not a degraded research pipeline. It is a broken truth pipeline.

The current system:
- fails to acquire real bill text for California bills
- bypasses retrieval/RAG entirely in the legislation-analysis path even though retrieval-capable tooling exists elsewhere
- performs shallow, bill-agnostic research
- flattens or discards structured evidence/provenance before generation
- forces quantified output through a rigid schema even when evidence is absent
- persists hallucinated-looking estimates as if they were valid analysis
- misrepresents weak backend outputs in the frontend through misleading labels and placeholder UI

This plan assumes `ALL_IN_NOW`.

No phased coexistence, no “soft” transition period, and no dev-only tolerance for unsupported quantified outputs.

## Big-Bang Objective

Replace the current California legislation analysis path with a truthful, evidence-gated pipeline that:
- acquires real California bill text and provenance
- uses retrieval and bill-specific research in the actual legislation-analysis path
- refuses quantification when evidence is insufficient
- stores and exposes source-of-truth fields honestly
- prevents unsupported analyses from being ranked or displayed as authoritative
- backfills and re-verifies affected California bills, especially `SB 277` and `ACR 117`

Important scope note:
- changes to `AnalysisPipeline`, `LegislationAnalysisResponse`, retrieval backends, and evidence validation are platform-level and affect all jurisdictions
- California remains the validation anchor because its failures are the clearest and most urgent
- acceptance criteria below name California bills explicitly, but the read/write truth fixes must apply system-wide

## Root-Cause Ranking

### Primary

1. Retrieval/evidence chain is not connected
   - The legislation-analysis runtime does not execute against the retrieval substrate that exists elsewhere in the codebase.
   - The local retrieval interface is broken at the contract boundary today: retrieval-capable paths depend on `retrieve()`, while the local backend’s `retrieve()` is currently a stub that returns no results.
   - Structured evidence/provenance tooling exists, but the legislation path does not preserve or consume it.

2. Source acquisition failure
   - California ingestion extracts `versions[0].note` or bill title instead of actual bill text.
   - The official linked bill text/PDF/HTML is not followed.
   - The stored legislation payload ends up detached from ground truth.

### Secondary

3. Legislation path bypasses retrieval/RAG
   - The `AnalysisPipeline` does not use the retrieval path that exists elsewhere.
   - pgvector/retrieval is effectively orphaned for the legislation-analysis workflow.
   - Audit/telemetry currently implies embedding/retrieval happened even when it did not.

4. Research depth is too shallow and not legislation-specific
   - The runtime path performs shallow web-search collection rather than true bill-specific research.
   - Research does not produce a strong “insufficient evidence” contract when it fails.
   - The planner prompt is still finance/ticker-oriented and the available research path is constrained to generic search tooling.

### Tertiary

5. Schema and quantification contract force fabricated precision
   - Required `p10/p25/p50/p75/p90` and required evidence lists create pressure to invent numbers and placeholder evidence.
   - There is no explicit non-quantified “insufficient evidence” state.

6. Review and validation are advisory, not truth-enforcing
   - Review is LLM-only and cannot programmatically block placeholder evidence, fake URLs, or unsupported math.

7. Evidence provenance is dropped before generation
   - Chat-path tools can emit structured `EvidenceEnvelope` provenance, but the legislation path reduces research output to loosely structured `collected_data`.
   - `_generate_step()` receives a stringified blob of research snippets instead of a validated evidence contract.
   - This means the analysis model is not reasoning over enforceable citations, only over unverified text fragments.

### Amplifiers

8. Persistence/API contract hides truth gaps
   - Synthetic titles, placeholder text, dropped/mutated confidence fields, and missing model/source metadata obscure the real state.

9. Frontend mislabels and decorates invalid outputs
   - confidence is transformed into an “Impact Score”
   - unsupported analyses are ranked beside valid ones
   - hardcoded placeholder panels imply system completeness

## Non-Negotiable Remediation Decisions

1. California quantified outputs must be quarantined until the repaired pipeline proves evidence sufficiency.
2. Real bill text and source provenance are mandatory before California analysis is considered valid.
3. Retrieval/RAG must be part of the actual legislation-analysis path, not only the chat path.
4. Quantification must be evidence-gated, not schema-forced.
5. Review must include programmatic truth validation, not only LLM critique.
6. The frontend must display uncertainty and incompleteness honestly.
7. Existing suspect California analyses must be backfilled or invalidated, not grandfathered.
8. Cross-jurisdiction retrieval leakage is unacceptable; retrieval filters and chunk metadata must isolate jurisdictions and source classes.

## Current RAG and Evidence Reality Check

The current codebase already contains pieces of a more truthful retrieval/evidence stack, but the California legislation path does not actually use them end to end.

What exists today:
- `backend/services/ingestion_service.py` chunks raw scrapes, embeds them, and writes `document_id`-backed chunks into the retrieval backend.
- `backend/agents/tools/retriever.py` can return structured `EvidenceEnvelope` provenance from retrieved internal documents.
- `backend/agents/tools/zai_search.py` can wrap external research results into `EvidenceEnvelope` objects.
- `backend/routers/chat.py` wires `PolicyAgent` with `RetrieverTool`, `ScraperTool`, and `ZaiSearchTool`.

What the legislation-analysis path actually does today:
- `backend/services/llm/orchestrator.py` instantiates `ResearchAgent(llm_client, search_client)` and calls `_research_step()`.
- `llm_common/agents/research_agent.py` only registers `web_search`; it does not register `RetrieverTool`, `ScraperTool`, or the local `ZaiSearchTool`.
- the planner in `llm_common/agents/planner.py` is still framed as a “financial research assistant”
- `_research_step()` returns `collected_data`, not structured evidence envelopes
- `_generate_step()` injects raw `research_data` and `bill_text` directly into the prompt as plain text
- `_review_step()` critiques the same flattened payload, so review cannot verify provenance either

Current conclusion:
- retrieval exists, but not on the California legislation execution path
- even where retrieval-like interfaces exist, the local backend contract is broken because `LocalPgVectorBackend.retrieve()` currently returns `[]`
- `RetrieverTool` must be wired with a real backend and embedder; otherwise it stays in mock mode
- evidence/provenance machinery exists, but is not preserved into generation
- the first failure is therefore upstream of quantification: source text + retrieval + evidence contract all fail before the model is asked to estimate anything

## Immediate Safety Action

Before deeper remediation is complete, the system should stop presenting unsupported California analyses as authoritative.

Required stop-the-bleeding behavior:
- remove California bills with `research_incomplete`, `missing_bill_text`, or `insufficient_evidence` from “highest impact” ranking
- suppress quantified impact cards when the bill lacks validated source text and quantitative basis
- replace current values with an explicit `Research incomplete` / `No defensible estimate yet` state
- disable misleading “Impact Score” display derived from confidence

This is part of the big-bang plan, not a separate mini-project.
This quarantine behavior must land at the beginning of the remediation, not wait until the final frontend cleanup phase.

## Beads Subtasks

### `bd-tytc.1` Big-bang spec: California pipeline truth remediation

Purpose:
- freeze the remediation design
- encode sequencing
- prepare consultant review

Acceptance:
- this spec exists
- consultant review prompts cover all raised failure modes

### `bd-tytc.3` Impl: California bill-text ingestion and source fidelity

Purpose:
- fix California source acquisition so the system actually gets the right bill text

Required changes:
- follow official linked bill text/PDF/HTML from California/OpenStates version records instead of using `versions[].note`
- use OpenStates for discovery and metadata only; use the linked official California legislature source (HTML/PDF/text) as the canonical bill-text source whenever available
- store:
  - source URL
  - source type
  - version identifier/note
  - extraction status
  - extraction error when applicable
  - raw text provenance
- stop storing title-or-note placeholders as if they were bill text
- support bill-targeted fetch/re-ingest for specific bill numbers like `SB 277` and `ACR 117`
- delete fictional/mock California fallback behavior from normal runtime paths rather than conditionally bypassing it
- delete scraper-level mock fallback methods rather than leaving them as available runtime substitutes
- fix bulk-discovery limitations so important bills are not silently missed because of low result limits or updated-order truncation
- ensure California bill text enters the vector-ingestion write path by:
  - writing canonical bill text to `raw_scrapes`
  - invoking `IngestionService.process_raw_scrape()` for California bill records before analysis
- denormalize jurisdiction/source identity into raw-scrape and chunk metadata so retrieval filters can isolate California analysis from other jurisdictions

Acceptance:
- `SB 277` and `ACR 117` both have real bill text persisted
- `SB 277` and `ACR 117` both produce chunkable raw-scrape records that enter the vector store
- relevant clause extraction can point to actual source text
- placeholder text like `Introduced` is no longer treated as bill content

### `bd-tytc.4` Impl: legislation retrieval and research depth unification

Purpose:
- make the actual legislation-analysis pipeline use real retrieval and deeper bill-specific research

Required changes:
- make the legislation-analysis path call a retrieval-backed research service directly; remove “where appropriate” ambiguity about whether retrieval is optional
- stop treating pgvector as a sidecar asset that the legislation path never queries
- unify the `PolicyAgent`/retrieval capabilities and the `AnalysisPipeline` legislation workflow behind one canonical legislation-research path
- implement the retrieval contract end to end rather than only “integrating RAG” conceptually, including:
  - make `backend/services/retrieval/local_pgvector.py:LocalPgVectorBackend.retrieve()` actually perform retrieval instead of returning `[]`
  - update `LocalPgVectorBackend` to accept/use an embedder dependency so text queries can be embedded at retrieval time
  - make `LocalPgVectorBackend.query()` apply jurisdiction/source filters instead of ignoring the `filter` argument
  - ensure `RetrieverTool` is instantiated with a real retrieval backend and embedder; if the backend is missing in production, the tool MUST explicitly fail or return zero chunks rather than silently falling back to mock data
  - repair the interface mismatch in `backend/services/llm/orchestrator.py:_research_step()` so that it properly unwraps the `PolicyAnalysisResult` object to preserve `EvidenceEnvelope` objects rather than using an incompatible dictionary getter (`.get("collected_data", [])`) which silently drops evidence
  - repair or remove dead import paths such as `llm_common.retrieval.pgvector_backend` in the universal harvester path
- ensure research can:
  - retrieve actual bill text chunks
  - search for official fiscal notes and committee analyses
  - gather bill-specific sources rather than generic snippet search
- replace shallow fixed-query behavior with legislation-aware research depth and explicit insufficiency signaling
- explicitly remove/testing-only caps and hardcoded domain bias from the current research implementation, including:
  - `services/research/zai.py` `queries[:5]`
  - housing/tenant/landlord-specific query templates that are unrelated to the bill domain
- ensure the planner/research prompts are legislation-specific, not finance/ticker-oriented
- add bill-identity disambiguation so searches do not confuse current California bills with older bills that reuse the same number
- preserve structured provenance through the legislation path so retrieval/search results are passed forward as evidence envelopes or equivalent typed evidence objects rather than flattened snippet blobs
- choose and document one canonical research runtime for legislation analysis; do not leave `ResearchAgent` vs `ZaiResearchService` ambiguity unresolved
- ensure the legislation path can represent a hard “no useful evidence found” outcome before generation, instead of forcing research outputs to look successful
- remove silent throughput caps that truncate analysis scope for whole jurisdictions unless they are explicitly operator-configurable, including the current `bills[:3]` processing cap

Acceptance:
- the legislation-analysis path uses retrieved bill-context evidence in runtime
- research emits explicit insufficiency when bill-specific evidence is not found
- `SB 277` and `ACR 117` show real retrieval artifacts, not only generic web snippets
- evidence passed into generation retains URL/internal-document provenance instead of collapsing to ad hoc lists of dicts
- the configured retrieval backend returns real chunks through the same method signature the runtime actually calls
- retrieval results can be constrained to the target jurisdiction/source instead of semantically leaking documents from other jurisdictions

Dependencies:
- blocked by `bd-tytc.3`

### `bd-tytc.2` Impl: evidence-gated quantification and schema truthfulness

Purpose:
- stop schema pressure from forcing invented quantification

Required changes:
- redesign the analysis response contract so unsupported bills can fail gracefully
- make percentile outputs optional or otherwise gated behind evidence sufficiency
- add a pre-generation programmatic evidence sufficiency gate that runs before `_generate_step()`
- add a structured non-quantified state such as:
  - `research_incomplete`
  - `insufficient_evidence`
  - `qualitative_only`
- require quantified impacts to include:
  - numeric basis
  - assumptions
  - estimate method
  - cited source linkage
- redesign evidence requirements so the system can return zero validated evidence items when research fails, rather than forcing `min_items=1` at all times
- reject placeholder evidence such as fake URLs, synthetic source names, or generic unsupported evidence blobs
- ensure “bill-specific clause” fields can be absent or explicitly marked unresolved rather than fabricated
- define concrete minimum sufficiency rules in code, not in the model prompt, including at minimum:
  - bill text is present and not a known placeholder
  - at least one source has a verifiable HTTP URL
  - quantified output is blocked automatically when no official fiscal note, government cost estimate, or other approved numeric basis is present
- require the generation step to consume typed evidence/provenance structures or a normalized evidence contract rather than raw stringified search output
- add construction-time validation for evidence objects so fabricated URLs/source names/excerpts are rejected before persistence-time validation
- align backend persistence and frontend/API contracts with nullable or absent quantitative fields so “qualitative-only” and “research-incomplete” states are representable without type breakage

Acceptance:
- no bill can emit `p10..p90` without a defensible evidence basis
- the system can represent “I do not have enough evidence to quantify this”
- `SB 277` would no longer be able to surface a `$15,000,000` estimate under title-only or evidence-poor conditions
- quantification is blocked by deterministic code gates before the LLM is asked to fill percentile fields
- the evidence schema no longer forces fake support when the truthful state is “nothing defensible was found”

Dependencies:
- blocked by `bd-tytc.3`

### `bd-tytc.5` Impl: review, persistence, and telemetry honesty

Purpose:
- make validation and stored truth reflect what really happened

Required changes:
- add programmatic validators before persistence for:
  - bill-text presence
  - evidence URL validity
  - evidence URL resolvability
  - official-source requirements where applicable
  - numeric-basis requirements for quantification
  - placeholder/fabricated evidence detection
  - causal/numeric-anchor consistency for quantified impacts
- demote LLM review from sole gatekeeper to one input in a harder validation chain
- persist real metadata:
  - model used
  - evidence sufficiency state
  - bill-text acquisition status
  - quantification eligibility state
- require that the `_research_step` in the orchestrator inspects the structured evidence (e.g., `EvidenceEnvelope` objects) to dynamically compute and log a "Sufficiency Breakdown" containing:
  - `source_text_present`: bool
  - `rag_chunks_retrieved`: int (extracted directly from `source_tool="retriever"` evidence items)
  - `web_research_sources_found`: int
  - `fiscal_notes_detected`: bool
- ensure this breakdown is visible in the "Glass Box" admin view to allow for rapid debugging of data gaps
- remove or correct cosmetic audit steps that imply embedding/retrieval happened when they did not, specifically mandating the removal of the "Virtual" Step 0.5 embedding log from the runtime orchestrator since static document chunk counts belong in a "Document Health" view, not in a dynamic pipeline execution trace
- ensure stored titles/text/status fields reflect source truth instead of synthetic placeholders like `Analysis: <bill>`
- explicitly remove persistence-side placeholder injection in `backend/services/llm/orchestrator.py:_complete_pipeline_run()` so it no longer writes synthetic title/text/status fields such as `Analysis: <bill>` and `Full text placeholder`
- harmonize the stored analysis/evidence contract enough that provenance-bearing evidence remains queryable and does not fork permanently into incompatible runtime-only vs stored-only shapes

Acceptance:
- invalid analyses are blocked before persistence
- pipeline traces do not falsely imply retrieval or embedding occurred
- stored records distinguish valid quantified analysis from incomplete research states

Dependencies:
- blocked by `bd-tytc.2`
- blocked by `bd-tytc.4`

### `bd-tytc.6` Impl: frontend truth contract and quarantine of invalid outputs

Purpose:
- stop the UI from amplifying or disguising backend truth failures

Required changes:
- remove confidence-to-impact-score misuse
- stop ranking unsupported California analyses in “Bills by Impact”
- surface `research_incomplete` and `insufficient_evidence` explicitly
- update frontend/API types so impacts can carry nullable/optional percentiles without breaking rendering
- define explicit rendering for three bill states:
  - quantified
  - qualitative-only
  - research-incomplete
- require that when a bill is qualitative-only or research-incomplete, the UI provides a "Data Gap Summary" (e.g., "Full bill text available, but no external fiscal analysis found") based on the sufficiency breakdown telemetry
- remove hardcoded unrelated placeholder content from:
  - bill detail page
  - sector breakdown
  - legislative feed
  - decorative “data” blocks that imply grounded analysis
- show effective date only when actually derived and stored
- keep invalid or qualitative-only analyses visually distinct from validated quantified analyses
- ensure “Total Annual Cost” and similar KPI cards do not render `$0`/`NaN` as if they were legitimate quantified results when percentiles are absent

Acceptance:
- the UI no longer presents weak/incomplete analyses as authoritative ranked outputs
- confidence is labeled as confidence, not “Impact Score”
- placeholder mock content is removed from the California analysis experience
- frontend data contracts compile cleanly with optional percentile fields and incomplete-analysis states

Dependencies:
- blocked by `bd-tytc.2`
- blocked by `bd-tytc.5`

### `bd-tytc.7` Impl: backfill, re-run, and end-to-end truth verification

Purpose:
- repair existing data and lock in the corrected behavior

Required changes:
- invalidate or quarantine all previously generated suspect California analyses produced under the broken pipeline, not only `SB 277` and `ACR 117`
- identify whether the same platform-level failures require broader invalidation for non-California jurisdictions and either:
  - perform platform-wide invalidation, or
  - file a clearly linked follow-up epic if jurisdiction-specific rollback is intentionally deferred
- re-ingest and re-run `SB 277` and `ACR 117`
- compare final outputs against source truth manually
- add a "Pipeline Truth Diagnostic Utility" (CLI or Admin API) that can trace a single bill ID through every lifecycle stage: Scrape -> Raw Text -> Vector Chunks -> Research Proofs, and use this to validate the anchor bills `SB 277` and `ACR 117`
- add end-to-end truth tests that assert:
  - missing bill text blocks quantification
  - placeholder evidence cannot pass validation
  - retrieval is actually invoked in the legislation path
  - unsupported bills are not ranked as quantified outputs
- add durable fixtures or audit tests for the two anchor bills

Acceptance:
- `SB 277` and `ACR 117` are reprocessed under the new contract
- no unsupported quantified outputs survive in the California dashboard
- the new truth gates are covered by regression tests

Dependencies:
- blocked by `bd-tytc.3`
- blocked by `bd-tytc.4`
- blocked by `bd-tytc.5`
- blocked by `bd-tytc.6`

## Big-Bang Implementation Order

1. `bd-tytc.3` California bill-text ingestion and source fidelity
2. early quarantine/visibility suppression from `bd-tytc.6` lands immediately after ingestion truth work begins, so invalid California outputs stop being presented while the deeper repair is in flight
3. `bd-tytc.4` legislation retrieval and research depth unification
4. `bd-tytc.2` evidence-gated quantification and schema truthfulness
5. `bd-tytc.5` review, persistence, and telemetry honesty
6. remainder of `bd-tytc.6` frontend truth contract cleanup
7. `bd-tytc.7` backfill, re-run, and end-to-end truth verification

This is intentionally big-bang:
- no temporary dev coexistence where invalid California outputs remain user-visible
- no “keep ranking but add disclaimers” compromise
- no acceptance of fake telemetry or schema-coerced quantification during transition

## Required Validation Gates

### Gate A: Source Fidelity

Must prove:
- actual source URL fetched
- actual bill text persisted
- actual clause extraction can be traced to source text
- California bill text is written into `raw_scrapes` and successfully chunked/embedded before analysis

Required for:
- `SB 277`
- `ACR 117`

### Gate B: Retrieval and Research Depth

Must prove:
- legislation-analysis path uses retrieval or equivalent source-grounded context
- research artifacts are bill-specific
- insufficiency is represented explicitly when evidence fails
- structured evidence/provenance survives from retrieval/search into generation and review
- the runtime retrieval interface returns real chunks from the configured backend rather than empty stubs or mock documents
- retrieval filtering prevents cross-jurisdiction/source leakage

### Gate C: Quantification Eligibility

Must prove:
- no percentiles emitted without numeric basis
- invalid evidence cannot satisfy the contract
- unsupported bills fall back to non-quantified state

### Gate D: Honest Persistence and Telemetry

Must prove:
- pipeline runs show what actually happened
- no fake “embedding” or retrieval steps
- model/source/evidence state is persisted truthfully

### Gate E: Frontend Truthfulness

Must prove:
- no misuse of confidence as impact score
- no ranking of invalid California outputs
- no hardcoded placeholder panels implying real analysis
- incomplete-analysis states render without numeric-contract breakage or misleading `$0`/fallback values

### Gate F: Reprocessed Bill Audit

Must prove for `SB 277` and `ACR 117`:
- final displayed state matches repaired source/research truth
- if quantification is still unsupported, the UI says so plainly

### Gate G: Platform Spillover Check

Must prove:
- platform-level pipeline changes do not silently leave other jurisdictions on the old broken truth contract
- any intentionally deferred non-California follow-up is explicit and tracked

## Consultant-Coverage Matrix

This plan explicitly addresses:

### Issues I raised
- source acquisition failure as primary root cause
- legislation path must use retrieval
- evidence gate before quantification
- frontend confidence/impact-score misuse
- suppression of unsupported rankings

### Issues Gemini raised
- California scraper using wrong text field
- RAG illusion / bypass
- shallow five-query research
- schema-driven hallucination
- fake telemetry and low-confidence distortion

### Issues Opus raised
- stage-by-stage cascading failure
- official California source not actually followed
- OpenStates-only bulk discovery problems
- requirement to express “I don’t know”
- review step not capable of catching fabricated evidence/math
- hardcoded placeholder UI sections that compound false confidence

## Resolved Design Decisions

1. OpenStates is discovery/metadata only for California; the official California legislature-linked text/PDF/HTML source is canonical for bill text.
2. Retrieval is mandatory on the legislation-analysis path; the implementation may factor this as a shared legislation-research service, but the path may not fall back to web-search-only analysis when retrieval is available.
3. Quantification eligibility must be decided by deterministic evidence sufficiency gates before generation, not delegated to the model.
4. Mock and placeholder retrieval paths are not acceptable production fallbacks for California analysis; broken retrieval must fail closed, not silently substitute example documents.
5. Platform-level truth fixes must be treated as platform changes even when California is used as the anchor validation surface.

## Open Questions To Resolve During Implementation

1. Which exact source classes count as sufficient for direct fiscal quantification versus qualitative-only analysis?
2. What is the minimum acceptable numeric-basis contract for a quantified impact when no formal fiscal note exists?
3. Should the canonical legislation research runtime be a retrieval-backed `PolicyAgent` flow or a shared service extracted from both `PolicyAgent` and `AnalysisPipeline`?

These are implementation decisions inside the remediation, not reasons to delay the big-bang fix.

## Consultant Review Request

Before implementation starts, run:
- one frontend/product-truth architecture review
- one backend/research/orchestration architecture review

Both reviews must check whether this plan:
- fixes every diagnosed failure mode
- sequences the big-bang cutover safely
- avoids leaving unsupported California outputs visible in dev
