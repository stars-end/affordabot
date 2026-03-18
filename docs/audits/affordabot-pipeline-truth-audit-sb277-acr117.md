# Affordabot Pipeline Truth Audit: SB 277 & ACR 117

## Executive Verdict
The system is currently fabricating high-precision dollar impact estimates based on fundamentally broken ingestion and superficial research. The pipeline never acquires the actual bill text for California legislation, substituting titles and "mock" fallback text. Because the rigid JSON schema requires quantitative `p10`-`p90` bounds, the LLM hallucinates precise numbers backed by placeholder or missing evidence. Furthermore, the frontend actively distorts the LLM’s low confidence scores by rebranding them as an "Impact Score" out of 10.

## Timeline / Dataflow Map
1. **Source Acquisition**: `CaliforniaStateScraper` attempts to fetch bills via OpenStates API but extracts the version `note` (e.g., "Introduced") or falls back to the `title` instead of the actual bill text.
2. **Ingestion**: The pipeline stores "Full text placeholder" in the database (`AnalysisPipeline._complete_pipeline_run`). 
3. **Research**: `ZaiResearchService` generates hardcoded keyword strings and limits to 5 searches. It returns shallow snippets without true synthesis. For SB 277, it returns "N/A - Research unavailable".
4. **Quantification**: The `generate_step` forces the LLM to output a strict JSON schema (`LegislationAnalysisResponse`) which requires `p10`-`p90` floats. Without text or research, the LLM hallucinates numbers (e.g., $15M for SB 277, $5K for ACR 117).
5. **Review / Refine**: The `_review_step` asks an LLM to critique the analysis without programmatic validation of math or evidence links, easily passing confidently hallucinated numbers.
6. **API / Persistence**: `confidence_score` is mapped to `confidence` in the API. `effective_date` is omitted.
7. **Frontend Display**: The UI misinterprets the `confidence` score (e.g., 0.3) by multiplying it by 10 and labeling it "Impact Score" (3.0/10). Missing `effective_date` defaults statically to "Jan 1, 2024".

## Bill: SB 277 (California)
- **Live Output**: Shows a Total Annual Cost of $15,000,000. 
- **Evidence State**: Evidence array explicitly says "N/A - Research unavailable" and the excerpt admits "Analysis based on bill title alone due to search failure".
- **Verdict**: The quantitative values are completely fabricated by the LLM trying to fulfill the Pydantic schema requirements. The system never had bill-specific evidence to justify the estimates.

## Bill: ACR 117 (California)
- **Live Output**: Shows a median impact of $5,000 for "Maternal Health Awareness Day".
- **Evidence State**: Evidence contains generic links to the CA legislative info site and the state protocol office, with no specific research on this particular resolution.
- **Verdict**: The low-dollar estimates are genuinely ungrounded speculation, hallucinated by the model because the schema demands quantitative bounds.

## Stage-by-Stage Findings
### 1. Raw Source and Scrape (Source Acquisition Failure)
- **Code Reference**: `backend/services/scraper/california_state.py` line 48.
- **Finding**: Extracts `note` from OpenStates version objects, falling back to `title`. It never gets the true `text` of the bill.
- **Code Reference**: `backend/services/llm/orchestrator.py` line 431.
- **Finding**: Hardcodes `text: "Full text placeholder"` when saving to the database.

### 2. Research Depth (Research-Depth Failure)
- **Code Reference**: `backend/services/research/zai.py` line 186.
- **Finding**: Executes 5 hardcoded keyword queries and concatenates the resulting snippets. This is superficial search, not deep research.

### 3. Quantification (Schema Design Failure)
- **Code Reference**: `backend/schemas/analysis.py` line 21-25.
- **Finding**: The Pydantic schema strongly types `p10` through `p90` as floats, forcing the LLM to output precise dollar estimates even when the prompt context contains zero relevant facts.

### 4. Review and Validation (Validation Failure)
- **Finding**: The review loop (`_review_step`) relies entirely on the LLM to self-critique. Unsupported specific numbers easily bypass this step because they look structurally correct.

### 5. Frontend Distortion (API/Frontend Contract Failure)
- **Code Reference**: `frontend/src/components/ImpactCard.tsx` and `frontend/src/app/dashboard/[jurisdiction]/page.tsx` line 164.
- **Finding**: The frontend maps the 0.0-1.0 `confidence_score` (which drops to `confidence` in API) to a `/10` scale and misleadingly labels it "Impact Score".
- **Finding**: `Effective Date` defaults to `Jan 1, 2024` if missing.

## Root-Cause Ranking
1. **Primary Root Cause**: **Schema Design Failure** - The rigid requirement for `p10`-`p90` floats forces the LLM to fabricate numbers when evidence is missing.
2. **Secondary Enabling Cause**: **Source Acquisition Failure** - The system never acquires the actual bill text, starving the analysis of ground truth.
3. **Tertiary Enabling Cause**: **Research-Depth Failure** - The "deep research" is a shallow 5-query snippet fetch, failing to provide compensatory evidence.
4. **UI/API Contract Bugs**: **Frontend Interpretation Failure** - The frontend dangerously rebrands `confidence` as `Impact Score`, creating false authority for bad data.

## Change First (Remediation Order)
1. **Fix the Schema Constraint**: Make the `p10`-`p90` fields optional (`Optional[float]`) or strictly allow a "cannot determine" state when evidence is insufficient.
2. **Fix the Frontend Distortions**: Remove the misleading "Impact Score" label (call it "Confidence") and remove the hardcoded "Jan 1, 2024" effective date.
3. **Fix Bill Ingestion**: Update `CaliforniaStateScraper` to actually fetch the full bill text content instead of just the version note/title, and store it properly in `store_legislation` instead of using "Full text placeholder".
