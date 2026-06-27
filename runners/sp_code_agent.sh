#!/usr/bin/env bash
# SuperPlane runnerBash: Code Agent via Groq API
set -euo pipefail
source "$(dirname "$0")/sp_common.sh"
APP_ROOT="${APP_ROOT:-$(resolve_app_root "$0")}"
export APP_ROOT
WORKDIR="${WORKDIR:-/tmp/issueforge/$RANDOM}"
mkdir -p "$WORKDIR"

SPEC_TEXT=$(llm_text "Spec Agent")
if [ -z "$SPEC_TEXT" ]; then
  echo "ERROR: no text from Spec Agent"
  exit 1
fi

echo "$SPEC_TEXT" > "$WORKDIR/spec_raw.txt"
STAGES="$(stages_py_path "$APP_ROOT")"
RESULT=$(python3 "$STAGES" code "$WORKDIR" "$WORKDIR/spec_raw.txt")
echo "$RESULT" > "$SUPERPLANE_RESULT_FILE"
