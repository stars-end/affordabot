# dx-review Friction: Policy Evidence Lockdown Review

Date: 2026-04-15
Beads: `bd-3wefe.8`
PR: https://github.com/stars-end/affordabot/pull/436
Reviewed head intended: `1dab7b920d72502a1d9e0da70d26d839a4c0a841`

## Goal

Run an architecture/code-review quorum over the policy evidence package POC before
making a framework-lock recommendation.

## Intended Review Prompt

Prompt file used locally:

- `/tmp/affordabot_policy_evidence_architecture_review.prompt.md`

The prompt asked reviewers to evaluate:

- Windmill orchestration-only boundary.
- Affordabot backend ownership of evidence packaging, sufficiency gates, economic
  mechanism representation, and storage semantics.
- Postgres as canonical row store, MinIO as artifact body store, and pgvector as
  derived retrieval index.
- Whether combined scraped/structured packages are plausible inputs for
  decision-grade quantitative cost-of-living analysis.

## Observed Tooling Failures

### 1. `dx-review doctor` failed Claude review preflight

Command:

```bash
dx-review doctor --worktree /tmp/agents/bd-2agbe.1/affordabot
```

Observed result:

- `claude-code-review`: failed.
- Failure class: `claude_code_headless_flags_missing`.
- Message: installed `claude` binary does not expose required headless flags.
- `cc-glm-review`: passed.

Impact:

- The default dx-review quorum could not run because the Claude reviewer lane is
  structurally unavailable on this host.

### 2. OpenCode reviewer preflight failed pinned-model availability

Command:

```bash
dx-runner preflight --provider opencode --beads bd-3wefe.8 --worktree /tmp/agents/bd-2agbe.1/affordabot
```

Observed result:

- `opencode` binary present.
- Headless run capability present.
- Canonical pinned model `zhipuai/glm-5.1` missing.
- Suggested fallback in output: use `cc-glm` or `gemini`.

Impact:

- The normal OpenCode/GLM review lane was unavailable through the OpenCode
  provider, even though `cc-glm` itself could preflight successfully.

### 3. `dx-review --help` hung

Command:

```bash
dx-review --help
```

Observed result:

- Command produced no help output for more than 10 seconds.
- Process had to be killed manually.

Impact:

- Product agents cannot reliably discover supported dx-review options at the
  point of use. This is a P2 usability issue, but it becomes P1 when the wrapper
  is required for architecture-lock quorum.

### 4. Direct `dx-runner start` hung before job registration

Commands attempted:

```bash
dx-runner start --provider gemini --beads bd-3wefe.8-gemini \
  --worktree /tmp/agents/bd-2agbe.1/affordabot \
  --prompt-file /tmp/affordabot_policy_evidence_architecture_review.prompt.md \
  --json

dx-runner start --provider cc-glm --beads bd-3wefe.8-ccglm \
  --worktree /tmp/agents/bd-2agbe.1/affordabot \
  --prompt-file /tmp/affordabot_policy_evidence_architecture_review.prompt.md \
  --json
```

Observed result:

- Gemini preflight passed.
- cc-glm preflight passed.
- `dx-runner status --json` showed no registered jobs.
- Start wrapper processes remained running with no additional output and had to
  be killed.

Impact:

- Even after bypassing dx-review and using two available provider lanes directly,
  the governed runner did not produce usable reviewer jobs.

## Product Fallback Used

Because the product review should not block on dx-review internals, two Codex
subagents were dispatched as read-only reviewers:

- Reviewer A: data moat, storage, Windmill boundary, provenance, idempotency.
- Reviewer B: sufficiency gates, mechanism cases, direct/indirect/secondary
  economic-analysis readiness, fail-closed behavior.

## Recommended DX Follow-Ups

1. `dx-review doctor` should report whether each reviewer lane is runnable and
   whether quorum can be satisfied on the current host.
2. `dx-review --help` must be non-blocking and should not depend on provider
   preflight or runtime state.
3. `dx-review run` should support an explicit `--reviewers gemini,cc-glm` or
   similar provider allowlist when Claude/OpenCode are unavailable.
4. `dx-runner start --json` should fail fast with structured JSON if the job
   cannot be registered after preflight.
5. OpenCode preflight should print the available model ids or an exact repair
   command when the canonical pinned model is missing.
6. Product agents need one documented fallback path for architecture reviews:
   `dx-review` first, then `dx-runner` provider allowlist, then Codex subagent
   read-only reviewers with a required QA note.
