# Railway Environment Variables

## Backend Service

### Required
```bash
# LLM API (choose one)
OPENROUTER_API_KEY=sk-or-v1-...
# OR
OPENAI_API_KEY=sk-...

# Database (Railway Postgres)
DATABASE_URL=postgresql://postgres:password@host:port/railway
# (Postgres is DEPRECATED - DO NOT USE)
# DATABASE_URL=... (Removed)
# DATABASE_URL=... (Removed)

# Open States API (for California State Legislature)
OPENSTATES_API_KEY=your-key-from-open.pluralpolicy.com

# Error Tracking (Optional but Recommended)
SENTRY_DSN=https://xxxxx@xxxxx.ingest.sentry.io/xxxxx
ENVIRONMENT=production  # or development

# Email Notifications (Optional)
SENDGRID_API_KEY=SG.xxxxx
FROM_EMAIL=notifications@affordabot.ai

# Object Storage (MinIO/S3)
MINIO_URL=minio.railway.internal:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET=affordabot-artifacts
MINIO_SECURE=false

# Optional: LLM Configuration
LLM_MODEL=x-ai/grok-beta  # Default: grok-beta (free tier)
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1  # Default
```

### Optional
```bash
# For production
PORT=8000  # Railway sets this automatically
PYTHON_VERSION=3.9  # Railway auto-detects
```

---

## Frontend Service

### Required
```bash
# Backend API URL (set to Railway backend URL after deployment)
NEXT_PUBLIC_API_URL=https://affordabot-backend.railway.app
```

### Optional
```bash
# For production
PORT=3000  # Railway sets this automatically
NODE_VERSION=18  # Railway auto-detects
```

---

## Shared Variables (if using Railway shared config)

None required - all variables are service-specific.

---

## Setup Instructions

### 1. Backend Service
```bash
railway service create backend
railway link --project <project-id> --environment <env> --service backend
railway variables set OPENROUTER_API_KEY=sk-or-v1-...
railway variables set OPENSTATES_API_KEY=your-key
```

### 2. Frontend Service
```bash
railway service create frontend
railway link --project <project-id> --environment <env> --service frontend
railway variables set NEXT_PUBLIC_API_URL=https://affordabot-backend.railway.app
```

### 3. Local Development (Worktree-Safe)

Affordabot uses a thin repo-local wrapper over the shared agent-skills Railway contract for worktree-safe, non-interactive execution.

```bash
# Verify Railway auth is configured (non-interactive)
make auth-check

# Run backend with Railway context
cd backend
../scripts/dx-railway-run.sh -- poetry run uvicorn main:app --reload

# Run frontend with Railway context
cd frontend
../scripts/dx-railway-run.sh --service frontend -- pnpm dev
```

Or use the Makefile:
```bash
make auth-check
make dev-backend
make dev-frontend
```

The wrapper resolves Railway context from:
1. Worktree context files (`/tmp/agents/.dx-context/<beads-id>/<repo>/railway-context.env`)
2. Local `.dx/railway-context.env`
3. Explicit environment variables (`AFFORDABOT_PROJECT_ID`, `AFFORDABOT_ENV`, `AFFORDABOT_SERVICE`)

---

## Environment Variable Sources

### Get OPENROUTER_API_KEY
1. Sign up at https://openrouter.ai/
2. Navigate to "Keys" section
3. Create new API key
4. **Free tier**: Use model `x-ai/grok-beta`

### Get DATABASE_URL and DATABASE_URL
1. Create project at https://postgres.com/
2. Go to Project Settings → API
3. Copy:
   - `URL` → `DATABASE_URL`
   - `service_role` key → `DATABASE_URL`
4. Run migration:
   ```bash
   psql $DATABASE_URL -f backend/migrations/20251129000000_initial_schema.sql
   ```

### Get OPENSTATES_API_KEY
1. Sign up at https://open.pluralpolicy.com/
2. Navigate to API Keys section
3. Create new API key
4. **Free tier**: Sufficient for MVP usage

---

## Supported Jurisdictions

- **Saratoga**: City of Saratoga (PDF scraping - mocked for MVP)
- **San Jose**: City of San Jose (Legistar API)
- **Santa Clara County**: County of Santa Clara (Legistar API)
- **California**: State of California (Open States API)

---

## Verification

### Backend Health Check
```bash
curl https://affordabot-backend.railway.app/
# Expected: {"message":"Welcome to AffordaBot API","jurisdictions":["saratoga","san-jose","santa-clara-county","california"]}
```

### Deployment Freshness (Runtime Truth, Preferred)
```bash
cd backend
poetry run python ../scripts/verification/verify_remote_deployment.py --check-freshness-only
```

This compares live runtime commit identity from `/health/build` against `origin/master`.

### Scrape & Analyze
```bash
curl -X POST https://affordabot-backend.railway.app/scrape/san-jose
# Expected: JSON with bills + analysis
```

### Get Stored Legislation
```bash
curl https://affordabot-backend.railway.app/legislation/san-jose
# Expected: JSON with stored legislation + impacts
```
