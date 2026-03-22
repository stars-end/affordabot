# Comprehensive End-to-End Pipeline Truth Audit: SB 277 & ACR 117

## Executive Verdict
The Affordabot analytical pipeline for California legislation is a facade. It presents itself as a sophisticated "deep research" and "RAG-backed" AI system, but in reality, it operates entirely detached from ground truth. The system completely fails to acquire the actual bill text, explicitly bypasses the RAG vector database during analysis, executes an artificially shallow web search (capped at 5 queries), and forces an LLM to hallucinate precise quantitative impact estimates (`p10`-`p90` dollar bounds) to satisfy a rigid Pydantic schema. Finally, the frontend dangerously masks these ungrounded hallucinations by rebranding low LLM confidence scores as authoritative "Impact Scores."

## End-to-End Pipeline Breakdown (Fiction vs. Reality)

### Stage 1: Web Scraping & Source Acquisition (The Original Sin)
* **Intended Behavior:** The system scrapes full legislative texts to provide the LLM with a primary source document.
* **Actual Reality:** The `CaliforniaStateScraper` (`backend/services/scraper/california_state.py`) fetches bill metadata via the OpenStates API but completely fails to extract the substantive bill text. It pulls the `versions[0].note` field (which typically just says "Introduced" or "Amended") or falls back to the bill `title`. 
* **Persistence Failure:** Because the CA scraper returns `ScrapedBill` objects directly without persisting the raw text to the `raw_scrapes` table, the `AnalysisPipeline` looks for a scrape record and fails. It subsequently logs `"No raw scrape found for this bill"` and permanently hardcodes `text: "Full text placeholder"` into the `legislation` table (`backend/services/llm/orchestrator.py` line 431).

### Stage 2: The RAG Pipeline (Bypassed & Simulated)
* **Intended Behavior:** Municipal codes and legislation are embedded into `pgvector` and retrieved during analysis to ground the LLM's claims.
* **Actual Reality:** 
  1. The background cron jobs (`run_rag_spiders.py`) only ingest generic San Jose municipal codes and meetings, completely ignoring California state legislation.
  2. Even if CA bills were in the vector database, the `AnalysisPipeline` explicitly **does not use** the `RetrieverTool` or query `pgvector` during the generative step. 
  3. In `orchestrator.py`, the pipeline artificially logs a `step_number=0.5, step_name="embedding"` event to the audit trail if a `document_id` exists, but the generative step never actually performs a semantic search against this data. RAG is structurally bypassed for these bills.

### Stage 3: Deep Research (Superficial Snippet Fetching)
* **Intended Behavior:** The system executes exhaustive, multi-step web research to discover the economic impacts of the bill.
* **Actual Reality:** The `AnalysisPipeline` delegates to `ResearchAgent`, which uses the `ZaiResearchService`. While `ZaiResearchService._generate_search_queries` generates up to 40 highly specific keyword strings, the `search_exhaustively` method hardcodes a limit to loop over `queries[:5]`. It performs exactly 5 raw web searches, grabs the HTML snippets, and injects them as a single blob. This is a shallow, single-pass search, not iterative deep research.

### Stage 4: Quantification & LLM Generation (Schema-Driven Hallucination)
* **Intended Behavior:** An expert policy LLM mathematically synthesizes the RAG context, research, and bill text to produce bounded cost-of-living estimates.
* **Actual Reality:** 
  1. The LLM is provided with `"Full text placeholder"`.
  2. It receives either zero or 5 generic web snippets.
  3. The `LegislationAnalysisResponse` Pydantic schema **strictly requires** float values for `p10`, `p25`, `p50`, `p75`, and `p90`. 
  4. Without an "escape hatch" in the schema for unquantifiable data, the LLM is forced to invent a plausible-sounding `chain_of_causality` and completely fabricate dollar amounts to avoid failing the JSON parser.

### Stage 5: Review and Refinement (The Rubber Stamp)
* **Intended Behavior:** A secondary LLM agent critiques the analysis for accuracy and factual grounding, rejecting unsupported claims.
* **Actual Reality:** The `_review_step` passes the generated JSON to an LLM with the prompt: *"You are a senior policy reviewer. Critique the following analysis..."* Because the LLM evaluates the output purely on its internal logical consistency and structural adherence—without programmatic verification of math or citation links—it readily passes confidently hallucinated numbers.

