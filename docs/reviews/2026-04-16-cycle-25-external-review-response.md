# Cycle 25 External Review Response

Feature-Key: bd-3wefe.13
PR: https://github.com/stars-end/affordabot/pull/436

## Review Usefulness Scores

- Gemini: 86/100. Most useful for reframing the product risk: the unified package existed, but economic parameterization depth was brittle and rescued by secondary search. It correctly pushed past orchestration success into semantic data quality.
- Opus: 93/100. Most actionable review. It identified concrete code defects with file paths: hardcoded provider provenance, inner reader-substance disagreement, Tavily lane double-registration, evidence-card metadata degradation, stale run notes, and public/private SearXNG ambiguity.
- GLM-5.1: 82/100. Useful corroboration and prioritization. It correctly separated narrow architecture proof from broader lock, called out storage proof wording, CKAN overclaiming, and Tavily tiering. It was less precise than Opus on the hardcoded-provider root cause.

## Issue-by-Issue Disposition

### Hardcoded `private_searxng` provider label

Disposition: agree.

The provider label was emitted as a literal in the bridge, so artifacts could not prove whether SearXNG, Tavily, Exa, or Z.ai search actually ran. The fix derives provider provenance from the active search client and records runtime metadata: provider, client class, configured provider, endpoint host, and endpoint-present status.

Changed:

- `backend/services/pipeline/domain/bridge.py`
- `backend/tests/services/pipeline/test_bridge_runtime.py`

### Inner reader-substance gate failed while admin scraped/search passed

Disposition: agree.

The builder conflated economic insufficiency with reader-source insufficiency by setting scraped evidence readiness to `insufficient` whenever any fail-closed reason existed. That made a good reader artifact fail the inner reader gate because household pass-through evidence was missing. The fix separates scraped-source readiness from economic sufficiency.

Changed:

- `backend/services/pipeline/domain/bridge.py`
- `docs/poc/policy-evidence-quality-spine/manual_audit_cycle_25_data_moat.md`

### Tavily secondary evidence double-registered as scraped provenance

Disposition: agree.

`structured_secondary_source` was not recognized as structured, so Tavily rows could flow into `scraped_sources` with provider `other`, polluting `fail_closed_reasons` with `scraped_provider_identity_missing`. The fix maps structured secondary lanes to `SourceLane.STRUCTURED` and adds a regression test.

Changed:

- `backend/services/pipeline/policy_evidence_package_builder.py`
- `backend/tests/services/pipeline/test_policy_evidence_package_builder.py`

### Primary Legistar document did not emit parameter cards

Disposition: agree.

The captured Cycle 25 run summarized fee schedule text from the primary Legistar attachment but did not bind those values into parameter cards. The fix extracts source-bound fee facts from the analyze step's selected primary chunks/key points, preserves source excerpts, classifies them as `bill_or_reg_text`, and flags malformed currency strings.

Changed:

- `backend/services/pipeline/domain/bridge.py`
- `backend/services/pipeline/policy_evidence_package_builder.py`
- `backend/tests/services/pipeline/test_bridge_runtime.py`
- `docs/poc/policy-evidence-quality-spine/manual_audit_cycle_25_economic_analysis.md`

### Evidence-card metadata degradation on official Legistar attachment

Disposition: agree.

The captured package used `tier_c`, epoch retrieved time, `source_type=other`, and a stub excerpt for the authoritative attachment. The fix assigns the primary scraped artifact `tier_a`, uses raw scrape `created_at`, carries a real excerpt, and maps the source type to `ordinance_text`.

Changed:

- `backend/services/pipeline/domain/bridge.py`

### Stale reader-quality note and manual verdict

Disposition: agree.

The markdown report carried a stale note from an earlier failed discovery cycle. The fix corrects the Cycle 25 markdown report and explicitly calls out the monetary parsing anomaly.

Changed:

- `docs/poc/policy-evidence-quality-spine/live_cycle_25_windmill_domain_run.md`

### Public SearXNG bakeoff vs private product-path SearXNG ambiguity

Disposition: agree.

The diagnostic bakeoff and product path were separate, but the docs did not say that clearly. The fix adds documentation and runtime provider provenance for future package artifacts.

Changed:

- `backend/services/pipeline/domain/bridge.py`
- `docs/poc/policy-evidence-quality-spine/live_cycle_25_windmill_domain_run.md`

### Storage proof wording

Disposition: partially agree.

The admin read model is not merely reading refs; backend storage-service proof can include a persisted package row and MinIO artifact probe. However, the Windmill harness' independent DB probe failed from the local probing context. The fix changes the storage gate wording to `Backend storage-service proof` and exposes `proof_mode` plus `direct_probe_available`.

Changed:

- `backend/services/pipeline/policy_evidence_quality_spine_economics.py`
- `backend/tests/services/pipeline/test_policy_evidence_quality_spine_economics.py`
- `docs/poc/policy-evidence-quality-spine/live_cycle_25_windmill_domain_run.md`

### CKAN catalog overclaim

Disposition: agree.

CKAN was cataloged but unavailable in Cycle 25. The fix annotates catalog entries per runtime evidence and marks unavailable sources as `cataloged_unavailable` with `live_proven=false`.

Changed:

- `backend/services/pipeline/structured_source_enrichment.py`

### Tavily tier classification

Disposition: agree.

Tavily secondary search-derived snippets should not be weighted like direct structured/API sources. The fix downgrades Tavily secondary evidence to `tier_c`.

Changed:

- `backend/services/pipeline/structured_source_enrichment.py`
- `docs/poc/policy-evidence-quality-spine/manual_audit_cycle_25_economic_analysis.md`

### Monetary parsing anomaly

Disposition: agree.

`$18.706.00` is malformed and must not support a decision-grade numeric claim. The fix excludes malformed multi-decimal currency strings from primary parameter extraction and records `primary_parameter_money_format_anomaly`.

Changed:

- `backend/services/pipeline/domain/bridge.py`
- `backend/tests/services/pipeline/test_bridge_runtime.py`

### Beads memory coverage

Disposition: agree.

The review result should be durable in Beads memory after this patch is validated. If Beads/Dolt is unavailable, this document is the durable repo-local fallback.

## Architecture Impact

Data moat: still lock narrow only. The shape is sound: Windmill orchestrates, backend owns semantics and quality gates, Postgres/MinIO/pgvector persist and index, and admin/frontend consume read models. The patch makes provenance and lane semantics more falsifiable.

Economic analysis: do not lock globally. The fix improves economic input quality by binding primary-source fee facts, but final household cost-of-living analysis still correctly requires governed assumptions, model cards, arithmetic validation, uncertainty/sensitivity, and secondary research for indirect pass-through.

## Validation

Targeted test command:

```bash
cd backend
poetry run pytest tests/services/pipeline/test_bridge_runtime.py tests/services/pipeline/test_policy_evidence_package_builder.py tests/services/pipeline/test_policy_evidence_quality_spine_economics.py tests/routers/test_admin_pipeline_read_model.py -q
```

Result: 67 passed, 4 warnings.
