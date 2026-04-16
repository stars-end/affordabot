# Affordabot Local Context

## Verification

| Target | Command | When |
|--------|---------|------|
| Local | `make verify-local` | Before commit |
| E2E | `make verify-pipeline` | Before PR |
| Analysis | `make verify-analysis` | Logic changes |
| Live Freshness | `cd backend && poetry run python ../scripts/verification/verify_remote_deployment.py --check-freshness-only` | Rollout verification (runtime truth via `/health/build`) |

## Quick Start

```bash
dx-check
bd create "title" --type task
```

## Repo-Memory Brownfield Maps

Before changing pipeline, storage, Windmill orchestration, analysis, or admin
frontend surfaces, read:
- `docs/architecture/README.md`
- `docs/architecture/BROWNFIELD_MAP.md`
- `docs/architecture/DATA_AND_STORAGE.md`
- `docs/architecture/WORKFLOWS_AND_PATTERNS.md`
- `docs/architecture/ECONOMIC_ANALYSIS_PIPELINE.md`

## Repo Layout

- `frontend/` - Next.js Prism GUI (canonical frontend)
- `backend/` - FastAPI Python API
- `affordabot_scraper/` - LinkedIn scraper service
- `tests/` - Playwright E2E tests
