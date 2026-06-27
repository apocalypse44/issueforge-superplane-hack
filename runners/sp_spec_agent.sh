#!/usr/bin/env bash
# SuperPlane runnerBash: Spec Agent via Groq API
set -euo pipefail
APP_ROOT="${APP_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
WORKDIR="${WORKDIR:-/tmp/issueforge/$RANDOM}"
mkdir -p "$WORKDIR"
source "$(dirname "$0")/sp_common.sh"

ISSUE_TEXT=$(result_field "Fetch Issue" issue_text)
if [ -z "$ISSUE_TEXT" ]; then
  echo "ERROR: issue_text not found from Fetch Issue"
  exit 1
fi

echo "$ISSUE_TEXT" > "$WORKDIR/issue_text.txt"
RESULT=$(python3 "$APP_ROOT/scripts/superplane_stages.py" spec "$WORKDIR" "$WORKDIR/issue_text.txt")
echo "$RESULT" > "$SUPERPLANE_RESULT_FILE"
