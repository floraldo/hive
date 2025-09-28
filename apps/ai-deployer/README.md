# AI Deployer Agent

**Version**: 0.1.0
**Type**: Autonomous Daemon
**Purpose**: Complete the software development lifecycle by automatically deploying tested and approved applications

## Overview

The AI Deployer is the final piece in the Hive autonomous software agency, automatically handling deployment of applications that have passed review. It polls the database for `deployment_pending` tasks and executes deployments using various strategies.

## Architecture

### Core Components

```
apps/ai-deployer/
├── src/ai_deployer/
│   ├── agent.py              # Main async daemon
│   ├── deployer.py           # Deployment orchestration
│   ├── database_adapter.py   # Database operations
│   └── strategies/           # Deployment strategies
│       ├── ssh.py           # SSH-based deployment
│       ├── docker.py        # Docker container deployment
│       └── kubernetes.py    # Kubernetes deployment
└── tests/                   # Comprehensive test suite
```

### Task Flow

```
approved → deployment_pending → deploying → deployed/failed
         ↑                                  ↓
    ai-reviewer                        monitoring
```

## Deployment Strategies

### 1. SSH Strategy (Direct)
- **Use Case**: Traditional server deployments
- **Features**: File transfer, service management, rollback support
- **Requirements**: SSH access, target directory permissions

### 2. Docker Strategy (Rolling)
- **Use Case**: Containerized applications
- **Features**: Image building, container health checks, load balancer updates
- **Requirements**: Docker daemon access, image registry

### 3. Kubernetes Strategy (Canary)
- **Use Case**: Cloud-native applications
- **Features**: Manifest application, canary deployments, traffic shifting
- **Requirements**: Kubernetes cluster access, manifests

## Key Features

### ✅ Autonomous Operation
- Continuous polling for deployment tasks
- Automatic strategy selection based on task configuration
- Real-time status updates and progress tracking

### ✅ Multiple Deployment Strategies
- SSH for traditional deployments
- Docker for containerized applications
- Kubernetes for cloud-native workloads

### ✅ Robust Error Handling
- Automatic rollback on deployment failures
- Comprehensive health checking
- Detailed error reporting and logging

### ✅ Monitoring & Observability
- Post-deployment health validation
- Deployment metrics collection
- Event bus integration for notifications

### ✅ Production Ready
- Comprehensive test coverage (>80%)
- Golden Rules compliant architecture
- Proper error handling with hive-errors
- Structured logging with hive-logging

## Usage

### Running the Agent

```bash
# Production mode
python src/ai_deployer/agent.py

# Test mode (shorter polling intervals)
python src/ai_deployer/agent.py --test-mode

# Custom polling interval
python src/ai_deployer/agent.py --polling-interval 60
```

### Task Configuration

A deployment task requires:

```json
{
  "id": "task-001",
  "app_name": "web-application",
  "deployment_strategy": "direct|blue-green|rolling|canary",
  "source_path": "/path/to/application",
  "ssh_config": {
    "hostname": "deploy.example.com",
    "username": "deploy",
    "key_file": "/path/to/key.pem"
  },
  "environment": {
    "platform": "linux|docker|kubernetes",
    "has_load_balancer": true|false
  },
  "health_endpoint": "/health",
  "previous_deployment": {
    "backup": {...}
  }
}
```

## Integration Points

- **Database**: Uses `hive-db` for task management
- **Deployment**: Leverages `hive-deployment` for SSH operations
- **Logging**: Uses `hive-logging` for structured logs
- **Errors**: Implements `hive-errors` for resilient error handling
- **Event Bus**: Uses `hive-bus` for inter-agent communication

## Monitoring

The agent provides:
- Live status dashboard with Rich UI
- Deployment success/failure metrics
- Performance timing data
- Health check results
- Event-driven notifications

## Development

### Running Tests

```bash
cd apps/ai-deployer
PYTHONPATH=src python -m pytest tests/ -v
```

### Golden Rules Compliance

The AI Deployer follows all Hive Golden Rules:
- Apps → Packages dependency direction
- Proper async function naming
- hive-logging instead of print statements
- Type hints and docstrings
- Error handling standards

## Success Metrics

✅ **Autonomous polling** of deployment_pending tasks
✅ **Multiple deployment strategies** (SSH, Docker, Kubernetes)
✅ **Proper error handling** with automatic rollback
✅ **Golden Rules compliance** (no architectural violations)
✅ **Comprehensive test coverage** (>80%)
✅ **Integration** with existing agent ecosystem

## Next Steps

The AI Deployer completes the autonomous software agency vision:

1. **AI Planner** → Creates implementation plans
2. **Queen/Workers** → Execute development work
3. **AI Reviewer** → Reviews and approves code
4. **AI Deployer** → Deploys approved applications ← **YOU ARE HERE**

Your autonomous software agency is now complete and ready for end-to-end software delivery!