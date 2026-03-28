#!/bin/bash
#
# Test for bd-9dzi: Verifies that 'make verify-*' targets can run
# without interactive Railway login or ambient link state when required
# environment variables are provided.

set -e

if [ ! -f "Makefile" ]; then
    echo "FAIL: This script must be run from the repository root."
    exit 1
fi

echo "Test: Makefile verification logic (worktree-safe)..."

echo ""
echo "--- Test 1: Expect failure when env vars are missing ---"
unset RAILWAY_TOKEN
unset RAILWAY_PROJECT_NAME
unset RAILWAY_ENVIRONMENT
unset DX_RAILWAY_CONTEXT_FILE
unset BACKEND_URL FRONTEND_URL DATABASE_URL ZAI_API_KEY TEST_USER_EMAIL TEST_USER_PASSWORD

if ! make check-verify-env >/dev/null 2>&1; then
  echo "PASS: 'make check-verify-env' failed as expected without env vars."
else
  echo "FAIL: 'make check-verify-env' succeeded unexpectedly."
  exit 1
fi

echo ""
echo "--- Test 2: Expect success when all required env vars are provided ---"
export BACKEND_URL="http://localhost:8000"
export FRONTEND_URL="http://localhost:3000"
export DATABASE_URL="postgresql://user:pass@host/db"
export ZAI_API_KEY="dummy-key"
export TEST_USER_EMAIL="test@example.com"
export TEST_USER_PASSWORD="password"

if make check-verify-env; then
    echo "PASS: 'make check-verify-env' succeeded with all env vars."
else
    echo "FAIL: 'make check-verify-env' failed unexpectedly with env vars."
    unset BACKEND_URL FRONTEND_URL DATABASE_URL ZAI_API_KEY TEST_USER_EMAIL TEST_USER_PASSWORD
    exit 1
fi

echo ""
echo "--- Test 3: Wrapper script exists and is executable ---"
if [ -x "scripts/dx-railway-run.sh" ]; then
    echo "PASS: scripts/dx-railway-run.sh exists and is executable."
else
    echo "FAIL: scripts/dx-railway-run.sh missing or not executable."
    unset BACKEND_URL FRONTEND_URL DATABASE_URL ZAI_API_KEY TEST_USER_EMAIL TEST_USER_PASSWORD
    exit 1
fi

if [ -x "scripts/dx-load-auth.sh" ]; then
    echo "PASS: scripts/dx-load-auth.sh exists and is executable."
else
    echo "FAIL: scripts/dx-load-auth.sh missing or not executable."
    unset BACKEND_URL FRONTEND_URL DATABASE_URL ZAI_API_KEY TEST_USER_EMAIL TEST_USER_PASSWORD
    exit 1
fi

echo ""
echo "--- Test 4: Makefile no longer references bare 'railway run' ---"
if grep -n 'RUN_CMD.*railway run' Makefile >/dev/null 2>&1; then
    echo "FAIL: Makefile still contains ambient 'RUN_CMD.*railway run' pattern."
    unset BACKEND_URL FRONTEND_URL DATABASE_URL ZAI_API_KEY TEST_USER_EMAIL TEST_USER_PASSWORD
    exit 1
else
    echo "PASS: Makefile does not reference ambient 'railway run' via RUN_CMD."
fi

if grep -n 'railway login' Makefile >/dev/null 2>&1; then
    echo "FAIL: Makefile still contains 'railway login'."
    unset BACKEND_URL FRONTEND_URL DATABASE_URL ZAI_API_KEY TEST_USER_EMAIL TEST_USER_PASSWORD
    exit 1
else
    echo "PASS: Makefile does not contain interactive 'railway login'."
fi

if grep -nE '^\s*railway link$' Makefile >/dev/null 2>&1; then
    echo "FAIL: Makefile still contains bare 'railway link'."
    unset BACKEND_URL FRONTEND_URL DATABASE_URL ZAI_API_KEY TEST_USER_EMAIL TEST_USER_PASSWORD
    exit 1
else
    echo "PASS: Makefile does not contain bare interactive 'railway link'."
fi

unset BACKEND_URL FRONTEND_URL DATABASE_URL ZAI_API_KEY TEST_USER_EMAIL TEST_USER_PASSWORD

echo ""
echo "PASS: All test cases passed."
