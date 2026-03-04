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
