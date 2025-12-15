#!/usr/bin/env bash
set -euo pipefail

# Install repo-local git hooks from .githooks

ROOT_DIR=$(git rev-parse --show-toplevel 2>/dev/null || echo "")
if [ -z "$ROOT_DIR" ]; then
  echo "Not in a git repository" >&2; exit 1
fi

if [ ! -d "$ROOT_DIR/.githooks" ]; then
  mkdir -p "$ROOT_DIR/.githooks"
fi

git config core.hooksPath .githooks
git config merge.jsonl.name "Custom merge driver for JSONL files"
git config merge.jsonl.driver "bd merge %A %O %B %P"
chmod -R +x .githooks || true
echo "✅ Git hooks installed"
echo "   - Using hooksPath: .githooks"
echo "   - Blocks pushes to master"
echo "   - Requires 'Feature-Key:' trailer on commits (unless release/merge)"
echo "   - Nags if /sync-i guardrails stamp is missing"
echo "   - Hooks will warn on staging .command-proof or workflow edits on scenario branches"

