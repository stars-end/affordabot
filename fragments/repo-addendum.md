## Beads Integration

### Beads State Sync

**Before starting work**:
```bash
cd ~/bd
export BEADS_DOLT_SERVER_HOST="${BEADS_DOLT_SERVER_HOST:-100.107.173.83}"
export BEADS_DOLT_SERVER_PORT=3307
beads-dolt dolt test --json
beads-dolt status --json | jq -c '.summary'
```

**Failure mode**:
- `beads-dolt dolt test --json` reports `connection_ok: false`
- `beads-dolt status --json` fails or errors
- `jq` not available

Run `~/.agent/skills/health/bd-doctor/fix.sh` or `beads-dolt-fleet` after checking endpoint reachability.

### Feature-Key Trailers

**All commits MUST include**:
```
Feature-Key: {beads-id}
Agent: {routing-name or DX_AGENT_ID}
Role: {engineer-type}
```

### Beads CLI Reference

| Command | Purpose |
|---------|---------|
| `bd list` | Show all issues |
| `bd create "title" --type task` | Create new issue |
| `bd start bd-xxx` | Start working on issue |
| `beads-dolt dolt test --json` | Hub-spoke Beads health check |
| `beads-dolt status --json` | Source-of-truth issue summary |
| `bd sync` | Legacy JSONL compatibility (manual use only) |
| `bd export -o .beads/issues.jsonl` | Legacy JSONL compatibility export |

## Auth and Secrets

- Prefer cached OP service-account mode by default for any auth that needs to survive across tool calls or repeated secret reads.
- Use `~/agent-skills/scripts/dx-load-railway-auth.sh -- <cmd>` or an equivalent one-shell invocation when OP and Railway auth must be loaded together.
- If a command needs both `OP_SERVICE_ACCOUNT_TOKEN` and `RAILWAY_API_TOKEN`, load them in the same shell invocation rather than relying on exported state between tool calls.
- Canonical Windmill CLI source is `op://dev/Agent-Secrets-Production/WINDMILL_API_TOKEN`.
- Treat standalone references like "windmill dev api token" as legacy or ambiguous unless a specific migration step explicitly requires them.

## Affordabot DB Access Rule

For database inspection, validation, or ad hoc SQL in Affordabot:

- Use [$database-quickref](/Users/fengning/agent-skills/core/database-quickref/SKILL.md)
- Preferred repo-native read-only path:
  `~/agent-skills/scripts/dx-load-railway-auth.sh -- ~/agent-skills/scripts/dx-railway-postgres.sh --repo-root "$PWD" backend-python -- bash -lc 'cd backend && poetry run python scripts/db_inspect.py tables'`
- Additional paved commands:
  `... poetry run python scripts/db_inspect.py describe legislation`
  `... poetry run python scripts/db_inspect.py jurisdiction-summary --limit 25`
  `... poetry run python scripts/db_inspect.py pipeline-runs --limit 25`
  `... poetry run python scripts/db_inspect.py raw-scrapes --hours 24 --limit 25`
  `... poetry run python scripts/db_inspect.py query --sql 'SELECT COUNT(*) AS c FROM jurisdictions'`
- Do not rely on ambient Railway project linkage from another repo
- Do not guess Railway service names
- Do not use interactive Railway CLI flows in non-TTY sessions
- Do not treat `psql: No such file or directory` as a service-discovery problem
- If no verified repo-native query runner exists and no working `psql` path is available, agents MUST stop with the exact blocker contract from `database-quickref`
- In QA / audit passes, agents must not install packages ad hoc in Railway runtimes to work around missing DB tooling
