#!/usr/bin/env bash
# runners/verifier.sh
#
# Applies LLM-generated file changes to the repo, then builds and tests.
# On failure, calls the Fix Agent (via Groq API) and retries up to MAX_RETRIES times.
#
# Environment variables:
#   CHANGES_JSON     - Path to JSON file with file changes array
#   REPO_DIR         - Path to the cloned repo
#   SPEC_JSON        - Path to the spec JSON
#   CONTEXT_FILE     - Path to the repo context file
#   GROQ_API_KEY     - For fix agent calls
#   MAX_RETRIES      - Max repair attempts (default: 3)
#   FACTORY_TEST_MODE - If "1", skip LLM repair

set -euo pipefail

CHANGES_JSON="${CHANGES_JSON:?CHANGES_JSON is required}"
REPO_DIR="${REPO_DIR:?REPO_DIR is required}"
MAX_RETRIES="${MAX_RETRIES:-3}"
SCRIPTS_DIR="$(cd "$(dirname "$0")/../scripts" && pwd)"
PROMPTS_DIR="$(cd "$(dirname "$0")/../prompts" && pwd)"
WORKDIR="$(dirname "$CHANGES_JSON")"

ATTEMPT=1

apply_changes() {
    local changes_file="$1"
    echo "=== Applying file changes ==="
    python3 "$SCRIPTS_DIR/apply_patches.py" "$REPO_DIR" "$changes_file"
}

run_checks() {
    local dir="$1"
    local log_file="$2"
    cd "$dir"

    echo "=== Installing dependencies ===" | tee -a "$log_file"
    npm install 2>&1 | tail -20 | tee -a "$log_file"

    echo "=== Running build ===" | tee -a "$log_file"
    if grep -q '"build"' package.json 2>/dev/null; then
        npm run build 2>&1 | tee -a "$log_file"
    elif grep -q '"tsc"' package.json 2>/dev/null; then
        npx tsc --noEmit 2>&1 | tee -a "$log_file"
    else
        echo "No build script found, checking TypeScript..." | tee -a "$log_file"
        if [ -f "tsconfig.json" ]; then
            npx tsc --noEmit 2>&1 | tee -a "$log_file"
        fi
    fi

    if grep -q '"lint"' package.json 2>/dev/null; then
        echo "=== Running lint ===" | tee -a "$log_file"
        npm run lint 2>&1 | tee -a "$log_file" || true
    fi

    if grep -q '"test"' package.json 2>/dev/null; then
        echo "=== Running tests ===" | tee -a "$log_file"
        npm test -- --watchAll=false 2>&1 | tee -a "$log_file" || npm test 2>&1 | tee -a "$log_file"
    fi

    echo "=== All checks passed ===" | tee -a "$log_file"
}

call_fix_agent() {
    local error_log="$1"
    local output_file="$2"

    python3 << 'PYEOF'
import json
import os
from groq import Groq

client = Groq(api_key=os.environ["GROQ_API_KEY"])

fix_prompt_path = os.environ["FIX_PROMPT_PATH"]
spec_path = os.environ.get("SPEC_PATH", "")
changes_path = os.environ["CHANGES_PATH"]
error_log_path = os.environ["ERROR_LOG_PATH"]
context_path = os.environ.get("CONTEXT_PATH", "")
output_path = os.environ["OUTPUT_PATH"]

with open(fix_prompt_path) as f:
    system_prompt = f.read()

spec = ""
if spec_path and os.path.isfile(spec_path):
    with open(spec_path) as f:
        spec = f.read()

with open(changes_path) as f:
    changes = f.read()

with open(error_log_path) as f:
    errors = f.read()

context_text = ""
if context_path and os.path.isfile(context_path):
    with open(context_path) as f:
        context_text = f.read()[:40000]

user_message = f"""## Specification
{spec}

## Applied File Changes
{changes}

## Build/Test Error Output
{errors}

## Repository Context
{context_text}

Fix the errors and return the corrected file changes as a JSON array."""

response = client.chat.completions.create(
    model="llama-3.3-70b-versatile",
    max_tokens=16384,
    messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ],
)

text = response.choices[0].message.content
start = text.find("[")
end = text.rfind("]") + 1
fixed = json.loads(text[start:end])

with open(output_path, "w") as f:
    json.dump(fixed, f, indent=2)

print(f"Fix agent returned {len(fixed)} file changes")
PYEOF
}

# Main loop
echo "=== Verifier: Starting (max $MAX_RETRIES attempts) ==="

CURRENT_CHANGES="$CHANGES_JSON"

while [ "$ATTEMPT" -le "$MAX_RETRIES" ]; do
    echo "=== Attempt $ATTEMPT of $MAX_RETRIES ==="

    apply_changes "$CURRENT_CHANGES"

    ERROR_LOG="$WORKDIR/build_errors_attempt_${ATTEMPT}.log"
    > "$ERROR_LOG"

    if run_checks "$REPO_DIR" "$ERROR_LOG" 2>&1; then
        echo "=== VERIFICATION PASSED (attempt $ATTEMPT) ==="
        cat > "$WORKDIR/verify_result.json" << ENDJSON
{
    "status": "pass",
    "attempts": $ATTEMPT
}
ENDJSON
        exit 0
    fi

    echo "=== Build/test failed on attempt $ATTEMPT ==="

    if [ "$ATTEMPT" -ge "$MAX_RETRIES" ]; then
        echo "=== VERIFICATION FAILED after $MAX_RETRIES attempts ==="
        LAST_ERRORS=$(tail -50 "$ERROR_LOG" | tr '"' "'" | tr '\n' ' ')
        cat > "$WORKDIR/verify_result.json" << ENDJSON
{
    "status": "fail",
    "attempts": $ATTEMPT,
    "last_error": "$LAST_ERRORS"
}
ENDJSON
        exit 1
    fi

    if [ "${FACTORY_TEST_MODE:-0}" = "1" ]; then
        echo "Test mode: skipping LLM fix"
        exit 1
    fi

    echo "=== Calling Fix Agent ==="
    FIXED_CHANGES="$WORKDIR/fixed_changes_attempt_${ATTEMPT}.json"

    export FIX_PROMPT_PATH="$PROMPTS_DIR/fix_agent.md"
    export SPEC_PATH="${SPEC_JSON:-}"
    export CHANGES_PATH="$CURRENT_CHANGES"
    export ERROR_LOG_PATH="$ERROR_LOG"
    export CONTEXT_PATH="${CONTEXT_FILE:-}"
    export OUTPUT_PATH="$FIXED_CHANGES"

    call_fix_agent "$ERROR_LOG" "$FIXED_CHANGES"

    CURRENT_CHANGES="$FIXED_CHANGES"
    ATTEMPT=$((ATTEMPT + 1))

    # Reset repo to clean state before re-applying
    cd "$REPO_DIR"
    git checkout -- . 2>/dev/null || true
    git clean -fd 2>/dev/null || true
done
