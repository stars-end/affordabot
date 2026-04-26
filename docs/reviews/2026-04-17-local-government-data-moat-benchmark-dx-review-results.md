# 2026-04-17 Local Government Data Moat Benchmark dx-review Results

Feature-Key: `bd-3wefe.13`

PR: <https://github.com/stars-end/affordabot/pull/439>

PR head reviewed: `3fc560e3db3d34f410fa6039b6c4f6cce2e11519`

Prompt:
`docs/reviews/2026-04-17-local-government-data-moat-benchmark-dx-review-prompt.md`

Plan under review:

- `docs/specs/2026-04-17-local-government-data-moat-benchmark-v0.md`
- `docs/specs/2026-04-16-data-moat-quality-gates.md`
- `docs/specs/2026-04-14-evidence-package-dependency-lockdown.md`
- `docs/architecture/README.md`
- `docs/poc/policy-evidence-quality-spine/README.md`

## dx-review Outcome

Command:

```bash
BEADS_DIR=~/.beads-runtime/.beads dx-review run \
  --beads bd-3wefe.13 \
  --worktree /tmp/agents/bd-3wefe.13/affordabot \
  --prompt-file /tmp/agents/bd-3wefe.13/affordabot/docs/reviews/2026-04-17-local-government-data-moat-benchmark-dx-review-prompt.md \
  --template architecture-review \
  --pr https://github.com/stars-end/affordabot/pull/439 \
  --read-only-shell \
  --gemini \
  --wait \
  --timeout-sec 900 \
  --poll-sec 10
```

Result: partial quorum.

- Gemini: usable review, `pass_with_findings`, 4 findings.
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

This is a provider rate-limit failure, not a plan-review finding.

## Gemini Verdict

Verdict: `pass_with_findings`

Reviewer summary:

> The shift to a corpus-level data moat is well-executed. The implementation
> provides robust fail-closed gates and a clear iteration path via the
> 30-cycle eval engine. Strategic separation of data value from economic
> readiness is a significant architectural improvement.

## Findings

### [P2] Identity Logic Duplication

Classification of official sources is duplicated in
`PolicyEvidencePackageBuilder` and `RailwayRuntimeBridge`.

Recommended follow-up: centralize official-source and policy-identity
classification in a dedicated backend identity/source-quality service before
the corpus benchmark scales across jurisdictions.

### [P2] Manual Audit Gap

Manual gates are not yet proven for the new corpus benchmark. C5 requires
manual audit sampling, but the first implementation wave must make this a real
artifact, not an implied scorecard field.

Recommended follow-up: make the corpus matrix runner produce
`manual_audit_local_government_corpus.md` from sampled packages and require the
orchestrator to fill the human-verification verdicts before claiming
`corpus_ready_with_gaps` or better.

### [P3] Hardcoded Heuristics

Jurisdiction and policy identification signals are currently hardcoded in
service logic.

Recommended follow-up: move jurisdiction/source/policy-family signals into a
configuration surface or source-catalog-backed ruleset so adding jurisdictions
does not require code deployments.

### [P3] Validator Bloat

The policy evidence package schema contains significant cross-field validation
logic.

Recommended follow-up: keep Pydantic schemas focused on structure and move
cross-field product-quality checks into domain services or gate evaluators as
the corpus grows.

## Plan Impact

The review supports the strategic shift from San Jose vertical proof to
`local_government_data_moat_benchmark_v0`.

The next implementation wave should not start with another live corpus run
until the first executable task defines:

1. the corpus matrix schema;
2. the central source/identity classification surface;
3. the manual audit sampling artifact;
4. the golden regression output format.

The GLM lane should be retried later if architecture lock depends on a
two-provider quorum. For this planning checkpoint, Gemini's review is usable
but not a full quorum.
