# affordabot-bok6.10 — Persona verification stories + visual runner

## Context
PR `#202` introduces persona verification stories and a visual story runner, but it currently:
- lacks Beads linkage / Feature-Key
- fails CI (ruff F401 unused imports in `scripts/verification/visual_story_runner.py`)

## Plan
1. Fix ruff errors (remove unused imports, run `ruff check .`).
2. Amend commit message to include `Feature-Key: affordabot-bok6.10`.
3. Link PR `#202` to this issue (`scripts/bd-link-pr 202`).
4. Re-run CI until green, then merge.

## Acceptance Criteria
- PR `#202` passes `Backend Lint & Test`.
- PR is correctly linked to `affordabot-bok6.10` and has Feature-Key trailer.

