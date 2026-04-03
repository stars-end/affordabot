# Raw Data Viewer Build-vs-Buy (Operator Surface)

Date: 2026-04-03  
Epic/Subtask: `bd-exvc`  
Scope: Internal operator debugging for substrate/manual expansion runs (not customer BI)

## 1) Current State In Affordabot

Affordabot already has partial operator surfaces:

- Backend admin endpoints in `backend/routers/admin.py`:
  - `/admin/scrapes` (recent raw rows, limited shape)
  - `/admin/pipeline-runs` and `/admin/pipeline-runs/{run_id}`
  - `/admin/runs/{run_id}/steps`
  - `/admin/traces/{query_id}`
  - `/admin/document-health`
  - `/admin/bill-truth/{jurisdiction}/{bill_id}`
- GlassBox service in `backend/services/glass_box.py`:
  - run-head resolution, step retrieval, mechanism trace normalization
- Substrate inspection artifact generator in `backend/scripts/substrate/substrate_inspection_report.py`:
  - run-level counts, promotion/trust/content-class breakdowns
  - failure buckets
  - object-storage and vector-integrity checks
- Windmill manual trigger contract in `ops/windmill/README.md`:
  - manual run returns `run_id` and `inspection_report` artifact block
- Slack summaries in `backend/services/slack_summary.py`:
  - short run summaries and deep links to audit + bill-truth pages

Frontend status:

- `frontend/src/services/adminService.ts` exposes older admin calls but does not provide a dedicated substrate run explorer workflow.

## 2) Operator Requirements (Explicit)

Required capabilities for the raw-data browser:

1. Browse runs by `run_id`.
2. Inspect raw rows tied to one substrate run.
3. Filter by jurisdiction, asset class, promotion state, trust tier, content class.
4. Inspect failures and failure buckets.
5. View substrate inspection report summaries.
6. Drill into one raw scrape row.
7. Open/preview artifact references when possible.
8. Link raw substrate state with GlassBox/pipeline context.
9. Keep access internal/operator-friendly.
10. Keep Slack as alerting, not browsing.

## 3) Gap Analysis (Current vs Needed)

What exists:

- Canonical truth is present in Postgres + raw metadata + inspection artifacts.
- Useful endpoints for traces/run details already exist.

What is missing for a usable operator browser:

- No run-centric substrate page that starts from `run_id` and joins raw rows + inspection + step context.
- No first-class filtering on substrate fields (promotion/trust/content class/failure bucket).
- No dedicated raw-row detail page (with related links and integrity status).
- No artifact preview/open workflow beyond manual URI handling.
- Slack is summary-only (correct), but there is no equivalent browsing UI.
- Existing admin frontend service is too narrow for expansion-run forensic workflows.

## 4) Options

### Option A: Build on Existing In-House Admin + GlassBox (Primary Build)

Description:

- Add a dedicated internal operator viewer in existing backend/frontend:
  - run list
  - run detail
  - row detail
  - filters and failure-bucket views
  - artifact links/previews
  - glassbox deep-linking and context panes

Pros:

- Best fit for run-centric substrate semantics and affordabot-specific truth model.
- Reuses existing auth model and `/admin` access contract.
- Keeps one canonical operator surface without data sync duplication.

Cons:

- More engineering effort than dropping in a generic dashboard tool.
- Requires frontend and backend endpoint additions.

### Option B: OSS BI/Query Layer As Primary Viewer (Metabase/Superset/Grafana)

Description:

- Put operators on SQL/dashboard tools directly against Postgres.

Pros:

- Fast for ad-hoc querying and charting.
- Mature ecosystems and low marginal setup for SQL users.

Cons:

- Poor default fit for run-forensics UX and raw-row-to-artifact-to-glassbox flow.
- Harder to encode affordabot-specific semantics and guided debugging workflow.
- Risk of becoming dashboard-first when need is incident/debug-first.

### Option C: Internal App Platforms As Primary Viewer (ToolJet/Retool)

Description:

- Build internal app UI in ToolJet/Retool as the main substrate browser.

Pros:

- Faster than greenfield UI for forms/tables/filters.
- Can connect directly to Postgres and APIs.

Cons:

- Additional platform operations/governance and policy surface.
- Platform-specific permission/runtime constraints.
- Can drift into “second control plane” if not tightly constrained.

### Option D: Hybrid (In-House Primary + Tooling Secondary)

Description:

- Keep affordabot admin/glassbox as primary source-of-truth viewer.
- Use one secondary tool for ad-hoc SQL exploration only.

Pros:

- Preserves product-specific debugging flow.
- Gives power users ad-hoc query velocity.

Cons:

- Two surfaces to maintain and document.
- Requires strict boundary to avoid confusion.

## 5) External Option Evidence (Primary Sources)

As-of research date: 2026-04-03.

### Metabase

- SQL editor exists and is positioned for querying/analysis (not write operations).
- Data permissions include view/create-query/download/manage controls.
- Some data-permission controls (e.g., `View data`) are Pro/Enterprise.
- Row/column security has important limitations for SQL/native queries.
- Self-hosting via Docker is documented.

### Superset

- Broad SQL/database support and driver model.
- Strong security model including role-based controls and row-level security filters.
- SQL Lab is a first-class query surface (and corresponding API endpoints exist).
- Useful for analysis, but requires more modeling to mimic run-centric operator flow.

### Grafana

- Strong table visualization and data links/actions.
- Explore supports fast ad-hoc querying/inspection.
- Org roles are global; dashboard-level permissions can refine access.
- Data source permissions/RBAC depth varies by OSS vs Enterprise capability.

