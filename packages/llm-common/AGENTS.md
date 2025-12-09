# Agent Guidelines for llm-common

This document provides guidelines for AI coding agents (Claude Code, Codex CLI, Antigravity, etc.) working on the llm-common repository.

## Repository Context

**llm-common** is a shared LLM framework library for Affordabot and Prime Radiant projects. It provides:

- Core abstractions: `LLMClient`, `RetrievalBackend`
- Provider implementations: z.ai, OpenRouter
- Retrieval backends: Supabase pgvector
- Web search with caching
- Type-safe Pydantic models

**Status**: Stable (v0.3.0) - Paused for downstream integration validation

## Development Workflow

### Current Phase: Integration & Validation

llm-common is in a **validation phase**:
- ✅ Core features complete and tested
- ⏸️ New features paused until downstream integration
- 🎯 Focus on bug fixes and documentation improvements
- 📊 Waiting for Affordabot and Prime Radiant usage metrics

See `DEVELOPMENT_STATUS.md` for detailed pause rationale.

### When to Work on llm-common

Work on llm-common when:
1. **Bugs discovered** during downstream integration
2. **Documentation gaps** identified by downstream developers
3. **Scale limits reached** (see DEVELOPMENT_STATUS.md criteria)
4. **Explicit feature requests** from downstream teams with proven need

Do NOT:
- Add speculative features without downstream validation
- Implement helpers before patterns emerge
- Add backends without demonstrated need

### Testing Requirements

- **All changes must maintain 100% test pass rate** (currently 66/66)
- Add tests for new features
- Run full test suite: `poetry run pytest -v`
- Verify public API exports: `poetry run python -c "from llm_common import ..."`

### Documentation Requirements

- Update relevant documentation in `docs/`
- Add examples to `examples/` for new features
- Update `IMPLEMENTATION_STATUS.md` for completed work
- Maintain `DEVELOPMENT_STATUS.md` for status changes

## Commit Format (Required Trailers)

All commits must include these trailers:

```
Feature-Key: {issue-id}
Agent: <environment-id>
Role: <role-name>
```

### Feature-Key Trailer

**Important**: The `Feature-Key` must match your repository's configured issue ID prefix.

The format is `{prefix}-{identifier}` where:
- `{prefix}` is your repository's issue prefix (e.g., `bd`, `affordabot`, `prime-radiant`)
- `{identifier}` is the issue number or slug

**Examples by repository:**
- **Affordabot**: `affordabot-rdx`, `affordabot-123`
- **Prime Radiant**: `prime-radiant-svse`, `prime-radiant-456`
- **llm-common** (via primary repo): `bd-svse`, `bd-8vuj`

**Multi-repo projects**: When working on llm-common (a secondary repo), use the Feature-Key from the primary repository (Affordabot or Prime Radiant) that initiated the work.

### Agent Trailer Policy

The `Agent` trailer identifies your execution environment:

- **Agent: claude-code** - Claude Code (CC web interface)
- **Agent: codex-cli** - Codex CLI (terminal-based)
- **Agent: antigravity** - Antigravity IDE

### Role Trailer

Keep your active role (examples):
- **Role: backend-engineer**
- **Role: frontend-engineer**
- **Role: devops-engineer**
- **Role: documentation-writer**

## Commit Message Examples

### Bug Fix
```
fix: Handle empty embedding vectors in pgvector backend

Return empty results instead of raising when embedding is None.

Feature-Key: {issue-id}
Agent: claude-code
Role: backend-engineer
```

**Example with actual IDs:**
- Affordabot: `Feature-Key: affordabot-rdx`
- Prime Radiant: `Feature-Key: prime-radiant-svse`
- llm-common (via primary): `Feature-Key: bd-svse`

### Documentation
```
docs: Clarify pgvector RPC function setup

Add troubleshooting section for common RPC errors.

Feature-Key: {issue-id}
Agent: codex-cli
Role: documentation-writer
```

