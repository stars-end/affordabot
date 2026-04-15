# Package-Readiness Source-Quality Audit

Date: 2026-04-15
Beads: `bd-3wefe.2` / `bd-3wefe.3`
Input to: `bd-3wefe.4`

## 1) Source-quality taxonomy

This taxonomy is the pass/fail vocabulary for source inputs before package
assembly.

| Term | Definition | Fail signal |
| --- | --- | --- |
| `search_recall` | Provider returns official-domain and artifact-grade candidates for the query family within top-N. | Official artifacts absent from top-N or only portal/directory URLs appear. |
| `readable_artifact` | Selected candidate survives portal prefetch skip and reader-substance gate. | `prefetch_skipped_low_value_portal` or `reader_output_insufficient_substance`. |
| `economic_signal` | Artifact or structured facts contain policy parameters/mechanism clues usable for quantitative analysis (cost, units, affected population, compliance path). | Only navigation/header text, no measurable fields, no mechanism clue. |
| `package_ready_evidence` | Evidence has canonical identity, provenance, freshness, and either structured facts or substantive reader text. | Missing canonical key/content hash/provider lineage or evidence marked `insufficient`. |
| `insufficiency` | Explicit fail-closed state where evidence cannot support economic handoff. | `no_candidate_urls`, `no_raw_scrapes`, `no_evidence_chunks`, stale/empty blocked freshness. |

## 2) Scraped provider/query-family matrix (existing evidence only)

Primary evidence sources:

- `docs/poc/search-source-quality-bakeoff/artifacts/search_source_quality_bakeoff_report.json`
- `docs/research/2026-04-14-private-searxng-quality-review.md`
- `backend/services/pipeline/domain/commands.py`
- `backend/services/pipeline/domain/bridge.py`
- `backend/services/llm/web_search_factory.py`

| Provider | Official-domain hit rate | Reader-ready rate | Observed strengths | Observed failure mode | Package-readiness posture |
| --- | ---: | ---: | --- | --- | --- |
| `private_searxng` | 94.7% | 21.1% | Best official-domain recall in bakeoff; good top-5 artifact presence for San Jose queries. | Ranker can select portals over artifacts unless URL penalties/prefetch skip/substance gates are enforced. | Primary candidate only with strict candidate-ranking + reader gating. |
| `tavily` | 84.2% | 36.8% | Best aggregate bakeoff score in that run; stronger selected-candidate quality than SearXNG baseline. | Free-tier quota capped; cannot be default broad lane without spend/rate planning. | Hot fallback candidate. |
| `exa` | 73.7% | 31.6% | High top-score on some targeted queries and useful evaluation lane. | Free-tier cap and UA sensitivity; not suitable for broad default lane. | Bakeoff/eval-only lane. |

Query-family quality implication:

- `meeting_minutes` and `agenda_item` families are most sensitive to portal
  mis-selection.
- Existing `rank_reader_candidates(...)`, `prefetch_skip_reason(...)`, and
  `assess_reader_substance(...)` already provide enforceable gates; package
  readiness should consume their outcomes, not bypass them.

Provider identity requirement:

- Provider must survive from search snapshot -> ranked candidate -> reader
  artifact -> package card provenance. Current tables (`search_result_snapshots`,
  `content_artifacts`) and command refs can carry this; `bd-3wefe.4` must
  normalize it into package metadata.

## 3) Structured source-family matrix (existing evidence only)

Primary evidence sources:

- `docs/poc/structured-source-lane/artifacts/structured_source_lane_poc_report.json`
- `docs/poc/structured-source-lane/artifacts/structured_source_breadth_audit.json`
- `docs/poc/source-expansion/artifacts/source_expansion_api_key_matrix.md`
- `docs/research/2026-04-14-structured-source-lane-audit.md`
- `backend/services/scraper/california_state.py`

| Source family | Access | Free/key posture | Cadence/freshness shape | Economic usefulness | Storage/package target |
| --- | --- | --- | --- | --- | --- |
| `legistar_sanjose` | Public API | `free_public`, no key | Meeting/matter updates per jurisdiction cycle | High for direct fiscal/compliance evidence | Structured facts + linked artifact refs into package evidence cards |
| `ca_pubinfo_leginfo` | Official raw files | `free_public`, no key | Daily file feed | High for CA legislation text/metadata grounding | Raw file artifact + normalized policy facts + canonical linked refs |
| `arcgis_public_gis_dataset` | Public REST API | `free_public`, no key | Dataset-dependent refresh | Medium/contextual (must curate policy-specific layers) | Structured context facts with lower source tier unless policy-direct dataset |
| `ca_ckan_open_data_catalog` | CKAN API | `free_public`, no key | Dataset-dependent | Medium; useful for quantitative context and joins | Structured catalog facts; promote to package when policy-relevant fields exist |
| `openstates_plural_api` | API | `free_tier_available`, key (`OPENSTATES_API_KEY`) | Legislative session cadence | Medium/high for discovery/metadata; canonical text should remain official source | Discovery metadata plus official-text refs |
| `socrata_open_data` | SODA API | public with optional app token (`SOCRATA_APP_TOKEN`) | Dataset-dependent | High when jurisdiction has housing/zoning/permit datasets | Structured facts lane once token/signup is enabled for targeted jurisdictions |

