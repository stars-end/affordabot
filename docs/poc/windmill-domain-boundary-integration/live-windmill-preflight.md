# Live Windmill Preflight (Domain-Boundary POC)

Date: 2026-04-13  
Epic/Subtask: `bd-9qjof` / `bd-9qjof.6`  
PR branch: `feature/offline-20260412-windmill-bakeoff`  
Target PR head at start: `44d0bbe9bfc546cd937b20273991895117e2d7f9`

## Verdict

`blocked_by_auth`

Live remote preflight cannot proceed in this session because no Windmill workspace/profile is configured locally, and no non-interactive remote context is available without introducing secret/auth mutation risk.

### 2026-04-13 Expanded CLI Smoke Update

`pass_for_windmill_cli_and_skeleton_flow`, not blocked by CLI auth.

The earlier auth blocker was resolved with agent-safe cached 1Password access
and a throwaway Windmill CLI profile. No raw `op` commands, GUI-backed auth, or
persistent local Windmill profile were used.

Validated canonical variables:

- `WINDMILL_API_TOKEN`: cached at
  `op://dev/Agent-Secrets-Production/WINDMILL_API_TOKEN`.
- `WINDMILL_DEV_LOGIN_URL`: cached at
  `op://dev/Agent-Secrets-Production/WINDMILL_DEV_LOGIN_URL`.
- `WINDMILL_BASE_URL`: derived by stripping `/user/login` from
  `WINDMILL_DEV_LOGIN_URL`.
- `WINDMILL_WORKSPACE`: `affordabot`.
- `TMP_WMILL_CONFIG`: per-run temporary config directory.

Expanded read-only surface verified:

- temporary workspace profile creation via `workspace add`
- `workspace list`
- `job list --json`
- `flow list`
- `flow get f/affordabot/manual_substrate_expansion --json`
- `script list`
- `script get f/affordabot/trigger_cron_job --json`

Observed live workspace state:

- Existing scheduled flows are visible:
  - `f/affordabot/discovery_run`
  - `f/affordabot/daily_scrape`
  - `f/affordabot/rag_spiders`
  - `f/affordabot/universal_harvester`
- Existing manual flow is visible:
  - `f/affordabot/manual_substrate_expansion`
- Existing script is visible:
  - `f/affordabot/trigger_cron_job`
- Domain-boundary POC flow was initially not deployed:
  - `f/affordabot/pipeline_daily_refresh_domain_boundary__flow`
  - CLI result: `Flow not found`
- Domain-boundary POC script and flow were then deployed as unscheduled dev
  assets.
- Manual San Jose meeting-minutes skeleton flow run completed successfully:
  - job id: `019d87a2-41c1-9576-7d85-55834a78dbfc`
  - created at: `2026-04-13T16:17:31.052996Z`
  - script path: `f/affordabot/pipeline_daily_refresh_domain_boundary__flow`
  - success: `true`
  - idempotency key: `bd-9qjof.6-cli-smoke-2026-04-13-r5`
  - scope: `San Jose CA` / `meeting_minutes`
  - final status: `succeeded`
  - scope totals: `scope_total=1`, `scope_succeeded=1`,
    `scope_failed=0`, `scope_blocked=0`
  - verified step sequence:
    - `search_materialize`
    - `freshness_gate`
    - `read_fetch`
    - `index`
    - `analyze`
    - `summarize_run`
  - every step envelope included:
    - `contract_version=2026-04-13.windmill-domain.v1`
    - `orchestrator=windmill`
    - `windmill_workspace=affordabot`
    - `windmill_flow_path=f/affordabot/pipeline_daily_refresh_domain_boundary__flow`
    - `jurisdiction_id=San Jose CA`
    - `source_family=meeting_minutes`

CLI friction discovered:

- `windmill-cli` `1.682.0` rejects the runbook's old `-r "$WINDMILL_BASE_URL"`
  form.
- Direct `--base-url` commands require `--token` and `--workspace`, but the
  temporary-profile pattern is more reliable and easier to audit.
- `flow push` help says `file_path`, but passing the nested `flow.yaml` path made
  CLI `1.682.0` look for `flow.yaml/flow.yaml`; pass the local flow directory.
- The cached `WINDMILL_DEV_LOGIN_URL` is a browser login URL; using it directly
  returns HTML from some commands. Normalize it to instance root before API use.
- `ops/windmill/wmill.yaml` warns that `gitBranches` is deprecated in favor of
  `workspaces`.
- For-loop step transforms cannot use `iter.value` / `iter.index` directly in
  this exported YAML shape; use `flow_input.iter.value` and
  `flow_input.iter.index`.
- Windmill can pass omitted optional script inputs as `null`; the script
  entrypoint now coalesces nulls back to contract defaults, and the flow passes
  explicit contract metadata for every script step.

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

- Presence of required remote workspace paths/resources for domain-boundary dry-run.
- Safe isolated run namespace in live workspace.
- Backend endpoint + internal auth token wiring for live command execution.
- End-to-end non-scheduled flow run in live Windmill.

## Risk Assessment

Live skeleton execution is safe to proceed in the existing affordabot dev
workspace if it remains manual and unscheduled because:

1. The `affordabot` workspace is reachable with agent-safe cached auth.
2. Existing flows/scripts are inspectable.
3. The target domain-boundary POC flow is now deployed under a new unscheduled
   path.
4. The skeleton flow does not perform product writes.

## Required Next Step

Replace skeleton stubs with backend domain-command calls behind the same
Windmill flow shape, then repeat the manual San Jose run and verify persisted
Postgres/pgvector/MinIO evidence.

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
