# Policy Evidence Lockdown Review Results

Date: 2026-04-15
Beads: `bd-3wefe.8`
PR: https://github.com/stars-end/affordabot/pull/436
Reviewed head before repair: `1dab7b920d72502a1d9e0da70d26d839a4c0a841`

## Reviewer Quorum

`dx-review` could not produce quorum on this host. See:

- `docs/reviews/2026-04-15-dx-review-frictions-policy-evidence-lockdown.md`

Fallback used:

- Codex Reviewer A: data moat, storage, Windmill boundary, provenance, idempotency.
- Codex Reviewer B: sufficiency gates, mechanism cases, direct/indirect/secondary
  economic-analysis readiness, fail-closed behavior.

## Review Verdicts

Reviewer A:

- Verdict: `approve_with_changes`
- Score: `72/100`
- Lockdown recommendation: `do_not_lock`
- Main reason: deterministic proof was not enough for final boundary lock because
  live Windmill flow execution and live Postgres/MinIO/admin-read proof were still
  missing.

Reviewer B:

- Verdict: `approve_with_changes`
- Score: `76/100`
- Lockdown recommendation: `lock_with_conditions`
- Main reason: economic-analysis representation is plausible, but code-level
  gates needed stronger fail-closed and referential-integrity behavior.

## Findings Repaired In This Wave

1. Idempotency conflict now fails closed instead of silently reusing stale truth.
2. MinIO readback probes all declared MinIO refs using `uri`, or `reference_id`
   when it is URI-shaped.
3. Unsupported quantitative claims are compatible with `fail_closed` verdicts.
4. Quantitative model readiness now requires referential integrity:
   - model `input_parameter_ids` must resolve to resolved `ParameterCard`s;
   - model `assumption_ids` must resolve to `AssumptionCard`s;
   - model assumptions must have governed quantitative `assumption_usage`.
5. Mechanism-case `canonical_document_key` is now package-version independent.
6. Mechanism-case scraped provenance is case-specific instead of shared fixtures.
7. The live-reader economic probe now keeps qualitative economic text with no
   numeric parameter support blocked at `parameterization_sufficiency`, not
   `reader_substance`.
8. Windmill proof includes a non-stub `backend_endpoint` command-client lane,
   proven locally through an HTTP command surface.
9. Storage proof includes live/dev probe mode with real Postgres and MinIO adapter
   seams, while preserving deterministic offline mode.

## Current Evidence

Local validation after repair:

- Backend full test suite: `631 passed`.
- Backend ruff: passed.
- Focused policy evidence suite: `43 passed`.
- Storage verifier: `gates_passed=7/7`, `live_status=blocked`
  (`pgvector.railway.internal` is private-network-only from this runtime).
- Sufficiency verifier: `gates_passed=6/6`.
- Economic mechanism verifier: `gates_passed=6/6`.
- Windmill verifier: `local=passed`, `backend_endpoint_local=passed`,
  `live=passed_stub_flow_run`.
- `git diff --check`: passed.

## Remaining Architecture-Lock Conditions

This branch is strong enough to continue implementation on the chosen boundary:

- Windmill orchestrates.
- Affordabot backend owns evidence/economic product logic.
- Postgres stores canonical package rows.
- MinIO stores artifact bodies.
- pgvector remains derived retrieval state.
- Frontend/admin consumes read models.

It is not yet enough for final architecture lock because live runtime evidence is
still incomplete:

1. Run the deployed Windmill dev flow using the `backend_endpoint` command client
   against a deployed backend command endpoint.
2. Run storage verifier from a Railway/private-network-capable runtime with real
   `DATABASE_URL` and MinIO env available.
3. Verify admin/frontend read-model visibility for package status, evidence
   cards, storage refs, sufficiency state, and economic-analysis handoff state.
4. Run one live end-to-end package path:
   scraped + structured evidence -> persisted package -> sufficiency gate ->
   canonical analysis output -> admin/frontend display.

## Recommendation

Use `lock_with_conditions`.

The boundary is no longer speculative, and the code-level reviewer blockers were
repaired. The remaining blockers are runtime proof gaps, not evidence that the
architecture is wrong.
