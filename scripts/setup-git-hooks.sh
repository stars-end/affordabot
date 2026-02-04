#!/bin/zsh
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
# FIX: Robustly find hooks directory even in worktrees
HOOKS_DIR="$(git rev-parse --git-path hooks)"

echo "Installing git hooks for $(basename "$REPO_ROOT")..."

# Pre-commit hook (FIX 6: robust worktree detection)
cat > "$HOOKS_DIR/pre-commit" <<'HOOK'
#!/bin/zsh
set -euo pipefail

CANONICAL_REPOS=("agent-skills" "prime-radiant-ai" "affordabot" "llm-common")
REPO_NAME=$(basename "$(git rev-parse --show-toplevel)")

if [[ " ${CANONICAL_REPOS[@]} " =~ " ${REPO_NAME} " ]]; then
    # FIX 6: Robust worktree detection
    GITDIR_PATH="$(git rev-parse --git-dir)"
    
    # If .git is a file (worktree), read the actual gitdir path
    if [[ -f "$GITDIR_PATH" ]]; then
        GITDIR_PATH="$(sed -n 's/^gitdir: //p' "$GITDIR_PATH")"
    fi
    
    # Check if path contains /worktrees/
    if [[ "$GITDIR_PATH" != *"/worktrees/"* ]]; then
        echo ""
        echo "❌ Cannot commit to canonical repo: $REPO_NAME"
        echo ""
        echo "Canonical repos are read-mostly. Use worktrees:"
        echo ""
        echo "  1. Create worktree: dx-worktree create bd-xxxx $REPO_NAME"
        echo "  2. Navigate: cd /tmp/agents/bd-xxxx/$REPO_NAME"
        echo "  3. Commit there (safe)"
        echo ""
        exit 1
    fi
fi

exit 0
HOOK

chmod +x "$HOOKS_DIR/pre-commit"

echo "✅ Git hooks installed"
echo ""
echo "Test it:"
echo "  1. Try to commit in canonical repo (should block)"
echo "  2. Create worktree: dx-worktree create bd-test $(basename "$REPO_ROOT")"
echo "  3. Commit in worktree (should succeed)"
