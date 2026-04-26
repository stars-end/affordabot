# Offline Worklog: Windmill Storage Boundary Bakeoff

Tracking key: `offline-20260412-windmill-storage-bakeoff`
Started: 2026-04-12
Repo: affordabot
Beads: local Beads mutations are broken; reconcile after infra repair.

## Goal

Gather enough implementation evidence to recommend a final Windmill/affordabot/storage boundary for the San Jose meeting-minutes pipeline.

## Current Hypotheses

- Windmill should own orchestration: DAG, schedules, retries, branch decisions, run logs, operator controls.
- Affordabot may shrink substantially, but some domain boundary may still be needed for canonical document identity, idempotency, provenance, and analysis sufficiency.
- Direct Windmill storage writes are viable only if they do not turn Windmill scripts into the hidden product backend.

## Agent Assignments

- Path A: Windmill-heavy direct storage POC.
- Path B: Windmill orchestration plus affordabot domain-boundary POC.

## Reconcile Later

- Create or update the real Beads issue once infra restores reliable Beads mutations.
- Link the final PR URL(s), merge commit(s), and architecture recommendation.
- Close the tracker item if merged.

