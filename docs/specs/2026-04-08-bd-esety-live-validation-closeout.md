# 2026-04-08 Live Validation Closeout (bd-esety)

## Scope

Take over `bd-esety` in existing worktree and finish non-strategic product/runtime fixes, then rerun bounded live discovery validation against:

- San Jose
- Milpitas
- Alameda County

Runtime context (non-interactive Railway):

- Project: `1ed20f8a-aeb7-4de6-a02c-8851fff50d4e`
- Environment: `dev`
- Service: `backend`

## Product Fixes Landed

1. `expected str, got UUID` source dedupe/insert path:
   - normalize `jurisdiction_id` to string once per jurisdiction in discovery cron.
   - ensure `create_source` serializes `metadata` dict/list to JSON before insert.
2. `admin_tasks` constraint mismatch:
   - switched discovery task type from `discovery` to `research`.
3. Fallback hardening when browser/runtime is missing:
   - add DuckDuckGo HTML (non-Playwright) fallback.
   - disable Playwright fallback after launch failure instead of repeated hard-fail.
4. Malformed classifier structured-output hardening:
   - detect malformed `DiscoveryResponse` tool output errors.
   - apply deterministic URL heuristic fallback only for malformed-output cases.
   - keep non-malformed runtime errors (for example `429`) as explicit error path.

## Validation Run Notes

Focused tests (local worktree) passed:

- `pytest -q backend/tests/services/discovery/test_discovery.py backend/tests/cron/test_run_discovery.py backend/tests/test_postgres_client.py::test_create_source_serializes_metadata_dict backend/tests/test_discovery_services.py -k "discover_url or run_discovery or create_source_serializes_metadata_dict or search_discovery"`
- Result: `15 passed, 5 deselected`

Live bounded reruns were executed with explicit Railway context. Observed repeatedly:

- Accepted/duplicate/rejected paths are now active (for example: added candidate, duplicate skips, classifier rejects).
- UUID dedupe/insert crash is no longer observed.
- `task_type` DB constraint failure is no longer observed.
- Primary web search still fails with DNS resolution:
  - `[zai] Search failed: [Errno 8] nodename nor servname provided, or not known`
- Classifier/query generation calls intermittently hard-rate-limit:
  - `Error code: 429 - {'error': {'code': '1302', 'message': 'Rate limit reached for requests'}}`

Observed task IDs from this session:

- `9e4178c5-494a-4082-afee-9ef03ec25b1f`
- `7136bc3f-a776-4386-b5fc-312a143cc048`
- `8ba6e958-6070-48e0-9f12-6971a2cd1644`
- `f76e8a44-327d-4943-b1fd-6c14a2f9ea1c`
- `bc5eb3c8-02ef-4856-b061-7649418eacab`

## Final Classification

`bd-esety` product-side blockers are fixed in code and covered by tests.

Remaining instability is external/runtime truth:

1. upstream search DNS failures (`z.ai` search endpoint path),
2. upstream `429` rate limiting on chat/classifier/query-generation calls.

Given these external conditions, bounded live reruns cannot produce stable, complete end-to-end result metrics in this window despite product fixes.

Tool routing exception: `llm-tldr`/`serena` MCP surfaces were unavailable in this runtime (`list_mcp_resources` and templates returned empty), so shell fallback was used.
