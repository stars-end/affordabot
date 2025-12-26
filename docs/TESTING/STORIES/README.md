# Admin Console User Stories

Test stories for verifying the Affordabot admin console using UISmokeAgent with GLM-4.6V visual analysis.

## Stories

| Story | Description | Priority |
|-------|-------------|----------|
| [admin_dashboard_overview](admin_dashboard_overview.yml) | View dashboard metrics and navigation | P0 |
| [discovery_search_flow](discovery_search_flow.yml) | Search for legislation sources | P0 |
| [source_management](source_management.yml) | View and manage data sources | P0 |
| [jurisdiction_detail_view](jurisdiction_detail_view.yml) | View jurisdiction with bills | P0 |
| [prompt_configuration](prompt_configuration.yml) | View and edit LLM prompts | P0 |
| [review_queue_workflow](review_queue_workflow.yml) | Review generated analyses | P0 |
| [full_admin_e2e](full_admin_e2e.yml) | Complete E2E admin workflow | P0 |

## Running Stories

```bash
# Run all admin stories via verify-dev
make verify-dev

# Run specific story
make verify-story STORY=admin_dashboard_overview

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
