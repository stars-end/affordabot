# Local Government Corpus Report

- benchmark_id: `local_government_data_moat_benchmark_v0`
- feature_key: `bd-3wefe.13.4.1`
- corpus_state: `corpus_ready_with_gaps`
- package_rows: `90`
- seed_mode: `expanded_generator_cycle_45`

## Gate Status

- C0: `pass` - Corpus scope and composition satisfy C0.
- C1: `pass` - Official-source dominance and Tavily/Exa primary caps satisfy C1.
- C2: `not_proven` - C2 structured-source diversity/depth requirements not met.
- C3: `pass` - C3 package classifications reconcile cleanly with D11 handoff quality.
- C4: `pass` - C4 economic handoff distribution thresholds are satisfied.
- C5: `pass` - C5 manual audit sampling is stratified and complete.
- C6: `pass` - C6 golden regression fields are complete and taxonomy-versioned.
- C7: `pass` - C7 freshness/drift metadata is complete and visible.
- C8: `pass` - C8 identity/dedupe canonical fields are present.
- C9: `pass` - C9 normalized/exportable fields are present across corpus rows.
- C9a: `pass` - C9a product surface contract and query examples are present.
- C10: `pass` - C10 licensing/robots/ToS posture is documented for all rows.
- C11: `pass` - C11 schema/taxonomy/gate version contract is explicit and aligned.
- C12: `pass` - C12 known-policy coverage includes blind holdout and adequate coverage.
- C13: `not_proven` - C13 has orchestration intent metadata, but live Windmill run/job refs are not proven.
- C14: `not_proven` - C14 non-fee extraction depth is incomplete.

## Structured Proof Boundary

- C2 live structured coverage ratio: `0.1889`
- C2 live true structured families: `5`
- C2 cataloged true structured families: `5`
- C14 live non-fee families: `11`
- C14 cataloged non-fee families: `6`

## C13 Burn-down

- mode counts: `{"cli_only": 0, "mixed": 0, "orchestration_intent": 82, "windmill_live": 8}`
- live proof coverage ratio: `0.0889`
- live proof progress: `8/90`
- orchestration-intent rows awaiting live proof: `82`
- remaining seeded ref rows: `82`
- next seeded ref target rows: `lgm-005, lgm-006, lgm-008, lgm-009, lgm-010, lgm-011, lgm-012, lgm-014, lgm-016, lgm-017`

## Current Gaps

- non-pass gate count: `3`
- next blocker gate: `C2`
- next blocker reason: C2 structured-source diversity/depth requirements not met.

## Next Eval Blocker

- Address C2 before next decision-grade assertion.
