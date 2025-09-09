#!/bin/bash
set -e # Exit immediately if a command fails

echo "🐝 HIVE IGNITION SEQUENCE - The Definitive Launch Script"
echo "======================================================="

# --- STEP 1: ENVIRONMENT VERIFICATION ---
echo "🔍 Verifying environment..."

if [ ! -f "pyproject.toml" ]; then
    echo "❌ ERROR: This script must be run from the root of the 'hive' repository."
    echo "Run this from: /mnt/c/git/hive"
    exit 1
fi

if ! command -v tmux &> /dev/null; then
    echo "⚠️  tmux not found. Attempting to install..."
    sudo apt update && sudo apt install tmux -y
    echo "✅ tmux installed."
fi

if ! command -v make &> /dev/null; then
    echo "⚠️  make not found. Installing build-essential (includes make, gcc, g++)..."
    sudo apt update -qq && sudo apt install build-essential -y
    echo "✅ build-essential installed."
fi

# Check for Python3 and related tools
if ! command -v python3 &> /dev/null; then
    echo "⚠️  python3 not found. Installing..."
    sudo apt install python3 python3-pip python3-venv -y
    echo "✅ Python3 tools installed."
elif ! command -v pip3 &> /dev/null || ! python3 -m venv --help &> /dev/null; then
    echo "⚠️  pip3 or venv missing. Installing python3 tools..."
    sudo apt install python3-pip python3-venv -y
    echo "✅ Python3 tools updated."
fi

# --- STEP 2: PYTHON VENV & DEPENDENCY SETUP ---

VENV_DIR=".venv-wsl"
LOCK_FILE="$VENV_DIR/.install_lock"

if [ ! -d "$VENV_DIR" ]; then
    echo "🐍 WSL Python virtual environment not found. Creating at $VENV_DIR..."
    python3 -m venv $VENV_DIR
    echo "✅ Virtual environment created."
fi

echo "🐍 Activating WSL Python virtual environment..."
source $VENV_DIR/bin/activate

# --- THE NEW "SMART INSTALL" LOGIC ---

if [ ! -f "$LOCK_FILE" ]; then
    echo "📦 First-time setup: Installing all Hive packages. This may take a few minutes..."
    
    # Install individual packages first to handle dependencies
    echo "Installing hive-logging..."
    pip install --quiet -e packages/hive-logging
    
    echo "Installing hive-db..."
    pip install --quiet -e packages/hive-db
    
    echo "Installing hive-deployment..."
    pip install --quiet -e packages/hive-deployment
    
    echo "Installing hive-api..."
    pip install --quiet -e packages/hive-api
    
    echo "Installing main hivemind package..."
    pip install --quiet -e .
    
    echo "Installing additional dependencies (libtmux, gitpython)..."
    pip install --quiet libtmux gitpython
    
    echo "✅ All packages installed successfully."
    echo "   Creating install lock file to speed up future launches."
    touch "$LOCK_FILE"
    
else
    echo "✅ All packages are already installed (lock file found). Skipping installation."
fi

# --- END OF NEW LOGIC ---

# Verify critical tools are working
if ! make --version &> /dev/null; then
    echo "❌ ERROR: make command still not working after installation."
    exit 1
fi

if ! tmux -V &> /dev/null; then
    echo "❌ ERROR: tmux command still not working after installation."
    exit 1
fi

# --- STEP 3: LAUNCHING THE SWARM & ORCHESTRATOR ---

echo "🚀 Launching the Hive Swarm in a new tmux session..."
make swarm

echo "✅ Tmux session 'hive-swarm' is running in the background."
echo "   You can attach to it to watch the agents with: tmux attach -t hive-swarm"
echo ""
echo "---"
echo ""

echo "👑 Launching the Queen Orchestrator in this terminal..."
echo "   The Queen is now ready and awaits your command."
echo "---"

# Launch the orchestrator in the current terminal
make run