#!/bin/bash
# Poetry-only environment setup for Hive platform
# Clean, simple, one-tool approach

set -e

echo "============================================================"
echo "Hive Platform Setup (Poetry-only)"
echo "============================================================"
echo ""

# Check if Poetry is installed
if ! command -v poetry &> /dev/null; then
    echo "[1/3] Installing Poetry..."
    curl -sSL https://install.python-poetry.org | python3 -
    export PATH="$HOME/.local/bin:$PATH"
else
    echo "[1/3] Poetry already installed: $(poetry --version)"
fi

echo ""
echo "[2/3] Configuring Poetry for Python 3.11..."
cd /c/git/hive/apps/ecosystemiser

# Tell Poetry to use Python 3.11 (it will download if needed)
poetry env use python3.11 || poetry env use 3.11 || {
    echo ""
    echo "Python 3.11 not found. Installing via Poetry..."
    poetry env use python3.11
}

echo ""
echo "[3/3] Installing all dependencies..."
poetry install

echo ""
echo "============================================================"
echo "Setup Complete!"
echo "============================================================"
echo ""
echo "Poetry created a virtual environment with Python 3.11"
echo ""
echo "To activate:"
echo "  poetry shell"
echo ""
echo "Or run commands directly:"
echo "  poetry run python --version"
echo "  poetry run python scripts/validate_database_logging.py"
echo ""
echo "Your IDE should auto-detect the Poetry venv at:"
poetry env info --path
echo ""
