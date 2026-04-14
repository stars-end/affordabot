# Economic Readiness Overlay Report (bd-2agbe.5)

- generated_at: `2026-04-14T07:39:59.752997+00:00`
- verifier_version: `2026-04-14.overlay-v1`
- live_report_path: `docs/poc/windmill-domain-boundary-integration/artifacts/sanjose_live_gate_report.json`
- bakeoff_report_path: `docs/poc/search-source-quality-bakeoff/artifacts/search_source_quality_bakeoff_report.json`
- gate_fixture_path: `backend/scripts/verification/fixtures/economic_evidence_gate_cases.json`

## Verdict

- decision_grade_for_numeric_economic_analysis: `False`
- final_verdict: `fail_closed_qualitative_only`
- blocking_gate: `economic_evidence_card_sufficiency`

Recommendation: Not decision-grade for numeric economics. Retrieval/reader quality is usable, but structured evidence cards are missing; fail closed before parameterization.

## Gate Results

| gate | status | reason |
|---|---|---|
| search_provider_source_quality | pass | search_sources_sufficient_for_artifact_discovery |
| reader_substrate_quality | pass | reader_and_substrate_outputs_are_substantive |
| economic_evidence_card_sufficiency | fail | missing_structured_evidence_cards_with_provenance |
| parameterization_sufficiency | fail | missing_parameter_cards_or_formula_ids |
| assumption_sufficiency | fail | missing_or_invalid_assumption_cards |
| deterministic_quantification_readiness | fail | deterministic_quantification_not_supported |
| llm_explanation_support | pass | llm_explanation_present_but_requires_quant_guardrails |

## Gate Details

### search_provider_source_quality

- status: `pass`
- reason: `search_sources_sufficient_for_artifact_discovery`
- provider_count: `3`
- providers_with_official_hits: `3`
- best_official_domain_hit_rate_percent: `94.7`
- best_reader_ready_rate_percent: `36.8`
- live_search_materialize_status: `succeeded`
- live_search_result_count: `10`

### reader_substrate_quality

- status: `pass`
- reason: `reader_and_substrate_outputs_are_substantive`
- read_fetch_status: `succeeded`
- index_status: `succeeded`
- analyze_status: `succeeded`
- raw_scrape_row_count: `7`
- reader_excerpt_chars: `591`
- selected_chunk_count: `20`

### economic_evidence_card_sufficiency

- status: `fail`
- reason: `missing_structured_evidence_cards_with_provenance`
- structured_evidence_card_count: `0`
- valid_evidence_card_count: `0`
- note: `Reader snippets without explicit source_url/content_hash/excerpt cards are not sufficient for quantified economics.`

### parameterization_sufficiency

- status: `fail`
- reason: `missing_parameter_cards_or_formula_ids`
- parameter_card_count: `0`
- resolved_numeric_parameter_count: `0`
- formula_id_count: `0`
- formula_ids: `[]`

### assumption_sufficiency

- status: `fail`
- reason: `missing_or_invalid_assumption_cards`
- assumption_card_count: `0`
- valid_assumption_card_count: `0`

### deterministic_quantification_readiness

- status: `fail`
- reason: `deterministic_quantification_not_supported`
- deterministic_flag: `False`
- quant_output_count: `0`
- valid_quant_output_count: `0`

### llm_explanation_support

- status: `pass`
- reason: `llm_explanation_present_but_requires_quant_guardrails`
- llm_excerpt_chars: `382`
- llm_quality_note: `LLM analysis produced a substantive answer from persisted evidence.`

## Manual Audit Notes

- Search/provider quality is treated independently from quantitative economics readiness.
- Reader/substrate success confirms retrieval and persistence, not quantitative sufficiency.
- Quantified economics requires structured evidence cards + parameterization + assumptions + deterministic formulas.
- Current San Jose live artifact contains selected chunks and qualitative analysis, but does not expose structured evidence cards with source_url/content_hash/excerpt linkage.
- No explicit numeric parameter card payload and formula_id set were found in the live analyze step output.
- No deterministic quantification outputs with scenario bounds were found; numeric economic judgment should fail closed.
- Live manual audit note: LLM analysis produced a substantive answer from persisted evidence.
