# Hive CLI Guide

The Hive CLI (`hive.py`) provides a unified interface for all Hive MAS operations. It wraps the existing modules (QueenOrchestrator, HiveStatus, CCWorker) without changing the core architecture.

## Quick Start

```bash
# Initialize the system and create sample task
python hive.py init --sample

# Start the Queen orchestrator (in one terminal)
export HIVE_DISABLE_PR=1  # For safe testing
python hive.py queen

# Monitor status (in another terminal)  
python hive.py status

# Watch events in real-time (optional third terminal)
python hive.py events:tail
```

## Command Reference

### System Commands

#### `init` - Initialize directory structure
```bash
python hive.py init [--sample]
```
- Creates all required directories (hive/, tasks/, results/, etc.)
- `--sample`: Creates a sample task for testing

#### `queen` - Run Queen orchestrator
```bash
python hive.py queen
```
- Starts the main orchestrator in foreground mode
- Handles task processing, worker spawning, and PR management
- Press Ctrl+C to stop

#### `status` - Status dashboard
```bash
python hive.py status [--refresh N]
```
- Shows real-time status of tasks, workers, and system health
- `--refresh N`: Set refresh interval in seconds (default: 2)
- Press Ctrl+C to stop

### Task Management

#### `task:add` - Add new task
```bash
python hive.py task:add --id TASK_ID --title "Task Title" [options]
```

**Required:**
- `--id`: Unique task identifier (e.g., tsk_001, feature_auth)
- `--title`: Human-readable task title

**Optional:**
- `--description "Text"`: Detailed task description
- `--tags tag1 tag2`: Space-separated tags
- `--priority P0|P1|P2|P3`: Priority level (default: P2)
- `--risk low|medium|high`: Risk assessment (default: low)
- `--front`: Add to front of queue instead of back

**Examples:**
```bash
# Basic task
python hive.py task:add --id auth_001 --title "Implement JWT authentication"

# Complex task with all options
python hive.py task:add --id api_refactor --title "Refactor user API" \
  --description "Split monolithic user service into microservices" \
  --tags backend api microservices --priority P1 --risk high --front
```

#### `task:queue` - Show task queue
```bash
python hive.py task:queue
```
- Displays current task queue with order and titles
- Shows which tasks are pending execution

#### `task:view` - View task details
```bash
python hive.py task:view --id TASK_ID
```
- Shows complete task information in JSON format
- Useful for debugging and verification

### Operator Controls

#### `hint:set` - Set guidance hint
```bash
python hive.py hint:set --id TASK_ID --text "Hint text"
```
- Provides guidance to workers for specific tasks
- Hints are read by workers during execution
- Useful for steering implementation approach

**Examples:**
```bash
python hive.py hint:set --id auth_001 --text "Use bcrypt for password hashing, keep middleware minimal"
python hive.py hint:set --id ui_component --text "Follow existing design system patterns"
```

#### `hint:clear` - Remove hint
```bash
python hive.py hint:clear --id TASK_ID
```

#### `interrupt:set` - Pause task execution
```bash
python hive.py interrupt:set --id TASK_ID --reason "Reason for interrupt"
```
- Causes the Queen to pause task processing at safe checkpoints
- Useful for review, direction changes, or blocking issues

**Examples:**
```bash
python hive.py interrupt:set --id auth_001 --reason "Wait for security review"
python hive.py interrupt:set --id deploy_prod --reason "Hold for approval"
```

#### `interrupt:clear` - Resume task execution
```bash
python hive.py interrupt:clear --id TASK_ID
```

### Worker Operations

#### `worker:oneshot` - Spawn one-shot worker
```bash
python hive.py worker:oneshot --role ROLE --id TASK_ID [options]
```

**Required:**
- `--role backend|frontend|infra`: Worker specialization
- `--id TASK_ID`: Task to work on

**Optional:**
- `--phase plan|apply|test`: Execution phase (default: apply)
- `--workspace PATH`: Override workspace directory
- `--run-id ID`: Override run identifier

**Examples:**
```bash
# Plan phase for backend task
python hive.py worker:oneshot --role backend --id auth_001 --phase plan

# Execute frontend task
python hive.py worker:oneshot --role frontend --id dashboard_ui

# Test phase with custom workspace
python hive.py worker:oneshot --role backend --id api_endpoint --phase test --workspace ./custom_workspace
```

#### `worker:local` - Local development mode (NEW)
```bash
python worker.py ROLE --local --task-id TASK_ID [options]
```

Run tasks directly without the Queen orchestrator - perfect for debugging and development.

**Required:**
- `ROLE`: Worker ID (backend|frontend|infra)
- `--local`: Enable local development mode
- `--task-id`: Task to execute

**Optional:**
- `--phase apply|test`: Execution phase (default: apply)
- `--workspace PATH`: Custom workspace directory
- `--run-id ID`: Custom run ID (auto-generated if not provided)

