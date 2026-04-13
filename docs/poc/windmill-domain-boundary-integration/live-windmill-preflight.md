# Live Windmill Preflight (Domain-Boundary POC)

Date: 2026-04-13  
Epic/Subtask: `bd-9qjof` / `bd-9qjof.6`  
PR branch: `feature/offline-20260412-windmill-bakeoff`  
Target PR head at start: `44d0bbe9bfc546cd937b20273991895117e2d7f9`

## Verdict

`blocked_by_auth`

Live remote preflight cannot proceed in this session because no Windmill workspace/profile is configured locally, and no non-interactive remote context is available without introducing secret/auth mutation risk.

## Scope Checked

Reviewed domain-boundary design and flow assets:

- `docs/architecture/2026-04-12-windmill-affordabot-boundary-adr.md`
- `docs/specs/2026-04-13-windmill-domain-brownfield-spec-lock.md`
- `ops/windmill/f/affordabot/pipeline_daily_refresh_domain_boundary.py`
- `ops/windmill/f/affordabot/pipeline_daily_refresh_domain_boundary__flow/flow.yaml`

## Commands Run (Non-Mutating)

```bash
git -C /tmp/agents/offline-20260412-windmill-bakeoff/affordabot fetch origin feature/offline-20260412-windmill-bakeoff
git -C /tmp/agents/offline-20260412-windmill-bakeoff/affordabot rev-parse HEAD
git -C /tmp/agents/offline-20260412-windmill-bakeoff/affordabot rev-parse origin/feature/offline-20260412-windmill-bakeoff

command -v wmill
npx --yes windmill-cli --version
npx --yes windmill-cli --help
npx --yes windmill-cli profile list
npx --yes windmill-cli workspace list-remote

env | rg '^WINDMILL_' | sed 's/=.*//'
sed -n '1,220p' ops/windmill/wmill.yaml
```

## Evidence Summary

Proven:

- PR branch is pinned to expected head SHA (`44d0bbe...`) before investigation.
- Local native `wmill` binary is not installed on PATH.
- Windmill CLI is available via `npx windmill-cli` (version `1.682.0`).
- Local Windmill profile state shows no active workspace.
- Remote workspace enumeration fails with: no workspace given and no default set.
- Repository has committed Windmill sync config (`ops/windmill/wmill.yaml`) for paths and sync behavior.

Not proven:

- Authenticated access to the development Windmill workspace.
- Presence of required remote workspace paths/resources for domain-boundary dry-run.
- Safe isolated run namespace in live workspace.
- Backend endpoint + internal auth token wiring for live command execution.
- End-to-end non-scheduled flow run in live Windmill.

## Risk Assessment

Live execution is **not safe to proceed autonomously** from this session because:

1. Remote workspace context is absent (no active profile/workspace).
2. Attempting to establish auth/workspace here would require secret/bootstrap steps that are outside this no-mutation preflight lane.
3. Shared workspace isolation is not yet proven (dev-only folder/flow path plus no-schedule policy).

## Required Next Step

Run a controlled auth/bootstrap preflight in a dedicated dev context (cache/service-account path only, no interactive 1Password prompts), then repeat read-only remote checks before any flow run.

If remote preflight passes, run only a **manual non-scheduled dry-run** of:

- `f/affordabot/pipeline_daily_refresh_domain_boundary__flow`

with:

- dev-only idempotency key
- single scope (`san-jose-ca` + `meeting_minutes`)
- explicit proof that no schedule/workspace globals are mutated

## Orchestrator Dry-Run Checklist (Non-Mutating First)

1. Confirm workspace/profile exists and is dev-scoped.
2. Confirm flow/script path exists remotely under affordabot dev workspace.
3. Confirm required backend base URL is dev/staging, not production.
4. Confirm cron/internal auth strategy is available without raw secret reads in shell logs.
5. Confirm run invocation is manual-only (no schedule edits, no enable/disable operations).
6. Confirm evidence capture target:
   - Windmill run ID / URL
   - command envelopes (contract version + jurisdiction/source family)
   - domain command statuses and alerts
7. Confirm rollback procedure is "stop after run"; no persistent schedule mutation.

## POC Search/Reader/LLM Policy (Locked)

- Z.ai direct web search is deprecated for this POC and is not the primary discovery path.
- OSS/SearXNG search is primary for discovery.
- Z.ai direct reader remains canonical for reader extraction.
- Z.ai LLM analysis remains canonical for analysis generation.
