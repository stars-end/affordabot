# Scrape + Structured Source Integration POC

Date: 2026-04-14
Feature key: `bd-2agbe.11`

## Goal

Prove a single backend-owned envelope contract that merges:

1. structured source lane:
   - `legistar`
   - `leginfo`
   - `ckan`
   - `arcgis`
2. scrape/search lane:
   - `private_searxng`
   - `tavily`
   - `exa`

## Why This POC Exists

This addresses two core concerns directly:

- scraping lane role and quality posture (`private_searxng` primary, Tavily fallback, Exa eval-only)
- integration of scraped + structured candidates into one evidence handoff contract

It also explicitly maps `schemas.analysis.ImpactMode` to
`schemas.economic_evidence.MechanismFamily` and validates ready evidence against
`schemas.economic_evidence.EvidenceCard` when imports are available.

## Outputs

- [scrape_structured_integration_report.json](/tmp/agents/bd-2agbe.1/affordabot/docs/poc/source-integration/artifacts/scrape_structured_integration_report.json)
- [scrape_structured_integration_report.md](/tmp/agents/bd-2agbe.1/affordabot/docs/poc/source-integration/artifacts/scrape_structured_integration_report.md)

## Runbook

```bash
cd /tmp/agents/bd-2agbe.1/affordabot
python3 backend/scripts/verification/verify_scrape_structured_integration_poc.py --mode replay --self-check
```

If `pytest` is unavailable, run direct test execution via Python import loader
for:

- [test_scrape_structured_integration_poc.py](/tmp/agents/bd-2agbe.1/affordabot/backend/tests/verification/test_scrape_structured_integration_poc.py)

## Current Quality Boundary

This verifier proves contract integration and fail-closed classification. It does
not claim all envelopes are quantified-ready; only `evidence_card_ready` items
with a non-null mechanism mapping are marked `economic_handoff_ready=true`.
