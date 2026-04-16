---
repo_memory: true
status: active
owner: affordabot-architecture
last_verified_commit: f0a29e3b24e4d7f752614216b44d1d5d084852a2
last_verified_at: 2026-04-16T16:24:11Z
stale_if_paths:
  - backend/models/**
  - backend/services/**
  - backend/db/**
  - backend/scripts/**
  - frontend/src/services/**
  - docs/specs/**
  - docs/research/**
  - ops/**
---

# Data And Storage

Affordabot's durable value is the evidence corpus and its provenance, not the
fact that a scheduler ran. Storage decisions must preserve the data moat.

## Storage Layers

- Postgres stores source metadata, pipeline runs, step status, raw scrape rows,
  structured source rows, analysis package metadata, and frontend/admin read
  models.
- pgvector is a derived retrieval index over promoted chunks. It is not the
  source of truth for raw evidence.
- MinIO stores raw and intermediate artifacts that are too large or too binary
  for normal relational rows. A stored object is not proven until the pipeline
  can read it back by storage URI.
- Backend/domain code owns writes that need product invariants: canonical
  document key, source provenance, promotion tier, idempotency key, analysis
  package shape, and economic quality gates.
- Windmill may pass artifact handles and step outputs, but should not become
  the keeper of product identity rules.

## Scraped Evidence Lane

Minimum durable record for a scraped candidate:
- jurisdiction and source family
- query family and provider
- result URL, title, snippet, rank, score, and provider metadata
- candidate classification, portal/artifact signals, and ranker decision
- reader status, content length, substance verdict, and raw artifact URI
- canonical document key and promotion tier

Quality gates must measure top-N artifact recall, selected-candidate quality,
portal skip behavior, reader substance, fallback trigger, and staleness policy.

## Structured Evidence Lane

Minimum durable record for a structured source:
- source catalog ID and access method
- jurisdiction coverage and cadence
- raw fetch URI or API response hash
- schema version and normalization status
- canonical entity/document keys
- provenance link to the official source
- economic usefulness score and policy-domain tags

Free API/raw-file sources should be favored. A source that requires custom
browser scraping belongs in the scraped lane, not the structured lane, unless a
separate product decision approves it.

## Unified Evidence Package

A package passed to economic analysis should combine scraped and structured
items into one provenance-preserving shape:
- source inventory with freshness and confidence
- legislation/action summary and jurisdiction context
- mechanism candidates
- parameter table with source-bound values and units
- assumptions with provenance and uncertainty
- retrieval chunks and reader excerpts
- unsupported or missing claims

The package is not analysis-ready until it can be persisted, replayed, read
from admin/glass-box surfaces, and regenerated idempotently.

## Storage Proof Required

For any pipeline implementation PR, evidence should show:
- Postgres rows written for run, step, source, package, and analysis metadata
- pgvector chunks derived from promoted evidence
- MinIO objects written and read back by URI
- partial-write recovery or transaction boundaries
- replay/idempotency with the same canonical keys
- frontend/admin read model can inspect the run and package
