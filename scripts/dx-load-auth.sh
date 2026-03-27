#!/usr/bin/env bash
# scripts/dx-load-auth.sh
# Thin affordabot wrapper over agent-skills shared auth contract.
#
# Usage:
#   ./scripts/dx-load-auth.sh -- <command> [args...]
#   ./scripts/dx-load-auth.sh --check
#
# Loads OP_SERVICE_ACCOUNT_TOKEN + RAILWAY_API_TOKEN, then executes command.

set -euo pipefail

AGENT_SKILLS_DIR="${AGENT_SKILLS_DIR:-$HOME/agent-skills}"
AUTH_LOADER="$AGENT_SKILLS_DIR/scripts/dx-load-railway-auth.sh"

if [[ ! -x "$AUTH_LOADER" ]]; then
  echo "dx-load-auth: agent-skills auth contract not found at $AUTH_LOADER" >&2
  echo "Set AGENT_SKILLS_DIR to point to your agent-skills checkout." >&2
  exit 2
fi

if [[ $# -eq 0 ]]; then
  echo "Usage: $0 -- <command> [args...]" >&2
  echo "       $0 --check" >&2
  exit 2
fi

exec "$AUTH_LOADER" "$@"
