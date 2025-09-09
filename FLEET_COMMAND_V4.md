# Fleet Command v4.0 - Claude Code Multi-Agent System

**The world's first fully automated Claude Code Multi-Agent System with expect-based automation, persistent message bus, and real-time monitoring.**

## 🚀 What is Fleet Command?

Fleet Command v4.0 transforms Claude Code from a single-agent tool into a coordinated multi-agent system where AI agents can communicate, collaborate, and work autonomously without human intervention.

### Key Innovations

- **🤖 Full Automation**: No manual Enter presses - messages execute automatically
- **📡 Message Bus**: Persistent JSON-based inter-agent communication  
- **⚡ Expect Integration**: Robust retry logic with readiness detection
- **📊 Real-time Monitoring**: Live dashboard showing agent activity
- **🔧 Error Recovery**: Automatic fallback mechanisms and comprehensive testing

## 📋 Quick Start

```bash
# 1. Launch the fleet
make swarm

# 2. Send automated messages
./scripts/fleet_send.sh send frontend "Create a login component"
./scripts/fleet_send.sh broadcast "Fleet status report"

# 3. Use persistent message bus
./scripts/hive-send --to backend --topic task --message "Implement JWT auth"
./scripts/hive-recv --for backend --unread-only

# 4. Monitor the fleet
./scripts/hive-status --watch

# 5. Run full demonstration
./scripts/demo_automation.sh
```

## 🏗️ Architecture

### Fleet Structure (2x2 tmux Grid)
```
┌─────────────────┬─────────────────┐
│  Queen (0.0)    │  Frontend (0.1) │
│  🧠 Commander   │  🎨 React/Next  │
├─────────────────┼─────────────────┤
│  Backend (0.2)  │  Infra (0.3)    │
│  🔧 Python/API  │  🏗️ Docker/K8s │
└─────────────────┴─────────────────┘
```

### Communication Layers

1. **Direct Pane Injection** - Immediate execution via expect
2. **Persistent Message Bus** - JSON-based asynchronous communication
3. **Status Monitoring** - Real-time agent activity dashboard

## 🛠️ Core Tools

### Automation Scripts

| Script | Purpose | Example |
|--------|---------|---------|
| `fleet_send.sh` | Direct pane automation | `./scripts/fleet_send.sh send backend "Task"` |
| `hive-send` | Message bus sending | `./scripts/hive-send --to frontend --topic task` |
| `hive-recv` | Message bus receiving | `./scripts/hive-recv --for backend --unread-only` |
| `hive-status` | Fleet monitoring | `./scripts/hive-status --watch` |

### System Utilities

| Script | Purpose | Example |
|--------|---------|---------|
| `readiness_test.sh` | System validation | `./scripts/readiness_test.sh` |
| `test_automation.sh` | Comprehensive testing | `./scripts/test_automation.sh` |
| `demo_automation.sh` | Full demonstration | `./scripts/demo_automation.sh` |

## 📡 Message Bus System

### Message Structure
```json
{
  "id": "msg_1693123456_1234_5678",
  "timestamp": "2025-09-09T10:30:00.000Z",
  "from": "queen",
  "to": "backend", 
  "topic": "task",
  "priority": "high",
  "message": "Implement user authentication system",
  "status": "sent",
  "read": false
}
```

### Message Topics
- **task** - Task assignments and work items
- **status** - Progress reports and updates  
- **question** - Questions requiring responses
- **info** - General information sharing
- **alert** - Important notifications
- **general** - Default for misc messages

### Priority Levels
- **critical** - Immediate attention required
- **high** - Important, handle soon
- **normal** - Standard priority (default)
- **low** - Handle when convenient

## 🔧 Advanced Usage

### Large Message Handling
```bash
# Automatic chunking for large tasks
./scripts/fleet_send.sh send backend "$(cat large_task_description.md)"

# File-based message sending
./scripts/hive-send --to frontend --topic task --file requirements.md
```

### Broadcast Communication
```bash
# Send to all workers simultaneously
./scripts/fleet_send.sh broadcast "Fleet-wide announcement"

# Priority broadcast
./scripts/hive-send --to queen --topic alert --priority critical \
  --message "System maintenance in 5 minutes"
```

