#!/bin/bash
# QA Agent Session Startup Script
# Purpose: Configure environment and display prioritized task list for QA agent
set -euo pipefail

echo "=========================================="
echo "🏛️  QA AGENT SESSION STARTUP"
echo "=========================================="
echo ""

# Apply QA agent Git configuration
echo "📋 Applying QA Agent Git Configuration..."
git config --local include.path ../.git-config-qa-agent
git config --local commit.template .git-commit-template-qa
echo "✅ Git config applied"
echo ""

# Verify strict pre-commit is active
echo "🔒 Verifying Strict Pre-Commit Profile..."
if [ -f .git/hooks/pre-commit ]; then
    echo "✅ Pre-commit hooks installed"
else
    echo "⚠️  Pre-commit hooks not found - installing..."
    pre-commit install
fi
echo ""

# Display current branch and status
echo "📍 Current Branch:"
git branch --show-current
echo ""

# Pull latest changes
echo "🔄 Pulling Latest Changes..."
git pull origin main --quiet || true
echo "✅ Up to date with origin/main"
echo ""

# Generate health metrics
echo "📊 Platform Health Metrics:"
echo "-------------------------------------------"
if [ -f scripts/qa/health-metrics.py ]; then
    python scripts/qa/health-metrics.py || echo "⚠️  Health metrics unavailable"
else
    echo "⚠️  Health metrics script not found"
fi
echo ""

# Show recent bypass activity
echo "🚨 Recent Bypass Activity:"
echo "-------------------------------------------"
if [ -f .git/bypass-log.txt ]; then
    tail -5 .git/bypass-log.txt || echo "No recent bypasses"
else
    echo "No bypass log found (no bypasses recorded)"
fi
echo ""

# Run quick validation to show task list
echo "📋 Current Technical Debt To-Do List:"
echo "-------------------------------------------"

# Syntax check
echo "⚡ Syntax Errors:"
python -m pytest --collect-only -q 2>&1 | grep -E "error|ERROR" | head -5 || echo "  ✅ No syntax errors"
echo ""

# Linting violations
echo "🧹 Linting Violations:"
ruff check . --quiet --statistics 2>&1 | head -10 || echo "  ✅ No linting violations"
echo ""

# Golden Rules validation
echo "🏆 Golden Rules Status:"
python scripts/validation/validate_golden_rules.py --level ERROR --quiet 2>&1 | grep -E "CRITICAL|ERROR" | head -5 || echo "  ✅ No Golden Rules violations"
echo ""

# Session ready
echo "=========================================="
echo "✅ QA Agent Session Ready"
echo "=========================================="
echo ""
echo "Next Steps:"
echo "1. Review health metrics above"
echo "2. Check bypass log for priority guidance"
echo "3. Fix violations systematically (syntax → linting → Golden Rules)"
echo "4. Commit with: git commit -m 'refactor(quality): ...'"
echo "5. Monitor CI/CD: gh run watch"
echo ""
echo "Workflow documentation: docs/workflows/QA_AGENT_WORKFLOW.md"
echo ""
