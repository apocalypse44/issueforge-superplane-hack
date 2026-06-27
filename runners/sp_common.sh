# Shared jq helpers for SuperPlane runnerBash scripts.
# Source: . "$(dirname "$0")/sp_common.sh"

export OUTPUT_REPO="${OUTPUT_REPO:-apocalypse44/issueforge-superplane-hack}"

issue_url_from_payload() {
  jq -r '
    (.["Submit Issue"]? | .data.issue_url?) //
    (.["Submit Issue"]? | .data[0].issue_url?) //
    (.["Issue Webhook"]? | .data.body.issue_url?) //
    (.["Issue Webhook"]? | .data.body.issueUrl?) //
    (.["Issue Webhook"]? | .data[0].body.issue_url?) //
    (.. | objects | select(has("issue_url")) | .issue_url) //
    empty
  ' "$SUPERPLANE_PAYLOAD_FILE" | head -1
}

result_field() {
  local node="$1" field="$2"
  jq -r --arg n "$node" --arg f "$field" '
    (.[$n].data.result[$f]?) //
    (.[$n].data[0].result[$f]?) //
    empty
  ' "$SUPERPLANE_PAYLOAD_FILE"
}

# LLM output from claude.textPrompt (data.text) or Groq runner (data.result.text)
llm_text() {
  local node="$1"
  jq -r --arg n "$node" '
    (.[$n].data.text?) //
    (.[$n].data[0].text?) //
    (.[$n].data.result.text?) //
    (.[$n].data[0].result.text?) //
    empty
  ' "$SUPERPLANE_PAYLOAD_FILE"
}

claude_text() {
  llm_text "$1"
}

# App root: scripts live at Files root (flat) or legacy runners/ subfolder
resolve_app_root() {
  if [ -n "${APP_ROOT:-}" ] && { [ -f "${APP_ROOT}/sp_common.sh" ] || [ -f "${APP_ROOT}/runners/sp_common.sh" ]; }; then
    echo "$APP_ROOT"
    return
  fi
  local dir
  dir="$(cd "$(dirname "$1")" && pwd)"
  if [ -f "$dir/sp_common.sh" ]; then
    echo "$(cd "$dir/.." && pwd)"
  elif [ -f "$dir/../sp_common.sh" ]; then
    echo "$(cd "$dir/.." && pwd)"
  else
    echo "$(cd "$dir/.." && pwd)"
  fi
}

stages_py_path() {
  local root="$1"
  if [ -f "$root/superplane_stages.py" ]; then
    echo "$root/superplane_stages.py"
  else
    echo "$root/scripts/superplane_stages.py"
  fi
}
