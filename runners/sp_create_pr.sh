#!/usr/bin/env bash
# SuperPlane runnerBash: create GitHub PR
set -euo pipefail
source "$(dirname "$0")/sp_common.sh"
APP_ROOT="${APP_ROOT:-$(resolve_app_root "$0")}"
export APP_ROOT
WORKDIR="${WORKDIR:-/tmp/issueforge/$RANDOM}"

ISSUE_NUM=$(result_field "Fetch Issue" issue_number)
ISSUE_URL=$(result_field "Fetch Issue" issue_url)
ISSUE_TITLE=$(result_field "Fetch Issue" issue_title)
ISSUE_TEXT=$(result_field "Fetch Issue" issue_text)
SPEC_FILE=$(result_field "Validate Spec" spec_file)
PROJECT_DIR=$(result_field "Verify Build" project_dir)
ATTEMPTS=$(result_field "Verify Build" attempts)

# Build issue + deploy JSON for python stage
mkdir -p "$WORKDIR"
jq -n \
  --argjson number "${ISSUE_NUM:-0}" \
  --arg url "$ISSUE_URL" \
  --arg title "$ISSUE_TITLE" \
  --arg text "$ISSUE_TEXT" \
  '{number: $number, url: $url, title: $title, text: $text}' > "$WORKDIR/issue.json"
cp "$SPEC_FILE" "$WORKDIR/spec.json"

DEPLOY_JSON=$(jq -c --arg n "Deploy" '
  (.[$n].data.result?) // (.[$n].data[0].result?) // {}
' "$SUPERPLANE_PAYLOAD_FILE")
echo "$DEPLOY_JSON" > "$WORKDIR/deploy_result.json"

STAGES="$(stages_py_path "$APP_ROOT")"
RESULT=$(python3 "$STAGES" pr "$WORKDIR" "$WORKDIR/spec.json" "$WORKDIR/issue.json" "$WORKDIR/deploy_result.json" "$ATTEMPTS")
echo "$RESULT" > "$SUPERPLANE_RESULT_FILE"
