#!/usr/bin/env bash
# Fix Staged Files - The Boy Scout Rule Automation
#
# This script runs 'ruff --fix' ONLY on files currently staged for commit.
# This makes the incremental cleanup process intentional and visible.
#
# Usage: bash scripts/maintenance/fix-staged-files.sh
#
# Philosophy: Leave the code cleaner than you found it.

set -e

echo "========================================="
echo "Applying Boy Scout Rule to staged files"
echo "========================================="

# Get the list of staged Python files
STAGED_FILES=$(git diff --cached --name-only --diff-filter=ACM | grep ".py$" || true)

if [ -z "$STAGED_FILES" ]; then
    echo "No staged Python files to fix."
    echo "========================================="
    exit 0
fi

echo "Found $(echo "$STAGED_FILES" | wc -l) staged Python file(s)"
echo ""

# Run ruff --fix on ONLY those files
echo "Running ruff --fix on staged files..."
ruff check --fix $STAGED_FILES || true

# Re-stage the files that ruff may have modified
echo ""
echo "Re-staging fixed files..."
git add $STAGED_FILES

echo ""
echo "========================================="
echo "Auto-fixes applied and re-staged"
echo "Review changes: git diff --cached"
echo "Commit when ready: git commit -m '...'"
echo "========================================="
