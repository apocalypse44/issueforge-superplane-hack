#!/usr/bin/env bash
# SuperPlane runnerBash: fetch GitHub issue text
set -euo pipefail
APP_ROOT="${APP_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
WORKDIR="${WORKDIR:-/tmp/issueforge/$RANDOM}"
mkdir -p "$WORKDIR"
source "$(dirname "$0")/sp_common.sh"

ISSUE_URL=$(issue_url_from_payload)

if [ -z "$ISSUE_URL" ] || [ "$ISSUE_URL" = "null" ]; then
  echo "ERROR: issue_url not found in webhook payload"
  exit 1
fi

export GITHUB_TOKEN="${GITHUB_TOKEN:-}"
RESULT=$(python3 "$APP_ROOT/scripts/superplane_stages.py" fetch "$ISSUE_URL" "$WORKDIR")
echo "$RESULT" > "$WORKDIR/fetch_result.json"
echo "$RESULT" > "$SUPERPLANE_RESULT_FILE"
