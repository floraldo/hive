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
    echo "⚠️  make not found. Attempting to install..."
    sudo apt install make -y
    echo "✅ make installed."
fi

# --- STEP 2: PYTHON VENV SETUP ---
if [ ! -d ".venv" ]; then
    echo "🐍 Python virtual environment not found. Creating..."
    python3 -m venv .venv
    echo "✅ Virtual environment created."
fi

echo "🐍 Activating Python virtual environment..."
source .venv/bin/activate

echo "📦 Installing/updating all Hive packages..."
pip install --quiet -e .
pip install --quiet libtmux

echo "✅ All packages are installed and ready."

# --- STEP 3: LAUNCHING THE SWARM ---
echo "🚀 Launching the Hive Swarm in tmux..."

# Kill any existing session
tmux kill-session -t hive-swarm 2>/dev/null || true

# Start the swarm using the setup script
echo "Starting tmux session with Queen and Workers..."
./setup.sh &

# Wait for tmux session to be ready
sleep 3

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