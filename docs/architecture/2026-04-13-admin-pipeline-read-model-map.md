# Admin Pipeline Read-Model Map (Backend)

Date: 2026-04-13  
Scope: backend API/read-model consolidation for `bd-bupjb.1`

## Endpoint Surface

| Endpoint | Owner | DB Tables | Identifier Semantics | Frontend Consumer (observed) |
| --- | --- | --- | --- | --- |
| `GET /api/admin/pipeline-runs` | GlassBox (`GlassBoxService.list_pipeline_runs`) | `pipeline_runs` | Run list (`pipeline_runs.id`) | Audit Trace list page |
| `GET /api/admin/pipeline-runs/{run_id}` | GlassBox (`GlassBoxService.get_pipeline_run`) | `pipeline_runs` + `pipeline_steps` | **Strict** pipeline run id (`pipeline_runs.id`) | Audit Trace detail page |
| `GET /api/admin/runs/{run_id}/steps` | GlassBox (`GlassBoxService.get_pipeline_steps`) | `pipeline_steps` | Historically permissive query key; typically run id | Audit Trace and diagnostics |
| `GET /api/admin/pipeline/jurisdictions/{jurisdiction_id}/status` | Pipeline status read-model | `jurisdictions`, `pipeline_runs` | Jurisdiction id/name key, source-family scoped | Admin substrate/pipeline status panel |
| `GET /api/admin/pipeline/runs/{run_id}` | **Compatibility alias** over GlassBox | GlassBox-backed (`pipeline_runs`, `pipeline_steps`) | **Strict** pipeline run id (`pipeline_runs.id`) | No primary frontend owner; prefer Audit Trace detail for run debugging |
| `GET /api/admin/pipeline/runs/{run_id}/steps` | **Compatibility alias** over GlassBox | GlassBox-backed (`pipeline_steps`) | **Strict** pipeline run id (`pipeline_runs.id`) | No primary frontend owner; prefer Audit Trace detail for step debugging |
| `GET /api/admin/pipeline/runs/{run_id}/evidence` | GlassBox-backed evidence projection | GlassBox-backed run payload (`pipeline_runs.result`) | **Strict** pipeline run id (`pipeline_runs.id`) | No primary frontend owner; kept only as compatibility/product-evidence projection |
| `POST /api/admin/pipeline/jurisdictions/{jurisdiction_id}/refresh` | Backend accepted/manual wiring | `jurisdictions` lookup only | Jurisdiction id/name key | Admin status panel refresh action |

## Consolidation Notes

- Duplicated SQL run/steps read-shaping was removed from `/api/admin/pipeline/runs/*`.
- Compatibility endpoints now normalize their response from GlassBox outputs.
- Product-specific freshness/status remains a distinct endpoint because it is jurisdiction/source-family scoped and not part of generic run trace inspection.
- `PipelineStatusPanel` links to Audit Trace only through a backend-provided `pipeline_run_id`; it no longer renders run detail, steps, or evidence directly.