Backlog/scrape-lane families (not structured-lane for this wave):

- `granicus`, `civicplus`, `boarddocs`, `novusagenda`, `primegov`, `swagit`,
  `escribe` remain scrape/reader lane unless a stable API/raw-file contract is
  proven.

## 4) Minimum unified package input fields for bd-3wefe.4

Minimum required fields to merge scraped + structured lanes into one
`PolicyEvidencePackage` input surface:

1. Identity and provenance:
   `canonical_document_key`, `jurisdiction`, `source_lane`, `provider`,
   `source_tier`, `artifact_url`, `retrieved_at`, `content_hash`.
2. Search/read lineage (scraped lane):
   `query_family`, `query`, `search_snapshot_id`, `candidate_rank`,
   `candidate_score`, `prefetch_skip_reason` (if skipped),
   `reader_substance_reason`, `reader_artifact_ref`.
3. Structured lineage (structured lane):
   `source_family`, `access_method`, `sample_endpoint_or_file_url`,
   `structured_policy_facts[]` with `field/value/unit`, `linked_artifact_refs[]`.
4. Economic mapping:
   `artifact_type`, `evidence_source_type`, `selected_impact_mode`,
   `mechanism_family`, `economic_handoff_ready`, `evidence_readiness`.
5. Freshness and gate state:
   `freshness_status`, `snapshot_age_hours`, `decision_reason`, `retry_class`,
   `alerts[]`.

Evidence basis:

- Existing integration artifact already carries a near-minimum envelope:
  `docs/poc/source-integration/artifacts/scrape_structured_integration_report.json`.
- Domain command responses already expose decision/failure semantics needed for
  fail-closed packaging.

## 5) Failure classes and gate recommendations

Map these failure classes into explicit gate outputs across
`bd-3wefe.2/.3/.4/.10/.12`:

| Failure class | Typical reason code | Where observed | Gate recommendation |
| --- | --- | --- | --- |
| search transport/provider failure | `search_transport_error` | domain bridge/commands | mark retryable, preserve provider + query metadata, trigger fallback policy only if configured |
| empty recall | `search_empty_result`, `empty_blocked`, `empty_but_usable` | freshness + search | fail closed for blocked states; allow alerted continuation only under explicit stale/empty policy |
| portal mis-selection | `prefetch_skipped_low_value_portal` | prefetch skip | keep in candidate audit trail; do not promote as package-ready evidence |
| reader unusable | `reader_output_insufficient_substance` | reader gate | block package promotion; retain artifact ref and reason for audit |
| reader runtime outage | `reader_provider_error`, `reader_provider_unavailable` | reader fetch | fallback/retry policy with preserved decision reason; no silent downgrade to success |
| missing persisted substrate | `no_raw_scrapes`, `no_evidence_chunks` | chunk/index/analyze stages | block economic handoff; force storage proof before claiming package readiness |
| storage transient failure | `reader_artifact_write_failed`, `vector_write_failed` | write paths | retry class `transient_storage`; require idempotent replay evidence in bd-3wefe.10 |
| contract/path violation | `missing_snapshot`, `analysis_failed` | command sequencing | terminal failure; require operator intervention and explicit run audit |

## 6) Readiness verdict for bd-3wefe.4 handoff

Current evidence supports a constrained next step:

- Build the package builder using existing envelope fields and domain gate
  outcomes.
- Treat `private_searxng` as primary candidate lane, `tavily` as hot fallback
  candidate, `exa` as evaluation lane.
- Keep structured-first behavior where structured sources exist and are
  policy-relevant.
- Do not treat provider score alone as readiness; package-readiness depends on
  selected candidate quality and reader-substance gates.

What remains open (should be tracked in bd-3wefe.4/.10/.12 implementation):

- Persisted package contract proof across Postgres + MinIO + pgvector with
  read-back and replay.
- End-to-end Windmill execution proof for both scraped and structured lanes with
  backend command IDs and gate outputs preserved.
- Canonical economic handoff proof from package output into `AnalysisPipeline`.

## Artifact index

- `artifacts/package_readiness_source_quality_matrix.json`
