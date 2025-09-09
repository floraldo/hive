# Claude Code Multi-Agent System (cc MAS) Architecture Plan

## Vision: Autonomous Agent Communication Without Manual Oversight

The goal is to create a Claude Code Multi-Agent System where Queen and Worker agents can communicate autonomously, coordinate tasks, and operate without constant human supervision of individual REPLs.

## Current State Analysis

### What We Have
- ✅ 2x2 tmux grid with Claude Code instances
- ✅ Visual organization and manual oversight capability
- ✅ Text delivery via tmux send-keys (but no execution)

### The Core Problem
- ❌ No programmatic command execution (Claude Code input isolation)
- ❌ No inter-agent communication mechanism
- ❌ Requires constant human supervision for task execution
- ❌ Agents operate in isolation, can't coordinate autonomously

## Strategic Architecture Options

### Option A: MCP Server Communication Bus 🏆 **PREFERRED LONG-TERM**

**How it works:**
- Custom MCP server exposes `send_message()` and `receive_messages()` tools
- Each Claude Code instance calls these tools natively (structured communication)
- Messages stored in SQLite/Redis/file-based bus
- Agents communicate through tool calls, not tmux text injection

**Implementation:**
```python
# MCP Server with tools:
send_message(to: str, topic: str, payload: dict) -> bool
receive_messages(for: str, since: timestamp, topic?: str) -> List[Message]
```

**Pros:**
- ✅ Native Claude Code tool integration
- ✅ Structured, durable communication
- ✅ Easy logging and inspection
- ✅ No tmux race conditions
- ✅ Scales to many agents

**Cons:**
- ⚠️ Requires custom MCP server development
- ⚠️ Need to register MCP server with each Claude Code instance

### Option B: File/SQLite Logging Bus 🚀 **IMMEDIATE PROTOTYPE**

**How it works:**
- Shared `bus/` directory or SQLite database
- Each agent reads/writes structured messages (JSON/Markdown)
- Agents instructed via prompts to check bus periodically
- tmux displays live tails of communication logs

**Implementation:**
```bash
# Bus interface scripts:
hive-send --to frontend --topic task --json '{task: "implement auth"}'
hive-recv --for frontend --since '2025-09-09T00:00:00Z'
```

**Pros:**
- ✅ Works today with existing Claude Code
- ✅ Dead simple implementation
- ✅ Durable message history
- ✅ Easy debugging and replay

**Cons:**
- ⚠️ Polling-based (not real-time)
- ⚠️ Requires prompt discipline
- ⚠️ File locking considerations

### Option C: Git-Based Communication 📋 **NOVEL APPROACH**

**How it works:**
- Queen commits tasks to `queen-tasks` branch
- Workers pull, implement, and push to `worker-{name}` branches
- Communication happens through git commits, diffs, and PRs
- CI pipelines provide additional coordination

**Implementation:**
```bash
# Queen workflow:
git checkout queen-tasks
echo "Task: Implement auth API" > tasks/T101-auth.md
git add . && git commit -m "T101: Auth API task"
git push origin queen-tasks

# Worker workflow:
git pull origin queen-tasks
# Process tasks/T101-auth.md
git checkout worker-backend
# Implement and commit
git push origin worker-backend
```

**Pros:**
- ✅ Fits developer workflows
- ✅ Built-in audit trail
- ✅ Merge conflict resolution
- ✅ CI/CD integration potential

**Cons:**
- ⚠️ Higher latency (push/pull cycles)
- ⚠️ More complex conflict resolution
- ⚠️ Overhead for simple messages

### Option D: expect-based REPL Automation 🔧 **INTERIM BRIDGE**

**How it works:**
- Wrap each Claude Code REPL with expect scripts
- Handle Enter key injection with retries and readiness detection
- Enable reliable large message injection
- Bridge solution while building permanent architecture

**Implementation:**
```bash
#!/usr/bin/env expect
set timeout 10
set prompt_re "^(> |\\$|claude.*ready)"

proc send_reliable {text} {
    send -- "$text\r"
    expect -re $prompt_re
}
```

**Pros:**
- ✅ Works today with existing setup
- ✅ Enables large message injection
- ✅ Retries and error handling
- ✅ No Claude Code modifications needed

**Cons:**
- ⚠️ Fragile timing dependencies
- ⚠️ Still requires manual coordination
- ⚠️ Hard to scale beyond 4-6 agents

## Recommended Implementation Roadmap

