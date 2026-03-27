#!/usr/bin/env bash
# scripts/dx-railway-run.sh
# Thin affordabot wrapper over agent-skills shared Railway execution contract.
#
# Usage:
#   ./scripts/dx-railway-run.sh -- <command> [args...]
#   ./scripts/dx-railway-run.sh --env dev --service backend -- <command> [args...]
#
# Environment overrides:
#   AFFORDABOT_PROJECT_ID    Railway project ID
#   AFFORDABOT_ENV           Environment name (default: dev)
#   AFFORDABOT_SERVICE       Service name (default: backend)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENT_SKILLS_DIR="${AGENT_SKILLS_DIR:-$HOME/agent-skills}"

DX_RUNNER="$AGENT_SKILLS_DIR/scripts/dx-railway-run.sh"

if [[ ! -x "$DX_RUNNER" ]]; then
  if [[ -x "$AGENT_SKILLS_DIR/scripts/dx-railway-run.sh" ]]; then
    DX_RUNNER="$AGENT_SKILLS_DIR/scripts/dx-railway-run.sh"
  elif [[ -x "${AGENT_SKILLS_DIR:-}/scripts/dx-railway-run.sh" ]]; then
    DX_RUNNER="${AGENT_SKILLS_DIR:-}/scripts/dx-railway-run.sh"
  else
    echo "dx-railway-run: agent-skills shared contract not found at $DX_RUNNER" >&2
    echo "Set AGENT_SKILLS_DIR to point to your agent-skills checkout." >&2
    exit 2
  fi
fi

export DX_RAILWAY_PROJECT_ID="${AFFORDABOT_PROJECT_ID:-${DX_RAILWAY_PROJECT_ID:-}}"
export DX_RAILWAY_ENV="${AFFORDABOT_ENV:-${DX_RAILWAY_ENV:-dev}}"
export DX_RAILWAY_SERVICE="${AFFORDABOT_SERVICE:-${DX_RAILWAY_SERVICE:-backend}}"

extra_args=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env)
      export DX_RAILWAY_ENV="${2:-}"
      shift 2
      ;;
    --service)
      export DX_RAILWAY_SERVICE="${2:-}"
      shift 2
      ;;
    --project-id)
      export DX_RAILWAY_PROJECT_ID="${2:-}"
      shift 2
      ;;
    --)
      shift
      break
      ;;
    *)
      extra_args+=("$1")
      shift
      ;;
  esac
done

if [[ ${#extra_args[@]} -gt 0 ]]; then
  set -- "${extra_args[@]}" -- "$@"
fi

[[ $# -gt 0 ]] || {
  echo "Usage: $0 [--env ENV] [--service SVC] [--project-id ID] -- <command> [args...]" >&2
  exit 2
}

exec "$DX_RUNNER" "$@"
