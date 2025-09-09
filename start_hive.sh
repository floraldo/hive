#!/bin/bash
set -e # Exit immediately if a command fails

echo "🐝 STARTING THE HIVE - ULTIMATE LAUNCH SCRIPT"
echo "============================================="

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

# --- STEP 2: PYTHON VENV SETUP ---
if [ ! -d ".venv-wsl" ]; then
    echo "🐍 WSL Python virtual environment not found. Creating..."
    python3 -m venv .venv-wsl
    echo "✅ WSL Virtual environment created."
fi

echo "🐍 Activating WSL Python virtual environment..."
source .venv-wsl/bin/activate

echo "📦 Installing/updating all Hive packages..."
# Install individual packages first to handle dependencies
if ! pip install --quiet -e packages/hive-logging; then
    echo "❌ ERROR: Failed to install hive-logging package."
    exit 1
fi

if ! pip install --quiet -e packages/hive-db; then
    echo "❌ ERROR: Failed to install hive-db package."
    exit 1
fi

if ! pip install --quiet -e packages/hive-deployment; then
    echo "❌ ERROR: Failed to install hive-deployment package."
    exit 1
fi

if ! pip install --quiet -e packages/hive-api; then
    echo "❌ ERROR: Failed to install hive-api package."
    exit 1
fi

# Now install main hivemind package
if ! pip install --quiet -e .; then
    echo "❌ ERROR: Failed to install Hive main package."
    exit 1
fi

# Install additional required dependencies
if ! pip install --quiet libtmux gitpython; then
    echo "❌ ERROR: Failed to install libtmux and gitpython."
    exit 1
fi

echo "✅ All packages are installed and ready."

# Verify critical tools are working
if ! make --version &> /dev/null; then
    echo "❌ ERROR: make command still not working after installation."
    exit 1
fi

if ! tmux -V &> /dev/null; then
    echo "❌ ERROR: tmux command still not working after installation."
    exit 1
fi

# --- STEP 3: LAUNCHING THE SWARM ---
echo "🚀 Launching the Hive Swarm in tmux..."

# Kill any existing session
tmux kill-session -t hive-swarm 2>/dev/null || true

# Start the swarm using the setup script
echo "Starting tmux session with Queen and Workers..."
./setup.sh
if [ $? -ne 0 ]; then
    echo "❌ ERROR: Failed to start tmux session. Check setup.sh script."
    exit 1
fi

# Wait for tmux session to be ready
sleep 3

# Verify tmux session is actually running
if ! tmux list-sessions | grep -q "hive-swarm"; then
    echo "❌ ERROR: Tmux session 'hive-swarm' failed to start properly."
    echo "Try running manually: ./setup.sh"
    exit 1
fi

echo "✅ Tmux session 'hive-swarm' is running!"
echo "   View the swarm: tmux attach -t hive-swarm"
echo ""

# --- STEP 4: LAUNCH THE QUEEN ---
echo "👑 LAUNCHING THE QUEEN ORCHESTRATOR..."
echo "====================================="
echo ""
echo "The Queen is now ready for her first mission!"
echo ""
echo "SUGGESTED FIRST MISSION (copy and paste when prompted):"
echo "-------------------------------------------------------"
echo "Add a GET /api/v1/ping endpoint to the apps/backend service. It should return JSON {\"status\": \"pong\", \"timestamp\": current_time}. Add a pytest test for this endpoint. After tests pass, create a Pull Request."
echo "-------------------------------------------------------"
echo ""

# Launch the orchestrator in the current terminal
python hive_cli.py run