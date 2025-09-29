#!/usr/bin/env python3
"""
Simplified Queen Orchestrator - Core functionality only
Removes unnecessary complexity: learning, retry logic, PR management
Focuses on: task discovery, worker spawning, state management
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class Phase(Enum):
    """Task execution phases"""

    PLAN = "plan"
    APPLY = "apply"
    TEST = "test"


class SimpleQueenOrchestrator:
    """Simplified orchestrator - core functionality only"""

    def __init__(self, fresh_env: bool = False):
        self.root = Path.cwd()
        self.hive_dir = self.root / "hive"
        self.tasks_dir = self.hive_dir / "tasks"
        self.results_dir = self.hive_dir / "results"
        self.hints_dir = self.hive_dir / "operator" / "hints"
        self.events_file = self.get_events_file()
        self.worktrees_dir = self.root / ".worktrees"

        # Configuration
        self.fresh_env = fresh_env
        self.max_parallel_per_role = {"backend": 2, "frontend": 2, "infra": 1}

        # State
        self.active_workers = {}  # task_id -> {process, run_id, phase}

        # Ensure directories exist
        for d in [self.tasks_dir, self.results_dir, self.hints_dir, self.worktrees_dir]:
            d.mkdir(parents=True, exist_ok=True)

    def timestamp(self) -> str:
        """Current timestamp for logging"""
        return datetime.now().strftime("%H:%M:%S")

    def get_events_file(self) -> Path:
        """Get daily-rotated events file"""
        return self.hive_dir / "bus" / f"events_{datetime.now().strftime('%Y%m%d')}.jsonl"

    def emit_event(self, **kwargs):
        """Emit event to the event bus"""
        event = {"ts": datetime.now(timezone.utc).isoformat(), **kwargs}
        self.events_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.events_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")

    def load_task_index(self) -> List[str]:
        """Load task queue order"""
        index_file = self.tasks_dir / "index.json"
        if index_file.exists():
            try:
                data = json.loads(index_file.read_text())
                return data.get("queue", [])
            except:
                return []
        return []

    def load_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Load individual task"""
        task_file = self.tasks_dir / f"{task_id}.json"
        if task_file.exists():
            try:
                return json.loads(task_file.read_text())
            except:
                return None
        return None

    def save_task(self, task: Dict[str, Any]):
        """Save individual task"""
        task_file = self.tasks_dir / f"{task['id']}.json"
        task_file.write_text(json.dumps(task, indent=2))

    def create_fresh_workspace(self, worker: str, task_id: str) -> Path:
        """Create fresh isolated workspace"""
        workspace_path = self.worktrees_dir / "fresh" / worker / task_id
        workspace_path.mkdir(parents=True, exist_ok=True)

        # Create basic .gitignore
        gitignore = workspace_path / ".gitignore"
        if not gitignore.exists():
            gitignore.write_text("__pycache__/\n*.pyc\n.env\nnode_modules/\n")

        return workspace_path

    def check_hint(self, task_id: str) -> Optional[str]:
        """Check for operator hints"""
        hint_file = self.hints_dir / f"{task_id}.md"
        if hint_file.exists():
            return hint_file.read_text().strip()
        return None

    def spawn_worker(self, task: Dict[str, Any], worker: str, phase: Phase) -> Optional[Tuple[subprocess.Popen, str]]:
        """Spawn one-shot worker for specific phase"""
        task_id = task["id"]

        # Create workspace
        if self.fresh_env:
            workspace = self.create_fresh_workspace(worker, task_id)
        else:
            workspace = self.worktrees_dir / worker / task_id
            workspace.mkdir(parents=True, exist_ok=True)

        # Generate run_id
        run_id = f"{task_id}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{phase.value}"

        # Build worker command
        cmd = [
            sys.executable,
            "cc_worker.py",
            worker,
            "--one-shot",
            "--task-id",
            task_id,
            "--workspace",
            str(workspace),
            "--phase",
            phase.value,
            "--run-id",
            run_id,
        ]

        # Set environment variables
        env = os.environ.copy()
        env.update({"CLAUDE_BIN": os.environ.get("CLAUDE_BIN", ""), "HIVE_SKIP_PERMS": "1", "HIVE_DISABLE_PR": "1"})

        try:
            process = subprocess.Popen(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

            # Emit spawn event
            self.emit_event(
                type="spawn",
                task_id=task_id,
                run_id=run_id,
                phase=phase.value,
                worker=worker,
                workspace=str(workspace),
                pid=process.pid,
                component="queen",
            )

            print(f"[{self.timestamp()}] Spawned {worker} for {task_id} phase:{phase.value} (PID: {process.pid})")
            return process, run_id

        except Exception as e:
            print(f"[{self.timestamp()}] Failed to spawn worker: {e}")
            return None

    def check_worker_result(self, task_id: str, run_id: str) -> Optional[Dict[str, Any]]:
        """Check for specific worker result"""
        results_dir = self.results_dir / task_id
        if not results_dir.exists():
            return None

        result_file = results_dir / f"{run_id}.json"
        if result_file.exists():
            try:
                return json.loads(result_file.read_text())
            except:
                return None
        return None

    def advance_task_state(self, task: Dict[str, Any], result: Dict[str, Any], phase: Phase):
        """Advance task state based on result"""
        task_id = task["id"]
        status = result.get("status", "failed")
        next_state = result.get("next_state", "failed")

        if status == "success":
            if next_state == "completed":
                task["status"] = "completed"
                print(f"[{self.timestamp()}] Task {task_id} completed successfully")
            else:
                # Move to next phase
                if phase == Phase.PLAN:
                    task["current_phase"] = Phase.APPLY.value
                elif phase == Phase.APPLY:
                    task["current_phase"] = Phase.TEST.value
                elif phase == Phase.TEST:
                    task["status"] = "completed"
        else:
            # Task failed - revert to queued for retry
            task["status"] = "queued"
            if "current_phase" in task:
                del task["current_phase"]
            if "assignee" in task:
                del task["assignee"]
            if "assigned_at" in task:
                del task["assigned_at"]
            print(f"[{self.timestamp()}] Task {task_id} failed - reverted to queued")

        self.save_task(task)

    def assign_worker(self, task: Dict[str, Any]) -> Optional[str]:
        """Determine which worker should handle task"""
        tags = task.get("tags", [])

        if "backend" in tags:
            return "backend"
        elif "frontend" in tags:
            return "frontend"
        elif "infra" in tags:
            return "infra"
        else:
            return "backend"  # Default fallback

    def process_queue(self):
        """Process task queue - simplified version"""
        queue = self.load_task_index()
        if not queue:
            return

        # Count active workers per role
        active_per_role = {"backend": 0, "frontend": 0, "infra": 0}
        for task_id in self.active_workers:
            task = self.load_task(task_id)
            if task:
                worker = task.get("assignee")
                if worker in active_per_role:
                    active_per_role[worker] += 1

        # Process queued tasks
        for task_id in queue:
            task = self.load_task(task_id)
            if not task or task.get("status") != "queued":
                continue

            worker = self.assign_worker(task)
            if not worker:
                continue

            # Check per-role limit
            if active_per_role[worker] >= self.max_parallel_per_role.get(worker, 1):
                continue

            # Start first phase - skip planning for test tasks
            current_phase = Phase.APPLY if (task_id.endswith("_test") or task_id == "hello_hive") else Phase.PLAN

            # Assign task
            task["status"] = "assigned"
            task["assignee"] = worker
            task["assigned_at"] = datetime.now(timezone.utc).isoformat()
            task["current_phase"] = current_phase.value
            self.save_task(task)

            # Spawn worker
            result = self.spawn_worker(task, worker, current_phase)
            if result:
                process, run_id = result
                self.active_workers[task_id] = {"process": process, "run_id": run_id, "phase": current_phase.value}
                active_per_role[worker] += 1

    def monitor_workers(self):
        """Monitor active workers - simplified version"""
        completed = []

        for task_id, metadata in list(self.active_workers.items()):
            process = metadata["process"]
            run_id = metadata["run_id"]
            poll = process.poll()

            if poll is not None:
                # Worker finished
                task = self.load_task(task_id)
                if not task:
                    completed.append(task_id)
                    continue

                current_phase = Phase(task.get("current_phase", Phase.PLAN.value))

                # Check if worker failed
                if poll != 0:
                    print(f"[{self.timestamp()}] Worker failed for {task_id} (exit: {poll}) - reverting to queued")
                    task["status"] = "queued"
                    # Remove assignment details
                    for key in ["assignee", "assigned_at", "current_phase"]:
                        if key in task:
                            del task[key]
                    self.save_task(task)
                    completed.append(task_id)
                    continue

                # Check result
                result = self.check_worker_result(task_id, run_id)
                if result:
                    self.advance_task_state(task, result, current_phase)

                    # Check if we need to spawn next phase
                    task = self.load_task(task_id)
                    if task and task.get("status") == "in_progress":
                        next_phase = Phase(task.get("current_phase"))
                        worker = task.get("assignee")

                        # Spawn next phase
                        spawn_result = self.spawn_worker(task, worker, next_phase)
                        if spawn_result:
                            new_process, new_run_id = spawn_result
                            self.active_workers[task_id] = {
                                "process": new_process,
                                "run_id": new_run_id,
                                "phase": next_phase.value,
                            }
                            continue

                completed.append(task_id)

        # Remove completed
        for task_id in completed:
            del self.active_workers[task_id]

    def print_status(self):
        """Print simplified status"""
        # Count task statuses
        stats = {"queued": 0, "assigned": 0, "in_progress": 0, "completed": 0, "failed": 0}
        for task_file in self.tasks_dir.glob("*.json"):
            if task_file.name == "index.json":
                continue
            try:
                task = json.loads(task_file.read_text())
                status = task.get("status", "unknown")
                if status in stats:
                    stats[status] += 1
            except:
                pass

        # Single-line status
        print(
            f"[{self.timestamp()}] Active: {len(self.active_workers)} | "
            f"Q: {stats['queued']} | A: {stats['assigned']} | "
            f"IP: {stats['in_progress']} | C: {stats['completed']} | F: {stats['failed']}"
        )

    def run_forever(self):
        """Main orchestration loop - simplified"""
        print(f"[{self.timestamp()}] Queen Orchestrator v2 starting...")
        print("Epoch-based execution with interrupt/resume capability")
        print("=" * 50)

        try:
            while True:
                self.process_queue()
                self.monitor_workers()
                self.print_status()
                time.sleep(2)

        except KeyboardInterrupt:
            print(f"\n[{self.timestamp()}] Queen shutting down...")

            # Terminate workers
            for task_id, metadata in self.active_workers.items():
                print(f"[{self.timestamp()}] Terminating {task_id}")
                metadata["process"].terminate()

            sys.exit(0)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Simplified Queen Orchestrator")
    parser.add_argument("--fresh-env", action="store_true", help="Use fresh workspaces")
    args = parser.parse_args()

    if args.fresh_env:
        print("Starting Queen Orchestrator in FRESH ENVIRONMENT mode")

    queen = SimpleQueenOrchestrator(fresh_env=args.fresh_env)
    queen.run_forever()


if __name__ == "__main__":
    main()
