# Shared jq helpers for SuperPlane runnerBash scripts.
# Source: . "$(dirname "$0")/sp_common.sh"

issue_url_from_payload() {
  jq -r '
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

claude_text() {
  local node="$1"
  jq -r --arg n "$node" '
    (.[$n].data.text?) //
    (.[$n].data[0].text?) //
    empty
  ' "$SUPERPLANE_PAYLOAD_FILE"
}
