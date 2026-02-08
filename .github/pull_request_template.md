## Summary

Describe the change and link the Beads issue.

## Feature Metadata

**Required fields:**
- Feature-Key: bd-xyz (Beads issue ID - verify: `bd show bd-xyz`)
- Beads spec: Read from stars-end/bd: `bd show bd-xyz`

**Optional fields:**
- Tests path: tests/features/bd-xyz/
- Scripts path: scripts/bd-xyz/

**Note:** Feature-Key MUST be a Beads issue ID (bd-xyz format). All Beads issues live in [stars-end/bd](https://github.com/stars-end/bd) (the single source of truth).

## Beads-Only Workflow

- [ ] Beads issue created in stars-end/bd (`bd create "Title" --type feature --priority 1`)
- [ ] Feature-Key matches Beads ID (bd-xyz format) in commit message
- [ ] Work committed via sync-feature-branch skill (say "commit my work")
- [ ] CI checks passing

**Workflow:**
```bash
# Create Beads issue (in stars-end/bd)
bd create "Feature title" --type feature --priority 1

# Work on feature...

# Commit work (say "commit my work" - agent auto-invokes skill)
# At least one commit must include: Feature-Key: bd-xyz

# Create PR (say "create PR" - agent auto-invokes skill)

# Track progress
bd show bd-xyz
```

## Important Notes

- **Per Beads-only product specs**, we no longer create `docs/bd-*.md` stubs in product repos.
- The authoritative spec lives in [stars-end/bd](https://github.com/stars-end/bd/blob/master/.beads/issues.jsonl).
- Use `bd show bd-xyz` to read the full spec.
- DO NOT create `.beads/` directories in product repos.

Guides: see `AGENTS.md` (Start Here).
