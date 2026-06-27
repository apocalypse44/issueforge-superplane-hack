#!/usr/bin/env bash
# SuperPlane runnerBash: push PoC branch + trigger Render
set -euo pipefail
source "$(dirname "$0")/sp_common.sh"
APP_ROOT="${APP_ROOT:-$(resolve_app_root "$0")}"
export APP_ROOT
WORKDIR="${WORKDIR:-/tmp/issueforge/$RANDOM}"

PROJECT_DIR=$(result_field "Verify Build" project_dir)
ISSUE_NUM=$(result_field "Fetch Issue" issue_number)

if [ -z "$PROJECT_DIR" ] || [ ! -d "$PROJECT_DIR" ]; then
  echo "ERROR: project_dir missing from Verify Build"
  exit 1
fi

STAGES="$(stages_py_path "$APP_ROOT")"
RESULT=$(python3 "$STAGES" deploy "$WORKDIR" "$PROJECT_DIR" "$ISSUE_NUM")
echo "$RESULT" > "$SUPERPLANE_RESULT_FILE"
