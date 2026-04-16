# Cycle 13: Live Provider Failure With Storage Readback

Feature-Key: bd-3wefe.13

## Purpose

Cycle 13 tested whether the Cycle 12 ranking and economic-parameter filtering changes improved the San Jose policy-document path for a direct-cost housing fee query.

The cycle used a narrower source family and query than Cycle 12:

- Jurisdiction: `San Jose CA`
- Source family: `policy_documents`
- Query: `San Jose commercial linkage fee affordable housing impact fee fee schedule per square foot`
- Analysis question: extract Commercial Linkage Fee or Affordable Housing Impact Fee rates, affected project categories, direct development-cost mechanism, and mark secondary research needed for household cost-of-living pass-through.

## Evidence Artifacts

- Live run: `docs/poc/policy-evidence-quality-spine/artifacts/live_cycle_13_windmill_domain_run.json`
- Live run summary: `docs/poc/policy-evidence-quality-spine/live_cycle_13_windmill_domain_run.md`
- Storage probe: `docs/poc/policy-evidence-quality-spine/artifacts/live_cycle_13_storage_probe.json`
- Admin read model: `docs/poc/policy-evidence-quality-spine/artifacts/live_cycle_13_admin_analysis_status.json`

## Result

Cycle 13 did not pass the product-quality gates, but it materially improved the diagnosis.

The live run completed the expected Windmill/backend step sequence:

1. `search_materialize`
2. `freshness_gate`
3. `read_fetch`
4. `index`
5. `analyze`
6. `summarize_run`

The run ended as `failed_terminal` because the Z.ai analysis call returned rate limit `429`.

## Data-Moat Findings

The search/ranking path improved substantially versus Cycle 11:

- Private SearXNG found the official San Jose Commercial Linkage Fee source as the top candidate.
- The reader attempted the official San Jose page first.
- Z.ai reader returned transient `500` errors for the official page twice.
- The pipeline then selected the SV@Home Commercial Linkage Fee page as a fallback source.

The selected fallback source was substantively relevant but not official-of-record:

- Selected URL: `https://siliconvalleyathome.org/resources/commercial-linkage-fees-2/`
- Reader evidence contained direct Commercial Linkage Fee context, ordinance timing, nexus-study framing, and fee feasibility discussion.
- The package also included a structured Legistar Web API lane, but that structured lane was diagnostic meeting metadata rather than policy-cost parameters.

Storage/readback is now live-proven for the package:

- Postgres package row: pass
- MinIO reader/package artifact readback: pass
- pgvector derivation: pass, with 46 chunks and 46 embeddings
- Windmill run id binding: pass in admin read model

The storage probe still reported overall fail because the run included a terminal failed analysis step. That is a useful product finding: provider failures should not discard or poison the data-moat proof, but economic-analysis quality must remain fail-closed.

## Economic-Analysis Findings

The admin read model correctly refused to produce a decision-grade economic conclusion:

- `decision_grade_verdict`: `not_decision_grade`
- `sufficiency_readiness_level`: `qualitative_only`
- `economic_analysis_status`: `secondary_research_needed`
- `canonical_analysis_binding`: `not_proven`
- `economic_output.user_facing_conclusion`: `null`

The Cycle 12 parameter filtering behaved correctly:

- `economic_trace.parameter_table`: empty
- `economic_trace.diagnostic_parameter_table`: one diagnostic `event_attachment_hint_count`
- `parameter_readiness`: fail because no economically meaningful source-bound parameter was present

This is the right behavior. The package contained relevant qualitative policy evidence, but not enough governed numeric parameters, assumptions, uncertainty bounds, or canonical LLM binding to support a quantitative cost-of-living conclusion.

## Gate Delta

- D2 scraped evidence quality: improved from procedural/weak source selection to substantively relevant fee-policy source selection, but not pass because official source reader failed and provider-quality metrics are incomplete.
- D3 structured evidence quality: still partial; structured lane exists but does not add economic parameters.
- D4 unified package: partial/pass mechanics; package contains scraped and structured lanes with provenance.
- D5 storage readback: pass for Postgres, MinIO, and pgvector mechanics.
- D6 Windmill integration: pass for current-run id/read-model binding.
- E1-E5 economic quality: fail/not_proven, correctly fail-closed.

## Next Tweak

Cycle 14 should make analysis provider failure non-destructive to the data-moat run:

- Preserve the package, storage, indexing, and admin read model.
- Return an auditable fail-closed analysis payload when the LLM provider fails after evidence chunks exist.
- Keep economic Gate B blocked until canonical LLM narrative, parameter provenance, assumptions, sensitivity, and secondary research are proven.