### Phase 1: Immediate (Days 1-3) - Dual Track
**Track A: Option B (File Bus)**
- [ ] Create `bus/` directory with SQLite backend
- [ ] Implement `hive-send` and `hive-recv` scripts
- [ ] Add bus communication prompts to each agent
- [ ] Test autonomous task coordination

**Track B: Option D (expect Bridge)**
- [ ] Create expect scripts for reliable message injection
- [ ] Add readiness detection and retry logic
- [ ] Enable large task description injection
- [ ] Validate with multi-step workflows

### Phase 2: Integration (Week 1) - MCP Server
- [ ] Build Python MCP server with `send_message`/`receive_messages` tools
- [ ] Register MCP server with Claude Code instances
- [ ] Migrate from file bus to native tool calls
- [ ] Add real-time communication capabilities

### Phase 3: Enhancement (Week 2-3) - Advanced Features
- [ ] Add message routing and topic filtering
- [ ] Implement task queuing and status tracking
- [ ] Create web dashboard for swarm monitoring
- [ ] Add integration hooks for external systems

### Phase 4: Scale (Month 1) - Production Ready
- [ ] Support for 10+ agent swarms
- [ ] Fault tolerance and agent recovery
- [ ] Performance optimization
- [ ] Integration with existing CI/CD pipelines

## Technical Specifications

### Message Protocol (All Options)
```json
{
  "id": "msg-uuid",
  "timestamp": "2025-09-09T14:30:00Z",
  "from": "queen",
  "to": "backend-worker", 
  "topic": "task",
  "priority": "high",
  "payload": {
    "task_id": "T101",
    "description": "Implement user authentication API with JWT",
    "requirements": ["TDD", "FastAPI", "SQLAlchemy"],
    "deadline": "2025-09-10T00:00:00Z"
  },
  "reply_to": "msg-parent-uuid"
}
```

### Agent Roles and Responsibilities

**Queen (Pane 0)**
- Mission planning and task decomposition
- Worker coordination and status monitoring
- Progress reporting and bottleneck resolution
- Human interface for high-level guidance

**Workers (Panes 1-3)**
- Specialized task execution (Frontend, Backend, Infra)
- Status reporting and request clarification
- Cross-worker collaboration when needed
- Quality assurance and testing

### Communication Patterns

1. **Task Assignment**: Queen → Worker
2. **Status Updates**: Worker → Queen
3. **Peer Collaboration**: Worker ↔ Worker
4. **Clarification Requests**: Worker → Queen
5. **Completion Reports**: Worker → Queen

## Success Metrics

### Immediate Goals (Phase 1)
- [ ] Agents exchange messages without human typing
- [ ] Tasks completed with minimal human oversight
- [ ] Clear audit trail of agent communication
- [ ] Error recovery and retry mechanisms

### Long-term Goals (Phase 4)
- [ ] 90%+ autonomous task completion
- [ ] Sub-second inter-agent communication
- [ ] Support for complex multi-day projects
- [ ] Integration with external tools and APIs

## Risk Mitigation

### Technical Risks
- **Message loss**: Durable storage with acknowledgments
- **Race conditions**: Message queuing and locking
- **Agent failures**: Health monitoring and restart capabilities
- **Scale limits**: Performance testing and optimization

### Operational Risks
- **Over-automation**: Maintain human oversight capabilities
- **Communication loops**: Circuit breakers and timeout mechanisms
- **Context drift**: Periodic agent context refresh
- **Security concerns**: Message validation and sanitization

## Alternative Architectures Considered

### Integration with Existing Frameworks
- **CrewAI + MCP**: Use CrewAI for orchestration, MCP for tool integration
- **AutoGen Backend**: Mount AutoGen behind tmux panes for richer dialogue
- **LangChain Agents**: Use LangChain's multi-agent capabilities

### Cloud-Native Options
- **Agent APIs**: REST/GraphQL endpoints for each agent
- **Message Queues**: Kafka/RabbitMQ for enterprise-scale messaging
- **Containerized Agents**: Docker-based agent deployment

## Conclusion

The recommended approach combines **immediate value** (Option B + D) with a **clear path to production** (Option A). This allows rapid prototyping while building toward a robust, scalable Claude Code Multi-Agent System.

Key insight: Rather than fighting Claude Code's input isolation, we embrace it by creating **structured communication channels** that agents use naturally through tool calls or file operations.

The result: A truly autonomous cc MAS where you can assign a complex mission to the Queen and watch the swarm coordinate, implement, test, and deploy - without constant human supervision.

---

*Next Steps: Implement Phase 1 dual track to validate core concepts and measure autonomous coordination effectiveness.*