#!/bin/bash
# Quick Golden Rules validation for developers
# Run this before committing to check architectural compliance

echo "🔍 Validating Golden Rules compliance..."
echo ""

python scripts/validate_golden_rules.py "$@"

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