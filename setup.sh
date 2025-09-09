#!/bin/bash
set -e # Exit immediately if a command fails

SESSION="hive-swarm"

# --- PREFLIGHT CHECK ---
# This safety check is critical for a smooth, error-free experience.
if [ "$EUID" -eq 0 ]; then
  echo "❌ ERROR: For a seamless experience, this script should be run as a non-root user (e.g., 'hiveuser')."
  echo "   The '--dangerously-skip-permissions' flag is disabled for the root user."
  echo "   Please switch users with 'su - hiveuser' and run this script again."
  exit 1
fi

# --- SESSION SETUP ---
echo "🚀 Creating Fleet Command session: $SESSION"
tmux kill-session -t $SESSION 2>/dev/null || true

# --- THE PERFECT & SIMPLE 2x2 GRID LOGIC ---
# 1. Create the session and the first two (top/bottom) panes
tmux new-session -d -s $SESSION -n "Fleet"
tmux split-window -v -t $SESSION:0

# 2. Select the top pane (0) and split it horizontally
tmux split-window -h -t $SESSION:0.0

# 3. Select the bottom pane (2) and split it horizontally
tmux split-window -h -t $SESSION:0.2

# This creates a perfect, predictable 2x2 grid. The panes are indexed:
# 0 (top-left), 1 (top-right), 2 (bottom-left), 3 (bottom-right)

# --- WORKSPACE SETUP ---
echo "📁 Creating workspace directories..."
mkdir -p workspaces/backend workspaces/frontend workspaces/infra

# --- CONFIGURATION & AGENT LAUNCH ---
tmux set-option -g mouse on
sleep 1

# Since we are NOT root, this flag will work perfectly for a seamless startup.
CLAUDE_CMD="claude --dangerously-skip-permissions"

echo "🧠 Starting Queen in Pane 0 (top-left)..."
tmux send-keys -t $SESSION:0.0 "$CLAUDE_CMD" C-m

echo "🎨 Starting Frontend Worker in Pane 1 (top-right)..."
tmux send-keys -t $SESSION:0.1 "cd workspaces/frontend && $CLAUDE_CMD" C-m

echo "🔧 Starting Backend Worker in Pane 2 (bottom-left)..."
tmux send-keys -t $SESSION:0.2 "cd workspaces/backend && $CLAUDE_CMD" C-m

echo "🏗️ Starting Infra Worker in Pane 3 (bottom-right)..."
tmux send-keys -t $SESSION:0.3 "cd workspaces/infra && $CLAUDE_CMD" C-m

echo ""
echo "✅ Hive Swarm is now fully operational."
echo "   All agents are online and awaiting commands."
echo "   Perfect 2x2 grid with seamless startup."
echo ""
echo "💡 Queen Command Examples (with auto-execute):"
echo "   tmux send-keys -t $SESSION:0.1 '[T101] Frontend task' C-m"
echo "   tmux send-keys -t $SESSION:0.2 '[T102] Backend task' C-m"  
echo "   tmux send-keys -t $SESSION:0.3 '[T103] Infra task' C-m"
echo ""
echo "📡 Attach with: tmux attach -t $SESSION"
echo "🚀 The factory is ready for production."