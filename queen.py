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
import re
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Tuple
from enum import Enum

# Import HiveCore for tight integration
from hive import HiveCore

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
    
    
    def create_worktree(self, worker: str, task_id: str, mode: str = "branch") -> Optional[Path]:
        """Create or reuse git worktree for task
        
        Args:
            worker: Worker type (backend, frontend, infra)
            task_id: Task identifier 
            mode: 'branch' for real implementation with repo files, 'fresh' for empty testing
        """
        safe_task_id = self.hive.slugify(task_id)
        
        # Unified naming: .worktrees/worker/task_id for both modes
        worktree_path = self.hive.worktrees_dir / worker / safe_task_id
        
        if mode == "fresh":
            # Create empty workspace for testing
            worktree_path.mkdir(parents=True, exist_ok=True)
            print(f"[{self.timestamp()}] Created fresh workspace: {worktree_path}")
            return worktree_path
        
        # Branching mode - create git worktree with repo files
        branch = f"agent/{worker}/{safe_task_id}"
        
        # If worktree already exists, reuse it (for refinements)
        if worktree_path.exists():
            print(f"[{self.timestamp()}] Reusing existing worktree: {worktree_path}")
            return worktree_path
        
        try:
            # Create new worktree with branch FROM CURRENT HEAD
            # Important: specify HEAD as the source to get all repo files
            result = subprocess.run(
                ["git", "worktree", "add", "-b", branch, str(worktree_path), "HEAD"],
                cwd=str(self.hive.root),
                capture_output=True, text=True
            )
            
            if result.returncode == 0:
                # CRITICAL: Validate that worktree was created properly
                git_file = worktree_path / ".git"
                if git_file.exists():
                    print(f"[{self.timestamp()}] ✅ Created valid git worktree: {worktree_path} (branch: {branch})")
                    return worktree_path
                else:
                    print(f"[{self.timestamp()}] ❌ Worktree created but missing .git file: {worktree_path}")
                    return None
            else:
                print(f"[{self.timestamp()}] ❌ Git worktree failed (exit {result.returncode}): {result.stderr}")
                return None
                
        except Exception as e:
            print(f"[{self.timestamp()}] ❌ Git worktree error: {e}")
            return None
    
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
                # Use git worktree with full codebase
                worktree = self.create_worktree(worker, task_id)
                if not worktree:
                    print(f"[{self.timestamp()}] ❌ Failed to create worktree for {task_id}")
                    return None
                task["worktree"] = str(worktree)
                task["branch"] = f"agent/{worker}/{self.hive.slugify(task_id)}"
                task["workspace_type"] = "git_worktree"
                self.hive.save_task(task)
        else:
            worktree = Path(task["worktree"])
        
        # Build command - use streamlined worker
        cmd = [
            sys.executable,
            str(self.hive.root / "worker.py"),  # Absolute path
            worker,
            "--one-shot",
            "--task-id", task_id,
            "--run-id", run_id,
            "--workspace", str(worktree),
            "--phase", phase.value
        ]
        
        # Add mode based on workspace type
        workspace_type = task.get("workspace_type")
        if workspace_type == "git_worktree":
            cmd += ["--mode", "repo"]
        else:
            cmd += ["--mode", "fresh"]
        
        # Enhanced environment
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        
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
            
            # Check dependencies
            depends_on = task.get("depends_on", [])
            if depends_on:
                dependencies_met = True
                print(f"[{self.timestamp()}] Checking dependencies for {task_id}: {depends_on}")
                for dep_id in depends_on:
                    dep_task = self.hive.load_task(dep_id)
                    if not dep_task:
                        print(f"[{self.timestamp()}] Dependency {dep_id} not found")
                        dependencies_met = False
                        break
                    dep_status = dep_task.get("status")
                    print(f"[{self.timestamp()}] Dependency {dep_id} status: {dep_status}")
                    if dep_status != "completed":
                        dependencies_met = False
                        break
                
                if not dependencies_met:
                    print(f"[{self.timestamp()}] Skipping {task_id} - dependencies not met")
                    continue
                else:
                    print(f"[{self.timestamp()}] Dependencies met for {task_id}")
            
            # Determine worker type
            worker = task.get("tags", [None])[0] if task.get("tags") else "backend"
            if worker not in ["backend", "frontend", "infra"]:
                worker = "backend"  # Default fallback
            
            # Check per-role limit
            max_per_role = self.hive.config["max_parallel_per_role"].get(worker, 1)
            if active_per_role[worker] >= max_per_role:
                continue
            
            # Always start with APPLY phase (skip PLAN - Claude plans internally)
            current_phase = Phase.APPLY
            
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
    
    def kill_worker(self, task_id: str) -> bool:
        """Kill a specific worker by task_id"""
        if task_id in self.active_workers:
            metadata = self.active_workers[task_id]
            process = metadata["process"]
            
            try:
                # Try graceful termination first
                process.terminate()
                print(f"[{self.timestamp()}] Terminating worker for {task_id} (PID: {process.pid})")
                
                # Wait up to 5 seconds for graceful shutdown
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    # Force kill if not responding
                    process.kill()
                    print(f"[{self.timestamp()}] Force killed worker for {task_id}")
                
                # Clean up from active workers
                del self.active_workers[task_id]
                return True
                
            except Exception as e:
                print(f"[{self.timestamp()}] Error killing worker for {task_id}: {e}")
                return False
        else:
            print(f"[{self.timestamp()}] No active worker found for {task_id}")
            return False
    
    def restart_worker(self, task_id: str) -> bool:
        """Restart a specific worker"""
        # First kill if running
        if task_id in self.active_workers:
            self.kill_worker(task_id)
        
        # Load and reset task
        task = self.hive.load_task(task_id)
        if not task:
            print(f"[{self.timestamp()}] Task {task_id} not found")
            return False
        
        # Reset task to queued for fresh start
        task["status"] = "queued"
        task["current_phase"] = "plan"
        
        # Remove assignment details for clean restart
        for key in ["assignee", "assigned_at", "started_at", "worktree", "workspace_type"]:
            if key in task:
                del task[key]
        
        self.hive.save_task(task)
        print(f"[{self.timestamp()}] Task {task_id} reset to queued for restart")
        return True
    
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
                            current_phase = metadata.get("phase", "apply")
                            
                            if status == "success":
                                # Check if we should advance to TEST phase
                                if current_phase == "apply":
                                    # Spawn TEST phase
                                    print(f"[{self.timestamp()}] Task {task_id} APPLY succeeded, starting TEST phase")
                                    worker = task.get("assignee", "backend")
                                    result = self.spawn_worker(task, worker, Phase.TEST)
                                    if result:
                                        process, run_id = result
                                        self.active_workers[task_id] = {
                                            "process": process,
                                            "run_id": run_id,
                                            "phase": Phase.TEST.value,
                                            "worker_type": worker
                                        }
                                        continue  # Don't mark as completed yet - TEST phase is running
                                else:
                                    # TEST phase completed successfully
                                    task["status"] = "completed"
                                    print(f"[{self.timestamp()}] Task {task_id} TEST succeeded - COMPLETED")
                                    completed.append(task_id)  # Now mark as completed
                            else:
                                # Check for retries before marking as failed
                                retry_count = task.get("retry_count", 0)
                                if retry_count < 2:  # Allow up to 2 retries
                                    print(f"[{self.timestamp()}] Task {task_id} {current_phase} failed - retrying (attempt {retry_count + 1}/2)")
                                    task["retry_count"] = retry_count + 1
                                    # Reset to queued for retry
                                    task["status"] = "queued"
                                    task["current_phase"] = "plan"
                                    # Remove assignment details for clean restart
                                    for key in ["assignee", "assigned_at", "started_at", "worktree", "workspace_type"]:
                                        if key in task:
                                            del task[key]
                                else:
                                    # Max retries reached
                                    task["status"] = "failed"
                                    print(f"[{self.timestamp()}] Task {task_id} {current_phase} failed after {retry_count} retries")
                                completed.append(task_id)  # Mark as completed (failed or retrying)
                            
                            self.hive.save_task(task)
                        except Exception as e:
                            print(f"[{self.timestamp()}] Error reading result for {task_id}: {e}")
                            completed.append(task_id)  # Mark as completed on error
                else:
                    # No result file yet, keep monitoring
                    continue
        
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