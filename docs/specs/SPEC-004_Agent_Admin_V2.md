# SPEC-004: Agent Admin V2

**Status**: Planning
**Epic**: `affordabot-9g6`
**Dependencies**: SPEC-003 (Resolved)

## 1. Overview
Rebuild the internal Admin Dashboard with recovered schemas and production-grade authentication.

## 2. Gap Resolution

### 2.1 Schema Recovery (Highest Priority)
**Status**: Recovered in `backend/migrations/002_schema_recovery_v2.sql`.
**Action**: Run this migration immediately to restore `admin_tasks`, `pipeline_runs`, `sources`.
**Why First?**: The application code (`routers/admin.py`) will crash 500s without these tables. We need the data model to be valid before we protect it.

### 2.2 Authentication Strategy
**Decision**: **Clerk Integration** (Recommended over Basic Auth)
**Rationale**:
- **Parity**: Matches `prime-radiant-ai` architecture.
- **Security**: Robust session management, no plaintext passwords in envs.
- **Future-Proof**: "Throwaway" Basic Auth work is avoided.
- **Effort**: Higher initial setup (Frontend SDK + Backend JWKS verify) but implies zero debt.

**Implementation Plan (Clerk)**:
1.  **Frontend**: Wrap Admin layout in `<ClerkProvider>` / `<SignedIn>`.
2.  **Backend**: Add `ClerkAuthUnverified` (dev) or proper JWT verification middleware to `main.py` / `admin.py`.
3.  **User**: Needs to provide `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` and `CLERK_SECRET_KEY`.

## 3. Execution Order
1.  **Schema**: Apply `002_schema_recovery_v2.sql`.
2.  **Auth**: Implement Clerk integration (Frontend + Backend).
