#!/usr/bin/env bash
# Anti-Prime theme contamination check.
# Scans frontend/ source for Prime Radiant-specific tokens, CSS variables,
# and component imports that should never appear in affordabot.
set -euo pipefail

FRONTEND_DIR="${1:-frontend}"
VIOLATIONS=0

echo "::group::Anti-Prime Contamination Check"

# Prime-specific color tokens (from Prime Radiant DESIGN_SYSTEM.md)
PRIME_TOKENS=(
  '--color-navy'
  '--navy-800'
  '--color-gold'
  'C5A55A'
  '1E3A6A'
  '8B95A5'
  '--color-positive'
  '--color-negative'
  '--font-display'
  'Playfair Display'
  'font-display.*Playfair'
)

# Prime-specific component/feature patterns
PRIME_PATTERNS=(
  'prime-radiant'
  'PrimeRadiant'
  'T-Split'
  'Account Rail'
  'Artifact Workspace'
)

# Scan for Prime tokens in TSX/TS/CSS files
for token in "${PRIME_TOKENS[@]}"; do
  matches=$(grep -rl --include='*.tsx' --include='*.ts' --include='*.css' "$FRONTEND_DIR/src" 2>/dev/null | grep -v node_modules | grep -v '.next' || true)
  if [ -n "$matches" ]; then
    echo "::error::Prime token '$token' found in: $matches"
    VIOLATIONS=$((VIOLATIONS + 1))
  fi
done

# Scan for Prime patterns
for pattern in "${PRIME_PATTERNS[@]}"; do
  matches=$(grep -rl --include='*.tsx' --include='*.ts' --include='*.css' "$FRONTEND_DIR/src" 2>/dev/null | grep -v node_modules | grep -v '.next' || true)
  if [ -n "$matches" ]; then
    echo "::error::Prime pattern '$pattern' found in: $matches"
    VIOLATIONS=$((VIOLATIONS + 1))
  fi
done

echo "::endgroup::"

if [ "$VIOLATIONS" -gt 0 ]; then
  echo "::error::$VIOLATIONS Prime Radiant contamination violation(s) detected in frontend/"
  exit 1
fi

echo "OK: No Prime Radiant contamination detected."