**Features:**
- **Auto-generated Run IDs**: Creates timestamped IDs like `local_20250911_143022`
- **Direct Execution**: No Queen orchestrator required
- **Full Logging**: Saves logs to `hive/logs/{task_id}/{run_id}.log`
- **Result Persistence**: Saves results to `hive/results/{task_id}/{run_id}.json`

**Examples:**
```bash
# Basic local execution
python worker.py backend --local --task-id hello_hive

# Test phase execution
python worker.py frontend --local --task-id user_auth --phase test

# Custom workspace for isolation
python worker.py infra --local --task-id docker_setup --workspace ./test_workspace

# With explicit run ID
python worker.py backend --local --task-id api_endpoint --run-id test_run_001
```

### Monitoring

#### `events:tail` - Watch event stream
```bash
python hive.py events:tail
```
- Shows real-time events from the message bus
- Displays worker activity, task progress, and system events
- Press Ctrl+C to stop

## Typical Workflows

### Development Workflow
```bash
# 1. Initialize system
python hive.py init --sample

# 2. Add your tasks
python hive.py task:add --id feature_123 --title "Add user profiles"

# 3. Set guidance if needed
python hive.py hint:set --id feature_123 --text "Keep it simple, focus on MVP"

# 4. Start Queen (with PR disabled for testing)
export HIVE_DISABLE_PR=1
python hive.py queen
```

### Production Workflow
```bash
# 1. Queue production tasks
python hive.py task:add --id hotfix_001 --title "Fix login bug" --priority P0 --front

# 2. Start Queen (with PRs enabled)
unset HIVE_DISABLE_PR  # or HIVE_DISABLE_PR=0
python hive.py queen

# 3. Monitor in another terminal
python hive.py status --refresh 5
```

### Manual Testing Workflow
```bash
# Test specific phase of a task manually
python hive.py worker:oneshot --role backend --id test_task --phase plan
python hive.py worker:oneshot --role backend --id test_task --phase apply  
python hive.py worker:oneshot --role backend --id test_task --phase test
```

### Local Development Workflow (NEW)
```bash
# 1. Create or modify a task
python hive.py task:add --id dev_feature --title "Development feature"

# 2. Run locally without Queen orchestrator
python worker.py backend --local --task-id dev_feature --phase apply

# 3. Check results
cat hive/results/dev_feature/local_*.json

# 4. Run tests locally
python worker.py backend --local --task-id dev_feature --phase test

# 5. Iterate as needed (auto-generates new run IDs)
python worker.py backend --local --task-id dev_feature --phase apply
```

This local mode is ideal for:
- **Rapid Development**: No need to start Queen orchestrator
- **Debugging**: Direct execution with full visibility
- **Testing**: Isolate and test individual tasks
- **CI/CD Integration**: Run tasks in automated pipelines

## Environment Variables

- `HIVE_DISABLE_PR=1`: Disable automatic PR creation (for testing)
- `CLAUDE_BIN=claude`: Override claude command path
- `HIVE_GIT_BASE=origin/develop`: Override base branch for worktrees

## Files and Directories

The CLI manages these directories automatically:
```
hive/
├── tasks/           # Individual task files (task_id.json)
│   └── index.json   # Task queue order
├── results/         # Worker execution results
├── bus/             # Event stream files (events_YYYYMMDD.jsonl)
└── operator/        # Human operator controls
    ├── hints/       # Task guidance files (task_id.md)
    └── interrupts/  # Task pause controls (task_id.json)
```

## Integration with Existing Scripts

The CLI is designed for gradual adoption:

- **Keep using existing scripts**: `python queen_orchestrator.py` still works
- **Mix approaches**: Use CLI for task management, existing scripts for orchestration
- **Full migration**: Eventually use only `python hive.py queen`

## Troubleshooting

### Common Issues

**Import errors**: Ensure you're in the project root directory
```bash
cd /path/to/hive && python hive.py --help
```

**Permission errors**: Make sure directories are writable
```bash
python hive.py init  # Re-initialize directories
```

**Worker timeouts**: Check claude binary is accessible
```bash
claude --version  # Verify claude command works
```

### Testing Installation

Run the comprehensive test suite:
```bash
./test_hive_cli.sh
```

## Next Steps

1. **Basic Setup**: Start with `python hive.py init --sample`
2. **Safe Testing**: Use `HIVE_DISABLE_PR=1` initially
3. **Add Real Tasks**: Use `task:add` for your actual work
4. **Monitor Progress**: Keep `status` and `events:tail` running
5. **Production Ready**: Remove `HIVE_DISABLE_PR` when confident

## Getting Help

```bash
# General help
python hive.py --help

# Command-specific help
python hive.py task:add --help
python hive.py worker:oneshot --help
```