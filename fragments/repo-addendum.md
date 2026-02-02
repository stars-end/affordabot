# Repo Addendum: Affordabot

## Tech Stack
- **Frontend**: Next.js 14+ (App Router), TailwindCSS, Clerk Auth.
- **Backend**: Python 3.12+, FastAPI, SQLAlchemy, Poetry.
- **Shared**: `llm-common` git dependency.

## Development Rules
- Use `make dev` to start both frontend and backend.
- UI changes MUST be verified with Playwright (`make e2e`).
- All economic analysis MUST use `z.ai` models.
- Backend routes MUST be registered in `backend/main.py`.
