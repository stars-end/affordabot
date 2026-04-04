# Admin Console User Stories

Executable repo-local stories for the affordabot admin surface.

The current founder-critical executable pack is the substrate viewer MVP:

- `substrate_run_list`
- `substrate_failure_buckets`
- `substrate_raw_row_detail`

These stories are the canonical product-truth checks for the merged substrate explorer because they cover:

- run list
- failure buckets
- raw row detail

Legacy broader admin-console stories remain in this directory, but they are no longer the only source of executable truth for founder debugging flows.

## Stories

| Story | Description | Priority |
|-------|-------------|----------|
| [substrate_run_list](substrate_run_list.yml) | Open substrate tab and verify run-first debugging shell | P0 |
| [substrate_failure_buckets](substrate_failure_buckets.yml) | Verify grouped failure debugging surface | P0 |
| [substrate_raw_row_detail](substrate_raw_row_detail.yml) | Verify row-level inspection surface | P0 |
| [admin_dashboard_overview](admin_dashboard_overview.yml) | View dashboard metrics and navigation | P0 |
| [discovery_search_flow](discovery_search_flow.yml) | Search for legislation sources | P0 |
| [source_management](source_management.yml) | View and manage data sources | P0 |
| [jurisdiction_detail_view](jurisdiction_detail_view.yml) | View jurisdiction with bills | P0 |
| [prompt_configuration](prompt_configuration.yml) | View and edit LLM prompts | P0 |
| [review_queue_workflow](review_queue_workflow.yml) | Review generated analyses | P0 |
| [full_admin_e2e](full_admin_e2e.yml) | Complete E2E admin workflow | P0 |

## Running Stories

```bash
# Run all admin UISmoke stories
make verify-stories

# Run the deterministic substrate gate
make verify-gate

# Run the broader nightly pack
make verify-nightly

# Run stories for PR verification
make verify-pr PR=185
```

## Story Format

Each story YAML contains:
- `id`: Unique identifier
- `persona`: Who is using this flow
- `priority`: P0/P1/P2
- `timeout_seconds`: Max time for story
- `goals`: What the story validates
- `start_url`: Entry point
- `steps`: Sequential actions with verification points
- `metadata`: Tags and duration estimate
