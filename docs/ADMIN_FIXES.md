# Admin Dashboard & Production Fixes

## Issues Reported
1.  **CORS/Network Errors**: Frontend trying to hit `http://localhost:8000` in production.
2.  **UI Readability**: White font on light background in Admin Dashboard.
3.  **Analysis Lab**: Manual triggers broken.
4.  **Models**: No models configured (need Z.ai GLM-4.6, OpenRouter).
5.  **Health Monitoring**: Missing/Placeholder.
6.  **Prompts**: Failed to load.

## Plan

### 1. Fix Environment & CORS
- [ ] Check `frontend/src/lib/api.ts` for `BACKEND_URL` logic.
- [ ] Ensure `NEXT_PUBLIC_BACKEND_URL` is set correctly in Railway or defaults to relative path if using proxy (or correct absolute path).
- [ ] Verify Railway environment variables.

### 2. Fix UI Readability
- [ ] Inspect `frontend/src/app/admin/page.tsx` and related components.
- [ ] Fix text colors for glassmorphism (ensure contrast).

### 3. Fix Models & Prompts
- [ ] Check backend `routers/admin.py` for model/prompt endpoints.
- [ ] Create a seed script or migration to insert default models (Z.ai, OpenRouter) into Supabase.
- [ ] Verify frontend data fetching for models/prompts.

### 4. Fix Analysis Lab
- [ ] Debug `frontend/src/components/admin/AnalysisLab.tsx`.
- [ ] Ensure API calls are correct.

### 5. Deployment & Verification
- [ ] Deploy changes.
- [ ] Verify using Railway CLI logs.
- [ ] Manual verification on deployed site.
