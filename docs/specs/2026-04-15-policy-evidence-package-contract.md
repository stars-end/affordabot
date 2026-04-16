# 2026-04-15 PolicyEvidencePackage Contract (`bd-3wefe.1`)

Status: draft implementation contract

PR: <https://github.com/stars-end/affordabot/pull/436>

## 1. Purpose

`PolicyEvidencePackage` is the backend-owned, auditable handoff contract between:

1. scraped/structured source collection and artifact reading,
2. evidence and parameter extraction, and
3. canonical economic runtime (`AnalysisPipeline` + `LegislationResearchService` + deterministic sufficiency gates).

This contract does not replace economic runtime authority. It packages and
projects existing runtime signals so storage, Windmill runs, admin APIs, and
frontend views can inspect the same truth.

## 2. Canonical schema location

- [policy_evidence_package.py](/tmp/agents/bd-2agbe.1/affordabot/backend/schemas/policy_evidence_package.py)
- [test_policy_evidence_package.py](/tmp/agents/bd-2agbe.1/affordabot/backend/tests/schemas/test_policy_evidence_package.py)

## 3. Core fields

`PolicyEvidencePackage` includes:

1. Envelope and identity:
   - `schema_version`, `package_id`, `jurisdiction`,
     `canonical_document_key`, `policy_identifier`, `created_at`,
     `source_lanes`.
2. Source provenance:
   - `scraped_sources[]` with explicit provider identity, query family, query
     text, snapshot id, candidate rank, selected URL, and reader outcome.
   - `structured_sources[]` with source family, access method, endpoint/file,
     and extracted field count.
3. Package cards:
   - `evidence_cards[]`, `parameter_cards[]`, `assumption_cards[]`,
     `model_cards[]`.
4. Gate state:
   - `gate_report` (card-level gate payload vocabulary).
   - `gate_projection` (canonical runtime gate projection).
5. Assumption usage status:
   - `assumption_usage[]` marks whether assumptions were used for quantitative
     claims, and whether they are applicable/stale.
6. Storage references:
   - `storage_refs[]` with storage system and truth role.
7. Readiness:
   - `freshness_status`, `economic_handoff_ready`, `insufficiency_reasons[]`.

## 4. Authority and mapping rules

### 4.1 `GateReport` and canonical sufficiency

`GateReport` is not a second authority. Runtime gate authority remains:

- `schemas.analysis.SufficiencyState`
- `schemas.analysis.SufficiencyBreakdown`
- `schemas.analysis.ImpactGateSummary`
- `services.llm.evidence_gates.assess_sufficiency(...)`

`gate_projection` exists to pin package-level gate state directly to canonical
runtime semantics:

- `runtime_sufficiency_state`
- `runtime_insufficiency_reason`
- `runtime_failure_codes`
- optional canonical run/step/breakdown references

If these ever diverge, runtime sufficiency is authoritative and package state
must be treated as stale/invalid.

### 4.2 `AssumptionCard` and `WAVE2_*` / `AssumptionRegistry`

Current runtime assumptions are still produced from:

- `WAVE2_PASS_THROUGH_LITERATURE`
- `WAVE2_ADOPTION_ANALOGS`

`AssumptionRegistry` is a candidate registry, not current runtime authority.

`PolicyEvidencePackage` is designed to hold both:

1. runtime-derived `WAVE2_*` assumptions as auditable `AssumptionCard` records,
2. future registry-backed assumptions, after explicit migration.

Quantitative claim usage requires explicit staleness and applicability metadata
at package validation time.

## 5. Invariants implemented in schema validators

Implemented fail-closed invariants:

1. Package requires at least one `source_lane` and one `evidence_card`.
2. Scraped lane requires scraped provenance with provider identity.
3. Structured lane requires structured provenance rows.
4. `economic_handoff_ready=true` requires:
   - no blocking gate,
   - `runtime_sufficiency_state=quantified`,
   - and a quantitative support path
     (`resolved_parameter` or quant-eligible model support).
5. `pgvector` references cannot be `source_of_truth`.
6. Assumptions used for quantitative claims require:
   - an existing assumption card,
   - staleness metadata (`stale_after_days`),
   - applicability tags,
   - `applicable=true`,
   - and `stale=false`.

## 6. Test coverage in this wave

Focused tests added for:

1. Valid scraped + structured package, handoff-ready.
2. Fail-closed package (`economic_handoff_ready=false`) with blocking gate.
3. Invalid pgvector source-of-truth rejection.
4. Missing scraped provider identity rejection.
5. Stale/inapplicable quantitative assumption rejection.

## 7. Required downstream consumption/proof

This contract is intentionally scoped as schema + validators only. Next tasks
must consume/prove it as follows:

1. `bd-3wefe.4` package builder:
   - emit this schema from backend-owned domain command outputs.
2. `bd-3wefe.10` storage proof:
   - prove durable Postgres + MinIO + pgvector refs and read-back.
3. `bd-3wefe.12` Windmill proof:
   - prove orchestration over scraped + structured lanes with command/run ids
     and persisted package refs.
4. `bd-3wefe.5` sufficiency gate:
   - enforce staleness/applicability fail-closed semantics over persisted
     packages.
5. `bd-3wefe.6` economic cases:
   - prove direct, indirect, and secondary research cases map to canonical
     runtime outputs without introducing a second analysis engine.
