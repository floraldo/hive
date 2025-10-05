# QA Agent - Hybrid Autonomous Quality Enforcement

**Architecture**: CC Terminal + Background Daemon orchestrating Chimera agents and CC workers

## Overview

QA Agent is a hybrid autonomous quality enforcement system that intelligently routes code quality violations to the most appropriate worker type:

- **Chimera Agents** (lightweight Python): Fast auto-fixes for simple violations (Ruff, simple Golden Rules)
- **CC Workers** (headless terminals): Deep reasoning for complex violations (architectural rules, test failures)
- **Interactive CC** (HITL): Critical violations requiring human review

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│              QA AGENT: CC TERMINAL (Interactive)                │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  📺 CC Terminal Process                                         │
│  └─> qa-agent-daemon (Background Python process)               │
│       ├─ Watches: hive-orchestrator task queue                 │
│       ├─ RAG Priming: qa_fix_patterns index on startup        │
│       ├─ Intelligence: Decides worker type per violation       │
│       └─ Orchestrates: Chimera agents OR CC workers           │
│                                                                  │
│  🎭 Dual Worker Strategy (Intelligent Routing):                │
│                                                                  │
│  A) Simple Fixes → Chimera Agents (In-Process)                 │
│     ├─ QAFixerAgent (RAG + morphllm)                          │
│     ├─ TestRunnerAgent (pytest execution)                      │
│     └─ Chimera ExecutorPool (parallel async)                   │
│     └─> Fast, lightweight, no subprocess overhead             │
│                                                                  │
│  B) Complex Tasks → CC Workers (Spawned Terminals)             │
│     ├─ Headless CC terminal per complex violation             │
│     ├─ RAG context injected via startup script                │
│     ├─ MCP tools: sequential-thinking, morphllm               │
│     └─> Full Claude Code reasoning for hard problems          │
│                                                                  │
│  💾 Shared Infrastructure:                                      │
│  ├─ Task Queue: hive-orchestrator tasks table                  │
│  ├─ Worker Registry: hive-orchestrator workers table           │
│  ├─ Event Bus: hive-bus coordination                           │
│  └─ RAG Index: qa_fix_history patterns                        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Decision Matrix

| Violation Type                    | Complexity | Worker Type      | Rationale                          |
|-----------------------------------|------------|------------------|------------------------------------|
| Ruff E501 (line length)           | Low        | Chimera Agent    | Simple pattern, morphllm bulk edit |
| Ruff F401 (unused import)         | Low        | Chimera Agent    | AST-based removal, fast            |
| Golden Rule 31 (config)           | Low        | Chimera Agent    | File append operation              |
| Golden Rule 9 (logging)           | Medium     | Chimera Agent    | Pattern replacement with RAG       |
| Failing pytest                    | Medium     | CC Worker        | Needs debugging reasoning          |
| Golden Rule 37 (config migration) | High       | CC Worker        | Complex refactoring                |
| Security vulnerability            | High       | CC Worker + HITL | Requires deep analysis             |

## Usage

### Start QA Agent Daemon

```bash
# Launch CC terminal with QA agent daemon
./apps/qa-agent/cli/start_qa_agent.sh

# Daemon automatically polls hive-orchestrator queue
# Routes violations to appropriate workers
# Publishes events to hive-bus for monitoring
```

### Submit QA Tasks

```bash
# Via hive-orchestration client
from hive_orchestration import create_task

task = create_task(
    title="Fix Ruff violations in auth module",
    task_type="qa_workflow",
    payload={
        "qa_type": "ruff",
        "scope": "apps/ecosystemiser/src/ecosystemiser/auth/",
        "severity_level": "ERROR"
    }
)
```

### Monitor Workers

```bash
# Check worker status via dashboard (Phase 5)
qa-agent dashboard

# View escalations
qa-agent escalations --show-pending
```

## Components

### Core Daemon (`daemon.py`)
- Polls hive-orchestrator task queue every 5s
- Loads RAG patterns on startup for fast retrieval
- Routes violations based on complexity scoring
- Manages Chimera executor pool + CC worker spawner

### Decision Engine (`decision_engine.py`)
- Scores violation complexity (0.0-1.0)
- Checks RAG pattern confidence
- Routes: CRITICAL → HITL, complexity >0.7 → CC worker, else Chimera

### RAG Priming (`rag_priming.py`)
- Loads qa_fix_patterns from data/rag_index/
- Indexes historical fix patterns
- Provides reactive retrieval for Chimera agents
- Injects proactive context for CC workers

### Chimera Agents (`workflows/qa_agents.py`)
- **QAFixerAgent**: RAG-enhanced violation fixer (morphllm + sequential-thinking)
- **TestRunnerAgent**: Automated test execution and reporting
- Lightweight, in-process, parallel execution

### CC Worker Spawner (`cc_spawner.py`)
- Spawns headless CC terminals for complex violations
- Injects RAG context via startup script environment
- Registers workers in hive-orchestrator workers table
- Monitors worker health and handles failures

### Monitoring (`monitoring.py`)
- Tracks Chimera agent status
- Monitors CC worker processes
- Escalates failures to HITL
- Publishes metrics to hive-bus

## Integration Points

### hive-orchestration
- Uses existing Task/Worker models
- Shares ChimeraExecutor infrastructure
- Extends workflows with QA-specific agents

### hive-bus
- Publishes QATaskEvent for completion/failures
- Publishes EscalationEvent for HITL review
- Publishes WorkerHeartbeat for health monitoring

### RAG Index
- Reads from data/rag_index/qa_fix_patterns
- Stores fix success/failure history
- Learns from human escalation resolutions

## Development

### Install Dependencies

```bash
cd apps/qa-agent
poetry install
```

### Run Tests

```bash
poetry run pytest tests/
```

### Code Quality

```bash
# Auto-fix violations
poetry run ruff check --fix src/

# Type checking
poetry run mypy src/
```

## Performance Targets

- **Auto-Fix Success Rate**: 50%+ (varies by violation type)
- **Fix Latency**: <10s per file (Chimera), <2min per complex task (CC worker)
- **False Positive Rate**: <0.5% (AST-based validation)
- **Escalation Rate**: <20% (most violations auto-fixable)

## Roadmap

- ✅ Phase 1: Daemon core with decision engine
- ✅ Phase 2: Chimera QA agents integration
- ✅ Phase 3: CC worker spawning
- ✅ Phase 4: Intelligent routing and batching
- ⏳ Phase 5: Monitoring dashboard and escalation UI

## License

Part of the Hive Platform - Internal Use Only
