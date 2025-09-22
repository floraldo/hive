# Hive - Multi-Agent Orchestration System

A production-ready multi-agent development system using tmux-based Claude Code agents with Queen-Worker architecture.

## Architecture

- **Queen**: Architect/Orchestrator - Creates plans and delegates tasks
- **Worker1-Backend**: Backend implementation specialist  
- **Worker2-Frontend**: Frontend implementation specialist
- **Worker3-Infra**: Infrastructure and DevOps specialist

## Features

- ✅ Complete agent isolation via Git worktrees
- ✅ Structured communication protocol (STATUS/CHANGES/NEXT)
- ✅ Automated Git workflow with PR creation
- ✅ CI/CD integration with auto-merge capability
- ✅ Multiple safety kill-switches
- ✅ Comprehensive JSON logging
- ✅ Dry-run mode for safe testing

## Quick Start

### Prerequisites

- Git and GitHub CLI (`gh`) installed and authenticated
- Python 3.11+
- Claude CLI (`claude`) installed via npm
- Windows 10/11 or Unix-like system

### Windows Users

For Windows-specific setup instructions, see [Windows Setup Guide](docs/WINDOWS_SETUP.md).

### Setup

1. Clone the repository:
```bash
git clone https://github.com/YOUR_USERNAME/hive.git
cd hive
```

2. Create Python environment:
```bash
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

3. Set up GitHub repository and branch protection (one-time):
```bash
# Run the setup script (follow prompts)
./scripts/initial_setup.sh
```

4. Start the hive:
```bash
# Terminal 1: Start tmux session
./setup.sh

# Terminal 2: Run orchestrator
python run.py --dry-run  # Test mode first
python run.py             # Real execution
```

## Safety Features

- **Dry Run**: `python run.py --dry-run` - Simulate without changes
- **No Auto-merge**: `python run.py --no-auto-merge` - Manual PR merging
- **Hold Label**: Add "hold" label to any PR to prevent merge
- **Pause File**: Create `.ops/PAUSE` to stop all PR creation
- **Manual Override**: Configure branch protection to require reviewer

## Communication Protocol

All agents must end tasks with:
```
STATUS: success|partial|blocked|failed
CHANGES: <files changed or summary>
NEXT: <recommended next action>
```

## Project Structure

```
hive/
├── orchestrator/       # Core orchestration logic
├── plugins/           # GitOps and other plugins
├── agents/            # Agent configurations
├── workspaces/        # Isolated agent worktrees
├── logs/              # JSON logs
├── tests/             # Test suite
└── .github/           # CI/CD workflows
```

## License

MIT