### Stage 6: Frontend UI Distortion (Misrepresentation of Certainty)
* **Intended Behavior:** The UI presents the data accurately with clear confidence intervals.
* **Actual Reality:** 
  1. The backend passes down a `confidence` field (a 0.0-1.0 float representing the LLM's own uncertainty, e.g., 0.3).
  2. The frontend (`frontend/src/components/ImpactCard.tsx` and `dashboard/[jurisdiction]/page.tsx`) multiplies this confidence by 10 and explicitly labels it **"Impact Score"** (e.g., 3.0/10). This creates a dangerous false authority, tricking the user into thinking a 30% confidence level is actually a 3/10 measure of severity.
  3. The `Effective Date` is statically hardcoded to default to `"Jan 1, 2024"` if the LLM doesn't invent one.

---

## Deep-Dive: Bill Specific Traces

### SB 277 (California)
* **What it actually is:** A bill regarding criminal procedure and the search of persons.
* **What the Scraper found:** Only the title.
* **What Research found:** The web search completely failed. The returned evidence explicitly states: `url: "N/A - Research unavailable"`, `excerpt: "Analysis based on bill title alone due to search failure; detailed research needed for precise impacts."`
* **The Hallucination:** Despite having **zero** text and **zero** external research, the LLM was forced by the Pydantic schema to output numbers. It fabricated a `p50` (median) Total Annual Cost of **$15,000,000**.
* **The Fabricated Causality:** To justify the hallucinated $15M, it invented a 5-step chain: *"1) Bill modifies search procedures → 2) Law enforcement requires new training... → 4) Potential constitutional challenges increase litigation costs → 5) Municipal budgets affected"*.

### ACR 117 (California)
* **What it actually is:** Assembly Concurrent Resolution 117 designating "Maternal Health Awareness Day". Concurrent resolutions typically express legislative opinion and have no direct fiscal appropriations.
* **What the Scraper found:** Only the title.
* **What Research found:** 5 generic web searches returned definitions of what an Assembly Concurrent Resolution is (from `leginfo.legislature.ca.gov`) and a link to the California State Protocol Office. It found no specific data on ACR 117.
* **The Hallucination:** Forced by the quantitative schema bounds, the LLM fabricated a `p50` impact of **$5,000**.
* **The Fabricated Causality:** It invented a chain suggesting *"Minimal administrative costs for notification and documentation"* by state agencies. While logically plausible, the $5,000 figure is an entirely ungrounded invention strictly generated to prevent a schema validation error.

---

## Required Review Questions Answered
1. **For SB 277, did the system ever obtain enough real bill-specific evidence to justify any of the displayed dollar estimates?** 
   * **No.** The system explicitly logged "Research unavailable" and had no bill text. The estimates are 100% mathematically ungrounded fabrications.
2. **For ACR 117, are the low-dollar estimates genuinely grounded or merely more plausible-looking speculation?** 
   * **Plausible speculation.** An awareness day resolution has no codified fiscal impact. The $5,000 figure is a schema-driven hallucination designed to look reasonable.
3. **At what exact pipeline stage do fabricated-looking estimates first appear?** 
   * In the `_generate_step` of `AnalysisPipeline`. The prompt demands economic analysis, and the Pydantic schema strictly enforces float types for `p10`-`p90` without allowing `null` or "cannot determine".
4. **Are the evidence items for these bills tool-produced, model-synthesized, or mixed?** 
   * **Mixed/Fabricated.** The tool retrieved generic URLs (or failed entirely for SB 277), but the specific excerpts and the mapping of that evidence to the fabricated dollar amounts were entirely synthesized by the LLM.
5. **Is the current research step meaningfully "deep," or is it shallow search/snippet retrieval?** 
   * **Shallow snippet retrieval.** `ResearchAgent` runs a maximum of 5 concurrent Google searches, grabs the text snippets, and immediately passes them downstream. RAG is bypassed, and there is no iterative digging.
6. **Is the current review/refine loop a real truthfulness gate?** 
   * **No.** It is a blind LLM-to-LLM rubber stamp. It cannot programmatically verify if the math adds up or if the citations actually contain the claims.
7. **Which UI fields are merely displaying bad backend data, and which are independently broken by frontend/API contract bugs?** 
   * The `Total Annual Cost` and `Evidence` lists are displaying hallucinated backend data.
   * The **Impact Score** is an active frontend distortion (it is actually the LLM's `confidence` score multiplied by 10).
   * The **Effective Date** ("Jan 1, 2024") is statically hardcoded in the frontend when data is missing.
8. **What are the first three changes to make, in order, if the goal is to stop false precision immediately?**
   * **Fix 1 (The Schema):** Modify `LegislationAnalysisResponse` so `p10`-`p90` are `Optional[float]`, and explicitly prompt the LLM to omit them when the evidence does not support a precise calculation.
   * **Fix 2 (The Scraper):** Rewrite `CaliforniaStateScraper` to download the actual PDF/HTML text of the bills, and remove the hardcoded `"Full text placeholder"` from `postgres_client.store_legislation`.
   * **Fix 3 (The Frontend):** Correct the UI to explicitly label `confidence` as "Confidence" (and render it as a percentage or descriptive tag) rather than misrepresenting it as an "Impact Score." Remove the hardcoded fallback dates.

---

## Root-Cause Ranking
1. **Primary Root Cause (Schema Design Failure):** The rigid enforcement of quantitative float bounds (`p10`-`p90`) in Pydantic acts as a "Hallucination Engine," forcing the LLM to invent numbers when evidence is missing.
2. **Secondary Enabling Cause (Source Acquisition Failure):** The `CaliforniaStateScraper` systematically fails to retrieve actual bill text, blinding the entire analytical pipeline from the very first step.
3. **Tertiary Enabling Cause (Research-Depth Failure):** The pipeline falsely assumes it is doing RAG and Deep Research, when in reality it skips `pgvector` entirely and arbitrarily caps web searches at 5 shallow queries.
4. **UI/API Contract Bugs (Frontend Interpretation Failure):** The frontend actively commits data distortion by mapping a low statistical `confidence` metric into a high-visibility `Impact Score`, lending a false aura of authority to broken backend output.
