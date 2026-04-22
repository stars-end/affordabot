# Manual Audit: Cycle 41 Broad Local-Policy Moat

Feature key: `bd-3wefe.13`  
Commit under test: `e0a82bf`  
Run key: `bd-3wefe.13-live-cycle-41-20260417060514`  
Windmill job: `019d9a0b-5180-9853-4f50-4f2391710fc3`  
Backend run: `43f4dca9-e202-43c4-9e27-599c737f775e`  
Package: `pkg-c48016e9161bbb4a8fef90c7`  
Scenario: `parking_policy`

## Cycle Goal

Cycle 41 intentionally moved beyond the San Jose Commercial Linkage Fee
calibration slice. The target was a broader city/local-government data-moat
case: capture, store, classify, and expose useful San Jose policy evidence even
when it is not yet an economic-analysis-ready package.

This follows the product rule: Affordabot may eventually sell the data directly,
so high-quality local government evidence has standalone value. Economic
analysis remains a required separate gate, but not every stored policy artifact
must immediately produce a quantified cost-of-living conclusion.

## Inputs

- Query: `San Jose parking minimums ordinance policy action city council`
- Source family: `parking_policy`
- Expected evidence use: `useful_local_policy_evidence`
- Expected economic readiness: `not_required`

## Manual Evidence Inspected

- Windmill run artifact:
  `docs/poc/policy-evidence-quality-spine/artifacts/live_cycle_41_windmill_domain_run.json`
- Admin read model:
  `docs/poc/policy-evidence-quality-spine/artifacts/live_cycle_41_admin_analysis_status.json`
- Stored package payload:
  `docs/poc/policy-evidence-quality-spine/artifacts/live_cycle_41_policy_package_payload.json`

## What Improved

1. The live harness accepted a non-CLF policy scenario and recorded
   `policy_evidence_capture`.
2. Private SearXNG was actually exercised:
   `OssSearxngWebSearchClient`, configured provider `searxng`, endpoint host
   `searxng-private.railway.internal:8080`.
3. The selected official source was relevant to the requested policy family:
   San Jose Legistar Matter `11803`, `PP22-015`, Parking and Transportation
   Demand Management Policy Ordinance.
4. The package unified scraped and structured lanes:
   - scraped source: private SearXNG selected Legistar gateway URL
   - structured source: Legistar Web API Matter `11803`
5. The package now carries explicit moat metadata:
   - `policy_families`: `meeting_action`, `parking_policy`, `zoning_land_use`
   - `evidence_use`: `meeting_record`
   - `economic_relevance`: `contextual`
6. The admin read model exposes `data_moat_value.status=stored_not_economic`.
   This is the correct product distinction for useful stored policy evidence
   that has no current economic parameter/model signal.

## Manual Quality Assessment

The selected evidence is credible and relevant for broad local-government data:

- It is official San Jose Legistar content.
- It identifies the policy action: amendment to Title 20 for Parking/TDM.
- It records policy lineage: Matter `11803`, File `22-1876`, council agenda
  date `2022-12-06`.
- It includes source-grounded policy details: removing mandatory minimum
  off-street parking requirements, TDM additions, zoning-code chapters, and
  enforcement timing for outdoor business operations.

The package is not decision-grade economic evidence:

- `parameter_cards=[]`
- `true_structured_row_count=0`
- `official_attachment_row_count=0`
- `economic_handoff_quality.status=not_analysis_ready`
- `economic_output.status=not_proven`

That economic failure is acceptable for the broad-data lane, but only if the
package is clearly classified as stored policy evidence rather than falsely
reported as economic handoff-ready. Cycle 41 now does that through
`data_moat_value`.

## Gate Check

- D1 source catalog/metadata: partial pass. The run records `parking_policy`,
  Legistar API access, and source family metadata, but not a full source catalog
  row update.
- D2 scraped evidence quality: partial/fail. Private SearXNG selected relevant
  official content, but `scraped/search` still fails because selected artifact
  family is `official_page`, not a high-confidence artifact.
- D3 structured evidence quality: partial. Legistar Web API was live and linked
  to Matter `11803`, but contributed metadata/lineage only, not economic rows.
- D4 unified package identity: pass for broad data. Scraped and structured lanes
  unify under one package and canonical document key.
- D5 storage/readback: pass via admin read model. Direct harness DB probe is not
  available from local DNS, but backend storage proof reports Postgres, MinIO,
  and pgvector refs.
- D6 Windmill integration: pass. Current Windmill run/job ids are bound to the
  package.
- Economic gates E1-E6: not proven. Correctly fail closed for this package.
- M1 manual data audit: complete in this document.
- M2 manual economic audit: not applicable as a pass; economic output is
  explicitly not decision-grade.

## Verdict

`EVIDENCE_READY_WITH_GAPS__BROAD_LOCAL_POLICY_CAPTURE_PROVEN__TOP_LEVEL_GATE_OVERFITTED_TO_ECONOMIC_ROWS`

Cycle 41 proves a new and useful data-moat capability: broad local policy
evidence can be found, stored, unified with structured metadata, and classified
as valuable even when not economic-analysis-ready.

The next substantive improvement should adjust the top-level data-moat gate so
it does not fail all broad local-government evidence merely because it lacks
economic parameter rows. The gate should distinguish:

- `stored_policy_evidence`: valuable, source-grounded local-government data;
- `economic_handoff_candidate`: evidence with policy/economic parameter signals;
- `economic_analysis_ready`: decision-grade economic package candidate.

Economic analysis remains required for packages claiming economic readiness.