### Status Monitoring
```bash
# Real-time dashboard
./scripts/hive-status --watch

# Detailed breakdown
./scripts/hive-status --detailed

# Agent-specific status  
./scripts/hive-status --agent frontend
```

## 🧪 Testing & Validation

### System Tests
```bash
# Quick validation
./scripts/readiness_test.sh

# Comprehensive testing
./scripts/test_automation.sh

# Performance testing
./scripts/test_automation.sh performance
```

### Test Coverage
- ✅ Basic message delivery
- ✅ Large message chunking (>500 chars)
- ✅ Special character handling
- ✅ Error recovery scenarios
- ✅ Broadcast functionality
- ✅ Message bus persistence
- ✅ Status monitoring accuracy

## 📊 Monitoring & Diagnostics

### Fleet Status Dashboard
```bash
./scripts/hive-status --detailed --watch
```

**Sample Output:**
```
🚀 Fleet Command Message Bus Status
2025-09-09 14:30:15

System Overview:
  Total Messages: 42
  Unread Messages: 7
  Bus Directory: /path/to/bus

Agent Status:
AGENT        STATUS     | TOTAL | UNREAD | PRIORITY | RECENT
--------------------------------------------------------------
queen        READY      |    15 |      2 |        0 |      3
frontend     ACTIVE     |    12 |      3 |        1 |      5
backend      BUSY       |    18 |      8 |        2 |      7
infra        URGENT     |     9 |      4 |        3 |      2
```

### Message Bus Structure
```
bus/
├── messages/all.jsonl          # Complete message audit trail
├── queen/
│   ├── inbox.jsonl            # Queen's incoming messages
│   └── outbox.jsonl           # Queen's sent messages
├── frontend/
│   ├── inbox.jsonl            # Frontend messages
│   └── outbox.jsonl
├── backend/
│   ├── inbox.jsonl            # Backend messages
│   └── outbox.jsonl
└── infra/
    ├── inbox.jsonl            # Infra messages
    └── outbox.jsonl
```

## 🛡️ Security & Safety

### Built-in Safety Features
- **Permission Validation** - All tmux operations require explicit permissions
- **Agent Verification** - Invalid agents are rejected gracefully
- **Message Validation** - Empty or malformed messages handled properly
- **Error Recovery** - Automatic retries with exponential backoff
- **Audit Trail** - Complete message history in JSON format

### Security Best Practices
```bash
# Use scoped permissions instead of --dangerously-skip-permissions
CLAUDE_CMD="claude --allowedTools 'Bash(*:*)' --add-dir $(pwd)/workspaces/frontend"

# Monitor system activity
./scripts/hive-status --watch

# Regular testing
./scripts/test_automation.sh
```

## 🚀 Getting Started Tutorial

### Step 1: Launch Fleet
```bash
# Start the 2x2 tmux grid with all agents
make swarm
```

### Step 2: Verify System
```bash
# Check all agents are ready
./scripts/readiness_test.sh

# View fleet status
./scripts/hive-status
```

### Step 3: Send First Message
```bash
# Send automated message to frontend
./scripts/fleet_send.sh send frontend "Hello, Frontend Worker! Please acknowledge."

# Check the frontend pane (0.1) - message appears automatically!
```

### Step 4: Try Message Bus
```bash
# Send persistent message
./scripts/hive-send --to backend --topic task --priority high \
  --message "Implement health check endpoint at /api/health"

# Receive messages
./scripts/hive-recv --for backend --unread-only
```

### Step 5: Monitor Activity
```bash
# Start real-time monitoring
./scripts/hive-status --watch
```

### Step 6: Full Demo
```bash
# Experience all features
./scripts/demo_automation.sh
```

## 🔮 Advanced Scenarios

### Complex Mission Orchestration
```bash
# Queen orchestrates a full-stack feature
./scripts/fleet_send.sh send queen "Plan implementation of user authentication system"

# Queen delegates to workers
./scripts/hive-send --to backend --topic task --priority high \
  --message "[T101] Implement JWT authentication with refresh tokens"

./scripts/hive-send --to frontend --topic task --priority high \
  --message "[T102] Create login/register components with validation"

./scripts/hive-send --to infra --topic task --priority high \
  --message "[T103] Setup Redis for session management and Docker configs"
```

