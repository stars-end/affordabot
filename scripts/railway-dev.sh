#!/bin/bash
# scripts/railway-dev.sh
# Wrapper for Railway dev mode using the shared agent-skills contract.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if ! command -v railway >/dev/null 2>&1; then
    echo "Error: Railway CLI not found."
    echo "Install: npm install -g @railway/cli"
    exit 1
fi

RUNNER="$SCRIPT_DIR/dx-railway-run.sh"

if [[ -x "$RUNNER" ]]; then
    echo "Starting Affordabot in Railway Dev Mode..."
    exec "$RUNNER" -- railway dev "$@"
else
    echo "Warning: dx-railway-run.sh not found, falling back to bare railway dev."
    echo "For worktree-safe execution, ensure agent-skills is available."
    exec railway dev "$@"
fi
