#!/bin/bash
set -e # Exit immediately if a command fails

echo "🐝 HIVE IGNITION SEQUENCE - The Definitive Launch Script"
echo "======================================================="

# --- STEP 1: ENVIRONMENT VERIFICATION ---

echo "🔍 Verifying environment..."
if [ ! -f "pyproject.toml" ]; then
    echo "❌ ERROR: This script must be run from the root of the 'hive' repository."
    exit 1
fi

# Function to check for and install missing packages
install_if_missing() {
    if ! command -v $1 &> /dev/null; then
        echo "⚠️  $1 not found. Installing..."
        sudo apt update -qq && sudo apt install -y $2
        echo "✅ $1 is now installed."
    fi
}

install_if_missing make build-essential
install_if_missing tmux tmux
install_if_missing python3 python3-pip
install_if_missing pip3 python3-pip
install_if_missing python3 python3-venv

echo "✅ All required system packages are present."

# --- STEP 2: PYTHON VENV & SMART DEPENDENCY SETUP ---

VENV_DIR=".venv-wsl"
LOCK_FILE="$VENV_DIR/.install_lock"

if [ ! -d "$VENV_DIR" ]; then
    echo "🐍 WSL Python virtual environment not found. Creating at $VENV_DIR..."
    python3 -m venv $VENV_DIR
fi

echo "🐍 Activating WSL Python virtual environment..."
source $VENV_DIR/bin/activate

if [ ! -f "$LOCK_FILE" ]; then
    echo "📦 First-time setup: Installing all Hive packages. This may take a few minutes..."
    
    # Use sequential installation for maximum reliability
    pip install --quiet -r requirements.txt
    pip install --quiet -e packages/hive-logging
    pip install --quiet -e packages/hive-db
    pip install --quiet -e packages/hive-deployment
    pip install --quiet -e packages/hive-api
    pip install --quiet -e . # Install the main hivemind package
    
    echo "✅ All packages installed successfully."
    touch "$LOCK_FILE"
    
else
    echo "✅ Packages are already installed (lock file found)."
fi

# --- STEP 3: THE "ONE WORD" COMMAND SETUP (ALIAS) ---

ALIAS_CMD="alias hive='cd /mnt/c/git/hive && ./start_hive.sh'"
SHELL_CONFIG=""

if [ -f "$HOME/.bashrc" ]; then
    SHELL_CONFIG="$HOME/.bashrc"
elif [ -f "$HOME/.zshrc" ]; then
    SHELL_CONFIG="$HOME/.zshrc"
fi

if [ -n "$SHELL_CONFIG" ] && ! grep -q "alias hive=" "$SHELL_CONFIG"; then
    echo "🔧 Creating the 'hive' command for easy launching..."
    echo "" >> "$SHELL_CONFIG"
    echo "$ALIAS_CMD" >> "$SHELL_CONFIG"
    echo "✅ The 'hive' command has been created! Please restart your WSL terminal to use it."
    echo "   From now on, you can just type 'hive' to launch the system."
elif [ -n "$SHELL_CONFIG" ]; then
    echo "✅ The 'hive' command is already configured."
fi

# --- STEP 4: LAUNCHING THE SWARM & ORCHESTRATOR ---

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

# Launch the orchestrator in the current terminal, giving you direct control
make run