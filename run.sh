#!/usr/bin/env bash
# Run IssueForge using the project venv (Git Bash / WSL)
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON="$DIR/venv/Scripts/python.exe"
if [ ! -f "$PYTHON" ]; then
  PYTHON="$DIR/venv/bin/python"
fi
if [ ! -f "$PYTHON" ]; then
  echo "venv not found. Run: python -m venv venv && pip install -r requirements.txt" >&2
  exit 1
fi
exec "$PYTHON" "$DIR/run_local.py" "$@"
