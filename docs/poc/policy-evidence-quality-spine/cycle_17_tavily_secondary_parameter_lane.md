# Cycle 17: Tavily Secondary Parameter Lane

Feature-Key: bd-3wefe.13

## Purpose

Cycles 14-16 showed that the official San Jose CLF page is the correct primary source, but the Z.ai reader output misses table rows containing dollar fee rates. A controlled Tavily probe recovered those rows from the official San Jose page snippet.

Cycle 17 implements a bounded secondary structured evidence lane so those source-bound rate facts can enter the data moat and economic parameter table without becoming unsupported analysis.

## Tweak

### Structured Evidence Lane

`StructuredSourceEnricher` now supports a Tavily secondary search lane:

- Runs only when `TAVILY_API_KEY` is configured.
- Runs only for rate/economic contexts such as fee, rate, impact fee, linkage, nexus, per square foot, or cost.
- Uses one bounded request with `max_results=5`.
- Accepts only provenance-safe official/public-sector URLs.
- Extracts only explicit dollar values tied to CLF/impact-fee and square-foot context.
- Marks the lane as `structured_secondary_source`, not primary search-of-record.

The extracted facts include:

- field
- value
- unit
- source URL
- source excerpt
- provider rank
- provenance lane

### Economic Parameter Consumption

`PolicyEvidenceQualitySpineEconomicsService` now treats source-bound structured fee facts as economically meaningful when they carry economic signal in name, unit, or excerpt.

It preserves per-row metadata:

- category
- effective date
- payment timing
- time horizon

It still blocks final decision-grade output when model cards, uncertainty, canonical analysis binding, or assumptions are missing.

## Validation

Focused validation:

- `poetry run pytest tests/services/pipeline/test_structured_source_enrichment.py tests/services/pipeline/test_policy_evidence_quality_spine_economics.py tests/services/pipeline/test_bridge_runtime.py -q` -> 56 passed
- `poetry run ruff check services/pipeline/structured_source_enrichment.py services/pipeline/policy_evidence_quality_spine_economics.py tests/services/pipeline/test_structured_source_enrichment.py tests/services/pipeline/test_policy_evidence_quality_spine_economics.py` -> passed

## Expected Gate Delta

- D3 structured evidence quality should improve from diagnostic metadata to source-bound numeric fee facts.
- D4 unified package should include scraped official source plus secondary structured provider facts.
- E1/E2 should improve because the economic parameter table can now contain source-bound fee rates.
- E5 should remain not decision-grade until model/assumption/uncertainty/canonical binding are present.

## Live Follow-Up

Cycle 18 should deploy this change and rerun the San Jose CLF path. Manual audit must verify:

1. Tavily secondary facts are present in the stored package.
2. The facts are official-source-bound.
3. `economic_trace.parameter_table` contains fee rows.
4. Final economic output still refuses a household cost-of-living conclusion without pass-through assumptions and uncertainty bounds.
