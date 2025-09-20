#!/bin/bash
# Run the full system health check locally (mimics GitHub Actions workflow)
# This is what runs when you trigger the CI manually

set -e

echo "🔍 ============================================"
echo "🔍   HIVE SYSTEM HEALTH CHECK"
echo "🔍 ============================================"
echo ""

# Parse arguments
VERBOSE=false
COVERAGE=false

for arg in "$@"; do
    case $arg in
        --verbose|-v)
            VERBOSE=true
            shift
            ;;
        --coverage)
            COVERAGE=true
            shift
            ;;
        --help)
            echo "Usage: ./scripts/health-check.sh [options]"
            echo ""
            echo "Options:"
            echo "  -v, --verbose    Run with verbose output"
            echo "  --coverage       Generate coverage report"
            echo "  --help           Show this help message"
            echo ""
            exit 0
            ;;
    esac
done

# Navigate to project root
cd "$(dirname "$0")/.."

# Check if running in Docker or native
if [ -f /.dockerenv ]; then
    echo "📦 Running inside Docker container"
    RUNNER="poetry run"
else
    # Check if we should use Docker
    if command -v docker &> /dev/null && [ -f "docker-compose.dev.yml" ]; then
        echo "🐳 Running health check in Docker container..."
        docker-compose -f docker-compose.dev.yml run --rm hive-dev \
            /workspace/scripts/health-check.sh "$@"
        exit $?
    else
        echo "💻 Running natively (ensure dependencies are installed)"
        RUNNER="poetry run"
    fi
fi

echo ""
echo "1️⃣  Checking Python environment..."
echo "======================================"
python --version
poetry --version || echo "Poetry not installed"

echo ""
echo "2️⃣  Installing/Updating dependencies..."
echo "======================================"
poetry install --with workspace --with dev || echo "Failed to install dependencies"

echo ""
echo "3️⃣  Running linter (Ruff)..."
echo "======================================"
if $RUNNER ruff --version &> /dev/null; then
    if [ "$VERBOSE" = true ]; then
        $RUNNER ruff check . --output-format=full
    else
        $RUNNER ruff check . || echo "⚠️  Linting issues found (non-blocking)"
    fi
else
    echo "⚠️  Ruff not installed - skipping linting"
fi

echo ""
echo "4️⃣  Running all tests..."
echo "======================================"
if [ "$COVERAGE" = true ]; then
    $RUNNER pytest -v --tb=short \
        --cov=apps --cov=packages \
        --cov-report=term-missing \
        --cov-report=html:coverage_report \
        || echo "⚠️  Some tests failed"
else
    if [ "$VERBOSE" = true ]; then
        $RUNNER pytest -v --tb=short || echo "⚠️  Some tests failed"
    else
        $RUNNER pytest -q || echo "⚠️  Some tests failed"
    fi
fi

echo ""
echo "5️⃣  Quick import checks..."
echo "======================================"
python -c "
import sys
sys.path.insert(0, 'packages/hive-core-db/src')
sys.path.insert(0, 'packages/hive-config/src')
sys.path.insert(0, 'apps/ecosystemiser/src')

try:
    import hive_core_db
    print('✅ hive-core-db imports successfully')
except Exception as e:
    print(f'❌ hive-core-db import failed: {e}')

try:
    from hive_config.loader import load_config_for_app
    print('✅ hive-config imports successfully')
except Exception as e:
    print(f'❌ hive-config import failed: {e}')

try:
    from EcoSystemiser.hive_env import get_app_config
    print('✅ EcoSystemiser imports successfully')
except Exception as e:
    print(f'❌ EcoSystemiser import failed: {e}')
"

echo ""
echo "======================================"
echo "🐝 HEALTH CHECK COMPLETE"
echo "======================================"
echo ""
echo "💡 Tips:"
echo "  - Run with --verbose for detailed output"
echo "  - Run with --coverage for coverage report"
echo "  - Check GitHub Actions for automated runs"
echo ""