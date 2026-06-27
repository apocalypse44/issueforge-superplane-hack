#!/usr/bin/env bash
# SuperPlane runnerBash: materialize PoC + npm build
set -euo pipefail
APP_ROOT="${APP_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
WORKDIR="${WORKDIR:-/tmp/issueforge/$RANDOM}"
mkdir -p "$WORKDIR"
source "$(dirname "$0")/sp_common.sh"

CODE_TEXT=$(claude_text "Code Agent")
SPEC_FILE=$(result_field "Validate Spec" spec_file)

if [ -z "$CODE_TEXT" ]; then
  echo "ERROR: no text from Code Agent"
  exit 1
fi

echo "$CODE_TEXT" > "$WORKDIR/changes_raw.txt"
if [ -n "$SPEC_FILE" ] && [ -f "$SPEC_FILE" ]; then
  cp "$SPEC_FILE" "$WORKDIR/spec.json"
else
  jq -r '.["Validate Spec"].data.result // .["Validate Spec"].data[0].result // {}' "$SUPERPLANE_PAYLOAD_FILE" > /dev/null
  SPEC_FILE="$WORKDIR/spec.json"
  [ -f "$SPEC_FILE" ] || echo '{"title":"PoC"}' > "$SPEC_FILE"
fi

RESULT=$(python3 "$APP_ROOT/scripts/superplane_stages.py" verify "$WORKDIR" "$WORKDIR/changes_raw.txt" "$SPEC_FILE")
echo "$RESULT" > "$SUPERPLANE_RESULT_FILE"
