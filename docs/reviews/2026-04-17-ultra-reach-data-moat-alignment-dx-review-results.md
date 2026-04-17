# 2026-04-17 Ultra-Reach Data Moat Alignment dx-review Results

Feature-Key: `bd-3wefe.13`

PR: <https://github.com/stars-end/affordabot/pull/439>

PR head reviewed: `b333fd4cf0f7ec7cced2053f87cfc88d1d20aa20`

Prompt:
`docs/reviews/2026-04-17-ultra-reach-data-moat-alignment-dx-review-prompt.md`

Plan under review:

- `docs/specs/2026-04-17-local-government-data-moat-benchmark-v0.md`
- `docs/specs/2026-04-16-data-moat-quality-gates.md`
- `docs/specs/2026-04-14-evidence-package-dependency-lockdown.md`
- `docs/architecture/README.md`
- `docs/poc/policy-evidence-quality-spine/README.md`

## Review Focus

The second review was deliberately narrower than the prior architecture review.
It asked reviewers to judge whether the plan is an **ULTRA reach goal** aligned
with Affordabot's two products:

1. Product A, 90 percent weight: robust city/county/local/state data moat that
   combines scraped official artifacts and true structured API/raw data into
   durable, auditable, reusable evidence packages.
2. Product B, 10 percent weight: economic analysis grounded by the proprietary
   data moat, with explicit handoff classification and no hidden LLM
   assumptions.

## dx-review Outcome

Command:

```bash
BEADS_DIR=~/.beads-runtime/.beads dx-review run \
  --beads bd-3wefe.13 \
  --worktree /tmp/agents/bd-3wefe.13/affordabot \
  --prompt-file /tmp/agents/bd-3wefe.13/affordabot/docs/reviews/2026-04-17-ultra-reach-data-moat-alignment-dx-review-prompt.md \
  --template architecture-review \
  --pr https://github.com/stars-end/affordabot/pull/439 \
  --read-only-shell \
  --gemini \
  --wait \
  --timeout-sec 900 \
  --poll-sec 10
```

Result: partial quorum.

- Gemini: usable review, `pass_with_findings`, 3 findings.
- GLM: failed after launch with Z.ai API `429` rate limit.

Raw artifacts:

- `/tmp/dx-review/bd-3wefe.13/summary.md`
- `/tmp/dx-review/bd-3wefe.13/summary.json`
- `/tmp/dx-runner/gemini/bd-3wefe.13.gemini.log`
- `/tmp/dx-runner/cc-glm/bd-3wefe.13.glm.log`

GLM failure class:

```text
API Error: Request rejected (429) - Rate limit reached for requests
```

This is the second GLM rate-limit failure for the corpus-plan review and should
be treated as a provider availability issue, not a plan finding.

## Gemini Verdict

Verdict: `pass_with_findings`

Reviewer summary:

> The plan is highly ambitious and correctly prioritizes a robust local data
> moat (Product A) over mere mechanics. The architecture is sound, but the
> "Ultra Reach" benchmark is at risk due to current source-selection weaknesses
> and missing longitudinal metrics (freshness/drift).

The reviewer did not return the requested separate 0-100 scores for Product A
and Product B. Treat that as a review-contract miss; do not infer numeric
scores from the prose.

## Findings

### [P1] Official-Source Selection Lag

References:

- `backend/services/pipeline/policy_evidence_package_builder.py`
- `docs/poc/policy-evidence-quality-spine/manual_audit_cycle_43_data_moat.md`

Cycle 43 demonstrates that the ranker can still select external advocacy PDFs
over official documents. The gate now fails this correctly, but the behavior
blocks the C1 official-source dominance target.

Why it matters:

- Product A: official-source dominance is central to a defensible local data
  moat.
- Product B: economic analysis should not be grounded primarily in advocacy or
  news sources when authoritative government records exist.

Recommended patch:

- Implement a deterministic official-source ranking/classification layer before
  running the corpus benchmark.
- Centralize official-domain/source-of-truth rules so external sources can be
  retained as context without satisfying primary evidence.

### [P2] Missing Freshness And Drift Dimensions

Reference:

- `backend/schemas/policy_evidence_package.py`

The plan and schema include freshness concepts, but the ultra-reach benchmark
does not yet require explicit source-drift or update-cadence drift metrics.

Why it matters:

- Product A: a data moat must stay current and detect source-shape changes.
- Product B: stale policy records or changed source schemas can silently corrupt
  economic assumptions and handoff classifications.

Recommended patch:

- Add explicit source freshness, source-shape drift, update-cadence drift, and
  last-successful-refresh metrics to the corpus/package gates.
- Fold these into D8 robustness or add a new durability subgate.

### [P2] Corpus Matrix Readiness

Reference:

- `docs/specs/2026-04-17-local-government-data-moat-benchmark-v0.md`

The 30-50 package, 3+ jurisdiction benchmark is well-defined, but the
implementation is still behind the spec. Current artifacts remain dominated by
vertical San Jose cycles.

Why it matters:

- Product A: corpus breadth is the actual product test.
- Product B: economic handoff quality cannot be evaluated realistically if the
  corpus does not cover diverse policy families and jurisdictions.

Recommended patch:

- Prioritize the Phase 1 corpus matrix contract before another live eval cycle.
- Make the first executable task produce the machine-readable corpus matrix,
  seed rows, source-family expectations, official-source expectations, and
  scorecard schema.

## Plan Impact

The second review supports the strategic shift and says the plan is a genuine
ultra-reach goal, but it identifies three required hardening steps before
implementation:

1. official-source dominance must be implemented before corpus-scale proof;
2. freshness/source-drift durability must become part of the moat gates;
3. corpus matrix and scorecard artifacts must exist before another live cycle.

The next implementation wave should start with the corpus matrix contract and
central source/identity classification layer, not another San Jose live run.
