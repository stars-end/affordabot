# Affordabot Local Context

## Skills Architecture

This repo uses a compiled AGENTS.md from:
- **Global skills**: `~/agent-skills/AGENTS.global.md` (workflow skills)
- **Local context**: This file (repo-specific content)
- **Context skills**: `.claude/skills/context-*/` (domain knowledge)

**Auto-Update**: Context skills are automatically updated via GitHub Actions when PRs are merged.

## Verification

| Target | Command | When |
|--------|---------|------|
| Local | `make verify-local` | Before commit |
| E2E | `make verify-pipeline` | Before PR |
| Analysis | `make verify-analysis` | Logic changes |

## Quick Start

```bash
dx-check
bd create "title" --type task
```

## Repo Layout

- `frontend/` - React/Next.js job application UI
- `frontend-v2/` - New version (WIP)
- `backend/` - FastAPI Python API
- `affordabot_scraper/` - LinkedIn scraper service
- `tests/` - Playwright E2E tests
