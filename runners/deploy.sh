#!/usr/bin/env bash
# runners/deploy.sh
#
# Pushes implementation branch to GitHub and triggers Render deploy.
#
# Environment variables:
#   REPO_DIR          - Path to the repo with applied changes
#   GITHUB_TOKEN      - GitHub PAT
#   REPO_SLUG         - e.g., "superplanehq/superplane"
#   ISSUE_NUMBER      - Issue number for branch naming
#   RENDER_API_KEY    - Render API key
#   RENDER_SERVICE_ID - Render service ID

set -euo pipefail

REPO_DIR="${REPO_DIR:?REPO_DIR is required}"
GITHUB_TOKEN="${GITHUB_TOKEN:?GITHUB_TOKEN is required}"
REPO_SLUG="${REPO_SLUG:?REPO_SLUG is required}"
ISSUE_NUMBER="${ISSUE_NUMBER:?ISSUE_NUMBER is required}"
WORKDIR="$(dirname "$REPO_DIR")"

BRANCH_NAME="issueforge/${ISSUE_NUMBER}"

cd "$REPO_DIR"

echo "=== Creating branch $BRANCH_NAME ==="
git checkout -b "$BRANCH_NAME" 2>/dev/null || git checkout "$BRANCH_NAME"
git add -A
git commit -m "feat: implement issue #${ISSUE_NUMBER} [IssueForge]

Automated implementation by IssueForge software factory." || echo "Nothing to commit"

echo "=== Pushing to $REPO_SLUG ==="
git remote set-url origin "https://x-access-token:${GITHUB_TOKEN}@github.com/${REPO_SLUG}.git" 2>/dev/null || \
    git remote add origin "https://x-access-token:${GITHUB_TOKEN}@github.com/${REPO_SLUG}.git"
git push -u origin "$BRANCH_NAME" --force

COMMIT_SHA=$(git rev-parse HEAD)
echo "Pushed: $COMMIT_SHA"

# Trigger Render deploy
PREVIEW_URL=""
if [ -n "${RENDER_API_KEY:-}" ] && [ -n "${RENDER_SERVICE_ID:-}" ]; then
    echo "=== Triggering Render deploy ==="
    DEPLOY_RESPONSE=$(curl -s -X POST \
        "https://api.render.com/v1/services/${RENDER_SERVICE_ID}/deploys" \
        -H "Authorization: Bearer ${RENDER_API_KEY}" \
        -H "Content-Type: application/json" \
        -d "{\"clearCache\": \"do_not_clear\"}")

    DEPLOY_ID=$(python3 -c "import json; print(json.loads('''$DEPLOY_RESPONSE''').get('id','unknown'))" 2>/dev/null || echo "unknown")
    echo "Deploy ID: $DEPLOY_ID"

    echo "=== Waiting for deploy ==="
    for i in $(seq 1 30); do
        sleep 10
        STATUS=$(curl -s \
            "https://api.render.com/v1/services/${RENDER_SERVICE_ID}/deploys/${DEPLOY_ID}" \
            -H "Authorization: Bearer ${RENDER_API_KEY}" \
            | python3 -c "import sys,json; print(json.load(sys.stdin).get('status','pending'))" 2>/dev/null || echo "pending")

        echo "Status: $STATUS ($i/30)"
        if [ "$STATUS" = "live" ]; then
            break
        elif [ "$STATUS" = "build_failed" ] || [ "$STATUS" = "deactivated" ]; then
            echo "WARNING: Render deploy failed ($STATUS) — continuing without preview"
            break
        fi
    done

    PREVIEW_URL=$(curl -s \
        "https://api.render.com/v1/services/${RENDER_SERVICE_ID}" \
        -H "Authorization: Bearer ${RENDER_API_KEY}" \
        | python3 -c "import sys,json; s=json.load(sys.stdin); print(s.get('serviceDetails',{}).get('url', s.get('url','')))" 2>/dev/null || echo "")
fi

echo "=== Deploy complete ==="
cat > "$WORKDIR/deploy_result.json" << ENDJSON
{
    "branch": "$BRANCH_NAME",
    "commit_sha": "$COMMIT_SHA",
    "preview_url": "$PREVIEW_URL",
    "repo": "$REPO_SLUG"
}
ENDJSON
