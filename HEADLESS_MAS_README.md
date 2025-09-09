# Hive Headless Multi-Agent System (MAS)

**🚀 The world's first fully autonomous Claude Code development system**

Transform your development workflow with AI agents that work 24/7, writing code, running tests, and deploying features without human intervention.

## 🎯 What is Hive Headless MAS?

Hive Headless MAS is an autonomous development system where specialized AI agents continuously:
- **Plan features** and break down work into tasks  
- **Write code** following best practices and project conventions
- **Run tests** and fix failures automatically
- **Create pull requests** with comprehensive documentation
- **Deploy changes** after validation and approval

**No REPL interaction needed** - agents execute tasks through headless Claude calls and coordinate via a persistent task queue.

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    HIVE ORCHESTRATOR                        │
│              (Task Assignment & Coordination)              │
└─────────────────────┬───────────────────────────────────────┘
                      │
           ┌──────────┴──────────┐
           │                     │
    ┌─────▼─────┐         ┌─────▼─────┐
    │ TASK QUEUE │◄────────┤ EVENTS LOG │
    │ tasks.json │         │events.jsonl│
    └─────┬─────┘         └───────────┘
           │
  ┌────────┴────────┐
  │                 │
┌─▼─┐  ┌──▼──┐  ┌──▼──┐  ┌──▼──┐
│👑 │  │ 🎨  │  │ 🔧  │  │ 🏗️ │
│QUEEN│ │FRONT│  │BACK │  │INFRA│
│    │  │END  │  │END  │  │     │
└───┘  └─────┘  └─────┘  └─────┘
```

### Core Components

#### 🧠 **Orchestrator** (`orchestrator.py`)
- **Central coordinator** managing task lifecycle
- **Worker assignment** based on skills and availability  
- **Status monitoring** and progress tracking
- **Event logging** for full system auditability

#### 👑 **Queen (Planner)**
- **Strategic planning** - analyzes repo and creates roadmaps
- **Task generation** - breaks down features into actionable items  
- **Quality assurance** - reviews completed work
- **Coordination** - ensures workers have clear instructions

#### 🎨 **Frontend Worker**  
- **React/Next.js development** - modern component-based UI
- **TypeScript implementation** - type-safe development
- **Responsive design** - mobile-first accessibility
- **Testing** - Jest + React Testing Library

#### 🔧 **Backend Worker**
- **Python/Flask/FastAPI** - robust API development
- **Database management** - SQLAlchemy ORM + migrations
- **API documentation** - OpenAPI/Swagger specs  
- **Security** - authentication, validation, best practices

#### 🏗️ **Infrastructure Worker**
- **Docker containerization** - multi-stage builds
- **CI/CD pipelines** - GitHub Actions automation
- **Monitoring** - health checks and logging
- **Deployment** - orchestration and scaling

## 🚀 Quick Start

### Prerequisites
- **Claude Code CLI** installed and configured
- **Python 3.8+** for orchestrator and workers
- **Git** for version control and branch management

### 1. Launch the System
```bash
# Simple one-command launch
python start_headless_mas.py

# Or quick background start  
python start_headless_mas.py quick
```

### 2. Create Your First Task
```bash
# Add a task via CLI
python hive_cli.py create-task "Add user authentication" \
  --description "Implement JWT-based auth with login/logout" \
  --tags "backend,security" \
  --priority "high" \
  --criteria "JWT working;Tests pass;API documented"
```

### 3. Monitor Progress
```bash
# Watch system status
python hive_cli.py status

# Monitor specific workers
python hive_cli.py workers

# View task progress
python hive_cli.py list-tasks --status in_progress
```

### 4. Watch the Magic
- **Queen** analyzes your task and creates detailed implementation plan
- **Backend worker** implements JWT authentication with tests
- **System** runs validation and creates pull request
- **You** review and approve the PR - fully implemented feature ready!

## 📋 Task Management

### Task Lifecycle
```
queued → assigned → in_progress → ready_for_review → completed
```

### Creating Tasks

**Via CLI:**
```bash
python hive_cli.py create-task "Build user dashboard" \
  --description "Create responsive dashboard with analytics" \
  --tags "frontend,ui" \
  --priority "normal" \
  --criteria "Responsive design;Charts working;Tests >80%"
