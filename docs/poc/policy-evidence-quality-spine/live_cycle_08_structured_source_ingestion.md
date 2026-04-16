# Live Cycle 08: Structured Source Ingestion + Catalog (bd-3wefe.14)

- cycle: `08`
- subtask: `bd-3wefe.14`
- feature_key: `bd-3wefe.14`
- scope: backend-owned structured-source catalog + structured evidence ingestion path into `PolicyEvidencePackage`
- mode: implementation and test proof (live Windmill run delegated to orchestrator lane)

## Goal

Improve data-moat structured lane from `not_proven` by:

1. adding a canonical San Jose structured source catalog artifact with required metadata fields;
2. wiring a backend-owned structured enrichment path into runtime package materialization;
3. proving package contract now supports combined scraped + structured lanes in one package payload.

## Inputs

- `docs/poc/policy-evidence-quality-spine/README.md`
- `docs/poc/policy-evidence-quality-spine/policy_evidence_quality_spine_cycle_learning_report.md`
- `docs/poc/policy-evidence-quality-spine/artifacts/quality_spine_eval_cycles_report.md`
- `docs/specs/2026-04-14-evidence-package-dependency-lockdown.md`
- `docs/architecture/2026-04-15-affordabot-pipeline-brownfield-map.md`
- `docs/architecture/2026-04-15-economic-literature-inventory.md`
- `backend/services/pipeline/domain/bridge.py`
- `backend/services/pipeline/policy_evidence_package_builder.py`
- `backend/schemas/policy_evidence_package.py`

## Code and Config Tweaks

1. Added canonical structured source catalog module for San Jose:
   - `backend/services/pipeline/structured_source_catalog.py`
   - includes required catalog fields: free/key/signup, access method, cadence, coverage, relevance, storage target, usefulness score, lane classification, runtime status.
2. Added backend-owned structured enrichment module:
   - `backend/services/pipeline/structured_source_enrichment.py`
   - probes two real structured source families:
     - `legistar_web_api` (`webapi.legistar.com`)
     - `san_jose_open_data_ckan` (`data.sanjoseca.gov` CKAN API)
   - returns typed result with candidate envelopes + catalog refs.
3. Integrated structured enrichment into runtime package materialization:
   - `backend/services/pipeline/domain/bridge.py`
   - replaced hardcoded `structured_enrichment_status=not_configured` behavior;
   - feeds `structured_candidates` into `PolicyEvidencePackageBuilder().build(...)`;
   - persists structured enrichment status/candidates/catalog under `run_context`.
4. Added noop enrichment behavior for non-Postgres/test runtimes to keep tests deterministic and avoid external-network dependency in unit tests.

## Artifacts Produced

- San Jose structured source catalog artifact:
  - `docs/poc/policy-evidence-quality-spine/artifacts/live_cycle_08_structured_source_catalog.json`

## Tests and Checks

Commands executed:

```bash
cd backend
poetry run pytest tests/services/pipeline/test_structured_source_enrichment.py \
  tests/services/pipeline/test_bridge_runtime.py::test_runtime_bridge_materializes_structured_sources_when_enrichment_available \
  tests/services/pipeline/test_bridge_runtime.py::test_runtime_bridge_persists_policy_evidence_package_refs -q
poetry run pytest tests/services/pipeline/test_policy_evidence_package_builder.py -q
poetry run ruff check services/pipeline/domain/bridge.py \
  services/pipeline/structured_source_catalog.py \
  services/pipeline/structured_source_enrichment.py \
  tests/services/pipeline/test_structured_source_enrichment.py \
  tests/services/pipeline/test_bridge_runtime.py
```

Results:

- `5 passed` (structured enrichment + bridge integration subset)
- `5 passed` (package builder suite)
- Ruff: `All checks passed`

## D-Gate Delta (Cycle 07 -> Cycle 08)

- `D1 source catalog`: **not_proven -> pass (code + artifact)**
  - backend-owned canonical catalog for San Jose structured families now exists and is versioned as an artifact.
- `D3 structured source quality`: **not_proven -> partial**
  - runtime path now produces structured candidate envelopes from real source families and can embed them into package materialization.
  - still requires orchestrator/manual live-cycle verification to claim full `pass`.
- `D4 unified package`: **not_proven -> partial**
  - runtime package now supports `source_lanes={"scraped","structured"}` in the same package with structured provenance attached.
  - still needs live Windmill cycle evidence + manual audit to mark full `pass`.

## Manual Verification Needed (Orchestrator Lane)

1. Run a live San Jose cycle in Railway/Windmill and confirm `run_context.structured_sources` is populated from actual API responses.
2. Confirm `PolicyEvidencePackage` row in Postgres and package artifact in MinIO include structured lane provenance for the same package id.
3. Manual audit whether structured facts are economically useful for the selected San Jose policy scenario (not just present).

## Blockers / Risks

- No hard blocker in code path.
- Live-source availability remains external dependency (Legistar/CKAN API uptime and rate behavior); runtime fails open to scraped-only with explicit structured alerts/status.
