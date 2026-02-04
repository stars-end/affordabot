#!/bin/bash
set -e

# scripts/verification/uismoke-rerun.sh
# Rerun failing stories from the last run (or specified RUN_DIR)

RUN_TYPE=${1:-uismoke}
OVERRIDE_RUN_DIR=${RUN_DIR:-}

echo "🔄 Starting UISmoke Rerun..."

if [ -n "$OVERRIDE_RUN_DIR" ]; then
    LAST_RUN_PATH="$OVERRIDE_RUN_DIR"
else
    # Find last run
    LAST_RUN=$(ls -t artifacts/verification/${RUN_TYPE} 2>/dev/null | head -1)
    if [ -z "$LAST_RUN" ]; then
        echo "❌ No runs found in artifacts/verification/${RUN_TYPE}"
        exit 1
    fi
    LAST_RUN_PATH="artifacts/verification/${RUN_TYPE}/${LAST_RUN}"
fi

echo "🔍 Analyzing run in ${LAST_RUN_PATH}..."
RUN_JSON="${LAST_RUN_PATH}/run.json"

if [ ! -f "$RUN_JSON" ]; then
    echo "❌ run.json not found at ${RUN_JSON}"
    exit 1
fi

FAILURES=$(jq -r '.story_results[] | select(.status != "pass") | .story_id' "$RUN_JSON" | tr '\n' ' ')

if [ -z "$FAILURES" ]; then
    echo "✨ No failures found in last run. Nothing to rerun."
    exit 0
fi

echo "🔥 Rerunning failures: $FAILURES"

# artifacts/verification/rerun/<timestamp>
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
OUTPUT_DIR="../artifacts/verification/rerun/${TIMESTAMP}"
mkdir -p "$OUTPUT_DIR"

TARGET_URL=${BASE_URL:-${RAILWAY_DEV_FRONTEND_URL:-https://frontend-dev-5093.up.railway.app}}

cd backend
poetry run uismoke run \
    --stories ../docs/TESTING/STORIES \
    --base-url ${TARGET_URL} \
    --output "$OUTPUT_DIR" \
    --auth-mode cookie_bypass \
    --cookie-name ${COOKIE_NAME:-x-test-user} --cookie-value ${COOKIE_VALUE:-admin} --cookie-signed \
    --cookie-secret-env TEST_AUTH_BYPASS_SECRET \
    --mode qa --repro 1 \
    --tracing \
    --only-stories $FAILURES
