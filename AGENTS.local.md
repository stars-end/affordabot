# Affordabot Local Context

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
