# AGENTS.md — Affordabot V3 DX

**Start Here**
1. **Initialize**: `source ~/.bashrc && dx-check || curl -fsSL https://raw.githubusercontent.com/stars-end/agent-skills/master/scripts/dx-hydrate.sh | bash`
2. **Check Environment**: `dx-check` checks git, Beads, and Skills.

**Core Tools**:
- **Beads**: Issue tracking. Use `bd` CLI.
- **Skills**: Automated workflows (`start-feature`, `sync-feature`, `finish-feature`).

**Daily Workflow**:
1. `start-feature bd-xxx` - Start work.
2. Code...
3. `sync-feature "message"` - Save work (runs ci-lite).
4. `finish-feature` - Verify & PR.

---

# AGENTS.md — Affordabot V3 DX

**Start Here**

1. **Check Environment**:
   ```bash
   ./scripts/cli/dx_doctor.sh
   ```
   This checks git status, Beads CLI, Railway shell, and Skills.

2. **Core Tools**:
   - **Beads**: Issue tracking. Use `bd` CLI.
   - **Serena**: Code navigation/search/edit. Use via MCP.
   - **Skills**: Automated workflows. Trigger via natural language (e.g., "commit my work").

3. **Documentation**:
   - `scripts/README.md` - Scripts hierarchy
   - `docs/` - Project documentation

**Daily Workflow**:
1. `scripts/bd-context` - Check work
2. Code...
3. `make ci-lite` (Fast validation)
4. "commit my work" (Syncs feature branch)
5. "create PR" (Atomic merge)

**Development**:
- **Standard**: `make dev-frontend` + `make dev-backend` (Split terminals).
- **Validation**: `make lint` or `make ci-lite` (Recommended before push).

**Agent Rules**:
- Issue-First: Create `bd` issue before coding.
- Feature-Key: Required in commits.
- Railway Shell: Required for DB ops.
- **NO .env FILES**: Use `railway shell` for all secrets and env vars. NEVER create or use .env files.

**Verification Cheatsheet** (Harmonized Naming):
```
┌─────────────────────────────────────────────────────────────┐
│  Target             │ Scope       │ Use For                  │
├─────────────────────┼─────────────┼──────────────────────────┤
│  make verify-local  │ Local       │ Lint, unit tests (fast)  │
│  make verify-dev    │ Railway dev │ Full E2E after merge     │
│  make verify-pr PR=N│ Railway PR  │ P0/P1 PRs, multi-file    │
│  make verify-pr-lite│ Railway PR  │ P2+, docs, single file   │
├─────────────────────┤─────────────┼──────────────────────────┤
│  Skip when: typos, comments, .gitignore updates             │
└─────────────────────────────────────────────────────────────┘
```
Quick check: `gh pr view N --json files | jq '.files | length'`

Quick check: `gh pr view N --json files | jq '.files | length'` shows file count.

For full V3 guide, see `stars-end/prime-radiant-ai` or run `/help-dx`.
