# dx-review Gemini Dogfood QA

Date: 2026-04-16
Worktree: `/tmp/agents/bd-2agbe.1/affordabot`
PR: https://github.com/stars-end/affordabot/pull/436
Beads context: `bd-3wefe.13`

## Goal

Dogfood `dx-review` against PR #436 with the optional Gemini reviewer enabled. The review prompt focused on whether the PR honestly proves Affordabot's data-moat and economic-analysis pipeline goals:

- unified scraped plus true structured evidence packages;
- provider provenance for SearXNG;
- separation of scraped, structured, and secondary-search-derived evidence;
- storage/read-model proof caveats;
- fail-closed economic analysis behavior;
- whether PR #436 should merge, split, or remain an evidence workbench.

## Commands Tried

```bash
dx-review doctor --worktree /tmp/agents/bd-2agbe.1/affordabot --gemini
```

```bash
dx-review run \
  --beads bd-3wefe.13 \
  --worktree /tmp/agents/bd-2agbe.1/affordabot \
  --pr https://github.com/stars-end/affordabot/pull/436 \
  --template architecture-review \
  --prompt-file /tmp/dx-review-affordabot-pr436-data-moat.prompt \
  --read-only-shell \
  --gemini \
  --wait \
  --timeout-sec 1200 \
  --poll-sec 10
```

```bash
dx-review run \
  --beads bd-3wefe.13qa1 \
  --worktree /tmp/agents/bd-2agbe.1/affordabot \
  --prompt-file /tmp/dx-review-affordabot-pr436-small.prompt \
  --read-only-shell \
  --gemini \
  --wait \
  --timeout-sec 900 \
  --poll-sec 10
```

```bash
timeout 20 bash -x /Users/fning/agent-skills/scripts/dx-runner start \
  --profile cc-glm-review \
  --beads bd-3wefe.13trace.glm \
  --prompt-file /tmp/dx-review-affordabot-pr436-small.prompt \
  --worktree /tmp/agents/bd-2agbe.1/affordabot
```

## Results

`dx-review doctor --gemini` partially succeeded:

- `cc-glm-review`: preflight passed.
- `gemini-burst`: preflight passed.
- `claude-code-review`: preflight failed with `claude_code_headless_flags_missing`.

The review runs did not produce usable reviewer output. Both the full architecture prompt and the smaller prompt reproduced the same runner failure:

- `dx-review` launched `cc-glm-review`, `claude-code-review`, and `gemini-burst`.
- Claude failed preflight as expected.
- GLM and Gemini passed preflight but never reached provider execution.
- `dx-runner check` reported GLM/Gemini as `missing` with `pid_file_missing`.
- The GLM/Gemini metadata files were zero bytes or incomplete.
- The GLM log only reached `[cc-glm-adapter] START ...` in the first run and did not advance.

The traced direct `dx-runner start` isolated the failure before adapter launch. After successful preflight, execution reached metadata creation in `/Users/fning/agent-skills/scripts/dx-runner`:

```bash
cat > "$META_FILE" <<EOF
beads=$BEADS
provider=$PROVIDER
...
started_at=$(now_utc)
...
EOF
```

The process hung during this heredoc path and left `/tmp/dx-runner/cc-glm/bd-3wefe.13trace.glm.meta` as a zero-byte file. This makes the run invisible or incomplete to `dx-runner check`, and `dx-review --wait` then waits without useful progress.

## Product Review Impact

No new external review findings were obtained from this dogfood attempt. The useful result is tooling QA:

- optional Gemini preflight works on this host;
- cc-glm preflight works on this host;
- Claude Code Opus review lane is blocked by missing headless CLI flags;
- the current `dx-review`/`dx-runner` launch path can hang before provider start, even after successful preflight, so it is not yet reliable enough for architecture-lock review quorum on this host.

## Frictions

1. Help commands were not reliable during this dogfood pass. `dx-review --help`, `dx-review run --help`, and `dx-review doctor --help` hung and had to be killed. Reading `/Users/fning/bin/dx-review` was required to discover usage.
2. Doctor correctly surfaced `claude_code_headless_flags_missing`, but the later run still attempted the Claude lane and then summarized it as `no_meta`/start failure. The user-facing failure should preserve the concrete preflight reason.
3. `dx-review run --wait` did not fail fast when GLM/Gemini metadata stayed zero-byte after preflight. It remained silent while child `dx-runner start` processes were wedged.
4. `dx-runner check` showed `missing`/`pid_file_missing` for GLM/Gemini even though `dx-review` had launched runner processes. This is confusing because the actual state is `start_hung_before_metadata`, not missing.
5. `dx-review summarize --beads bd-3wefe.13qa1 --gemini` also hung after the failed run, instead of producing a partial failure summary from start logs.
6. The optional Gemini package preflight is good, but the start path did not reach Gemini execution, so this dogfood pass did not validate Gemini review quality.

## Requested Fixes For dx-review/dx-runner

P1:

- Add a startup watchdog for reviewer start processes. If metadata remains zero-byte or no PID appears within a short threshold, terminate the start process and emit `reason_code=start_hung_before_metadata`.
- Make `dx-review run --wait` surface per-reviewer start progress and terminal startup failures instead of staying quiet.
- Preserve concrete preflight reasons from start logs in `dx-review summarize`, especially `claude_code_headless_flags_missing`.
- Make `dx-review summarize` robust when reports/meta are missing or zero-byte.

P2:

- Make `dx-review --help`, subcommand help, and invalid invocations always print usage and exit quickly.
- Add a `dx-review run --doctor-first` or default doctor summary that prints expected lanes before launch.
- Add a compact final quorum table with lane, preflight, start, reviewer output, and schema status.
- Add an explicit `--skip-claude` or `--reviewers glm,gemini` flag for hosts where Claude preflight is known broken.

## Current Recommendation

Do not rely on this dx-review run as architecture-lock quorum for PR #436. Use the existing external review set plus manual source inspection for the current product decision, and file/fix the dx-review startup hang before treating optional Gemini quorum as reliable.