### Multi-Agent Collaboration
```bash
# Backend reports completion
./scripts/hive-send --to frontend --topic status \
  --message "AUTH API complete. Endpoints: /auth/login, /auth/refresh, /auth/logout"

# Frontend requests clarification  
./scripts/hive-send --to backend --topic question \
  --message "What's the exact JWT payload structure for user sessions?"

# Infra provides update
./scripts/hive-send --to queen --topic status \
  --message "Redis cluster ready. Docker compose updated with auth service config."
```

## 🎯 Use Cases

### Development Workflows
- **Feature Development** - Coordinate full-stack feature implementation
- **Code Reviews** - Distribute review tasks across specialized agents
- **Testing** - Orchestrate comprehensive test suites
- **Deployment** - Manage CI/CD pipeline coordination

### Team Coordination
- **Stand-ups** - Automated status collection from all agents
- **Task Distribution** - Intelligent work assignment based on expertise
- **Progress Tracking** - Real-time visibility into development progress
- **Issue Resolution** - Multi-agent problem-solving coordination

### CI/CD Integration
- **Build Coordination** - Parallel build processes across environments
- **Test Orchestration** - Distributed testing with result aggregation
- **Deployment Management** - Staged rollouts with automated verification
- **Monitoring** - Real-time system health across all components

## 🛠️ Customization

### Adding Custom Agents
1. Update `PANE_MAP` in `scripts/fleet_send.sh`
2. Add agent to validation arrays in message bus tools
3. Create workspace directory: `mkdir -p workspaces/new_agent`
4. Update setup.sh with new pane configuration

### Custom Message Topics
1. Add topic to help text in `hive-send` and `hive-recv`
2. Update validation arrays if strict topic enforcement desired
3. Document topic purpose and usage patterns

### Integration with External Systems
```bash
# Webhook integration
./scripts/hive-send --to infra --topic alert --priority critical \
  --message "$(curl -s https://api.service.com/status)"

# Database integration
./scripts/hive-send --to backend --topic task \
  --message "$(cat database_migration_plan.sql)"

# Slack/Discord notifications
./scripts/hive-recv --for queen --unread-only | \
  while read msg; do
    curl -X POST webhook_url -d "$msg"
  done
```

## 📚 Troubleshooting

### Common Issues

**Messages not executing automatically:**
```bash
# Check expect is installed
which expect

# Verify pane readiness
./scripts/readiness_test.sh expect

# Test with simple message
./scripts/fleet_send.sh test
```

**tmux session not found:**
```bash
# Launch the fleet first
make swarm

# Verify session exists
tmux list-sessions | grep hive-swarm
```

**Permission errors:**
```bash
# Check Claude Code permissions
# Ensure --dangerously-skip-permissions or proper allowedTools configuration
```

### Debug Mode
```bash
# Enable verbose logging in expect scripts
export DEBUG=1
./scripts/fleet_send.sh send frontend "debug message"

# Check tmux pane contents
./scripts/readiness_test.sh debug

# Monitor system activity
./scripts/hive-status --detailed --watch
```

## 🎉 Success Metrics

Fleet Command v4.0 delivers:
- **100% Automation** - Zero manual Enter presses required
- **Multi-Agent Coordination** - 4 specialized AI agents working in concert
- **Real-time Communication** - Instant message delivery with persistent bus
- **Enterprise Ready** - Comprehensive testing, monitoring, and error recovery
- **Scalable Architecture** - Easy to add agents and customize workflows

## 🔗 Resources

- **Setup Guide**: See setup.sh and make commands
- **Protocol Documentation**: .claude/CLAUDE.md  
- **Test Suite**: scripts/test_automation.sh
- **Live Demo**: scripts/demo_automation.sh
- **Status Monitoring**: scripts/hive-status --watch

## 🏆 Achievement Unlocked

**You now have the world's first fully automated Claude Code Multi-Agent System!** 

This represents a breakthrough in AI agent coordination, transforming individual Claude instances into a collaborative swarm intelligence capable of autonomous task execution, real-time communication, and coordinated problem-solving.

---

*Fleet Command v4.0 - Where Individual Intelligence Becomes Collective Capability* 🚀