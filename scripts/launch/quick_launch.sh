#!/bin/bash
set -e

echo "🚀 QUICK HIVE LAUNCH"
echo "===================="

# Check if we're in the right directory
if [ ! -f "pyproject.toml" ]; then
    echo "❌ Run this from the hive root directory"
    exit 1
fi

# Install dependencies
echo "📦 Installing dependencies..."
pip install -e . > /dev/null 2>&1 || echo "Packages already installed"
pip install libtmux > /dev/null 2>&1 || echo "libtmux already installed"

# Create worktrees
echo "🌳 Setting up worktrees..."
mkdir -p workspaces
git worktree add workspaces/backend -b worker/backend 2>/dev/null || echo "Backend worktree exists"
git worktree add workspaces/frontend -b worker/frontend 2>/dev/null || echo "Frontend worktree exists" 
git worktree add workspaces/infra -b worker/infra 2>/dev/null || echo "Infra worktree exists"

# Check tmux
if ! command -v tmux &> /dev/null; then
    echo "❌ tmux not found. Install with: sudo apt install tmux"
    exit 1
fi

# Start tmux session
echo "🐝 Starting hive swarm..."
bash setup.sh &

# Wait a moment for tmux to start
sleep 2

# Launch Queen
echo "👑 Starting Queen orchestrator..."
echo "==============================================="
echo "FIRST MISSION (copy/paste this):"
echo "Add a GET /api/health endpoint to apps/backend that returns JSON: {\"status\": \"ok\", \"service\": \"backend\", \"timestamp\": current_time}. Include a pytest test."
echo "==============================================="

python hive_cli.py run