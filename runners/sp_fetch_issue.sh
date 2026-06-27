#!/usr/bin/env bash
# SuperPlane runnerBash: fetch GitHub issue text
set -euo pipefail
source "$(dirname "$0")/sp_common.sh"
APP_ROOT="${APP_ROOT:-$(resolve_app_root "$0")}"
export APP_ROOT
WORKDIR="${WORKDIR:-/tmp/issueforge/$RANDOM}"
mkdir -p "$WORKDIR"

ISSUE_URL=$(issue_url_from_payload)

if [ -z "$ISSUE_URL" ] || [ "$ISSUE_URL" = "null" ]; then
  echo "ERROR: issue_url not found in webhook payload"
  exit 1
fi

export GITHUB_TOKEN="${GITHUB_TOKEN:-}"
STAGES="$(stages_py_path "$APP_ROOT")"
RESULT=$(python3 "$STAGES" fetch "$ISSUE_URL" "$WORKDIR")
echo "$RESULT" > "$WORKDIR/fetch_result.json"
echo "$RESULT" > "$SUPERPLANE_RESULT_FILE"
