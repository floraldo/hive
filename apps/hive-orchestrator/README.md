# Hive Orchestrator

The central orchestration engine for the Hive multi-agent system.

## Components

### Queen
The central coordinator that manages task distribution, worker lifecycle, and workflow orchestration. Supports parallel task execution and automatic worker scaling.

### Worker
Execution agents that perform tasks assigned by the Queen. Workers can run in various modes and handle different task types.

## Architecture

```
hive-orchestrator/
├── src/
│   └── hive_orchestrator/
│       ├── __init__.py
│       ├── queen.py       # Main orchestrator
│       ├── worker.py      # Worker implementation
│       └── cli.py         # Command-line interface
├── tests/
│   └── test_orchestration.py
└── pyproject.toml
```

## Usage

### Run the Queen
```bash
hive-queen --config /path/to/config.json
# or
poetry run hive-queen
```

### Run a Worker
```bash
hive-worker --mode backend --name worker1
# or
poetry run hive-worker
```

### CLI Interface
```bash
hive-orchestrator status
hive-orchestrator start-queen
hive-orchestrator spawn-worker --type backend
```

## Features

- **Parallel Task Execution**: Process multiple tasks concurrently
- **Dynamic Worker Management**: Automatically spawn and terminate workers
- **Workflow Support**: Complex multi-step task workflows
- **Database-Driven**: All state managed through hive-core-db
- **Configurable**: Flexible configuration for different deployment scenarios

## Dependencies

- `hive-core-db`: Database models and operations
- `hive-logging`: Centralized logging
- `hive-config`: Configuration management
- `hive-deployment`: Deployment utilities