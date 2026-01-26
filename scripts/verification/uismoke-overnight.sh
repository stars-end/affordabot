#!/bin/bash
set -e

# scripts/verification/uismoke-overnight.sh
# Run nightly smoke suite and perform automatic Beads triage

echo "🌙 Starting UISmoke Overnight QA..."

# 1. Run stories with repro effort
make verify-nightly

# 2. Triage failures and create Beads issues
echo "📋 Running triage..."
TARGET_DIR=nightly make verify-triage

echo "✅ Overnight QA cycle complete."
