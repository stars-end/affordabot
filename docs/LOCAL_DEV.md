# Local Development Guide

## Quick Start (Traditional)
1. **Frontend**: `make dev-frontend`
2. **Backend**: `make dev-backend`

## Quick Start (Railway Pilot)
Orchestrate all services with a single command (requires enabled Railway Project):

```bash
make dev-railway
# OR
./scripts/railway-dev.sh
```

### Prerequisites
- [Railway CLI](https://docs.railway.app/guides/cli) installed (`npm i -g @railway/cli`)
- Linked project: `railway link` (run once)
- Docker installed (required by Railway to spin up databases)

### Benefits
- **One Command**: Runs Postgres, Redis, Backend, and Frontend together.
- **Environment**: Automatically injects secrets from your linked Railway project.
- **Production Parity**: Runs services closer to how they run in production.

### Troubleshooting
- **"Project not found"**: Run `railway link` to select your project.
- **Port Conflicts**: Ensure nothing else is running on ports 8000 (API), 3000 (Web), or 5432 (Postgres).
