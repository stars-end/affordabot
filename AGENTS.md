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

**PR Verification** (When to use which):
```
┌─────────────────────────────────────────────────────────────┐
│  Use `make verify-pr PR=N` (FULL) when:                     │
│  • P0 or P1 priority issue                                   │
│  • Changes to agents/, services/, routers/                   │
│  • Infrastructure changes (Makefile, CI, Railway)            │
│  • Multi-file PRs (5+ files changed)                         │
│  • LLM/AI pipeline changes                                   │
├─────────────────────────────────────────────────────────────┤
│  Use `make verify-pr-lite PR=N` (QUICK) when:               │
│  • P2+ priority (minor fixes)                                │
│  • Single file changes                                       │
│  • Documentation only (docs/, README)                        │
│  • Test-only changes                                         │
│  • Beads/config changes                                      │
├─────────────────────────────────────────────────────────────┤
│  Skip verification when:                                     │
│  • Typo fixes                                                │
│  • Comment-only changes                                      │
│  • .gitignore updates                                        │
└─────────────────────────────────────────────────────────────┘
```

Quick check: `gh pr view N --json files | jq '.files | length'` shows file count.

For full V3 guide, see `stars-end/prime-radiant-ai` or run `/help-dx`.
