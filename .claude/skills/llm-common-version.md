---
description: Manage llm-common git dependency versions in Poetry. Use when llm-common imports fail, version mismatch, or updating llm-common.
triggers:
  - llm_common import error
  - ModuleNotFoundError llm_common
  - llm-common version
  - update llm-common
  - poetry.lock stale
---

# llm-common Version Management

## The Problem

Poetry git dependencies can have **stale lock files** where:
- `pyproject.toml` specifies a tag (e.g., `v0.6.0`)
- `poetry.lock` has an older cached commit hash
- `poetry update llm-common` may not update the lock

## Diagnosis

```bash
# 1. Check what version is installed
poetry show llm-common

# 2. Check what pyproject.toml requires
grep llm-common pyproject.toml

# 3. Check what's in the lock file
grep -A3 'name = "llm-common"' poetry.lock

# 4. Compare commits (in llm-common repo)
cd ~/llm-common
git log --oneline -5
git tag -l | tail -5
```

## Fix: Regenerate Lock File

```bash
# From affordabot/backend or prime-radiant-ai/backend
rm poetry.lock
poetry lock
poetry install

# Verify
poetry show llm-common
python -c "from llm_common.agents import ResearchAgent; print('OK')"
```

## Prevention Checklist

1. **When updating llm-common**:
   - [ ] Update tag in consumer's `pyproject.toml`
   - [ ] Run `poetry lock` in consumer repo
   - [ ] Commit the new `poetry.lock`

2. **When releasing llm-common**:
   - [ ] Ensure `version` in `pyproject.toml` matches tag
   - [ ] Create git tag: `git tag v0.X.0 && git push origin v0.X.0`

3. **Version alignment**:
   - llm-common package version should match tag (v0.6.0 → version = "0.6.0")
   - Consumer pyproject.toml should pin to released tags, not branches

## Common Scenarios

### Import Error: `No module named 'llm_common.agents'`
The agents module was added in v0.6.0. Check if lock file has older version.

### `poetry update` doesn't update
Git dependencies cache commits. Delete `poetry.lock` and regenerate.

### Railway deployment fails on llm-common
Ensure `poetry.lock` is committed with correct version.
