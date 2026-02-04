#!/bin/zsh
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
OUTFILE="$REPO_ROOT/AGENTS.md"

echo "Generating AGENTS.md from fragments..."

# Ensure fragments directory exists
mkdir -p "$REPO_ROOT/fragments"

# Check for baseline
if [[ ! -f "$REPO_ROOT/fragments/universal-baseline.md" ]]; then
    echo "⚠️  Warning: fragments/universal-baseline.md not found"
    echo "Run baseline-sync workflow or copy from agent-skills"
    exit 1
fi

# Start with header
cat > "$OUTFILE" <<'HEADER'
# AGENTS.md — Affordabot

<!-- AUTO-GENERATED — DO NOT EDIT DIRECTLY -->
<!-- Regenerate: make regenerate-agents-md -->
<!-- Source: fragments/universal-baseline.md + fragments/repo-addendum.md -->

HEADER

# Layer 1: Universal Baseline (from agent-skills)
cat "$REPO_ROOT/fragments/universal-baseline.md" >> "$OUTFILE"
echo "" >> "$OUTFILE"
echo "---" >> "$OUTFILE"
echo "" >> "$OUTFILE"

# Layer 2: Repo Addendum (optional)
if [[ -f "$REPO_ROOT/fragments/repo-addendum.md" ]]; then
    echo "## Repo-Specific Addendum" >> "$OUTFILE"
    echo "" >> "$OUTFILE"
    cat "$REPO_ROOT/fragments/repo-addendum.md" >> "$OUTFILE"
    echo "" >> "$OUTFILE"
fi

LINES=$(wc -l < "$OUTFILE")
echo "✅ Generated AGENTS.md ($LINES lines)"
