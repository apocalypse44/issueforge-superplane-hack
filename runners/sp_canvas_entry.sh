#!/usr/bin/env bash
# Run a runners/sp_*.sh script. Call after canvas bootstrap clones FILES_REPO to APP_ROOT.
set -euo pipefail
TARGET="${1:?usage: sp_canvas_entry.sh sp_fetch_issue.sh}"
APP_ROOT="${APP_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
export APP_ROOT
python3 -m pip install -q groq 2>/dev/null || pip3 install -q groq 2>/dev/null || true
exec bash "$APP_ROOT/runners/$TARGET"
