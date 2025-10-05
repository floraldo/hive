#!/bin/bash
# QA Agent Demo Deployment - See it in action!
# This script demonstrates the complete QA Agent workflow

set -e  # Exit on error

echo "========================================================================"
echo "QA AGENT DEMO DEPLOYMENT"
echo "========================================================================"
echo ""
echo "This demo will:"
echo "  1. Install QA Agent dependencies"
echo "  2. Create test file with violations"
echo "  3. Initialize infrastructure (if needed)"
echo "  4. Submit QA task to queue"
echo "  5. Show daemon processing the task"
echo ""
echo "Duration: ~2 minutes"
echo "========================================================================"
echo ""

read -p "Press Enter to start demo..."

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Step 1: Install dependencies
echo ""
echo "STEP 1/5: Installing dependencies..."
echo "------------------------------------------------------------------------"
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    poetry install
else
    echo "Virtual environment exists, verifying dependencies..."
    poetry install --sync
fi

echo "✅ Dependencies installed"
echo ""

# Step 2: Create test file with violations
echo ""
echo "STEP 2/5: Creating test file with violations..."
echo "------------------------------------------------------------------------"

TEST_FILE="/tmp/qa_agent_demo_test.py"
cat > "$TEST_FILE" << 'EOF'
import os
import sys
import json  # F401: Unused import
import datetime  # F401: Unused import

def example_function():
    """Example function with multiple Ruff violations."""

    # E501: Line too long
    result = "This is an intentionally very long line that exceeds the 120 character limit and will trigger a Ruff E501 violation for demonstration purposes"

    # F841: Unused variable
    unused_var = 42

    # E402: Module level import not at top
    import random

    return "Demo"

if __name__ == "__main__":
    example_function()
EOF

echo "Created: $TEST_FILE"
echo ""
echo "Violations in test file:"
poetry run ruff check "$TEST_FILE" || true
echo ""
VIOLATION_COUNT=$(poetry run ruff check "$TEST_FILE" 2>&1 | grep -c "Found" || echo "0")
echo "✅ Test file created with violations"
echo ""

# Step 3: Initialize infrastructure
echo ""
echo "STEP 3/5: Initializing infrastructure..."
echo "------------------------------------------------------------------------"

# Check orchestrator database
ORCHESTRATOR_DB="../../packages/hive-orchestration/data/orchestrator.db"
if [ ! -f "$ORCHESTRATOR_DB" ]; then
    echo "Creating hive-orchestrator database..."
    mkdir -p "$(dirname "$ORCHESTRATOR_DB")"

    # Initialize database (simplified for demo)
    poetry run python << 'PYEOF'
import sqlite3
from pathlib import Path

db_path = Path("../../packages/hive-orchestration/data/orchestrator.db")
db_path.parent.mkdir(parents=True, exist_ok=True)

conn = sqlite3.connect(str(db_path))
cursor = conn.cursor()

