#!/usr/bin/env python3
"""
Test worker in simulation mode
"""
import sys
import os
import subprocess
from pathlib import Path

# Add project paths
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "packages" / "hive-core-db" / "src"))
sys.path.insert(0, str(project_root / "apps" / "hive-orchestrator" / "src"))

import hive_core_db

# Seed a test task
hive_core_db.init_db()
task_id = hive_core_db.create_task(
    title="Test Calculator Task",
    task_type="backend",
    description="Create add_numbers function",
    workflow={
        "start": {"next_phase_on_success": "apply"},
        "apply": {"next_phase_on_success": "completed"}
    },
    payload={
        "requirements": ["Create calculator.py with add_numbers function"]
    },
    priority=5,
    tags=["test"],
    current_phase="apply"
)

print(f"Created task: {task_id}")

# Run worker directly
cmd = [
    sys.executable,
    str(project_root / "apps" / "hive-orchestrator" / "src" / "hive_orchestrator" / "worker.py"),
    "backend",
    "--task-id", task_id,
    "--run-id", "test-run-123",
    "--phase", "apply",
    "--one-shot"
]

print(f"Running: {' '.join(cmd)}")

result = subprocess.run(cmd, capture_output=True, text=True, cwd=project_root)

print(f"Exit code: {result.returncode}")
print(f"STDOUT:\n{result.stdout}")
print(f"STDERR:\n{result.stderr}")

# Check worktree
worktree_dir = project_root / "apps" / "hive-orchestrator" / "src" / "hive_orchestrator" / ".worktrees" / "backend" / task_id
if worktree_dir.exists():
    print(f"\nWorktree created at: {worktree_dir}")
    files = list(worktree_dir.glob("*"))
    print(f"Files created: {[f.name for f in files]}")
else:
    print(f"\nNo worktree found at: {worktree_dir}")