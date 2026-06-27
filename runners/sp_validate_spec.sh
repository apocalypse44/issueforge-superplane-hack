#!/usr/bin/env bash
# SuperPlane runnerBash: validate Spec Agent JSON output
set -euo pipefail
APP_ROOT="${APP_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
WORKDIR="${WORKDIR:-/tmp/issueforge/$RANDOM}"
mkdir -p "$WORKDIR"
source "$(dirname "$0")/sp_common.sh"

SPEC_TEXT=$(claude_text "Spec Agent")
if [ -z "$SPEC_TEXT" ]; then
  echo "ERROR: no text from Spec Agent"
  exit 1
fi

echo "$SPEC_TEXT" > "$WORKDIR/spec_raw.txt"
RESULT=$(python3 "$APP_ROOT/scripts/superplane_stages.py" validate "$WORKDIR" "$WORKDIR/spec_raw.txt")
echo "$RESULT" > "$SUPERPLANE_RESULT_FILE"
