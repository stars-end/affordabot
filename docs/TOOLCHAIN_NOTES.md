# Toolchain Notes

## Poetry Lockfile Generation Fix (affordabot-hwk)

**Date:** 2025-12-09  
**Issue:** Poetry lockfile generation failing with dulwich errors on git dependencies

### Problem

When using git-based dependencies in `backend/pyproject.toml` (e.g., `llm-common`), both `poetry lock` and `poetry install` would fail with:

```
AssertionError

at /home/linuxbrew/.linuxbrew/Cellar/poetry/2.2.1/libexec/lib/python3.14/site-packages/dulwich/repo.py:386 in get_parents
     382│ 
     383│         # Fallback to reading the commit object
     384│         if commit is None:
     385│             obj = self.store[commit_id]
    →  386│             assert isinstance(obj, Commit)
     387│             commit = obj
     388│         return commit.parents
```

### Root Cause

Poetry 2.2.1 by default uses **dulwich** (a pure-Python git implementation) for VCS operations. Dulwich has a bug when handling certain git objects (tags, commits), causing the assertion failure when trying to resolve git dependencies.

### Solution

Enable Poetry's system git client to use the system's native git (v2.43.0) instead of dulwich:

```bash
poetry config system-git-client true
```

This configuration is **persistent** and stored in Poetry's global config (`~/.config/pypoetry/config.toml`).

### Verification

After applying the fix:

```bash
cd backend
poetry lock    # Should complete without errors
poetry install # Should install git dependencies correctly
```

### Environment Details

- **Poetry:** 2.2.1 (installed via Homebrew)
- **Git:** 2.43.0
- **Python:** 3.14.1
- **OS:** Linux (Ubuntu/Debian-based)

### Future Guidance

If you encounter similar dulwich errors:

1. Check Poetry's git client configuration:
   ```bash
   poetry config --list | grep system-git
   ```

2. If `system-git-client = false`, enable it:
   ```bash
   poetry config system-git-client true
   ```

3. Clear Poetry's cache if needed:
   ```bash
   rm -rf ~/.cache/pypoetry/cache
   ```

4. Retry the operation:
   ```bash
   poetry lock && poetry install
   ```

### Related Issues

- **Beads Issue:** affordabot-hwk
- **PR:** #45
- **Upstream Bug:** Dulwich assertion error with git tags/commits (Poetry 2.2.1)

### Alternative Solutions Considered

1. **Downgrade Poetry** - Not recommended; 2.2.1 has other improvements
2. **Use path dependencies** - Doesn't work with Railway's "Isolated Monorepo" pattern
3. **Reinstall Poetry** - Unnecessary; configuration change is sufficient

The `system-git-client` approach is the cleanest solution and aligns with Poetry's recommended configuration for production environments.
