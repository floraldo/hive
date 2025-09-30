#!/bin/bash
# Quick Golden Rules validation for developers
# Run this before committing to check architectural compliance
#
# Usage:
#   ./scripts/check-golden-rules.sh              # Full validation
#   ./scripts/check-golden-rules.sh --incremental # Changed files only
#   ./scripts/check-golden-rules.sh --quick       # Quick mode
#   ./scripts/check-golden-rules.sh -i -q         # Incremental + quick

echo "🔍 Validating Golden Rules compliance..."
echo ""

# Default to incremental mode if no args provided
if [ $# -eq 0 ]; then
    echo "💡 Running incremental validation (changed files only)"
    echo "   Use --help to see all options"
    echo ""
    python scripts/validate_golden_rules.py --incremental
else
    python scripts/validate_golden_rules.py "$@"
fi

exit_code=$?

if [ $exit_code -eq 0 ]; then
    echo ""
    echo "✅ All Golden Rules passed!"
else
    echo ""
    echo "❌ Golden Rules violations detected"
    echo "Run 'python scripts/validate_golden_rules.py --help' for options"
fi

exit $exit_code