### Feature (During Active Development)
```
feat: Add Qdrant backend for high-scale retrieval

Implements RetrievalBackend for Qdrant cloud service.
Triggered by pgvector hitting scale limits in production.

Feature-Key: {issue-id}
Agent: antigravity
Role: backend-engineer
```

## Multi-Repo Context

llm-common is a **secondary repository** in the multi-repo agent pattern:

**Primary Repos** (drive development):
- Affordabot
- Prime Radiant

**Secondary Repos** (driven by primary):
- llm-common (this repo)

### No .claude/ or .beads/ in llm-common

This repository does NOT contain:
- `.claude/` directory
- `.beads/` directory

Work tracking happens in the primary repositories (Affordabot, Prime Radiant) using their Feature-Keys.

### Git Submodule Usage

llm-common is integrated via git submodules:
```bash
# In Affordabot or Prime Radiant
git submodule add git@github.com:stars-end/llm-common.git packages/llm-common
cd packages/llm-common
git checkout v0.3.0  # Pin to stable release
```

## Development Principles

### 1. Stability First
- No breaking changes without major version bump
- Maintain backward compatibility
- Document deprecations before removal

### 2. Evidence-Based Features
- Wait for downstream usage patterns
- Implement based on proven needs
- Avoid premature abstraction

### 3. Minimal Dependencies
- Keep optional dependencies optional
- No hard dependencies on Supabase, OpenAI, etc.
- Users choose their own backends and providers

### 4. Comprehensive Testing
- 100% test pass rate required
- Mock external services
- Test all public API exports

### 5. Clear Documentation
- Every public API documented
- Working examples for all features
- Production setup guides with SQL/config

## Common Tasks

### Running Tests
```bash
poetry install
poetry run pytest -v
poetry run pytest tests/retrieval/  # Specific module
```

### Type Checking
```bash
poetry run mypy llm_common
```

### Code Formatting
```bash
poetry run black llm_common tests
poetry run ruff check llm_common
```

### Adding a New Backend

Only add if:
1. Downstream project has proven need
2. Existing backends insufficient
3. Clear production use case

Steps:
1. Create `llm_common/retrieval/backends/your_backend.py`
2. Implement `RetrievalBackend` interface
3. Add comprehensive tests (15+ tests)
4. Update exports in `__init__.py` files
5. Add example to `examples/retrieval_usage.py`
6. Document in `docs/LLM_COMMON_WORKSTREAMS/INTEGRATION_AND_RETRIEVAL.md`

### Bug Fix Process

1. Create feature branch: `feature-{issue-id}-bug-description`
2. Add failing test demonstrating bug
3. Fix bug and verify test passes
4. Update documentation if needed
5. Commit with proper trailers
6. Open PR referencing issue (if exists)

**Branch naming examples:**
- Affordabot work: `feature-affordabot-rdx-fix-validation`
- Prime Radiant work: `feature-prime-radiant-svse-add-caching`
- llm-common via primary: `feature-bd-svse-pgvector-backend`

## Version Strategy

**Semantic Versioning**: MAJOR.MINOR.PATCH

- **PATCH** (0.3.1): Bug fixes, documentation updates
- **MINOR** (0.4.0): New features, backward compatible
- **MAJOR** (1.0.0): Breaking changes, API stability commitment

Current: **v0.3.0** - First backend implementation milestone

## Resources

- **Current Status**: `DEVELOPMENT_STATUS.md`
- **Implementation History**: `IMPLEMENTATION_STATUS.md`
- **Integration Guide**: `docs/LLM_COMMON_WORKSTREAMS/INTEGRATION_AND_RETRIEVAL.md`
- **Examples**: `examples/` directory
- **Tests**: `tests/` directory

## Questions?

For questions about:
- **llm-common features**: Check documentation first
- **Bug reports**: Open GitHub issue with reproduction steps
- **Feature requests**: Discuss with downstream teams first
- **Integration help**: See downstream repo documentation

---

**Remember**: llm-common is a **shared library** driven by downstream needs. Wait for validation before adding new features.
