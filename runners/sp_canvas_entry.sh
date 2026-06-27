#!/usr/bin/env bash
# Run a sp_*.sh script. Works with flat Files layout or runners/ subfolder.
set -euo pipefail
TARGET="${1:?usage: sp_canvas_entry.sh sp_fetch_issue.sh}"
ENTRY_DIR="$(cd "$(dirname "$0")" && pwd)"
if [ "$(basename "$ENTRY_DIR")" = "runners" ]; then
  export APP_ROOT="${APP_ROOT:-$(cd "$ENTRY_DIR/.." && pwd)}"
  SCRIPT_DIR="$ENTRY_DIR"
else
  export APP_ROOT="${APP_ROOT:-$ENTRY_DIR}"
  SCRIPT_DIR="$APP_ROOT/runners"
  [ -d "$SCRIPT_DIR" ] || SCRIPT_DIR="$APP_ROOT"
fi
python3 -m pip install -q groq 2>/dev/null || pip3 install -q groq 2>/dev/null || true
if [ -f "$SCRIPT_DIR/$TARGET" ]; then
  exec bash "$SCRIPT_DIR/$TARGET"
elif [ -f "$APP_ROOT/$TARGET" ]; then
  exec bash "$APP_ROOT/$TARGET"
else
  echo "ERROR: $TARGET not found under $APP_ROOT (flat or runners/)"
  ls -la "$APP_ROOT" "$APP_ROOT/runners" 2>/dev/null || true
  exit 1
fi