```

**Via Direct JSON Edit:**
```json
{
  "id": "tsk_20250909_001",
  "title": "Add search functionality",
  "description": "Implement full-text search with filters",
  "tags": ["backend", "search"], 
  "priority": "high",
  "status": "queued",
  "acceptance_criteria": [
    "Search API endpoint returns relevant results",
    "Supports filtering by category and date",
    "Response time < 200ms for typical queries",
    "Full test coverage including edge cases"
  ]
}
```

### Task Properties

| Property | Description | Values |
|----------|-------------|---------|
| `status` | Current lifecycle stage | `queued`, `assigned`, `in_progress`, `ready_for_review`, `completed`, `failed`, `blocked` |
| `priority` | Urgency level | `critical`, `high`, `normal`, `low` |
| `tags` | Categorization | `frontend`, `backend`, `infra`, `testing`, `security`, etc. |
| `assignee` | Responsible worker | `queen`, `frontend`, `backend`, `infra` |
| `acceptance_criteria` | Success conditions | Array of measurable requirements |

## 🤖 Worker Specialization

### Queen (Strategic Planner)
**Capabilities:** `planning`, `task_generation`, `coordination`, `review`

**Typical Tasks:**
- Repository analysis and technical debt identification
- Feature roadmap planning and task breakdown  
- Code review and quality assurance
- Cross-team coordination and dependency management

**Example Prompt:**
```
Analyze the current codebase and create a 3-sprint development roadmap focusing on:
1. User authentication system
2. Core business logic implementation  
3. API performance optimization

Break down each sprint into specific, testable tasks.
```

### Frontend Worker
**Capabilities:** `react`, `nextjs`, `typescript`, `css`, `ui_components`, `testing`

**Typical Tasks:**
- Component development with modern React patterns
- Responsive UI implementation with CSS Grid/Flexbox
- TypeScript integration and type safety
- Jest/RTL test suite development

### Backend Worker  
**Capabilities:** `python`, `flask`, `fastapi`, `sqlalchemy`, `pytest`, `api_design`, `database`

**Typical Tasks:**
- RESTful API endpoint development
- Database schema design and migrations
- Authentication and authorization logic
- Comprehensive test coverage with pytest

### Infrastructure Worker
**Capabilities:** `docker`, `kubernetes`, `ci_cd`, `monitoring`, `deployment`, `devops`

**Typical Tasks:**
- Container orchestration and deployment
- CI/CD pipeline configuration
- Monitoring and logging setup
- Performance optimization and scaling

## 🎮 CLI Commands

### Task Management
```bash
# Create tasks
python hive_cli.py create-task "Task title" --tags "backend" --priority "high"

# List and filter tasks  
python hive_cli.py list-tasks --status "in_progress" --assignee "frontend"

# Task details
python hive_cli.py show-task tsk_20250909_001

# Update task properties
python hive_cli.py update-task tsk_20250909_001 --status "completed"
```

### System Monitoring
```bash
# Overall system status
python hive_cli.py status

# Worker status and heartbeats
python hive_cli.py workers --json

# View logs and events
python hive_cli.py logs --events --limit 20
python hive_cli.py logs --worker backend --limit 50
```

### Process Management
```bash
# Start orchestrator
python hive_cli.py start-orchestrator --background

# Start specific workers
python hive_cli.py start-worker queen --background
python hive_cli.py start-worker frontend --interval 10
```

## 📊 Monitoring & Observability

### Real-time Dashboard
```bash
# Live system status
python hive_cli.py status

# Example output:
🚀 Hive System Status
==================

📋 Tasks (47 total)
   ⏳ queued: 12
   🔄 in_progress: 3  
   ✅ ready_for_review: 2
   🎉 completed: 30

🤖 Workers
   💤 idle: 2
   🔄 working: 2

📊 Priority Distribution
   🔴 critical: 1
   🟡 high: 8
   🟢 normal: 32
   🔵 low: 6
```

### Event Stream Monitoring
```bash
python hive_cli.py logs --events --detailed

# Example output:
📝 Recent Events (10)
====================
2025-09-09T14:30:15Z |    backend | task_execution_start
  task_id: tsk_20250909_auth_001
  
2025-09-09T14:45:22Z |   frontend | task_completed  
  task_id: tsk_20250909_ui_003
  success: true
  files_changed: ['src/components/Dashboard.tsx', 'src/tests/Dashboard.test.tsx']
