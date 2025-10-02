#!/bin/bash
# Setup script for Hive platform conda environment
# Creates Python 3.11 environment with all necessary dependencies

set -e  # Exit on error

echo "============================================================"
echo "Hive Platform Environment Setup"
echo "============================================================"
echo ""

# Find conda executable
CONDA_CMD=""
if command -v conda &> /dev/null; then
    CONDA_CMD="conda"
elif [ -f "/c/Users/flori/Anaconda/Scripts/conda.exe" ]; then
    CONDA_CMD="/c/Users/flori/Anaconda/Scripts/conda.exe"
elif [ -f "$HOME/Anaconda3/Scripts/conda.exe" ]; then
    CONDA_CMD="$HOME/Anaconda3/Scripts/conda.exe"
else
    echo "[ERROR] Conda not found"
    echo "Please ensure Anaconda/Miniconda is installed"
    exit 1
fi

echo "[1/5] Creating 'hive' conda environment with Python 3.11..."
"$CONDA_CMD" create -n hive python=3.11 -y

echo ""
echo "[2/5] Activating 'hive' environment..."
# Source conda.sh to enable conda activate in script
CONDA_BASE=$("$CONDA_CMD" info --base)
source "$CONDA_BASE/etc/profile.d/conda.sh"
conda activate hive

echo ""
echo "[3/5] Installing Poetry..."
pip install poetry

echo ""
echo "[4/5] Configuring Poetry to use conda environment..."
poetry config virtualenvs.create false

echo ""
echo "[5/5] Installing project dependencies..."
cd /c/git/hive/apps/ecosystemiser
poetry install || {
    echo "[WARNING] Poetry install encountered issues"
    echo "You can retry with: conda activate hive && cd /c/git/hive/apps/ecosystemiser && poetry install"
}

echo ""
echo "============================================================"
echo "Setup Complete!"
echo "============================================================"
echo ""
echo "Next steps:"
echo "  1. Restart your shell or run: source ~/.bashrc"
echo "  2. Activate environment: conda activate hive"
echo "  3. Verify Python: python --version  (should be 3.11.x)"
echo "  4. Test imports: python -c \"from hive_db import get_sqlite_connection; print('SUCCESS')\""
echo "  5. Run validation: cd /c/git/hive/apps/ecosystemiser && python scripts/validate_database_logging.py"
echo ""
echo "To use this environment in VSCode/IDEs:"
echo "  - Select Python interpreter: ~/Anaconda/envs/hive/bin/python"
echo "  - Or let IDE auto-detect the 'hive' conda environment"
echo ""
