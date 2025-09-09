#!/bin/bash
SESSION="hive-swarm"

# Kill existing session if it exists
tmux kill-session -t $SESSION 2>/dev/null || true

# Create new session with 4 panes (Queen + 3 Workers)
tmux new-session -d -s $SESSION -n "Hive"

# Create 3 additional panes (split horizontally then vertically)
tmux split-window -h -t $SESSION:0
tmux split-window -v -t $SESSION:0.0  
tmux split-window -v -t $SESSION:0.2

# Optional: Set pane titles if tmux version supports it
tmux send-keys -t $SESSION:0.0 "echo 'Queen Pane Ready'" C-m
tmux send-keys -t $SESSION:0.1 "echo 'Backend Worker Ready'" C-m  
tmux send-keys -t $SESSION:0.2 "echo 'Frontend Worker Ready'" C-m
tmux send-keys -t $SESSION:0.3 "echo 'Infra Worker Ready'" C-m

echo "✅ Tmux session '$SESSION' created with 4 panes"
echo "   Pane layout: Queen (top-left), Backend (top-right), Frontend (bottom-left), Infra (bottom-right)"