# AffordaBot

**Automated Affordability Analysis for California Legislation**

AffordaBot is a "Dependabot for government" - continuously monitoring new bills and regulations, analyzing their cost-of-living impact on typical families using SOTA LLMs, and presenting results through an interactive dashboard.

## Tech Stack

- **Backend**: FastAPI (Python) + Instructor (LLM orchestration)
- **Frontend**: Next.js 16 + Tremor (analytics UI)
- **Database**: Supabase (PostgreSQL)
- **Infrastructure**: Railway
- **LLMs**: OpenRouter (Grok-beta) / OpenAI / Anthropic

## Quick Start

### Prerequisites
- Python 3.9+
- Node.js 18+
- Railway CLI (`npm i -g @railway/cli`)
- Supabase account
- OpenRouter or OpenAI API key

### Local Development

1. **Clone & Install**
   ```bash
   git clone https://github.com/YOUR_USERNAME/affordabot.git
   cd affordabot
   ./scripts/bootstrap.sh
   
   # Backend
   cd backend
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   
   # Frontend
   cd ../frontend
   npm install
   ```

2. **Set Environment Variables**
   See [`RAILWAY_ENV.md`](./RAILWAY_ENV.md) for full list.
   
   ```bash
   # Backend (.env)
   OPENROUTER_API_KEY=sk-or-v1-...
   SUPABASE_URL=https://xxxxx.supabase.co
   SUPABASE_SERVICE_ROLE_KEY=eyJhbGc...
   
   # Frontend (.env.local)
   NEXT_PUBLIC_API_URL=http://localhost:8000
   ```

3. **Run Services**
    ```bash
    # Terminal 1 - Backend
    cd backend
    ../scripts/dx-railway-run.sh -- poetry run uvicorn main:app --reload
    
    # Terminal 2 - Frontend
    cd frontend
    ../scripts/dx-railway-run.sh --service frontend -- pnpm dev
    ```

    Or use the Makefile wrapper:
    ```bash
    make dev-backend
    make dev-frontend
    ```

4. **Visit Dashboard**
   Open http://localhost:3000

## Deployment

See [`RAILWAY_ENV.md`](./RAILWAY_ENV.md) for Railway deployment instructions.

## Project Structure

```
affordabot/
├── backend/
│   ├── main.py                 # FastAPI app
│   ├── services/
│   │   ├── scraper/           # Legislation scrapers
│   │   └── llm/               # LLM analysis
│   └── schemas/               # Pydantic models
├── frontend/
│   ├── src/
│   │   ├── app/               # Next.js pages
│   │   ├── components/        # React components
│   │   └── lib/               # API client
│   └── tailwind.config.js
├── supabase/
│   └── migrations/            # Database schema
└── railway.toml               # Deployment config
```

## Features

- ✅ Automated bill scraping (Saratoga MVP)
- ✅ LLM-powered impact analysis (Instructor + OpenRouter)
- ✅ Interactive dashboard with percentile sliders
- ✅ Structured output validation (prevents hallucination)
- ✅ Evidence-based analysis with citations
- 🚧 Multi-jurisdiction support (planned)
- 🚧 Real-time notifications (planned)

## License

MIT


## Contributing

See [`CONTRIBUTING.md`](./CONTRIBUTING.md) (coming soon)

## Lockfile Management

We use a **single root lockfile** (`pnpm-lock.yaml`) for the entire workspace.

**If you see lockfile errors in CI:**
1. Run `pnpm install` at the repo root.
2. Commit the updated `pnpm-lock.yaml`.
3. Do NOT commit `frontend/pnpm-lock.yaml` or `backend/pnpm-lock.yaml` (these are gitignored).

