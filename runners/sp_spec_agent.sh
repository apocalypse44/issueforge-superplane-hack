#!/usr/bin/env bash
# SuperPlane runnerBash: Spec Agent via Groq API
set -euo pipefail
source "$(dirname "$0")/sp_common.sh"
APP_ROOT="${APP_ROOT:-$(resolve_app_root "$0")}"
export APP_ROOT
WORKDIR="${WORKDIR:-/tmp/issueforge/$RANDOM}"
mkdir -p "$WORKDIR"

ISSUE_TEXT=$(result_field "Fetch Issue" issue_text)
if [ -z "$ISSUE_TEXT" ]; then
  echo "ERROR: issue_text not found from Fetch Issue"
  exit 1
fi

echo "$ISSUE_TEXT" > "$WORKDIR/issue_text.txt"
STAGES="$(stages_py_path "$APP_ROOT")"
RESULT=$(python3 "$STAGES" spec "$WORKDIR" "$WORKDIR/issue_text.txt")
echo "$RESULT" > "$SUPERPLANE_RESULT_FILE"
