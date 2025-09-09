#!/bin/bash
# WSL-specific setup script for tmux session

SESSION="hive-swarm"

# Kill existing session
tmux kill-session -t $SESSION 2>/dev/null

# Create new session with Queen pane
tmux new-session -d -s $SESSION -n "Hive"
tmux rename-pane -t $SESSION:0.0 "Queen"

# Create Worker panes
tmux split-window -h -t $SESSION:0
tmux rename-pane -t $SESSION:0.1 "Worker1-Backend"

tmux split-window -v -t $SESSION:0.0
tmux rename-pane -t $SESSION:0.2 "Worker2-Frontend"

tmux split-window -v -t $SESSION:0.1
tmux rename-pane -t $SESSION:0.3 "Worker3-Infra"

# For WSL, we need to navigate to the Windows git path
WIN_PATH="/mnt/c/git/hive"

# Queen operates from root (read-only overview)
tmux send-keys -t $SESSION:0.0 "cd $WIN_PATH && cc" C-m

# Workers in their isolated worktrees
tmux send-keys -t $SESSION:0.1 "cd $WIN_PATH/workspaces/backend && cc" C-m
tmux send-keys -t $SESSION:0.2 "cd $WIN_PATH/workspaces/frontend && cc" C-m
tmux send-keys -t $SESSION:0.3 "cd $WIN_PATH/workspaces/infra && cc" C-m

# Attach to session
tmux attach-session -t $SESSION