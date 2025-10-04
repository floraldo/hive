#!/bin/bash
# Bypass Tracker - Logs and justifies --no-verify usage
#
# Purpose: Track when feature agents bypass pre-commit hooks
# Creates accountability and provides QA agent with cleanup priorities
#
# Usage: Automatically invoked when git commit --no-verify is used
# Output: Appends entry to .git/bypass-log.txt with timestamp and justification

set -euo pipefail

BYPASS_LOG=".git/bypass-log.txt"
COMMIT_MSG_FILE="$1"

# Check if this commit is bypassing pre-commit hooks
# Note: This script should be called from prepare-commit-msg hook
if git rev-parse --verify HEAD >/dev/null 2>&1; then
    # Not a bypass if pre-commit ran successfully
    # This script only triggers when --no-verify was used
    :
fi

# Function to prompt for justification
prompt_for_justification() {
    echo ""
    echo "=========================================="
    echo "Pre-commit hooks were bypassed (--no-verify)"
    echo "=========================================="
    echo ""
    echo "Please provide a one-line justification:"
    echo "Examples:"
    echo "  - 'WIP: Incomplete feature, will fix in next commit'"
    echo "  - 'Emergency hotfix: Production down, validating later'"
    echo "  - 'Blocked by false positive: Ruff issue #1234'"
    echo ""
    read -r -p "Justification: " justification

    if [ -z "$justification" ]; then
        echo "Error: Justification cannot be empty"
        exit 1
    fi

    echo "$justification"
}

# Only run if --no-verify was actually used
# We detect this by checking if SKIP env var contains our hooks
if [[ "${SKIP:-}" == *"pre-commit"* ]] || [[ "${PRE_COMMIT:-}" == "0" ]]; then
    # Get justification from user
    justification=$(prompt_for_justification)

    # Log the bypass
    timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    commit_hash="(pending)"
    author=$(git config user.name || echo "unknown")

    # Append to bypass log
    echo "$timestamp | $author | $justification" >> "$BYPASS_LOG"

    # Append justification to commit message
    echo "" >> "$COMMIT_MSG_FILE"
    echo "[BYPASS-JUSTIFICATION]: $justification" >> "$COMMIT_MSG_FILE"

    echo ""
    echo "Bypass logged to $BYPASS_LOG"
    echo "QA agent will review this bypass during next cleanup cycle."
    echo ""
fi

exit 0
