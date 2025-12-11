# Development Guide

## Lockfile Management

We use a **single root lockfile** (`pnpm-lock.yaml`) for the entire workspace. This ensures consistent dependencies across all packages (`backend`, `frontend`) and prevents "lockfile drift" where the CI environment (which builds from root) sees different versions than local development.

### Troubleshooting Lockfile Errors

If you encounter `ERR_PNPM_OUTDATED_LOCKFILE` in CI or similar errors:

1.  **Do NOT** run `pnpm install` inside `frontend/` or `backend/`. This creates child lockfiles which are ignored by git but might confuse local tools.
2.  **DO** run `pnpm install` at the repository root. This updates the single `pnpm-lock.yaml`.
3.  **Commit** the updated `pnpm-lock.yaml`.

### Why this matters

Railway and CI pipelines often differ in how they install dependencies. By enforcing a single lockfile at the root, we ensure that:
- `frontend` uses the exact versions specified in the root lockfile.
- `backend` (if using Node dependencies) does the same.
- We have a single source of truth for the entire repo.
