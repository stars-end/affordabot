#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"
export PATH="$HOME/.local/bin:$HOME/Library/Python/3.13/bin:$HOME/Library/Python/3.14/bin:$PATH"

if command -v ruff >/dev/null 2>&1; then
  echo "Running Ruff via PATH..."
  ruff check backend
  exit 0
fi

if [[ -x "$REPO_ROOT/backend/.venv/bin/ruff" ]]; then
  echo "Running Ruff via backend virtualenv..."
  "$REPO_ROOT/backend/.venv/bin/ruff" check "$REPO_ROOT/backend"
  exit 0
fi

if python3 -c "import ruff" >/dev/null 2>&1; then
  echo "Running Ruff via python module..."
  python3 -m ruff check backend
  exit 0
fi

if command -v poetry >/dev/null 2>&1; then
  echo "Running Ruff via Poetry environment..."
  cd backend
  poetry run ruff check .
  exit 0
fi

echo "ERROR: Ruff is unavailable."
echo "Fix command:"
echo "  python3 -m pip install --user ruff"
echo "Then rerun:"
echo "  scripts/ci/backend-ruff-preflight.sh"
exit 1
