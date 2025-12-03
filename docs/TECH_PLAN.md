# Technical Plan: Toolchain & Dependency Hygiene

## Overview
This plan covers the updates to the Affordabot toolchain to ensure robust dependency management and a modern Python environment.

## Python 3.13 Migration
- **Goal**: Standardize on Python 3.13 for all backend development.
- **Implementation**:
  - Updated `.python-version` to `3.13`.
  - Updated `Makefile` to use `python3.13` when creating virtual environments.
  - **Verification**: `make dev-backend` ensures the venv is created with the correct version.

## Git Submodules (`llm-common`)
- **Goal**: Ensure `packages/llm-common` is always present and up-to-date.
- **Implementation**:
  - Added `git submodule update --init --recursive` to `make install` and `scripts/bootstrap.sh`.
  - Added a preflight check in `Makefile` and `bootstrap.sh` to fail if `packages/llm-common/pyproject.toml` is missing.
- **Requirement**: All dev/CI flows MUST run submodule update before installing backend dependencies.

## Testing
- Backend smoke tests verify basic admin endpoints and `llm-common` importability.
- Frontend build verification ensures no regressions in the build process.
