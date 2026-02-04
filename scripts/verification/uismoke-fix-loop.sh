#!/bin/bash
set -e

# scripts/verification/uismoke-fix-loop.sh
# Triage last run and list stories that need fixing

echo "🔄 Starting UISmoke Fix Loop..."

RUN_TYPE=${1:-uismoke}
echo "🔍 Analyzing last run in artifacts/verification/${RUN_TYPE}..."

# 1. Perform dry-run triage to show summary
TARGET_DIR=${RUN_TYPE} make verify-triage ARGS="--dry-run"

# 2. Extract failing story IDs for easy reference
LAST_RUN=$(ls -t artifacts/verification/${RUN_TYPE} 2>/dev/null | head -1)

if [ -z "$LAST_RUN" ]; then
    echo "❌ No runs found in artifacts/verification/${RUN_TYPE}"
    exit 1
fi

FAILURES=$(jq -r '.story_results[] | select(.status != "pass") | .story_id' artifacts/verification/${RUN_TYPE}/${LAST_RUN}/run.json)

if [ -n "$FAILURES" ]; then
    echo -e "\n🔥 Stories needing attention: $FAILURES"
    echo -e "\n💡 To rerun locally (auth-bypass):"
    echo "make verify-stories ARGS=\"--only-stories $FAILURES\""
    echo -e "\n💡 To rerun locally (real-auth):"
    echo "make verify-nightly ARGS=\"--only-stories $FAILURES\""
else
    echo "✨ No failures found in last run."
fi
