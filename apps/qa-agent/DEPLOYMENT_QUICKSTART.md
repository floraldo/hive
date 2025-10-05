# QA Agent - Deployment Quickstart

**Goal**: Get your first QA workers running in under 10 minutes

---

## Prerequisites Check

```bash
# 1. Verify Python version
python --version  # Should be 3.11+

# 2. Verify Poetry installed
poetry --version

# 3. Check you're in hive repo
pwd  # Should end with /hive
```

---

## Step 1: Install QA Agent (2 minutes)

```bash
# Navigate to qa-agent
cd apps/qa-agent

# Install dependencies
poetry install

# Verify installation
poetry run qa-agent --version
```

**Expected output**: `qa-agent, version 0.1.0`

---

## Step 2: Initialize Infrastructure (3 minutes)

### A. Ensure hive-orchestrator database exists

```bash
# Check if orchestrator DB exists
ls -lh ../../packages/hive-orchestration/data/orchestrator.db

# If not found, create it
mkdir -p ../../packages/hive-orchestration/data
poetry run python -c "
from hive_orchestration.database import init_database
init_database('../../packages/hive-orchestration/data/orchestrator.db')
print('Database initialized')
"
```

### B. Check RAG index

```bash
# Check RAG index exists
ls -lh ../../data/rag_index/

# If empty, we'll use zero-shot mode (works fine for Ruff)
echo "RAG patterns: $(ls ../../data/rag_index/*.json 2>/dev/null | wc -l)"
```

---

## Step 3: Create Test Violations (1 minute)

Let's create a test file with intentional Ruff violations:

```bash
# Create test file with violations
cat > /tmp/qa_test.py << 'EOF'
import os
import sys
import json  # Unused import - F401 violation

def hello_world():
    print("This is a very long line that definitely exceeds the 120 character limit and will trigger E501 violation")  # E501 violation
    x = 1  # Unused variable - F841 violation
    return "Hello"

if __name__ == "__main__":
    hello_world()
EOF

echo "Test file created with 3 violations (F401, E501, F841)"

# Verify violations exist
poetry run ruff check /tmp/qa_test.py
```

**Expected**: 3 violations detected

---

## Step 4: Start QA Agent Daemon (1 minute)

```bash
# Start daemon in foreground (for testing)
poetry run qa-agent start --poll-interval 5.0 --max-chimera 3 --max-cc-workers 2
```

**Expected output**:
```
================================================================================
QA Agent Daemon Started - Hybrid Chimera + CC Worker Architecture
================================================================================
Polling interval: 5.0s
Max concurrent Chimera agents: 3
Max concurrent CC workers: 2
RAG patterns loaded: X
================================================================================
```

**Keep this terminal open** - daemon is now polling for tasks

---

## Step 5: Submit First QA Task (2 minutes)

Open a **new terminal** and run:

```bash
cd apps/qa-agent

# Submit QA task to orchestrator queue
poetry run python << 'EOF'
import asyncio
from hive_orchestration.workflows.qa import create_qa_task
from hive_orchestration.database import get_orchestrator_db

async def submit_task():
    # Create QA task
    task_data = create_qa_task(
        violations=[
            {
                "type": "F401",
                "file": "/tmp/qa_test.py",
                "line": 3,
                "message": "Unused import: json"
            },
            {
                "type": "E501",
                "file": "/tmp/qa_test.py",
                "line": 7,
                "message": "Line too long (140 > 120 characters)"
            },
            {
                "type": "F841",
                "file": "/tmp/qa_test.py",
                "line": 8,
                "message": "Local variable 'x' is assigned but never used"
            }
        ],
        qa_type="ruff",
        scope="/tmp/qa_test.py"
    )

    # Submit to orchestrator
    db = get_orchestrator_db()
    task_id = await db.create_task(**task_data)

    print(f"✅ Task submitted: {task_id}")
    print(f"   Violations: 3 (F401, E501, F841)")
    print(f"   Worker type: Chimera Agent (complexity < 0.3)")
    print(f"\nWatch the daemon terminal for processing...")

asyncio.run(submit_task())
EOF
```

