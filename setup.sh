#!/bin/bash

SESSION="hive-swarm"

echo "🚀 Launching Fleet Command..."

# Use full path to tmux
TMUX="/usr/bin/tmux"

# Check if tmux exists
if ! command -v tmux &> /dev/null; then
    echo "❌ tmux not found. Installing..."
    apt update && apt install -y tmux
fi

$TMUX kill-session -t $SESSION 2>/dev/null || true

# Create workspaces
mkdir -p workspaces/backend workspaces/frontend workspaces/infra

# Simple approach - run claude without dangerous permissions
# It will prompt for permission when needed, which is actually safer

echo "🧠 Queen..."
$TMUX new-session -d -s $SESSION -c "$(pwd)" "bash -c 'claude; exec bash'"

echo "🔧 Backend..."
$TMUX split-window -h -c "$(pwd)/workspaces/backend" "bash -c 'claude; exec bash'"

echo "🎨 Frontend..." 
$TMUX split-window -v -c "$(pwd)/workspaces/frontend" "bash -c 'claude; exec bash'"

echo "🏗️ Infra..."
$TMUX select-pane -t 0
$TMUX split-window -v -c "$(pwd)/workspaces/infra" "bash -c 'claude; exec bash'"

# Configure layout
$TMUX set -g mouse on
$TMUX select-layout -t $SESSION tiled

echo "✅ Fleet launched successfully!"
echo "   All panes will stay open even if claude exits"
echo "   Layout: Perfect 2x2 grid"
echo ""
echo "Run 'make attach' to enter."