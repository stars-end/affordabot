#!/bin/bash
#
# Test case for affordabot-f46z
# Verifies that 'make verify-*' targets can run without a railway login
# when required environment variables are provided.

set -e # Exit immediately if a command exits with a non-zero status.

# Ensure we are in the project root
if [ ! -f "Makefile" ]; then
    echo "❌ This script must be run from the repository root."
    exit 1
fi

echo "🧪 Starting test for Makefile verification logic..."

# --- Test Case 1: Failure without env vars and without Railway ---
echo ""
echo "--- Test Case 1: Expect failure when env vars are missing ---"
# Unset all potentially conflicting variables to simulate a clean CI environment
unset RAILWAY_TOKEN
unset RAILWAY_PROJECT_NAME
unset BACKEND_URL FRONTEND_URL DATABASE_URL ZAI_API_KEY TEST_USER_EMAIL TEST_USER_PASSWORD

echo "  Running 'make check-verify-env' (should fail)..."
# We expect this command to fail, so we invert the exit code with !
if ! make check-verify-env >/dev/null 2>&1; then
  echo "✅ Test Case 1 PASSED: 'make check-verify-env' failed as expected."
else
  echo "❌ Test Case 1 FAILED: 'make check-verify-env' succeeded unexpectedly."
  exit 1
fi

# --- Test Case 2: Success with all required env vars ---
echo ""
echo "--- Test Case 2: Expect success when all env vars are provided ---"
# Export dummy values for all required variables
export BACKEND_URL="http://localhost:8000"
export FRONTEND_URL="http://localhost:3000"
export DATABASE_URL="postgresql://user:pass@host/db"
export ZAI_API_KEY="dummy-key"
export TEST_USER_EMAIL="test@example.com"
export TEST_USER_PASSWORD="password"

echo "  Exported required environment variables."
echo "  Running 'make check-verify-env' (should succeed)..."

if make check-verify-env; then
    echo "✅ Test Case 2 PASSED: 'make check-verify-env' succeeded as expected."
else
    echo "❌ Test Case 2 FAILED: 'make check-verify-env' failed unexpectedly."
    # Clean up before exiting
    unset BACKEND_URL FRONTEND_URL DATABASE_URL ZAI_API_KEY TEST_USER_EMAIL TEST_USER_PASSWORD
    exit 1
fi

# Clean up
unset BACKEND_URL FRONTEND_URL DATABASE_URL ZAI_API_KEY TEST_USER_EMAIL TEST_USER_PASSWORD

echo ""
echo "✅ All test cases for Makefile logic passed."

