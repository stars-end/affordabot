# MVP Go-Live Affordabot Final Plan
**Date**: 2026-01-15
**Verdict**: ⛔ **CRITICAL NO-GO**
**Status**: Final Consolidation (Union of MVP v7 + Launch Readiness + QA Findings)

---

## 1. Executive Summary
This document is the **single source of truth** for the Affordabot V3 launch. It merges the "Fake Data" crisis findings from MVP v7 with the functional failures (Search 404, Admin Traps) discovered during Exhaustive QA.

**The system is currently dangerous to launch.**
It combines **hallucinated costs** (Hypothetical fallback) with **broken navigation** (Users can't search) and **unreachable admin tools** (APIs 404ing).

**Launch Strategy**:
1.  **Phase 1 (Rescue)**: Fix P0s (Data, Search, Admin APIs).
2.  **Phase 2 (Value)**: Add P1s (Watch, Alerts).
3.  **Phase 3 (Growth)**: SEO & Polish.

---

## 2. The "Kill List" (P0 Blockers)
*All items below must be resolved before a "Go" decision.*

### 2.1 Core Integrity (The "Fake Data" Crisis)
*   **Issue**: Engine falls back to "Hypothetical" mock data when retrieval fails (e.g., San Jose Bill #26-041).
*   **Impact**: Legal liability. We are publishing fake civic data.
*   **Fix**: Hard disable of mock fallbacks in `backend/services/llm/orchestrator.py`. Error > Lies.

### 2.2 Public User Experience
*   **Issue**: **Search is Missing**. `/public/search` returns 404. No search bar exists.
*   **Issue**: **Confidence is NaN**. Bill pages display "NaN% Confidence".
*   **Issue**: **Misleading Labels**. $1.5M Impact labeled "Per Family" (Critical implementation error).

### 2.3 Admin Platform
*   **Issue**: **Navigation Trap**. No links to "Discovery", "Sources", or "Reviews" on the dashboard.
*   **Issue**: **API Blackout**. The following Admin APIs are returning 404/500:
    *   `/api/sources` (Source Management broken)
    *   `/api/prompts` (System Prompts broken)
    *   `/api/reviews` (Review Queue broken)
    *   `/api/jurisdictions` (Dashboard data broken)

### 2.4 Deep Audit
*   **Issue**: **Audit Offline**. `/admin/audits/trace` returns 404. Admin "Analysis" tab is unreachable. Use `glass_box_provenance_trace` story to verify.

---

## 3. Comprehensive Beads Execution Map (Exhaustive)

This list maps **every single bug and missing story requirement** found in the V7 QA process to a specific actionable task.

### Epic 1: Trust & Integrity (Data & Logic Rescue)
**Epic ID**: `affordabot-trust-v1`
**Theme**: "Errors > Lies" + "Math must work"

| Beads ID | Priority | Task Name | Maps to Bug/Issue | Implementation Note |
| :--- | :--- | :--- | :--- | :--- |
| `trust-01` | **P0** | **Disable Mock Data Fallback** | **Bug: "Hypothetical" Election Costs** (Story 1) | Hard disable `use_mock_data` in Orchestrator. Raise `InsufficientDataError`. |
| `trust-02` | **P0** | **Fix Confidence Score (NaN)** | **Bug-001: "NaN% Confidence"** (Story 1) | Frontend: `impact.confidence ?? 0`. Backend: Verify model output. |
| `trust-03` | **P1** | **Fix Impact Label Logic** | **Bug-002: "$1.5M per Family"** (Story 1) | `ImpactCard.tsx`: If scope='MUNICIPAL', label='Total Cost'. |
| `trust-04` | **P1** | **Fix Stale Scrapers (SJ/SC)** | **Infra: Stale Data (Dec 19)** | Debug `SanJoseScraper` and `SantaClara` cron jobs in Railway. |

### Epic 2: Public Journey Rescue (Frontend UX)
**Epic ID**: `affordabot-public-v1`
**Theme**: "Users must be able to find and understand bills"

| Beads ID | Priority | Task Name | Maps to Bug/Issue | Implementation Note |
| :--- | :--- | :--- | :--- | :--- |
| `public-01` | **P0** | **Implement /search Route** | **Bug-005: Search Missing** (Story 1) | Create `/public/search`. Add global Search Bar to Navbar. |
| `public-02` | **P0** | **Fix Discovery 404** | **Bug-004: /discovery 404** (Story 2) | Implement `app/discovery/page.tsx` or fix Next.js routing. |
| `public-03` | **P1** | **Add "Econ 101" Labels** | **UX Gap: Econ Analysis** (Story 1) | Add explicitly labeled "Supply", "Demand", "Cost" sections in Analysis UI. |
| `public-04` | **P1** | **Add Bottom Line Summary** | **UX Gap: Verdict Missing** (Story 1) | Add explicit "Positive" / "Negative" / "Neutral" badge to Bill Header. |
| `public-05` | **P0** | **Add Methodology Disclaimer** | **Audit Fail: Transparency** (Trust Audit) | Add footer: "Automated analysis. Verify with official sources." |

### Epic 3: Admin Platform Restoration (Backend/Ops)
**Epic ID**: `affordabot-admin-v1`
**Theme**: "Admins must not be blind or trapped"

| Beads ID | Priority | Task Name | Maps to Bug/Issue | Implementation Note |
| :--- | :--- | :--- | :--- | :--- |
| `admin-01` | **P0** | **Restore Source Mgmt API** | **Bug: /api/sources 404** (Story 6) | Fix FastAPI router. Verify `SourceController` is mounted. |
| `admin-02` | **P0** | **Restore Prompts API** | **Bug: Prompts Fetch Error** (Story 7) | Fix `/api/prompts` endpoint. Ensure DB connection for templates. |
| `admin-03` | **P0** | **Restore Review Queue API** | **Bug: Review Queue Empty/Broken** (Story 8) | Fix `/api/reviews`. Ensure pending items are fetched correctly. |
| `admin-04` | **P0** | **Restore Jurisdiction API** | **Bug: "Failed to load jurisdictions"** (Story 9) | Fix `/api/jurisdictions`. Check 500 logs on request. |
| `admin-05` | **P0** | **Fix Admin Nav Sidebar** | **Bug: Nav Traps** (Story 6-9) | Add links to Sidebar: Discovery, Sources, Prompts, Reviews. |
| `admin-06` | **P1** | **Fix Admin Auth Routing** | **Infra: Generic API Errors** | Ensure Nginx/Next.js middleware correctly proxies `/api/admin/*`. |

### Epic 4: Deep Audit Tools (Debug & Safety)
**Epic ID**: `affordabot-audit-v1`
**Theme**: "Glass Box Debugging for Admins"

| Beads ID | Priority | Task Name | Maps to Bug/Issue | Implementation Note |
| :--- | :--- | :--- | :--- | :--- |
| `audit-01` | **P0** | **Restore Trace Route** | **Bug: /admin/audits/trace 404** (Story 10) | Implement Trace View page. Show Raw Prompt/Response. |
| `audit-02` | **P0** | **Fix Analysis Tab Crash** | **Bug: Admin Analysis 500** (Story 10) | Fix API backing the "Analysis" tab in Admin Console. |
| `audit-03` | **P1** | **Restore Citation Debug** | **Bug: Citation Validity 404** (Story 12) | Implement `/admin/audits/trace/[id]` deep view. |
| `audit-04` | **P1** | **Restore Extraction Debug** | **Bug: Extraction Fidelity 404** (Story 13) | Implement `/admin/sources/debug/[id]` view. |
| `audit-05` | **P2** | **Implement Alerts Widget** | **Bug: Alerts Missing** (Story 11) | Re-enable Alerts Widget on Dashboard once Stats API works. |

### Epic 5: Senior QA & Verification (The "Human" Pass)
**Epic ID**: `affordabot-qa-v1`
**Theme**: "Comprehensive Story Validation"

*This epic triggers a full re-run of ALL stories after fixes are deployed.*

| Story File (Docs) | Focus Area | Complexity |
| :--- | :--- | :--- |
| `voter_bill_impact_journey.yml` | **Public** | High (E2E) |
| `discovery_search_flow.yml` | **Public** | Med (Search) |
| `economic_impact_validity.yml` | **Public** | High (Data) |
| `trend_integrity_check.yml` | **Public** | Low (Stats) |
| `admin_dashboard_overview.yml` | **Admin** | Low (UI) |
| `full_admin_e2e.yml` | **Admin** | High (Flow) |
| `source_management.yml` | **Admin** | Med (CRUD) |
| `prompt_configuration.yml` | **Admin** | Med (Config) |
| `review_queue_workflow.yml` | **Admin** | High (Workflow) |
| `jurisdiction_detail_view.yml` | **Admin** | Med (Data) |
| `glass_box_provenance_trace.yml`| **Audit** | High (Debug) |
| `alert_system_verification.yml` | **Audit** | Med (Integrity) |
| `citation_validity_check.yml` | **Audit** | High (RAG) |
| `extraction_fidelity_check.yml` | **Audit** | High (RAG) |
| `AUDIT_REPORT_20251226.md` | **Legacy** | Reference Only |

---

## 5. Jules Dispatch Strategy (Logical Chunks)
*Tasks grouped for 1-hour autonomous sessions. Prereqs must be met.*

### Session A: Backend Logic Rescue (Self-Contained)
**Target**: `affordabot-trust-v1` (Epic 1)
**Agent**: Jules (Python/Backend Specialist)
**Input**: `backend/services/llm/orchestrator.py`, `backend/models/*.py`
1.  **[JULES-READY]** `trust-01`: Disable Mock Data (Delete `use_mock_data`).
2.  **[JULES-READY]** `trust-04`: Verify/Fix Stale Scrapers (Debug Cron).
*Note: These tasks update python logic and config. No API dependencies.*

### Session B: Admin API Restoration (Self-Contained)
**Target**: `affordabot-admin-v1` (Epic 3)
**Agent**: Jules (Python/FastAPI Specialist)
**Input**: `backend/main.py`, `backend/api/*.py`
1.  **[JULES-READY]** `admin-01`: Restore Source Mgmt API (`/api/sources`).
2.  **[JULES-READY]** `admin-02`: Restore Prompts API (`/api/prompts`).
3.  **[JULES-READY]** `admin-03`: Restore Review Queue API (`/api/reviews`).
4.  **[JULES-READY]** `admin-04`: Restore Jurisdiction API (`/api/jurisdictions`).
*Note: Pure FastAPI router work. Can run parallel to Session A.*

### Session C: Frontend Skeleton & Routing (Self-Contained)
**Target**: `affordabot-public-v1` (Epic 2) & `affordabot-admin-v1` (Admin Nav)
**Agent**: Jules (React/Next.js Specialist)
**Input**: `frontend/src/app`
1.  **[JULES-READY]** `public-01`: Create `/public/search` Page Shell (Route Only).
2.  **[JULES-READY]** `public-02`: Create `/discovery` Page Shell (Route Only).
3.  **[JULES-READY]** `admin-05`: Add Sidebar Links (Discovery, Sources, Prompts).
*Note: Creates the UI shell. Data wiring happens after Session A/B.*

### Session D: Frontend Wiring & Logic (Dependent)
**Prereq**: Session A & B Complete
1.  **[JULES-READY]** `trust-02`: Fix NaN Confidence (`ImpactCard.tsx`).
2.  **[JULES-READY]** `trust-03`: Fix Impact Labels (`ImpactCard.tsx`).
3.  **[JULES-READY]** `public-05`: Add Disclaimer Footer.

---

## 4. Jules Dispatch Strategy (Logical Chunks)
*Tasks grouped for 1-hour autonomous sessions. Prereqs must be met.*

### Session A: Backend Logic Rescue (Self-Contained)
**Target**: `affordabot-trust-v1` (Epic 1)
**Agent**: Jules (Python/Backend Specialist)
**Input**: `backend/services/llm/orchestrator.py`, `backend/models/*.py`
1.  **[JULES-READY]** `trust-01`: Disable Mock Data (Delete `use_mock_data`).
2.  **[JULES-READY]** `trust-04`: Verify/Fix Stale Scrapers (Debug Cron).
*Note: These tasks update python logic and config. No API dependencies.*

### Session B: Admin API Restoration (Self-Contained)
**Target**: `affordabot-admin-v1` (Epic 3)
**Agent**: Jules (Python/FastAPI Specialist)
**Input**: `backend/main.py`, `backend/api/*.py`
1.  **[JULES-READY]** `admin-01`: Restore Source Mgmt API (`/api/sources`).
2.  **[JULES-READY]** `admin-02`: Restore Prompts API (`/api/prompts`).
3.  **[JULES-READY]** `admin-03`: Restore Review Queue API (`/api/reviews`).
4.  **[JULES-READY]** `admin-04`: Restore Jurisdiction API (`/api/jurisdictions`).
*Note: Pure FastAPI router work. Can run parallel to Session A.*

### Session C: Frontend Skeleton & Routing (Self-Contained)
**Target**: `affordabot-public-v1` (Epic 2) & `affordabot-admin-v1` (Admin Nav)
**Agent**: Jules (React/Next.js Specialist)
**Input**: `frontend/src/app`
1.  **[JULES-READY]** `public-01`: Create `/public/search` Page Shell (Route Only).
2.  **[JULES-READY]** `public-02`: Create `/discovery` Page Shell (Route Only).
3.  **[JULES-READY]** `admin-05`: Add Sidebar Links (Discovery, Sources, Prompts).
*Note: Creates the UI shell. Data wiring happens after Session A/B.*

### Session D: Frontend Wiring & Logic (Dependent)
**Prereq**: Session A & B Complete
1.  **[JULES-READY]** `trust-02`: Fix NaN Confidence (`ImpactCard.tsx`).
2.  **[JULES-READY]** `trust-03`: Fix Impact Labels (`ImpactCard.tsx`).
3.  **[JULES-READY]** `public-05`: Add Disclaimer Footer.

---

## 5. Comprehensive Testing Epic (Senior QA)
**Epic ID**: `affordabot-qa-v1`

*Trigger this epic after deployment.*

| Story | File |
| :--- | :--- |
| **Audit Report** | `AUDIT_REPORT_20251226.md` |
| **Admin Dashboard** | `admin_dashboard_overview.yml` |
| **Alert System** | `alert_system_verification.yml` |
| **Citation Check** | `citation_validity_check.yml` |
| **Discovery Search** | `discovery_search_flow.yml` |
| **Econ Impact** | `economic_impact_validity.yml` |
| **Extraction Check** | `extraction_fidelity_check.yml` |
| **Full Admin E2E** | `full_admin_e2e.yml` |
| **Glass Box Trace** | `glass_box_provenance_trace.yml` |
| **Jurisdiction View** | `jurisdiction_detail_view.yml` |
| **Prompt Config** | `prompt_configuration.yml` |
| **Review Queue** | `review_queue_workflow.yml` |
| **Source Mgmt** | `source_management.yml` |
| **Trend Check** | `trend_integrity_check.yml` |
| **Voter Journey** | `voter_bill_impact_journey.yml` |

---

## 6. Implementation Strategy

### Phase 1: Rescue (P0s)
Execute **Session A** and **Session B** immediately.
*   **Why**: We cannot launch a product that lies (Fake Data) or is unmanageable (Admin APIs down).

### Phase 2: Polish (P1s)
Execute **Session C** and remaining P1s.
*   **Why**: Once the system works, we need to prove it works (Audit Tools) and add the "Econ 101" framing (Public UX).

---
**Signed**: Antigravity
