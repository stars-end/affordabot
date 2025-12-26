# llm-common Git Dependency Management

## Critical: Poetry Lock File Staleness

When using `llm-common` as a git dependency in Poetry:
- `pyproject.toml` may specify a tag (e.g., `tag = "v0.6.0"`)
- `poetry.lock` can cache an **older commit hash** that doesn't match the tag
- `poetry update llm-common` may NOT update the lock file

## Symptoms

- `ModuleNotFoundError: No module named 'llm_common.agents'` (agents added in v0.6.0)
- Import errors for features that should exist
- `poetry show llm-common` shows different version than pyproject.toml expects

## Fix

```bash
# Delete stale lock and regenerate
rm poetry.lock
poetry lock
poetry install

# Verify
poetry show llm-common
python -c "from llm_common.agents import ResearchAgent; print('OK')"
```

## Prevention

1. When updating llm-common tag in consumer's pyproject.toml:
   - Run `poetry lock` explicitly
   - Commit the new `poetry.lock`

2. When releasing new llm-common version:
   - Ensure `version` in pyproject.toml matches tag (v0.6.0 → version = "0.6.0")

## Skill Location

Both repos have: `.claude/skills/llm-common-version.md`
