#!/bin/bash
# Install all hive packages in correct dependency order

packages=(
    "hive-logging"
    "hive-errors"
    "hive-config"
    "hive-async"
    "hive-performance"
    "hive-cache"
    "hive-db"
    "hive-bus"
    "hive-orchestration"
    "hive-deployment"
    "hive-service-discovery"
    "hive-cli"
    "hive-app-toolkit"
    "hive-algorithms"
    "hive-tests"
    "hive-ai"
)

echo "Installing all hive packages in editable mode..."
for pkg in "${packages[@]}"; do
    echo "Installing $pkg..."
    poetry run pip install -e "packages/$pkg" --no-deps --force-reinstall
done

echo "Installing all dependencies..."
poetry install --no-root

echo "Validation: Checking imports..."
poetry run python -c "from hive_ai import rag; from hive_performance import metrics; print('✓ All critical imports successful')"
