# TECH_PLAN: llm-common Integration for Affordabot

**Epic**: affordabot-ycs  
**Priority**: P2  
**Status**: Planning

## Goal

Migrate Affordabot from its local `packages/llm-common` copy to the canonical shared `llm-common` library (`~/llm-common`), updating the legislation analysis pipeline and admin flows while keeping behavior intact.

## Background

Affordabot currently has a local copy of `llm-common` in `packages/llm-common`. The canonical version lives in `~/llm-common` and is used by other projects (Prime-Radiant-AI). We need to:
1. Add `../llm-common` as a dependency
2. Switch imports to use the canonical version
3. Remove the local copy once everything passes

## Dependencies

- **Canonical llm-common**: `~/llm-common` (must exist and be up-to-date)
- **Affected files**:
  - `backend/services/llm/orchestrator.py`
  - `backend/routers/admin.py`
  - Any other files importing from `packages/llm-common`

## Implementation Phases

### Phase 1: Dependency Setup
- [ ] Verify `~/llm-common` exists and is current
- [ ] Add `../llm-common` to `backend/requirements.txt` or `pyproject.toml`
- [ ] Update Python path configuration if needed

### Phase 2: Import Migration
- [ ] Find all imports from `packages.llm-common` or `llm_common`
- [ ] Switch `backend/services/llm/orchestrator.py` to canonical `llm_common`
- [ ] Switch `backend/routers/admin.py` to canonical `llm_common`
- [ ] Update any other affected files

### Phase 3: Testing & Cleanup
- [ ] Run tests to verify behavior unchanged
- [ ] Test legislation analysis pipeline end-to-end
- [ ] Test admin flows (model registry, prompts)
- [ ] Remove `packages/llm-common` directory
- [ ] Update documentation

## Verification

- [ ] All tests pass
- [ ] Legislation analysis works identically
- [ ] Admin dashboard functions correctly
- [ ] No references to `packages/llm-common` remain
- [ ] Railway deployment succeeds

## Risks

- **Import path changes**: May break existing code if not thorough
- **Version mismatch**: Canonical llm-common may have diverged
- **Railway deployment**: Need to ensure `../llm-common` is accessible

## Success Criteria

- ✅ Affordabot uses canonical `~/llm-common`
- ✅ All functionality preserved
- ✅ Local `packages/llm-common` removed
- ✅ Tests pass
- ✅ Deployment works
