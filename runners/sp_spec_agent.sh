#!/usr/bin/env bash
# SuperPlane runnerBash: Spec Agent via Groq API
set -euo pipefail
echo "=== Spec Agent start ==="
source "$(dirname "$0")/sp_common.sh"
APP_ROOT="${APP_ROOT:-$(resolve_app_root "$0")}"
export APP_ROOT
echo "APP_ROOT=$APP_ROOT"

if [ -z "${GROQ_API_KEY:-}" ] || [ "$GROQ_API_KEY" = "REPLACE_GROQ_API_KEY" ]; then
  if [ -z "${OPENROUTER_API_KEY:-}" ] || [ "$OPENROUTER_API_KEY" = "REPLACE_OPENROUTER_API_KEY" ]; then
    echo "ERROR: Set GROQ_API_KEY or OPENROUTER_API_KEY on Spec Agent node"
    exit 1
  fi
  export LLM_PROVIDER="${LLM_PROVIDER:-openrouter}"
fi

WORKDIR="${WORKDIR:-/tmp/issueforge/$RANDOM}"
mkdir -p "$WORKDIR"

ISSUE_TEXT=$(result_field "Fetch Issue" issue_text)
if [ -z "$ISSUE_TEXT" ]; then
  echo "ERROR: issue_text not found from Fetch Issue in payload"
  echo "Payload keys:" && jq -r 'keys[]' "$SUPERPLANE_PAYLOAD_FILE" 2>/dev/null || true
  exit 1
fi

echo "Issue text length: ${#ISSUE_TEXT} chars"
echo "$ISSUE_TEXT" > "$WORKDIR/issue_text.txt"
STAGES="$(stages_py_path "$APP_ROOT")"
echo "Running: python3 $STAGES spec ..."
set +e
PYOUT=$(python3 "$STAGES" spec "$WORKDIR" "$WORKDIR/issue_text.txt" 2>&1)
PYRC=$?
set -e
if [ "$PYRC" -ne 0 ]; then
  echo "ERROR: spec stage failed (exit $PYRC):"
  echo "$PYOUT"
  exit 1
fi
RESULT="$PYOUT"
echo "$RESULT" > "$SUPERPLANE_RESULT_FILE"
echo "=== Spec Agent done ==="
