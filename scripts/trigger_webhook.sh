#!/usr/bin/env bash
# Test IssueForge webhook from your machine.
# Usage: ./scripts/trigger_webhook.sh "https://YOUR_WEBHOOK_URL" [issue_url]
set -euo pipefail
WEBHOOK_URL="${1:?Usage: $0 <webhook_url> [issue_url]}"
ISSUE_URL="${2:-https://github.com/superplanehq/superplane/issues/5368}"
TOKEN="${WEBHOOK_TOKEN:-}"

ARGS=(-sS -X POST "$WEBHOOK_URL" -H "Content-Type: application/json" -d "{\"issue_url\":\"$ISSUE_URL\"}")
if [ -n "$TOKEN" ]; then
  ARGS+=(-H "Authorization: Bearer $TOKEN")
fi

echo "POST $ISSUE_URL"
curl "${ARGS[@]}"
echo
