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

For full V3 guide, see `stars-end/prime-radiant-ai` or run `/help-dx`.
