---
repo_memory: true
status: active
owner: affordabot-architecture
last_verified_commit: f0a29e3b24e4d7f752614216b44d1d5d084852a2
last_verified_at: 2026-04-16T16:24:11Z
stale_if_paths:
  - backend/services/**
  - backend/agents/**
  - backend/prompts/**
  - llm_common/**
  - docs/specs/**
  - docs/research/**
  - frontend/src/**
---

# Economic Analysis Pipeline

The final product is not a scrape report. It is a source-grounded economic
analysis of how policy affects cost of living. The evidence pipeline exists to
make that analysis trustworthy.

## Required Analysis Inputs

An analysis-ready package should include:
- policy action and jurisdiction context
- source-bound facts from scraped and structured evidence
- mechanism hypotheses
- parameter table with units, values, source links, and confidence
- secondary research needs
- uncertainty and sensitivity ranges
- explicit unsupported or missing claims

For indirect costs, the package must support a mechanism chain. Example class:
a land-use or parking rule may affect construction cost, which may affect unit
price or rents, which may affect household cost burden. The system should not
pretend the raw meeting agenda alone is enough.

## Secondary Research

The economic analysis agent may need a second research pass. That pass should
be explicit and auditable:
- query family and provider
- source quality classification
- reader output
- parameters extracted
- citations retained
- missing evidence called out

Do not collapse this into the first local-government source-gathering pass.
The two passes answer different questions: what happened locally, and what
economic evidence supports the cost mechanism.

## Quality Rubric

A final analysis should be rejected or downgraded when it lacks:
- mechanism graph from policy action to household/business impact
- parameter table with source-bound assumptions
- quantitative estimate or a justified refusal to estimate
- uncertainty/sensitivity range
- citations for every material claim
- distinction between direct fiscal cost, compliance cost, housing supply cost,
  consumer price effect, and distributional impact

## Existing Evidence To Reuse

Before redesigning this area, inspect:
- `docs/specs/2026-03-19-affordabot-california-pipeline-truth-remediation.md`
- `docs/research/`
- backend analysis, prompt, agent, and verification code under `backend/`

The known risk is rediscovering existing economic-analysis work while focusing
too narrowly on search quality. Start with code and docs map review, then run
POCs that connect evidence quality to analysis quality.
