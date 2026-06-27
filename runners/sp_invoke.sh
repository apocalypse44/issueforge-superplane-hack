#!/usr/bin/env bash
# Bootstrap + run a sp_*.sh script (flat or runners/ layout). Called from canvas.yaml.
set -euo pipefail
TARGET="${1:?usage: sp_invoke.sh sp_fetch_issue.sh}"
FILES_REPO="${FILES_REPO:-apocalypse44/issueforge-superplane-hack}"
ROOT="/tmp/sp-issueforge"

has_scripts() {
  [ -f "$1/runners/$TARGET" ] || [ -f "$1/$TARGET" ] || \
    [ -f "$1/runners/sp_canvas_entry.sh" ] || [ -f "$1/sp_canvas_entry.sh" ]
}

if ! has_scripts "$ROOT"; then
  echo "Cloning https://github.com/${FILES_REPO}.git into ${ROOT} ..."
  rm -rf "$ROOT"
  if [ -n "${GITHUB_TOKEN:-}" ]; then
    git clone --depth 1 "https://x-access-token:${GITHUB_TOKEN}@github.com/${FILES_REPO}.git" "$ROOT"
  else
    git clone --depth 1 "https://github.com/${FILES_REPO}.git" "$ROOT"
  fi
else
  echo "Using cached app files at ${ROOT}"
fi

export APP_ROOT="$ROOT" FILES_REPO
echo "Running ${TARGET} (APP_ROOT=${APP_ROOT})"

if [ -f "$ROOT/runners/sp_canvas_entry.sh" ]; then
  exec bash "$ROOT/runners/sp_canvas_entry.sh" "$TARGET"
elif [ -f "$ROOT/sp_canvas_entry.sh" ]; then
  exec bash "$ROOT/sp_canvas_entry.sh" "$TARGET"
elif [ -f "$ROOT/runners/$TARGET" ]; then
  exec bash "$ROOT/runners/$TARGET"
elif [ -f "$ROOT/$TARGET" ]; then
  exec bash "$ROOT/$TARGET"
fi

echo "ERROR: ${TARGET} not found under ${ROOT}"
ls -la "$ROOT" "$ROOT/runners" 2>/dev/null || true
exit 1
