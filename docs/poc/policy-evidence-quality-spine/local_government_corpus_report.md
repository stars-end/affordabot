# Local Government Corpus Report

- benchmark_id: `local_government_data_moat_benchmark_v0`
- feature_key: `bd-3wefe.13.1`
- corpus_state: `corpus_ready_with_gaps`
- package_rows: `18`
- seed_mode: `seed_with_expansion_backlog`

## Gate Status

- C0: `not_proven` - Seed matrix is intentionally below 75 rows with explicit expansion backlog.
- C1: `pass` - Official-source dominance and Tavily/Exa primary caps satisfy C1.
- C2: `pass` - Structured-source diversity/depth satisfies C2.
- C3: `pass` - C3 package classifications reconcile cleanly with D11 handoff quality.
- C4: `pass` - C4 economic handoff distribution thresholds are satisfied.
- C5: `not_proven` - C5 manual audit exists but is not yet stratified to pass thresholds.
- C6: `pass` - C6 golden regression fields are complete and taxonomy-versioned.
- C7: `pass` - C7 freshness/drift metadata is complete and visible.
- C8: `pass` - C8 identity/dedupe canonical fields are present.
- C9: `pass` - C9 normalized/exportable fields are present across corpus rows.
- C9a: `pass` - C9a product surface contract and query examples are present.
- C10: `pass` - C10 licensing/robots/ToS posture is documented for all rows.
- C11: `pass` - C11 schema/taxonomy/gate version contract is explicit and aligned.
- C12: `pass` - C12 known-policy coverage includes blind holdout and adequate coverage.
- C13: `not_proven` - C13 live orchestration exists but cli_only share is above decision-grade cap.
- C14: `pass` - C14 non-fee extraction templates and live exercised families satisfy depth contract.

## Current Gaps

- non-pass gate count: `3`
- next blocker gate: `C0`
- next blocker reason: Seed matrix is intentionally below 75 rows with explicit expansion backlog.

## Next Eval Blocker

- Increase corpus package rows toward 75-120 and expand stratified manual audit coverage before attempting a decision-grade pass claim.

