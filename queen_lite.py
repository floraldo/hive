#!/usr/bin/env python3
"""
QueenLite - Streamlined Queen Orchestrator
Preserves ALL hardening while removing complexity
"""

import json
import subprocess
import sys
import time
import os
import argparse
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Tuple
from enum import Enum

# Import HiveCore for tight integration
from hive_core import HiveCore

class Phase(Enum):
    """Task execution phases"""
    PLAN = "plan"
    APPLY = "apply" 
    TEST = "test"

class QueenLite:
    """Streamlined orchestrator with preserved hardening"""
    
    def __init__(self, hive_core: HiveCore, fresh_env: bool = False):
        # Tight integration with HiveCore
        self.hive = hive_core
        self.fresh_env = fresh_env
        
        # State management
        self.active_workers = {}  # task_id -> {process, run_id, phase}
        
        # Apply fresh environment cleanup if requested
        if self.fresh_env:
            self.hive.clean_fresh_environment()
    
    def timestamp(self) -> str:
        """Current timestamp for logging"""
        return self.hive.timestamp()
    
    def create_fresh_workspace(self, worker: str, task_id: str) -> Path:
        """Create fresh isolated workspace for testing"""
        # Simple slugify
        safe_task_id = "".join(c if c.isalnum() or c in "-_" else "_" for c in task_id)
        workspace_path = self.hive.worktrees_dir / "fresh" / worker / safe_task_id
        
        # Create directory
        workspace_path.mkdir(parents=True, exist_ok=True)
        
        # Create basic template files
        self.setup_fresh_template(workspace_path, worker)
        
        print(f"[{self.timestamp()}] Created fresh workspace: {workspace_path}")
        return workspace_path
    
    def setup_fresh_template(self, workspace_path: Path, worker: str):
        """Setup basic template files for fresh workspace"""
        if worker == "backend":
            # Python project template
            readme_content = f"""# Backend Worker Test Environment
Basic Python workspace for {worker} tasks.
"""
            gitignore_content = """*.pyc
__pycache__/
*.egg-info/
.pytest_cache/
"""
        elif worker == "frontend":
            # Frontend project template  
            readme_content = f"""# Frontend Worker Test Environment
Basic web development workspace for {worker} tasks.
"""
            gitignore_content = """node_modules/
dist/
.cache/
*.log
"""
        elif worker == "infra":
            # Infrastructure project template
            readme_content = f"""# Infrastructure Worker Test Environment  
Basic infrastructure workspace for {worker} tasks.
"""
            gitignore_content = """*.tfstate
*.tfstate.backup
.terraform/
"""
        else:
            # Generic template
            readme_content = f"""# {worker.title()} Worker Test Environment
Workspace for {worker} tasks.
"""
            gitignore_content = """*.log
*.tmp
"""
        
        # Write template files
        (workspace_path / "README.md").write_text(readme_content)
        (workspace_path / ".gitignore").write_text(gitignore_content)
    
    def spawn_worker(self, task: Dict[str, Any], worker: str, phase: Phase) -> Optional[Tuple[subprocess.Popen, str]]:
        """Spawn worker with enhanced error handling"""
        task_id = task["id"]
        run_id = f"{task_id}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{phase.value}"
        
        # Get or create workspace
        if not task.get("worktree"):
            if self.fresh_env:
                worktree = self.create_fresh_workspace(worker, task_id)
                task["worktree"] = str(worktree)
                task["workspace_type"] = "fresh"
                self.hive.save_task(task)
            else:
                # Use regular worktree (simplified - just create directory)
                worktree = self.hive.worktrees_dir / worker / task_id
                worktree.mkdir(parents=True, exist_ok=True)
                task["worktree"] = str(worktree)
                task["workspace_type"] = "regular"
                self.hive.save_task(task)
        else:
            worktree = Path(task["worktree"])
        
        # Build command - use streamlined worker
        cmd = [
            sys.executable,
            str(self.hive.root / "worker_core.py"),  # Absolute path
            worker,
            "--one-shot",
            "--task-id", task_id,
            "--run-id", run_id,
            "--workspace", str(worktree),
            "--phase", phase.value
        ]
        
        # Enhanced environment
        env = os.environ.copy()
        env.update({
            "HIVE_SKIP_PERMS": "1",
            "HIVE_DISABLE_PR": "1",
            "PYTHONUNBUFFERED": "1"
        })
        
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                env=env
            )
            
            print(f"[{self.timestamp()}] Spawned {worker} for {task_id} phase:{phase.value} (PID: {process.pid})")
            return process, run_id
            
        except Exception as e:
            print(f"[{self.timestamp()}] Spawn failed: {e}")
            return None
    
    def process_queue(self):
        """Process task queue with hardened status management"""
        queue = self.hive.load_task_queue()
        if not queue:
            return
        
        # Count active workers per role
        active_per_role = {"backend": 0, "frontend": 0, "infra": 0}
        for metadata in self.active_workers.values():
            worker_type = metadata.get("worker_type", "unknown")
            if worker_type in active_per_role:
                active_per_role[worker_type] += 1
        
        # Check global limit
        max_parallel = sum(self.hive.config["max_parallel_per_role"].values())
        if len(self.active_workers) >= max_parallel:
            return
        
        for task_id in queue[:]:
            task = self.hive.load_task(task_id)
            if not task or task.get("status") != "queued":
                continue
            
            # Determine worker type
            worker = task.get("tags", [None])[0] if task.get("tags") else "backend"
            if worker not in ["backend", "frontend", "infra"]:
                worker = "backend"  # Default fallback
            
            # Check per-role limit
            max_per_role = self.hive.config["max_parallel_per_role"].get(worker, 1)
            if active_per_role[worker] >= max_per_role:
                continue
            
            # Start with APPLY phase for tests, PLAN for others
            current_phase = Phase.APPLY if (task_id.endswith("_test") or task_id == "hello_hive") else Phase.PLAN
            
            # Set assigned status
            task["status"] = "assigned"
            task["assignee"] = worker
            task["assigned_at"] = datetime.now(timezone.utc).isoformat()
            task["current_phase"] = current_phase.value
            self.hive.save_task(task)
            
            # CRITICAL: Spawn worker with failure handling
            result = self.spawn_worker(task, worker, current_phase)
            if result:
                process, run_id = result
                self.active_workers[task_id] = {
                    "process": process,
                    "run_id": run_id,
                    "phase": current_phase.value,
                    "worker_type": worker
                }
                task["status"] = "in_progress"
                task["started_at"] = datetime.now(timezone.utc).isoformat()
                self.hive.save_task(task)
                print(f"[{self.timestamp()}] Successfully spawned {worker} for {task_id} (PID: {process.pid})")
            else:
                # HARDENING: Spawn failed - revert task to queued status
                print(f"[{self.timestamp()}] Failed to spawn {worker} for {task_id} - reverting to queued")
                task["status"] = "queued"
                # Remove assignment details to allow reassignment
                for key in ["assignee", "assigned_at", "current_phase"]:
                    if key in task:
                        del task[key]
                self.hive.save_task(task)
    
    def recover_zombie_tasks(self):
        """HARDENING: Detect and recover zombie tasks"""
        for task_id in list(self.active_workers.keys()):
            task = self.hive.load_task(task_id)
            if not task:
                continue
            
            # Check if task is stuck in progress without active worker
            if task.get("status") == "in_progress" and task_id not in self.active_workers:
                started_at = task.get("started_at")
                if started_at:
                    start_time = datetime.fromisoformat(started_at.replace('Z', '+00:00'))
                    age_minutes = (datetime.now(timezone.utc) - start_time).total_seconds() / 60
                    
                    # Recover if zombie for >5 minutes
                    zombie_threshold = self.hive.config["zombie_detection_minutes"]
                    if age_minutes > zombie_threshold:
                        print(f"[{self.timestamp()}] Recovering zombie task: {task_id} (stale for {age_minutes:.1f} minutes)")
                        
                        # Reset to queued for retry
                        task["status"] = "queued"
                        task["current_phase"] = "plan"
                        
                        # Remove assignment details
                        for key in ["assignee", "assigned_at", "started_at", "worktree", "workspace_type"]:
                            if key in task:
                                del task[key]
                        
                        self.hive.save_task(task)
                        self.hive.emit_event("zombie_task_recovered", task_id=task_id, age_minutes=age_minutes)
    
    def monitor_workers(self):
        """Monitor active workers with zombie recovery"""
        # First, detect and recover zombie tasks
        self.recover_zombie_tasks()
        
        completed = []
        
        for task_id, metadata in list(self.active_workers.items()):
            process = metadata["process"]
            poll = process.poll()
            
            if poll is not None:
                # Worker finished
                task = self.hive.load_task(task_id)
                if not task:
                    completed.append(task_id)
                    continue
                
                # HARDENING: Check if worker failed (non-zero exit code)
                if poll != 0:
                    print(f"[{self.timestamp()}] Worker failed for {task_id} (exit: {poll}) - reverting to queued")
                    # Revert task to queued status for retry
                    task["status"] = "queued"
                    # Remove assignment details to allow reassignment
                    for key in ["assignee", "assigned_at", "current_phase", "started_at"]:
                        if key in task:
                            del task[key]
                    self.hive.save_task(task)
                    completed.append(task_id)
                    continue
                
                # Check for result file (simplified)
                results_dir = self.hive.results_dir / task_id
                if results_dir.exists():
                    # Find latest result file
                    result_files = list(results_dir.glob("*.json"))
                    if result_files:
                        latest = max(result_files, key=lambda f: f.stat().st_mtime)
                        try:
                            with open(latest, "r") as f:
                                result = json.load(f)
                            
                            # Update task based on result
                            status = result.get("status", "failed")
                            if status == "success":
                                task["status"] = "completed" 
                            else:
                                task["status"] = "failed"
                            
                            self.hive.save_task(task)
                            print(f"[{self.timestamp()}] Task {task_id} {status}")
                        except Exception as e:
                            print(f"[{self.timestamp()}] Error reading result for {task_id}: {e}")
                
                completed.append(task_id)
        
        # Clean up completed workers
        for task_id in completed:
            if task_id in self.active_workers:
                del self.active_workers[task_id]
    
    def print_status(self):
        """Print concise status"""
        stats = self.hive.get_task_stats()
        active_count = len(self.active_workers)
        
        print(f"[{self.timestamp()}] Active: {active_count} | "
              f"Q: {stats['queued']} | A: {stats['assigned']} | "
              f"IP: {stats['in_progress']} | C: {stats['completed']} | F: {stats['failed']}")
    
    def run_forever(self):
        """Main orchestration loop"""
        print(f"[{self.timestamp()}] QueenLite starting...")
        print(f"Fresh Environment: {self.fresh_env}")
        print("="*50)
        
        try:
            while True:
                self.process_queue()
                self.monitor_workers()
                self.print_status()
                
                # Check if all work is done
                stats = self.hive.get_task_stats()
                if len(self.active_workers) == 0 and stats['queued'] == 0 and stats['assigned'] == 0 and stats['in_progress'] == 0:
                    if stats['completed'] > 0 or stats['failed'] > 0:
                        print(f"[{self.timestamp()}] All tasks completed. Exiting...")
                        break
                
                time.sleep(2)
                
        except KeyboardInterrupt:
            print(f"\n[{self.timestamp()}] QueenLite shutting down...")
            
            # Terminate workers
            for task_id, metadata in self.active_workers.items():
                print(f"[{self.timestamp()}] Terminating {task_id}")
                process = metadata["process"]
                process.terminate()
            
            print(f"[{self.timestamp()}] QueenLite stopped")

def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(description="QueenLite - Streamlined Queen Orchestrator")
    parser.add_argument("--fresh-env", action="store_true", help="Use fresh environment mode with auto-cleanup")
    args = parser.parse_args()
    
    # Create tightly integrated components
    hive_core = HiveCore()
    queen = QueenLite(hive_core, fresh_env=args.fresh_env)
    
    # Start orchestration
    queen.run_forever()

if __name__ == "__main__":
    main()