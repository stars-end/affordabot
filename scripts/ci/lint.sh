#!/usr/bin/env bash
set -uo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RESET='\033[0m'

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

ERRORS=0

echo "🔍 Running Lint Checks..."

# 1. Backend: Python (Ruff)
echo "🐍 Backend: running ruff..."
if cd backend && poetry run ruff check .; then
    echo -e "${GREEN}✓ Backend lint passed${RESET}"
else
    echo -e "${RED}❌ Backend lint failed${RESET}"
    ERRORS=$((ERRORS+1))
fi

# 2. Frontend: pnpm lint
echo "⚛️  Frontend: running pnpm lint..."
if cd "$REPO_ROOT/frontend" && pnpm lint; then
     echo -e "${GREEN}✓ Frontend lint passed${RESET}"
else
     echo -e "${RED}❌ Frontend lint failed${RESET}"
     ERRORS=$((ERRORS+1))
fi

# Exit Logic
if [ "$ERRORS" -gt 0 ]; then
    if [ "${CI:-}" == "true" ]; then
        echo -e "${RED}❌ Lint failed with $ERRORS errors (CI mode: Fatal)${RESET}"
        exit 1
    else
        echo -e "${YELLOW}⚠️  Lint failed with $ERRORS errors (Local mode: Warn only)${RESET}"
        # We don't exit 1 locally to avoid blocking workflow, unless strict mode requested
        if [ "${STRICT:-}" == "true" ]; then
            exit 1
        fi
        exit 0
    fi
else
    echo -e "${GREEN}✅ All lint checks passed${RESET}"
    exit 0
fi
