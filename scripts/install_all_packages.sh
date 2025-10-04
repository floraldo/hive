#!/usr/bin/env bash
# Install all Hive packages in dependency order
# Resolves ModuleNotFoundError issues in test collection

set -e

echo "=========================================="
echo "Installing Hive Platform Packages"
echo "=========================================="

cd "$(dirname "$0")/.."

# Phase 1: Core infrastructure packages (no inter-package dependencies)
echo ""
echo "[Phase 1] Core Infrastructure Packages"
echo "--------------------------------------"

for pkg in hive-logging hive-config hive-errors hive-async; do
    echo "Installing $pkg..."
    pip install -e "packages/$pkg"
done

# Phase 2: Platform services (depend on Phase 1)
echo ""
echo "[Phase 2] Platform Service Packages"
echo "------------------------------------"

for pkg in hive-cache hive-db hive-bus hive-performance; do
    echo "Installing $pkg..."
    pip install -e "packages/$pkg"
done

# Phase 3: Advanced infrastructure (depend on Phase 1-2)
echo ""
echo "[Phase 3] Advanced Infrastructure"
echo "----------------------------------"

for pkg in hive-service-discovery hive-deployment hive-app-toolkit; do
    echo "Installing $pkg..."
    pip install -e "packages/$pkg"
done

# Phase 4: Domain packages (depend on earlier phases)
echo ""
echo "[Phase 4] Domain Packages"
echo "-------------------------"

for pkg in hive-ai hive-orchestration hive-cli hive-graph hive-algorithms; do
    if [ -d "packages/$pkg" ]; then
        echo "Installing $pkg..."
        pip install -e "packages/$pkg"
    fi
done

# Phase 5: Testing utilities (depend on all packages)
echo ""
echo "[Phase 5] Testing Utilities"
echo "----------------------------"
pip install -e "packages/hive-tests"

echo ""
echo "=========================================="
echo "Installation Complete!"
echo "=========================================="
echo ""
echo "Verify installation:"
echo "  python -c 'import hive_logging, hive_config, hive_app_toolkit'"
echo ""
echo "Run test collection:"
echo "  python -m pytest --collect-only"
