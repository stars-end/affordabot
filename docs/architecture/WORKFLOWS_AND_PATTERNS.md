---
repo_memory: true
status: active
owner: affordabot-architecture
last_verified_commit: f0a29e3b24e4d7f752614216b44d1d5d084852a2
last_verified_at: 2026-04-16T16:24:11Z
stale_if_paths:
  - ops/**
  - backend/services/pipeline/**
  - backend/api/**
  - backend/routes/**
  - backend/scripts/verification/**
  - frontend/src/**
  - .github/workflows/**
---

# Workflows And Patterns

## Boundary Rule

Use Windmill maximally for orchestration, not for product logic.

Windmill owns:
- schedules
- retries and backoff
- branch/for-loop/fanout control
- job visibility
- manual reruns and approvals where useful
- passing handles between coarse steps

Backend/domain code owns:
- provider contracts
- ranker and reader quality rules
- canonical document identity
- storage writes and idempotency
- promotion tiers
- evidence package contract
- economic analysis gates
- frontend/admin read models

## Preferred Flow Shape

The preferred pipeline is a Windmill flow that calls coarse domain commands:
search/materialize, rank/read, freshness gate, persist/promote/index, package,
analyze, and publish/admin read model. Avoid step-by-step business logic in
Windmill scripts.

Windmill does not provide true resume-from-step for arbitrary Python state.
Design reruns as full-flow retries where backend commands deduplicate by
idempotency keys and canonical document identity.

## Provider Strategy

- Private SearXNG: primary low-cost search candidate after metric gates pass.
- Tavily: hot fallback for higher quality/managed search when private search
  quality is weak.
- Exa: bakeoff/evaluation lane unless cost/quality evidence changes.
- Z.ai direct reader: canonical reader path while it continues to perform well.
- Z.ai web search: deprecated primary path; keep only a scheduled/manual
  health check for recovery evidence.
- Z.ai LLM analysis: still canonical for analysis unless a later quality review
  changes the model boundary.

## Verification Pattern

Every meaningful pipeline POC should produce machine-readable artifacts plus a
human audit summary:
- provider/query metrics
- selected candidates and skipped portals
- reader output with substance verdict
- persisted storage handles
- chunk/index status
- evidence package JSON
- economic analysis output
- unsupported-claim list
- admin/glass-box visibility

Do not call a POC successful only because a flow completed. The acceptance
question is whether the resulting package is good enough for quantitative
economic analysis.

## Frontend Pattern

Frontend is a display and review layer. It should read backend/admin APIs and
show status, provenance, evidence packages, and final analysis. It should not
own search, scraping, storage, or economic inference.

Before adding a new admin route or status panel, check:
- `backend/services/glass_box.py`
- existing admin API routes
- `frontend/src/services/adminService.ts`
- existing admin components
