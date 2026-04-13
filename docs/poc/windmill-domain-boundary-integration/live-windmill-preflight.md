# Live Windmill Preflight (Domain-Boundary POC)

Date: 2026-04-13  
Epic/Subtask: `bd-9qjof` / `bd-9qjof.6`  
PR branch: `feature-bd-9qjof.6`
Merged baseline: PR #432 at `b89ea9c04924673a221b28e3c1f16d535d4472e2`

## Verdict

`stub_orchestration_pass` (partial readiness)

Live remote preflight is no longer auth-blocked. The canonical live harness now runs end to end against the shared dev Windmill workspace using cache-only secret access and a temporary CLI profile.

Current blocker to full architecture lock is not CLI/auth; it is product bridge + storage/runtime evidence.

## Canonical Command

```bash
cd backend
poetry run python scripts/verification/verify_windmill_sanjose_live_gate.py \
  --run-mode stub-run
```

Outputs:

- `docs/poc/windmill-domain-boundary-integration/artifacts/sanjose_live_gate_report.json`
- `docs/poc/windmill-domain-boundary-integration/artifacts/sanjose_live_gate_report.md`

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
  - job id: `019d87c4-fca3-6779-c83e-960402d16ccc`
  - report generated at: `2026-04-13T16:55:32.604224+00:00`
  - script path: `f/affordabot/pipeline_daily_refresh_domain_boundary__flow`
  - success: `true`
  - idempotency key: `bd-9qjof.6-live-gate-20260413-165526`
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

- Local native `wmill` binary is not required; `npx --yes windmill-cli` works.
- Windmill CLI is available via `npx windmill-cli` (version `1.682.0`).
- Agent-safe cached auth resolves `WINDMILL_API_TOKEN` and `WINDMILL_DEV_LOGIN_URL`.
- Live `affordabot` workspace is reachable with a temp `--config-dir` profile.
- Domain-boundary script and flow are deployed and unscheduled.
- Manual San Jose stub run succeeds and emits expected command envelopes.

Not proven:

- Full product bridge execution from Windmill to affordabot domain commands with storage writes.
- Postgres + pgvector + MinIO evidence gates for this run.
- Idempotent rerun and stale/failure drills in live storage-backed mode.

## Risk Assessment

Live skeleton execution is safe to proceed in the existing affordabot dev
workspace if it remains manual and unscheduled because:

1. The `affordabot` workspace is reachable with agent-safe cached auth.
2. Existing flows/scripts are inspectable.
3. The target domain-boundary POC flow is now deployed under a new unscheduled
   path.
4. The skeleton flow does not perform product writes.

## Required Next Step (Before Full Product Pass)

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
