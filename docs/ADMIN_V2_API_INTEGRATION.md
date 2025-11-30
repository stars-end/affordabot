# Admin Dashboard V2 - API Integration Guide

**Last Updated**: 2025-11-30 18:42 PST
**Status**: ✅ Complete - All Routes Implemented

## Overview

Next.js API routes have been created to proxy requests from the frontend to the FastAPI backend. This provides a clean separation between frontend and backend while maintaining type safety and error handling.

## API Routes Created

All routes are in `frontend/src/app/api/admin/`:

### 1. Scraping
- **POST** `/api/admin/scrape` → `backend/admin/scrape`
  - Triggers manual scrape
  - Request: `{jurisdiction: string, force: boolean}`
  - Response: `{task_id, jurisdiction, status, message}`

- **GET** `/api/admin/scrapes` → `backend/admin/scrapes`
  - Fetches scrape history
  - Query params: `jurisdiction`, `limit`
  - Response: Array of scrape history items

### 2. Analysis
- **POST** `/api/admin/analyze` → `backend/admin/analyze`
  - Runs analysis step
  - Request: `{jurisdiction, bill_id, step, model_override?}`
  - Response: `{task_id, step, status}`

- **GET** `/api/admin/analyses` → `backend/admin/analyses`
  - Fetches analysis history
  - Query params: `jurisdiction`, `bill_id`, `step`, `limit`
  - Response: Array of analysis history items

### 3. Models
- **GET** `/api/admin/models` → `backend/admin/models`
  - Fetches model configurations
  - Response: Array of model configs

- **POST** `/api/admin/models` → `backend/admin/models`
  - Updates model configurations
  - Request: `{models: Array<ModelConfig>}`
  - Response: `{message, count}`

### 4. Prompts
- **GET** `/api/admin/prompts/[type]` → `backend/admin/prompts/{type}`
  - Fetches active prompt by type
  - Path param: `type` (generation | review)
  - Response: `{prompt_type, system_prompt, updated_at, updated_by}`

- **POST** `/api/admin/prompts` → `backend/admin/prompts`
  - Updates prompt (creates new version)
  - Request: `{prompt_type, system_prompt}`
  - Response: `{message, version, updated_at}`

## Environment Configuration

### Frontend (.env.local)

Create `frontend/.env.local`:

```bash
BACKEND_URL=http://localhost:8000
```

For production:
```bash
BACKEND_URL=https://your-backend-url.com
```

### Backend

Ensure these are set:
```bash
SUPABASE_URL=https://jqcnqlgbbcfwfpmvzbqi.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
```

## Running the Application

### Development

**Terminal 1 - Backend**:
```bash
cd backend
uvicorn main:app --reload --port 8000
```

**Terminal 2 - Frontend**:
```bash
cd frontend
pnpm dev
```

**Access**:
- Frontend: http://localhost:3000
- Admin Dashboard: http://localhost:3000/admin
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

### Production

**Backend** (Railway):
```bash
railway up
```

**Frontend** (Vercel/Railway):
```bash
pnpm build
pnpm start
```

## Error Handling

All API routes include:
- Try-catch blocks
- HTTP status code propagation
- Error message formatting
- Console logging for debugging

Example error response:
```json
{
  "error": "Failed to trigger scrape",
  "details": "Backend error message"
}
```

## Testing

### Manual Testing

```bash
# Test scrape endpoint
curl -X POST http://localhost:3000/api/admin/scrape \
  -H "Content-Type: application/json" \
  -d '{"jurisdiction": "san_jose", "force": false}'

# Test models endpoint
curl http://localhost:3000/api/admin/models

# Test prompts endpoint
curl http://localhost:3000/api/admin/prompts/generation
```

### Automated Testing

Use the test script:
```bash
# Update script to use Next.js API routes
sed -i '' 's|localhost:8000|localhost:3000|g' backend/test_admin_endpoints.sh
./backend/test_admin_endpoints.sh
```

## CORS Configuration

If needed, add CORS middleware to FastAPI backend:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## Troubleshooting

### Issue: "Failed to fetch"

**Solution**: Ensure backend is running on port 8000

```bash
cd backend
uvicorn main:app --reload --port 8000
```

### Issue: "BACKEND_URL not defined"

**Solution**: Create `.env.local` file

```bash
cd frontend
echo "BACKEND_URL=http://localhost:8000" > .env.local
```

### Issue: "Database not available"

**Solution**: Check Supabase credentials

```bash
# In backend directory
echo $SUPABASE_URL
echo $SUPABASE_SERVICE_ROLE_KEY
```

## Next Steps

1. ✅ API routes created
2. ⏳ Test all endpoints
3. ⏳ Add real-time updates (SWR)
4. ⏳ Deploy to production
5. ⏳ Add authentication

## File Structure

```
frontend/src/app/api/admin/
├── scrape/
│   └── route.ts          # POST /api/admin/scrape
├── scrapes/
│   └── route.ts          # GET /api/admin/scrapes
├── analyze/
│   └── route.ts          # POST /api/admin/analyze
├── analyses/
│   └── route.ts          # GET /api/admin/analyses
├── models/
│   └── route.ts          # GET/POST /api/admin/models
└── prompts/
    ├── [type]/
    │   └── route.ts      # GET /api/admin/prompts/[type]
    └── route.ts          # POST /api/admin/prompts
```

## Complete Integration Checklist

- [x] Create API routes (7 total)
- [x] Add error handling (try-catch in all routes)
- [x] Configure environment variables (BACKEND_URL)
- [x] Test build (✅ passing)
- [x] Backend database integration (all queries implemented)
- [ ] Manual testing (start backend + frontend locally)
- [ ] Add request logging (future enhancement)
- [ ] Add rate limiting (future enhancement)
- [ ] Deploy to production (future)