### ToolJet

- Self-host via Docker documented; requires PostgreSQL for app/auth/credentials metadata.
- Native PostgreSQL data source with SQL mode and SSH tunneling.
- Table component and access-control/data-source-permission model are documented.
- Good fit for quick internal CRUD/query UI, but still an additional platform.

### Retool

- Self-managed/self-hosted deployment guidance is documented (Kubernetes for production; Docker for local/test).
- Permission-level model (`Use`, `Edit`, `Own`) exists for apps/resources/workflows.
- Strong internal-tooling velocity, but introduces another product/runtime plane.

## 6) Comparison Table

| Option | Operator flow fit (run forensics) | Build speed | Artifact preview/link ergonomics | Auth/internal control | Ongoing ops | Lock-in risk |
|---|---|---|---|---|---|---|
| In-house admin/glassbox extension | High | Medium | High | High (existing) | Medium | Low |
| Metabase primary | Medium-low | Medium | Low-medium | Medium | Medium | Medium |
| Superset primary | Medium | Medium-low | Low-medium | Medium-high | High | Medium |
| Grafana primary | Medium-low | Medium | Medium (links strong, run semantics weak) | Medium | Medium-high | Medium |
| ToolJet primary | Medium | High | Medium | Medium-high | Medium-high | Medium-high |
| Retool primary | Medium | High | Medium | High | Medium-high | High |
| Hybrid (in-house primary + secondary SQL tool) | High | Medium | High | High | Medium-high | Medium |

## 7) Recommendation (Explicit)

Recommendation: **Option D with an in-house-primary bias**.

Concretely:

- Build the substrate operator browser into affordabot `/admin` + GlassBox as the canonical surface.
- Optionally add one secondary tool (ToolJet first, Retool only if organization explicitly wants paid governance) for ad-hoc SQL exploration, not as source-of-truth operator workflow.

Why this is lowest regret:

- The core problem is affordabot-specific debugging across `run_id -> raw rows -> failure buckets -> artifact refs -> pipeline/trace context`.
- That workflow maps directly to existing affordabot contracts and is awkward in generic BI/app-builder tools unless heavily customized.
- Preserves moat: operator muscle memory and high-signal debugging tied to substrate truth model.

## 8) Next 1–2 Iterations

### Iteration 1 (must-have, in-house)

- Add substrate run explorer endpoints:
  - list runs with summary stats
  - run detail with filterable raw rows
  - row detail with artifact links and integrity flags
  - failure-bucket views
- Add frontend operator pages that start from `run_id` and expose fast filters.
- Add deep links to existing `/admin/pipeline-runs/{run_id}` and `/admin/runs/{run_id}/steps`.

### Iteration 2 (optional hybrid)

- Stand up one secondary ad-hoc SQL surface (ToolJet recommended first) for power users.
- Restrict to read-mostly diagnostics scope and link back to canonical in-house run pages.
- Explicit policy: operational debugging decisions are made from affordabot admin/glassbox, not secondary dashboards.

## 9) What Not To Do

- Do not make Slack the primary raw-data browser.
- Do not create a second truth store for substrate state.
- Do not make generic BI dashboards the primary incident/debug interface.
- Do not start with a full platform migration before validating run-centric operator workflows in the native admin surface.

## 10) Source References

### Affordabot code/docs inspected

- `docs/specs/2026-04-03-municipal-coverage-campaign-report.md`
- `docs/specs/2026-04-03-municipal-coverage-readiness.md`
- `backend/routers/admin.py`
- `backend/services/glass_box.py`
- `frontend/src/services/adminService.ts`
- `backend/scripts/substrate/substrate_inspection_report.py`
- `ops/windmill/README.md`
- `backend/services/slack_summary.py`

### External primary sources

- Metabase SQL editor: https://www.metabase.com/docs/latest/questions/native-editor/writing-sql
- Metabase data permissions: https://www.metabase.com/docs/latest/permissions/data
- Metabase row/column security: https://www.metabase.com/docs/latest/permissions/row-and-column-security
- Metabase Docker: https://www.metabase.com/docs/latest/installation-and-operation/running-metabase-on-docker
- Superset DB connectivity: https://superset.apache.org/docs/configuration/databases/
- Superset security configs and RLS: https://superset.apache.org/admin-docs/security/
- Superset RLS API surface: https://superset.apache.org/developer-docs/api/row-level-security/
- Superset SQL Lab API surface: https://superset.apache.org/docs/api/sql-lab/
- Grafana Explore: https://grafana.com/docs/grafana/latest/visualizations/explore/
- Grafana PostgreSQL data source: https://grafana.com/docs/grafana/latest/datasources/postgres/
- Grafana Table visualization: https://grafana.com/docs/grafana/latest/visualizations/panels-visualizations/visualizations/table/
- Grafana roles/permissions: https://grafana.com/docs/grafana/latest/administration/roles-and-permissions/
- ToolJet Docker deploy: https://docs.tooljet.com/docs/setup/docker/
- ToolJet PostgreSQL data source: https://docs.tooljet.com/docs/data-sources/postgresql/
- ToolJet component library: https://docs.tooljet.com/docs/app-builder/building-ui/component-library/
- ToolJet access control: https://docs.tooljet.com/docs/user-management/role-based-access/access-control/
- Retool self-hosted quickstart: https://docs.retool.com/self-hosted/quickstart
- Retool permission levels: https://docs.retool.com/permissions/reference/permission-levels

