#!/usr/bin/env bash
# runners/repo_analyzer.sh
#
# Clones the target repo, fetches the GitHub issue, finds relevant files,
# and builds the context payload for the Spec Agent.
#
# Environment variables:
#   ISSUE_URL        - GitHub issue URL (e.g., https://github.com/org/repo/issues/123)
#   GITHUB_TOKEN     - GitHub personal access token
#   WORKDIR          - Working directory for cloning (default: /tmp/issueforge)

set -euo pipefail

ISSUE_URL="${ISSUE_URL:?ISSUE_URL is required}"
GITHUB_TOKEN="${GITHUB_TOKEN:?GITHUB_TOKEN is required}"
WORKDIR="${WORKDIR:-/tmp/issueforge}"
SCRIPTS_DIR="$(cd "$(dirname "$0")/../scripts" && pwd)"

# Parse issue URL → owner/repo and issue number
REPO_SLUG=$(echo "$ISSUE_URL" | sed -n 's|.*github\.com/\([^/]*/[^/]*\)/issues/.*|\1|p')
ISSUE_NUMBER=$(echo "$ISSUE_URL" | sed -n 's|.*/issues/\([0-9]*\).*|\1|p')

if [ -z "$REPO_SLUG" ] || [ -z "$ISSUE_NUMBER" ]; then
    echo "ERROR: Could not parse issue URL: $ISSUE_URL"
    echo "Expected format: https://github.com/owner/repo/issues/123"
    exit 1
fi

echo "=== Issue: $REPO_SLUG#$ISSUE_NUMBER ==="

# Fetch issue details
echo "=== Fetching issue ==="
ISSUE_JSON="$WORKDIR/issue.json"
mkdir -p "$WORKDIR"

export GH_TOKEN="$GITHUB_TOKEN"
gh issue view "$ISSUE_NUMBER" \
    --repo "$REPO_SLUG" \
    --json number,title,body,labels \
    > "$ISSUE_JSON"

ISSUE_TITLE=$(python3 -c "import json; print(json.load(open('$ISSUE_JSON'))['title'])")
ISSUE_BODY=$(python3 -c "import json; print(json.load(open('$ISSUE_JSON'))['body'])")
echo "Issue: $ISSUE_TITLE"

# Clone repo (shallow)
REPO_DIR="$WORKDIR/repo"
if [ -d "$REPO_DIR" ]; then
    echo "=== Repo already cloned, pulling latest ==="
    cd "$REPO_DIR" && git pull --ff-only 2>/dev/null || true
else
    echo "=== Cloning $REPO_SLUG (shallow) ==="
    gh repo clone "$REPO_SLUG" "$REPO_DIR" -- --depth=1
fi

# Find relevant files
echo "=== Finding relevant files ==="
ISSUE_TEXT="$ISSUE_TITLE $ISSUE_BODY"
RELEVANT_JSON="$WORKDIR/relevant_files.json"
python3 "$SCRIPTS_DIR/find_relevant_files.py" "$REPO_DIR" "$ISSUE_TEXT" 15 > "$RELEVANT_JSON"

FILE_COUNT=$(python3 -c "import json; print(len(json.load(open('$RELEVANT_JSON'))))")
echo "Found $FILE_COUNT relevant files"

# Build full context
echo "=== Building agent context ==="
CONTEXT_FILE="$WORKDIR/context.txt"
python3 "$SCRIPTS_DIR/extract_context.py" "$REPO_DIR" "$ISSUE_JSON" "$RELEVANT_JSON" > "$CONTEXT_FILE"

CONTEXT_SIZE=$(wc -c < "$CONTEXT_FILE")
echo "Context size: $CONTEXT_SIZE bytes"

# Output summary
echo "=== Repo Analysis Complete ==="
cat > "$WORKDIR/analysis_result.json" << ENDJSON
{
    "repo": "$REPO_SLUG",
    "issue_number": $ISSUE_NUMBER,
    "issue_title": "$ISSUE_TITLE",
    "relevant_file_count": $FILE_COUNT,
    "context_size_bytes": $CONTEXT_SIZE,
    "context_file": "$CONTEXT_FILE",
    "issue_file": "$ISSUE_JSON",
    "relevant_files_file": "$RELEVANT_JSON",
    "repo_dir": "$REPO_DIR"
}
ENDJSON

echo "Analysis result written to $WORKDIR/analysis_result.json"
