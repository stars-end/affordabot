# Manual Audit: Cycle 32 Data Moat

Feature-Key: `bd-3wefe.13`

Artifacts:
- `artifacts/live_cycle_32_windmill_domain_run.json`
- `artifacts/live_cycle_32_admin_analysis_status.json`
- `artifacts/live_cycle_32_policy_package_payload.json`

Runtime identity:
- Package: `pkg-a79daaf0005fb4d0ecb25347`
- Backend run: `f111406c-b0bf-4508-8a86-5e5c63cc6198`
- Windmill run: `bd-3wefe.13-live-cycle-32-20260417031252`
- Windmill job: `019d996d-76cf-c910-b7a1-dca180a1f45a`

## Verdict

`FAIL_DATA_MOAT__ARTIFACT_FIRST_POLICY_IDENTITY_REGRESSION`

Cycle 32 proves that artifact-grade selection is not sufficient for an Affordabot data moat. The pipeline selected a concrete PDF artifact, but the artifact was an HCD Los Altos housing element draft, not the San Jose Commercial Linkage Fee policy family under audit.

This is a high-value failure because it exposes a false-positive gate: `source_quality_ready=true` and `scraped/search=pass` were awarded from artifact shape alone. Moat-grade evidence selection must prove jurisdiction and policy identity before artifact preference can pass.

## What Passed

- Windmill executed the expected six-step sequence: `search_materialize`, `freshness_gate`, `read_fetch`, `index`, `analyze`, `summarize_run`.
- Storage/read-back passed through the admin read model and live storage refs.
- Private SearXNG runtime was proven in product-path provenance: client `OssSearxngWebSearchClient`, endpoint host `searxng-private.railway.internal:8080`.
- The reader persisted substantive content for the selected artifact.
- The package was durable and admin-readable.

## What Failed

- Selected URL: `https://www.hcd.ca.gov/housing-elements/docs/los altos_5th_draft011415.pdf`.
- Requested policy context: San Jose Commercial Linkage Fee / Matter 7526 / 2020 non-residential fee schedule.
- Selected artifact context: Los Altos housing element draft.
- Source quality status in admin read model: `pass`.
- Source quality reason: `selected_candidate_is_artifact_grade`.
- Manual source quality verdict: fail.
- Data moat status: fail.
- True structured economic rows: 0.
- Missing true structured corroboration count: 1.
- LLM narrative: not_proven.

## Manual Data Assessment

The data is not credible input for the San Jose CLF product claim. It contains an artifact and some numeric fee-looking values, but the artifact is from the wrong jurisdiction and policy family. The extracted `$7.00 per square foot` office fee comes from the Los Altos document and would be actively misleading if handed to the economic analysis layer as San Jose evidence.

The secondary San Jose CLF row from the official San Jose page remains relevant, but it cannot rescue the package. A moat-grade package cannot combine one correct secondary/official-page row with one wrong-jurisdiction primary artifact and still pass source quality. The package must reject or quarantine the wrong artifact before parameter cards and economic handoff are generated.

## Gate Implication

Add a policy identity gate before source quality can pass:

- Jurisdiction identity must match the requested jurisdiction or a strongly linked official source.
- Policy identity must match the target policy family, matter id, ordinance/resolution id, fee name, or related attachment lineage.
- Artifact-grade shape must be subordinate to jurisdiction and policy identity.
- Wrong-jurisdiction official artifacts must fail hard even if reader substance and artifact shape are strong.

Cycle 32 should be used as a regression fixture: an artifact-first run that selects `los altos_5th_draft011415.pdf` for San Jose CLF must fail `source_quality_ready`, `scraped/search`, and `data_moat_status`.

## Required Next Wave

1. Add jurisdiction and policy identity scoring to candidate ranking and source-quality gates.
2. Penalize artifacts whose URL/title/content signals another jurisdiction unless they are explicitly linked from the San Jose policy lineage.
3. Require San Jose CLF identity evidence before selecting HCD, third-party, or unrelated official artifacts.
4. Surface `policy_identity_ready=false` and a named blocker in `data_moat_status`.
5. Add regression coverage for Cycle 32 so artifact-grade wrong-policy documents cannot pass again.
