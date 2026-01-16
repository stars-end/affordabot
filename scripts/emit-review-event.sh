#!/bin/bash
# Emit REVIEW_COMPLETE event to #fleet-events
# Usage: emit-review-event.sh <repo> <pr_number> <passed> [beads_id] [summary]
#
# Args:
#   repo: Repository name (e.g., prime-radiant-ai)
#   pr_number: PR number
#   passed: "true" or "false"
#   beads_id: Optional beads issue ID (extracted from PR title if not provided)
#   summary: Optional summary message

set -e

REPO="${1:-unknown}"
PR_NUMBER="${2:-0}"
PASSED="${3:-false}"
BEADS_ID="${4:-}"
SUMMARY="${5:-}"

# Try to extract beads_id from PR title if not provided
if [ -z "$BEADS_ID" ] && [ -n "$PR_NUMBER" ]; then
    # Look for Feature-Key: bd-xxx or bd-xxx in title
    PR_TITLE=$(gh pr view "$PR_NUMBER" --json title -q '.title' 2>/dev/null || echo "")
    BEADS_ID=$(echo "$PR_TITLE" | grep -oE 'bd-[a-zA-Z0-9]+' | head -1 || echo "")
fi

if [ -z "$BEADS_ID" ]; then
    BEADS_ID="bd-unknown"
fi

# Build event
EVENT_ID="evt_$(date +%s)_review"
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
HOSTNAME=$(hostname -s 2>/dev/null || hostname | cut -d. -f1)
SENDER="claude-code-review@${HOSTNAME}"
REVIEW_RUN_URL="${GITHUB_SERVER_URL:-https://github.com}/${GITHUB_REPOSITORY:-stars-end/$REPO}/actions/runs/${GITHUB_RUN_ID:-0}"
PR_URL="${GITHUB_SERVER_URL:-https://github.com}/${GITHUB_REPOSITORY:-stars-end/$REPO}/pull/${PR_NUMBER}"

# Convert passed to boolean
if [ "$PASSED" = "true" ] || [ "$PASSED" = "1" ]; then
    PASSED_BOOL="true"
else
    PASSED_BOOL="false"
fi

# Build JSON event
EVENT=$(cat <<EOF
{"event_id":"$EVENT_ID","event_type":"REVIEW_COMPLETE","version":"1.0","repo":"$REPO","beads_id":"$BEADS_ID","sender":"$SENDER","timestamp":"$TIMESTAMP","payload":{"passed":$PASSED_BOOL,"pr_number":$PR_NUMBER,"pr_url":"$PR_URL","review_run_url":"$REVIEW_RUN_URL","summary":"$SUMMARY"}}
EOF
)

# Channel ID for #fleet-events
CHANNEL_ID="${FLEET_EVENTS_CHANNEL_ID:-C0A8YU9JW06}"

echo "Emitting REVIEW_COMPLETE event:"
echo "  repo: $REPO"
echo "  beads_id: $BEADS_ID"
echo "  passed: $PASSED_BOOL"
echo "  pr: $PR_NUMBER"

# Find slack-mcp-server
SLACK_MCP="$HOME/go/bin/slack-mcp-server"
if [ ! -f "$SLACK_MCP" ]; then
    SLACK_MCP="/home/linuxbrew/.linuxbrew/bin/slack-mcp-server"
fi
if [ ! -f "$SLACK_MCP" ]; then
    SLACK_MCP="slack-mcp-server"
fi

# Send via MCP
RESULT=$(cat <<MCPEOF | timeout 30 "$SLACK_MCP" --transport stdio 2>/dev/null | grep '"id":1' || echo '{"error":"timeout"}'
{"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"emit-review","version":"1.0"}}}
{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"conversations_add_message","arguments":{"channel_id":"$CHANNEL_ID","content_type":"text/plain","payload":"$EVENT"}}}
MCPEOF
)

if echo "$RESULT" | grep -q '"result"'; then
    echo "✅ Event emitted successfully"
    exit 0
else
    echo "❌ Failed to emit event: $RESULT"
    exit 1
fi
