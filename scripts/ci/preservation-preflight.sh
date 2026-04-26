#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT/frontend"

required_files=(
  "tests/e2e/fixtures/legislation-california.json"
  "tests/e2e/fixtures/bill-detail.json"
)

for file in "${required_files[@]}"; do
  if [[ ! -f "$file" ]]; then
    echo "ERROR: required preservation fixture missing: frontend/$file"
    echo "Fix command:"
    echo "  git checkout -- frontend/$file"
    exit 1
  fi
done

if [[ "${NEXT_PUBLIC_TEST_AUTH_BYPASS:-}" != "true" ]]; then
  echo "ERROR: NEXT_PUBLIC_TEST_AUTH_BYPASS must be true for preservation tests."
  echo "Fix command:"
  echo "  export NEXT_PUBLIC_TEST_AUTH_BYPASS=true"
  exit 1
fi

if [[ -z "${TEST_AUTH_BYPASS_SECRET:-}" ]]; then
  echo "ERROR: TEST_AUTH_BYPASS_SECRET is required."
  echo "Fix command:"
  echo "  export TEST_AUTH_BYPASS_SECRET=ci-test-secret-for-playwright-only"
  exit 1
fi

if [[ -z "${NEXT_PUBLIC_API_URL:-}" ]]; then
  echo "ERROR: NEXT_PUBLIC_API_URL is required for deterministic preservation routing."
  echo "Fix command:"
  echo "  export NEXT_PUBLIC_API_URL=http://127.0.0.1:65535"
  exit 1
fi

echo "OK: frontend preservation preflight passed"
