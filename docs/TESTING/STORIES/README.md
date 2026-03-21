# Admin Console User Stories

Test stories for verifying Affordabot admin and account flows.

## Execution Engine Policy

- **Default**: run Plaid sandbox stories with **Playwright**.
- **Conditional**: run Plaid sandbox stories via `uismoke` only when the full flow is deterministic end to end in the current environment (stable selectors, fixed sandbox behavior, predictable post-link render).
- The iframe proof-of-concept in [`../POC/poc-08-iframe.yml`](../POC/poc-08-iframe.yml) is not the production story contract.

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
| [plaid_sandbox_happy_path](plaid_sandbox_happy_path.yml) | Link sandbox account successfully from settings | P1 |
| [plaid_sandbox_login_failure](plaid_sandbox_login_failure.yml) | Invalid credentials fail safely with no linked account | P1 |

## Running Stories

```bash
# Run all admin stories via verify-dev
make verify-dev

# Run specific story
make verify-story STORY=admin_dashboard_overview

# Run stories for PR verification
make verify-pr PR=185

# Plaid sandbox stories (default engine: Playwright)
# Execute the concrete Plaid happy/failure automation with Playwright specs.
# Use uismoke only when deterministic end-to-end conditions are met.
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
