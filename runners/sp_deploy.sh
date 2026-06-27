#!/usr/bin/env bash
# SuperPlane runnerBash: push PoC branch + trigger Render
set -euo pipefail
APP_ROOT="${APP_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
WORKDIR="${WORKDIR:-/tmp/issueforge/$RANDOM}"
source "$(dirname "$0")/sp_common.sh"

PROJECT_DIR=$(result_field "Verify Build" project_dir)
ISSUE_NUM=$(result_field "Fetch Issue" issue_number)

if [ -z "$PROJECT_DIR" ] || [ ! -d "$PROJECT_DIR" ]; then
  echo "ERROR: project_dir missing from Verify Build"
  exit 1
fi

RESULT=$(python3 "$APP_ROOT/scripts/superplane_stages.py" deploy "$WORKDIR" "$PROJECT_DIR" "$ISSUE_NUM")
echo "$RESULT" > "$SUPERPLANE_RESULT_FILE"
