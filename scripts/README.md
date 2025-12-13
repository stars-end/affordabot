# Scripts Inventory & Hygiene

**Canonical Hierarchy:**

- `scripts/cli/` — Developer-facing tools (e.g., `dx_doctor.sh`, `bd` wrappers). Intended for direct execution.
- `scripts/ci/` — CI-only scripts (e.g., validation, environment checks). Invoked by GitHub Actions.
- `scripts/maintenance/` — Database ops, one-off fixes, cron maintenance.
- `scripts/legacy/` — Deprecated scripts slated for removal. Do not rely on these.
- `scripts/lib/` — Shared libraries and utilities imported by other scripts.

**Rules:**
1. Do not dump scripts in `scripts/` root.
2. New scripts must go into one of the above subdirectories.
3. Update `package.json`, `Makefile`, and CI workflows when moving scripts.

## Inventory
(Auto-generated manifest below - maintain this lists of key scripts)

### CLI
- `dx_doctor.sh`: Pre-session healthcheck.
- `agent_bootstrap.py`: Agent Mail connectivity check (session start).

### CI
- `bulk_validation.py`: Batch validation logic.
- `validate_pipeline_sanjose.py`: Specific pipeline verification.
- `e2e_test.py`: End-to-end testing script.

### Maintenance
- `create_minio_bucket.py`: Infrastructure setup.
- `seed_sources.py`: Database seeding.
- `git/`: Git hooks installers.

### Verification
- `verify_*.py`: Feature verification scripts.
- `test_pipeline.py`: Pipeline test wrapper.
