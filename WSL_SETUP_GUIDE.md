# WSL Setup Guide for Hive Swarm Activation

## Overview
The Hive swarm requires tmux, which is not available in Windows GitBash/MINGW64. You need to use WSL (Windows Subsystem for Linux) for the full swarm experience.

## Step-by-Step Setup

### 1. Install WSL (if not already installed)
```powershell
# Run in PowerShell as Administrator
wsl --install
```

### 2. Access Your Hive Project in WSL
```bash
# In WSL terminal
cd /mnt/c/git/hive
```

### 3. Install tmux in WSL
```bash
# Ubuntu/Debian
sudo apt update && sudo apt install tmux

# Or use the provided script
chmod +x setup_wsl.sh
./setup_wsl.sh
```

### 4. Verify Setup
```bash
python test_setup_simple.py
```

### 5. Start the Hive Swarm
```bash
# Terminal 1 (WSL): Start the swarm
make swarm

# Terminal 2 (WSL): Start orchestrator
make dry-run  # Test mode first
make run      # Production mode
```

## Alternative: Windows-Only Development

If you prefer to stay in Windows without WSL, you can:

1. **Direct Development**: Use this Claude Code instance for direct development
2. **Docker Development**: Use `make docker-up` for containerized development
3. **Manual Worker Coordination**: Work directly in the worktree directories

## Environment Variables in WSL

Your Windows environment variables should be accessible in WSL, but you can also set them directly:

```bash
# In WSL ~/.bashrc or ~/.zshrc
export OPENWEATHER_API_KEY="your-key-here"
```

## Next Steps

Once WSL is set up:
1. Run the Weather Widget mission: `python run.py`
2. Give the Queen this command: "Build a Weather Widget application following TDD protocol"
3. Watch the agents work in their tmux panes
4. Monitor progress through the orchestrator