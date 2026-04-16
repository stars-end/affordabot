# Policy Evidence Quality Spine (`bd-3wefe.13`)

This lane evaluates whether a vertical package is ready to feed canonical
economic analysis and admin/frontend read models.

## Artifacts

- `artifacts/horizontal_matrix.json`
- `artifacts/data_runtime_evidence.json`
- `artifacts/quality_spine_scorecard.json`
- `artifacts/quality_spine_report.md`
- `artifacts/retry_ledger.json`
- `artifacts/quality_spine_eval_cycles_report.json`
- `artifacts/quality_spine_eval_cycles_report.md`
- `artifacts/quality_spine_gap_audit.md`
- `artifacts/quality_spine_live_storage_probe.json`
- `artifacts/live_cycle_01_windmill_domain_run.json`
- `artifacts/live_cycle_01_windmill_domain_run.md`
- `artifacts/live_cycle_08_economic_bridge.md`
- `artifacts/live_cycle_25_windmill_domain_run.json`
- `artifacts/live_cycle_25_windmill_domain_run.md`
- `artifacts/live_cycle_25_admin_analysis_status.json`
- `cycle_08_gate_controller_upgrade.md`
- `cycle_09_metadata_and_manual_audit_hooks.md`

## Future Agent Start Here

**STOP:** Do not launch another POC cycle before reading the [2026-04-16 data moat quality gates](../../specs/2026-04-16-data-moat-quality-gates.md). The original product gates (v2, described below) were passed mechanically but failed the economic-depth substance bar (see `Current verdict` below for details). All future cycles must adhere to the hardened D0-D7 and E1-E5 gates in the new contract.

### Cycle 25 Honest Verdict

Cycle 25 did not pass the original product gates.

Verdict: `PASS_SCRAPED_ARTIFACT_AND_PACKAGE_MECHANICS_ONLY__STRUCTURED_MOAT_NOT_PROVEN__ECONOMIC_DECISION_GRADE_NOT_PROVEN`

What passed:
- SearXNG/scraped path found and read a useful official Legistar artifact.
- Package mechanics, persistence, and admin read model were useful.
- Economic analysis correctly failed closed on household cost-of-living claims.

What did not pass:
- Legistar Web API was mechanically live but economically shallow (no attachments).
- CKAN/San Jose Open Data was not live-proven.
- Tavily rescued fee parameters, but Tavily is secondary search-derived evidence, not true structured-source proof.
- The structured data moat was not proven.
- Economic analysis failing closed does not prove the upstream data moat is real.

Next POC must prove structured-source economic depth or honestly classify it as `not_proven`.

## Gate Contract v2 (Superseded by 2026-04-16 Gates)

The evaluator now uses explicit gate domains:

- Data moat: `D1..D6`
- Economic analysis: `E1..E6`
- Manual audit: `M1..M3`

Status enum: `pass|partial|not_proven|fail`.

Cycle policy:

- adaptive cycle budget up to `25`
- completion guard blocks diagnosis-only cycles unless there is:
  - implementation/fix attempt evidence, or
  - concrete external blocker proof, or
  - all blocking gates passed.

Key CLI helpers:

- `--cycle-metadata`
- `--manual-data-audit-md`
- `--manual-economic-audit-md`
- `--manual-gate-decision-md`
- `--current-package-status`

## Current verdict

- overall_verdict: `partial`
- decision_grade_verdict: `not_decision_grade`
- failed_categories: `0`
- not_proven_categories: `storage/read-back, Windmill/orchestration, LLM narrative`
- storage_readback_status: `not_proven`
- storage_readback_note: `Automated deterministic scorecard remains not_proven; manual Railway SSH evidence now proves MinIO artifact readback and pgvector chunks, but exact PolicyEvidencePackage row/current-package linkage is still missing.`
- windmill_orchestration_status: `not_proven`
- windmill_orchestration_note: `Historical Windmill stub proof exists but is not valid for current vertical package.`
- llm_narrative_status: `not_proven`
- llm_narrative_note: `LLM narrative not proven (canonical_llm_run_id_missing; source=quality_spine_deterministic_lane).`
- economic_quality_failing_dimensions: `none`

The current deterministic quality-spine pass has no failed data/economic
quality categories. Retry-3 adds strict category semantics: selected-artifact
search quality can pass only with explicit artifact metrics, while storage
remains `not_proven` until real Postgres/MinIO proof is available for the
current vertical package. Windmill/LLM also remain `not_proven` when evidence
is historical or lacks canonical run ids.

Retry-4 initially found a live MinIO `AccessDenied` blocker. After Railway
Bucket/Console/backend restarts, a manual Railway SSH probe proved the current
fallback artifact can be read from MinIO (`124319` bytes), the raw scrape row
exists, and `3382` pgvector chunks have embeddings for the document id referenced
by the live run. Storage remains `not_proven` because the exact
`PolicyEvidencePackage` row/current-package linkage is still missing, the
`documents` row for that document id was not present, and the live analysis id is
not persisted in `analysis_history`.

The eval-cycle harness now records per-cycle ledger rows with:
- cycle number
- targeted tweak
- deploy sha
- windmill job id
- backend run id
- package id
- selected url
- reader artifact uri
- MinIO readback status
- pgvector chunk stats
- package row linkage
- economic status endpoint (if captured)
- verdict and next tweak

Gate taxonomy is now explicit and severity-aware:
- `D1..D6` data moat
- `E1..E6` economic analysis
- `M1..M3` manual audits
- status: `pass|partial|not_proven|fail`
- severity: `blocking|nonblocking`

Cycle 1 (`live_cycle_01_windmill_domain_run.json`) is explicitly marked
`partial`, not product-proof.

## Matrix source

- mode: `agent_a_horizontal_matrix`
- path: `docs/poc/policy-evidence-quality-spine/artifacts/horizontal_matrix.json`
- used_package_id: `pkg-sj-parking-minimum-amendment`

## Validation

```bash
cd backend
poetry run pytest tests/services/pipeline/test_policy_evidence_quality_spine_economics.py tests/services/pipeline/test_policy_evidence_quality_spine_eval_cycles.py
poetry run pytest tests/verification/test_policy_evidence_quality_spine_live_storage.py
poetry run python scripts/verification/verify_policy_evidence_quality_spine_economics.py --max-cycles 25
poetry run python scripts/verification/verify_policy_evidence_quality_spine_live_storage.py --windmill ../docs/poc/policy-evidence-quality-spine/artifacts/live_cycle_01_windmill_domain_run.json --runtime ../docs/poc/policy-evidence-quality-spine/artifacts/data_runtime_evidence.json --live-mode off
poetry run python scripts/verification/verify_policy_evidence_quality_spine_eval_cycles.py --max-cycles 25 --live-cycle-artifact '../docs/poc/policy-evidence-quality-spine/artifacts/live_cycle_*_windmill_domain_run.json' --economic-status ../docs/poc/policy-evidence-quality-spine/artifacts/live_cycle_07_admin_analysis_status.json
```
