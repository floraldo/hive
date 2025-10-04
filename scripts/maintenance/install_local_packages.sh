#!/usr/bin/env bash
#
# Install all Hive packages as editable installs in current environment
#
# This ensures pytest uses local development code, not stale site-packages

set -e

echo "=========================================="
echo "Installing Hive Packages (Editable Mode)"
echo "=========================================="
echo ""

# Get project root (script is in scripts/maintenance/)
PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$PROJECT_ROOT"

echo "Project root: $PROJECT_ROOT"
echo ""

# Install packages in dependency order
PACKAGES=(
    "hive-logging"
    "hive-config"
    "hive-errors"
    "hive-cache"
    "hive-async"
    "hive-db"
    "hive-bus"
    "hive-models"
    "hive-ai"
    "hive-performance"
    "hive-service-discovery"
    "hive-deployment"
    "hive-tests"
    "hive-orchestration"
    "hive-app-toolkit"
    "hive-algorithms"
    "hive-graph"
    "hive-cli"
)

for pkg in "${PACKAGES[@]}"; do
    if [ -d "packages/$pkg" ]; then
        echo "Installing $pkg (editable)..."
        pip install -e "packages/$pkg" --no-deps || echo "  Warning: $pkg install had issues"
    else
        echo "Skipping $pkg (not found)"
    fi
done

echo ""
echo "Installing dependencies for all packages..."
for pkg in "${PACKAGES[@]}"; do
    if [ -d "packages/$pkg" ]; then
        pip install -e "packages/$pkg" || echo "  Warning: $pkg dependencies had issues"
    fi
done

echo ""
echo "=========================================="
echo "Installation Complete"
echo "=========================================="
echo ""
echo "Verification:"
pip list | grep hive-
