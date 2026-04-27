---
repo_memory: true
status: active
owner: affordabot-architecture
last_verified_commit: f0a29e3b24e4d7f752614216b44d1d5d084852a2
last_verified_at: 2026-04-16T16:24:11Z
stale_if_paths:
  - backend/**
  - frontend/**
  - ops/**
  - docs/specs/**
  - docs/research/**
  - contracts/**
---

# Architecture Docs Index

This directory contains the repo-owned brownfield maps for Affordabot. These
maps are the first source to read before changing the pipeline, storage model,
or analysis surface.

- `BROWNFIELD_MAP.md`: current codebase map from source discovery through
  backend commands, storage, analysis, and frontend/admin read models.
- `DATA_AND_STORAGE.md`: product data moat, Postgres/pgvector/MinIO ownership,
  and how scraped plus structured evidence should be persisted.
- `WORKFLOWS_AND_PATTERNS.md`: Windmill/backend/frontend/storage boundaries and
  operational workflow patterns.
- `ECONOMIC_ANALYSIS_PIPELINE.md`: economic analysis path, evidence packaging
  expectations, and known gaps before decision-grade analysis.

These files are maintained by the repo-memory freshness contract. Beads memory
is a pointer and decision log; these maps are the repo-owned source of truth for
brownfield orientation.

## Current Spec Locks

- `docs/specs/2026-04-27-data-moat-cycle-review-architecture.md`: review-first
  contract for 10-20 structured/scraped data-moat cycles, including the
  `data_moat_cycle_report` artifact, Windmill evidence boundary, Beads graph,
  and HITL review gate before implementation dispatch.
- `docs/reviews/2026-04-27-data-moat-original-workflow-pain-point-review.md`:
  pain-point review of the original structured-source and SearXNG/scraped
  workflows, including missed blockers and the revised implementation priority.
- `docs/reviews/2026-04-27-data-moat-windmill-ratchet-planning-review.md`:
  follow-up planning review focused on avoiding another 30+ low-progress
  iteration cycles by using Windmill as the runtime laboratory and enforcing a
  per-cell progress ratchet for structured and unstructured paths.
