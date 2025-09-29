#!/bin/bash
# Setup script for installing pre-commit hooks in the Hive platform

set -e

echo "==================================="
echo "Hive Platform Pre-commit Setup"
echo "==================================="

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed"
    exit 1
fi

# Install pre-commit if not already installed
if ! command -v pre-commit &> /dev/null; then
    echo "Installing pre-commit..."
    pip install --user pre-commit
else
    echo "pre-commit is already installed"
fi

# Install the git hooks
echo "Installing pre-commit hooks..."
pre-commit install

# Run hooks on all files to verify setup
echo "Running pre-commit on all files (first run may be slow)..."
pre-commit run --all-files || true

echo ""
echo "✅ Pre-commit hooks installed successfully!"
echo ""
echo "The following checks will run automatically on git commit:"
echo "  - Black (code formatting)"
echo "  - Ruff (linting)"
echo "  - isort (import sorting)"
echo "  - MyPy (type checking)"
echo "  - Bandit (security scanning)"
echo "  - Golden Rules validation"
echo "  - Unicode character detection"
echo "  - Async function naming convention"
echo ""
echo "To run hooks manually: pre-commit run --all-files"
echo "To skip hooks temporarily: git commit --no-verify"