# Create minimal tasks table for demo
cursor.execute("""
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    title TEXT,
    description TEXT,
    task_type TEXT,
    status TEXT,
    payload TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

# Create workers table
cursor.execute("""
CREATE TABLE IF NOT EXISTS workers (
    id TEXT PRIMARY KEY,
    worker_type TEXT,
    status TEXT,
    task_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

conn.commit()
conn.close()

print("✅ Orchestrator database initialized")
PYEOF
else
    echo "Orchestrator database exists"
fi

# Check RAG index
RAG_INDEX_DIR="../../data/rag_index"
if [ ! -d "$RAG_INDEX_DIR" ]; then
    echo "Creating RAG index directory..."
    mkdir -p "$RAG_INDEX_DIR"

    # Create minimal RAG index for demo
    cat > "$RAG_INDEX_DIR/git_commits.json" << 'EOF'
[
    {
        "sha": "abc123",
        "message": "fix(ruff): Auto-fix E501 line length violations",
        "diff": "- long_line = \"very long\"\n+ long_line = (\n+     \"split line\"\n+ )",
        "files_changed": ["test.py"]
    }
]
EOF

    cat > "$RAG_INDEX_DIR/chunks.json" << 'EOF'
[
    {
        "file": "example.py",
        "content": "# Ruff auto-fix example\nimport ruff",
        "language": "python"
    }
]
EOF

    cat > "$RAG_INDEX_DIR/metadata.json" << 'EOF'
{
    "version": "1.0",
    "indexed_at": "2025-10-05",
    "total_patterns": 2
}
EOF

    echo "✅ RAG index created with demo patterns"
else
    echo "RAG index exists"
fi

echo "✅ Infrastructure initialized"
echo ""

# Step 4: Submit QA task
echo ""
echo "STEP 4/5: Submitting QA task to queue..."
echo "------------------------------------------------------------------------"

poetry run python << PYEOF
import json
import sqlite3
import uuid
from datetime import datetime

# Create task
task_id = f"qa-demo-{uuid.uuid4().hex[:8]}"
task_data = {
    "id": task_id,
    "title": "QA Demo: Fix Ruff violations",
    "description": "Demo task to show QA Agent auto-fixing violations",
    "task_type": "qa_workflow",
    "status": "queued",
    "payload": json.dumps({
        "violations": [
            {"type": "F401", "file": "$TEST_FILE", "line": 3, "message": "Unused import: json"},
            {"type": "F401", "file": "$TEST_FILE", "line": 4, "message": "Unused import: datetime"},
            {"type": "E501", "file": "$TEST_FILE", "line": 11, "message": "Line too long"},
            {"type": "F841", "file": "$TEST_FILE", "line": 14, "message": "Unused variable"},
        ],
        "qa_type": "ruff",
        "scope": "$TEST_FILE"
    })
}

# Insert into database
conn = sqlite3.connect("../../packages/hive-orchestration/data/orchestrator.db")
cursor = conn.cursor()

cursor.execute(
    "INSERT INTO tasks (id, title, description, task_type, status, payload) VALUES (?, ?, ?, ?, ?, ?)",
    (task_data["id"], task_data["title"], task_data["description"],
     task_data["task_type"], task_data["status"], task_data["payload"])
)

conn.commit()
conn.close()

print(f"✅ Task submitted: {task_id}")
print(f"   Violations: 4 (F401 x2, E501, F841)")
print(f"   File: $TEST_FILE")
print(f"   Queue: hive-orchestrator")
PYEOF

echo ""
echo "✅ Task queued for processing"
echo ""

# Step 5: Show daemon info
echo ""
echo "STEP 5/5: QA Agent is ready to deploy!"
echo "------------------------------------------------------------------------"
echo ""
echo "📊 DEPLOYMENT STATUS"
echo ""
echo "Infrastructure:"
echo "  ✅ Dependencies installed"
echo "  ✅ Orchestrator database initialized"
echo "  ✅ RAG index populated (2 patterns)"
echo "  ✅ Test task queued (4 violations)"
echo ""
echo "Test File:"
echo "  📄 Location: $TEST_FILE"
echo "  🔍 Violations: 4 Ruff issues"
echo "  🎯 Expected: Chimera Agent (simple fixes)"
echo ""
echo "========================================================================"
echo "READY TO START DAEMON"
echo "========================================================================"
echo ""
echo "To see your first QA worker in action:"
echo ""
echo "  1. Start daemon:"
echo "     ./cli/start_qa_agent.sh"
echo ""
echo "  2. Watch it process the queued task automatically!"
echo ""
echo "  3. OR run daemon in demo mode (non-blocking):"
echo "     poetry run qa-agent start --poll-interval 2.0 &"
echo "     DAEMON_PID=\$!"
echo "     sleep 10"
echo "     kill \$DAEMON_PID"
echo ""
echo "  4. View results:"
echo "     poetry run ruff check $TEST_FILE"
echo ""
echo "  5. Monitor via dashboard:"
echo "     poetry run qa-agent dashboard"
echo ""
echo "========================================================================"
echo ""

read -p "Press Enter to start daemon now (or Ctrl+C to exit)..."

echo ""
echo "Starting daemon in foreground..."
echo "Press Ctrl+C to stop daemon"
echo ""

# Start daemon
poetry run qa-agent start --poll-interval 2.0