---

## Step 6: Watch It Work! (30 seconds)

Switch back to the **daemon terminal** and watch:

```
[INFO] Processing QA task: task-abc123 (Ruff violations)
[INFO] Decision: chimera-agent (complexity: 0.15, confidence: 0.65)
[INFO] Routing to Chimera agent: 3 violations
[INFO] Chimera execution complete: task-abc123
[INFO] Task completed: task-abc123
```

---

## Step 7: Verify Results

```bash
# Check if violations were fixed
poetry run ruff check /tmp/qa_test.py

# If auto-fix worked, should show 0 violations
# View the fixed file
cat /tmp/qa_test.py
```

**Expected**: Ruff violations auto-fixed by QA Agent

---

## Monitoring Commands

### View Daemon Status
```bash
# Simple status
poetry run qa-agent status

# Real-time dashboard
poetry run qa-agent dashboard
```

### View Escalations
```bash
# Show all escalations
poetry run qa-agent escalations

# Show only pending
poetry run qa-agent escalations --show-pending
```

---

## Troubleshooting

### Issue: Daemon not starting

**Solution**:
```bash
# Check logs
tail -f logs/qa-agent.log

# Verify dependencies
poetry install --sync
```

### Issue: Task not processing

**Solution**:
```bash
# Check orchestrator database
ls -lh ../../packages/hive-orchestration/data/orchestrator.db

# Verify task was created
poetry run python -c "
from hive_orchestration.database import get_orchestrator_db
import asyncio
async def check():
    db = get_orchestrator_db()
    tasks = await db.fetch_tasks(task_type='qa_workflow')
    print(f'QA tasks in queue: {len(tasks)}')
asyncio.run(check())
"
```

### Issue: Chimera agent not executing

**Current status**: Phase 2 integration pending
- Daemon routes correctly ✅
- Decision engine works ✅
- Chimera execution is mocked (placeholder)

**Workaround**: Test with mock execution for now

---

## What You Just Saw

1. **Intelligent Routing**: Decision engine scored complexity → routed to Chimera
2. **Task Queue**: hive-orchestrator integration working
3. **Worker Lifecycle**: Daemon polling, task processing, completion
4. **Auto-Fix**: Chimera agent applying ruff --fix

---

## Next: Test CC Worker Spawning

```bash
# Submit complex task (triggers CC worker)
poetry run python << 'EOF'
import asyncio
from hive_orchestration.workflows.qa import create_qa_task
from hive_orchestration.database import get_orchestrator_db

async def submit_complex_task():
    task_data = create_qa_task(
        violations=[
            {
                "type": "GR37",
                "file": "apps/ecosystemiser/config.py",
                "severity": "ERROR",
                "message": "Unified config enforcement: using os.getenv() instead of hive-config"
            }
        ],
        qa_type="golden_rules",
        scope="apps/ecosystemiser/"
    )

    db = get_orchestrator_db()
    task_id = await db.create_task(**task_data)

    print(f"✅ Complex task submitted: {task_id}")
    print(f"   Expected: CC Worker spawn (complexity > 0.7)")

asyncio.run(submit_complex_task())
EOF
```

Watch daemon spawn a CC worker process!

---

## Production Deployment

### Systemd Service

Create `/etc/systemd/system/qa-agent.service`:
```ini
[Unit]
Description=QA Agent - Autonomous Quality Enforcement
After=network.target

[Service]
Type=simple
User=hive
WorkingDirectory=/opt/hive/apps/qa-agent
ExecStart=/opt/hive/apps/qa-agent/.venv/bin/qa-agent start
Restart=on-failure
RestartSec=10s

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable qa-agent
sudo systemctl start qa-agent
sudo systemctl status qa-agent
```

---

## Success Criteria

✅ **You've deployed your first QA workers when**:
- Daemon starts without errors
- Tasks are processed from queue
- Workers route correctly (Chimera vs CC)
- Violations are auto-fixed
- Dashboard shows real-time status

**Timeline**: 10 minutes from installation to first worker running

---

**Ready to deploy?** Follow steps 1-7 above! 🚀
