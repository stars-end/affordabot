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
   railway run uvicorn main:app --reload
   
   # Terminal 2 - Frontend
   cd frontend
   railway run npm run dev
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
