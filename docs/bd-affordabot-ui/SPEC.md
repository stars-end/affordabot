# Frontend Rewrite (Prime Radiant v2.1 Prototype) Spec

## Objective
Rewrite `affordabot/frontend` to eliminate Next.js/Shadcn technical debt and prototype the future Prime Radiant stack.

## The Stack (v2.1)
*   **Build**: Vite
*   **Routing**: React Router 7
*   **UI Library**: Material UI v7 (Base components)
*   **Layout/Styling**: Tailwind CSS v4 (Speed & Layout)
*   **Data Fetching**: TanStack Query v5 (State management)
*   **Forms**: React Hook Form + Zod

## Migration Steps
1.  **Scaffold**: Initialize `frontend-v2` with Vite React TS template.
2.  **Setup**: Configure Tailwind, MUI Theme, and QueryClient.
3.  **Port**:
    *   `ScrapeManager` -> `routes/admin/scraping.tsx`
    *   `AnalysisLab` -> `routes/admin/analysis.tsx` (Glass Box Logic)
    *   `ModelRegistry` -> `routes/admin/models.tsx`
    *   `PromptEditor` -> `routes/admin/prompts.tsx`
4.  **Verify**: E2E tests must pass (parity with `frontend`).

## Verification
*   `pnpm test:e2e`: Runs existing Playwright specs adapted for new routes.