```

### Performance Metrics
- **Task completion rate** - tasks finished per hour/day
- **Worker utilization** - percentage of time workers are active  
- **Error rate** - failed tasks vs successful tasks
- **Cycle time** - average time from task creation to completion

## 🛡️ Safety & Quality Assurance

### Built-in Safety Features
- **Branch isolation** - each worker operates on separate git branches
- **Rollback capability** - all changes reversible via git
- **PR gates** - human approval required before merge
- **Comprehensive logging** - full audit trail of all actions
- **Error recovery** - automatic retry with exponential backoff

### Quality Standards
- **Test coverage** - minimum 80% for all new code
- **Code review** - automated analysis plus human approval
- **Security scanning** - dependency and vulnerability checks  
- **Performance monitoring** - response time and resource usage tracking

### Error Handling
```json
{
  "task_id": "tsk_20250909_001",
  "status": "failed", 
  "failure_reason": "Tests failed: authentication endpoint returns 500",
  "retry_count": 2,
  "next_retry": "2025-09-09T15:30:00Z",
  "execution_log": "hive/logs/backend_execution_20250909_143015.log"
}
```

## 🔧 Configuration

### Worker Configuration
Each worker has a JSON config file in `hive/workers/`:

```json
{
  "worker_id": "backend",
  "role": "backend_developer",
  "capabilities": ["python", "flask", "pytest", "database"],
  "max_concurrent_tasks": 1,
  "is_enabled": true,
  "config": {
    "claude_args": [
      "--add-dir", "./workspaces/backend",
      "--output-format", "stream-json",
      "--allowedTools", "Bash(python,pip,pytest,git),Read(*),Write(*),Edit(*)"
    ]
  }
}
```

### System Settings
Global settings in `hive/bus/tasks.json`:

```json
{
  "settings": {
    "max_concurrent_tasks": 4,
    "task_timeout_hours": 24, 
    "auto_assign": true,
    "require_acceptance_criteria": true,
    "retry_failed_tasks": 3,
    "notification_webhook": "https://hooks.slack.com/..."
  }
}
```

## 🎛️ Advanced Usage

### Custom Worker Roles
Create specialized workers for your domain:

1. **Add worker config** in `hive/workers/custom.json`
2. **Define capabilities** and tools in config
3. **Launch worker** with `python headless_workers.py custom`

### Integration Hooks
Connect with external systems:

```python
# Custom webhook for task completion
def task_completed_webhook(task):
    requests.post(SLACK_WEBHOOK, {
        "text": f"Task completed: {task['title']} by {task['assignee']}"
    })
```

### Parallel Development Branches
Scale to multiple parallel tracks:

```bash
# Launch additional workers for different features
python hive_cli.py start-worker frontend-mobile --interval 20
python hive_cli.py start-worker backend-api-v2 --interval 15
```

## 🚨 Troubleshooting

### Common Issues

**Workers not picking up tasks:**
```bash
# Check worker status
python hive_cli.py workers

# Verify task assignment
python hive_cli.py list-tasks --status assigned

# Restart problematic worker
pkill -f "headless_workers.py frontend"
python hive_cli.py start-worker frontend --background
```

**Task execution failures:**
```bash
# View execution logs
python hive_cli.py logs --worker backend --limit 100

# Check specific task details
python hive_cli.py show-task tsk_20250909_001

# Reset failed task
python hive_cli.py update-task tsk_20250909_001 --status queued
```

**Orchestrator not assigning tasks:**
```bash
# Check orchestrator logs
python hive_cli.py logs --events --limit 50

# Verify worker availability
python hive_cli.py workers --json

# Restart orchestrator
pkill -f orchestrator.py
python hive_cli.py start-orchestrator --background
```

### Debug Mode
Enable verbose logging:

```bash
export HIVE_DEBUG=1
python start_headless_mas.py
```

## 🔮 Roadmap & Extensions

### Phase 1: Foundation (Current)
- ✅ Core orchestrator and worker system
- ✅ Task queue and lifecycle management
- ✅ Basic safety and monitoring
- ✅ CLI management interface

### Phase 2: Intelligence (Next)
- 🔄 Advanced task prioritization algorithms
- 🔄 Worker performance optimization
- 🔄 Predictive failure detection
- 🔄 Resource usage optimization

### Phase 3: Integration (Future)
- 📋 MCP server integration for structured communication
- 📋 External API integrations (Slack, Jira, etc.)
- 📋 Multi-repository coordination
- 📋 Advanced deployment strategies

### Phase 4: Ecosystem (Vision)
- 📋 Worker marketplace and plugin system
- 📋 Cross-team collaboration features
- 📋 Enterprise security and compliance
- 📋 AI-powered code review and optimization

## 🤝 Contributing

This system is designed to be self-improving. The Queen agent continuously analyzes the codebase and suggests improvements. To contribute:

1. **Add tasks** via the CLI for features you want to see
2. **Review PRs** created by the autonomous system
3. **Provide feedback** through task acceptance criteria
4. **Monitor performance** and suggest optimizations

## 📄 License

This project is part of the Hive Fleet Command system and inherits the same licensing terms.

---

**🎯 Achievement Unlocked: You now have a fully autonomous development system that works while you sleep!**

The Hive Headless MAS represents a breakthrough in software development automation - a system that doesn't just assist with coding, but actively develops your application according to your specifications, maintaining quality standards and best practices throughout the process.

*Welcome to the future of autonomous software development.* 🚀