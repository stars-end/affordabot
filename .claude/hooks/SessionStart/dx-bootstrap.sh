#!/usr/bin/env bash
set -euo pipefail

# Repo-local SessionStart hook for Claude Code.
# Keep this as a thin adapter: the canonical logic lives in agent-skills.

AGENTS_ROOT="${AGENTS_ROOT:-$HOME/.agent/skills}"
if [[ ! -d "$AGENTS_ROOT" ]]; then
  AGENTS_ROOT="$HOME/agent-skills"
fi

exec "$AGENTS_ROOT/session-start-hooks/dx-bootstrap.sh"

