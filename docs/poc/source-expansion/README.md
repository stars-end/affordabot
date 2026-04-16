# Source Expansion/API-Key Readiness POC

Date: 2026-04-14  
Feature key: `bd-2agbe.12`

This POC answers two questions:

1. Which free API/raw-file source families should expand next (breadth)?
2. Which Railway variables/API keys are required now vs optional/deferred?

Scope constraints:

- No raw `op` secret reads.
- No Tavily/Exa quota use.
- No Socrata signup in this wave.
- Keep provider lanes explicit:
  - `structured`
  - `scrape_reader`
  - `search_provider`
  - `contextual`

## Verifier

- Script:
  [verify_source_expansion_api_key_matrix.py](/tmp/agents/bd-2agbe.1/affordabot/backend/scripts/verification/verify_source_expansion_api_key_matrix.py)
- Tests:
  [test_source_expansion_api_key_matrix.py](/tmp/agents/bd-2agbe.1/affordabot/backend/tests/verification/test_source_expansion_api_key_matrix.py)

## Artifacts

- JSON:
  [source_expansion_api_key_matrix.json](/tmp/agents/bd-2agbe.1/affordabot/docs/poc/source-expansion/artifacts/source_expansion_api_key_matrix.json)
- Markdown:
  [source_expansion_api_key_matrix.md](/tmp/agents/bd-2agbe.1/affordabot/docs/poc/source-expansion/artifacts/source_expansion_api_key_matrix.md)

## Run

```bash
cd /tmp/agents/bd-2agbe.1/affordabot
python3 backend/scripts/verification/verify_source_expansion_api_key_matrix.py --self-check
```

## Interpretation Guardrail

Breadth is useful only when a source yields policy facts or linked artifacts that
improve evidence cards and deterministic economic quantification. Source count by
itself is not a quality signal.
