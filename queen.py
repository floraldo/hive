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

# Hive logging system
from hive_logging import setup_logging, get_logger
from enum import Enum

# Import HiveCore for tight integration
from hive import HiveCore

# Hive database system
try:
    import hive_core_db
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent / "packages" / "hive-core-db" / "src"))
    import hive_core_db

class Phase(Enum):
    """Task execution phases"""
    PLAN = "plan"
    APPLY = "apply" 
    TEST = "test"

class QueenLite:
    """Streamlined orchestrator with preserved hardening"""
    
    def __init__(self, hive_core: HiveCore, live_output: bool = False):
        # Tight integration with HiveCore
        self.hive = hive_core
        self.live_output = live_output
        
        # Initialize logger
        self.log = get_logger(__name__)
        
        # State management
        self.active_workers = {}  # task_id -> {process, run_id, phase}
        
        # Simple mode toggle (optional environment-based simplification)
        self.simple_mode = os.environ.get("HIVE_SIMPLE_MODE", "false").lower() == "true"
        if self.simple_mode:
            self.log.info("Running in HIVE_SIMPLE_MODE - some features may be simplified")
    

    
    
    
    def spawn_worker(self, task: Dict[str, Any], worker: str, phase: Phase) -> Optional[Tuple[subprocess.Popen, str]]:
        """Spawn worker and let it manage its own workspace."""
        task_id = task["id"]
        run_id = f"{task_id}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{phase.value}"
        
        # The worker will create its own workspace based on task_id, worker_id, and mode.
        # We no longer need to create it here.
        self.log.info(f"Delegating workspace creation to worker for task: {task_id}")

        # Determine mode from task definition, default to "repo" if not specified
        mode = task.get("workspace", "repo")
        self.log.info(f"Task requires '{mode}' workspace mode")

        # Build command - remove the --workspace argument
        cmd = [
            sys.executable,
            str(self.hive.root / "worker.py"),
            worker,
            "--one-shot",
            "--task-id", task_id,
            "--run-id", run_id,
            "--phase", phase.value,
            "--mode", mode
        ]
        
        # Add live output flag if enabled
        if self.live_output:
            cmd.append("--live")
        
        # Enhanced environment
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        
        try:
            # Windows-specific fix: pipes cause Claude CLI to hang due to buffering deadlock
            # Claude blocks waiting for pipe buffer space, but worker never reads pipes
            # Solution: Let Claude write directly to console (stdout=None, stderr=None)
            import platform

            if platform.system() == "Windows":
                # On Windows, avoid pipes to prevent Claude CLI deadlock
                # Force no pipe by using subprocess.DEVNULL
                stdout_pipe = subprocess.DEVNULL
                stderr_pipe = subprocess.DEVNULL
                self.log.info(f"[DEBUG] Windows detected: using stdout=DEVNULL, stderr=DEVNULL")
            else:
                # On Unix, pipes work fine and provide better monitoring
                stdout_pipe = subprocess.PIPE
                stderr_pipe = subprocess.PIPE
                self.log.info(f"[DEBUG] Unix detected: using stdout=PIPE, stderr=PIPE")

            process = subprocess.Popen(
                cmd,
                stdin=subprocess.DEVNULL,  # Prevent stdin inheritance issues
                stdout=stdout_pipe,
                stderr=stderr_pipe,
                text=True,
                env=env
            )
            
            self.log.info(f"[SPAWN] Spawned {worker} for {task_id} phase:{phase.value} (PID: {process.pid})")
            if self.live_output:
                print("-" * 70)
            return process, run_id
            
        except Exception as e:
            self.log.info(f"Spawn failed: {e}")
            return None
    
    def process_queue(self):
        """Process task queue with hardened status management"""
        queued_tasks = hive_core_db.get_queued_tasks()
        if not queued_tasks:
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
        
        for task in queued_tasks:
            task_id = task["id"]
            
            # Check dependencies
            depends_on = task.get("depends_on", [])
            if depends_on:
                dependencies_met = True
                for dep_id in depends_on:
                    dep_task = hive_core_db.get_task(dep_id)
                    if not dep_task or dep_task.get("status") != "completed":
                        dependencies_met = False
                        break

                if not dependencies_met:
                    continue  # Skip silently - dependencies not met
            
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
            hive_core_db.update_task_status(task_id, "assigned", {
                "assignee": worker,
                "assigned_at": datetime.now(timezone.utc).isoformat(),
                "current_phase": current_phase.value
            })
            
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
                hive_core_db.update_task_status(task_id, "in_progress", {
                    "started_at": datetime.now(timezone.utc).isoformat()
                })
                self.log.info(f"Successfully spawned {worker} for {task_id} (PID: {process.pid})")
            else:
                # HARDENING: Spawn failed - revert task to queued status
                self.log.info(f"Failed to spawn {worker} for {task_id} - reverting to queued")
                hive_core_db.update_task_status(task_id, "queued", {
                    "assignee": None,
                    "assigned_at": None,
                    "current_phase": None
                })
    
    def kill_worker(self, task_id: str) -> bool:
        """Kill a specific worker by task_id"""
        if task_id in self.active_workers:
            metadata = self.active_workers[task_id]
            process = metadata["process"]
            
            try:
                # Try graceful termination first
                self.log.info(f"Terminating worker for {task_id} (PID: {process.pid})")
                process.terminate()
                
                # Wait up to N seconds for graceful shutdown
                try:
                    shutdown_timeout = self.hive.config.get("orchestration", {}).get("graceful_shutdown_seconds", 5)
                    process.wait(timeout=shutdown_timeout)
                except subprocess.TimeoutExpired:
                    # Force kill if not responding
                    process.kill()
                    self.log.info(f"Force killed worker for {task_id}")
                
                # Clean up from active workers
                del self.active_workers[task_id]
                return True
                
            except Exception as e:
                self.log.info(f"Error killing worker for {task_id}: {e}")
                return False
        else:
            self.log.info(f"No active worker found for {task_id}")
            return False
    
    def restart_worker(self, task_id: str) -> bool:
        """Restart a specific worker"""
        # First kill if running
        if task_id in self.active_workers:
            self.kill_worker(task_id)

        # Load and reset task
        task = hive_core_db.get_task(task_id)
        if not task:
            self.log.info(f"Task {task_id} not found")
            return False

        # Reset task to queued for fresh start
        hive_core_db.update_task_status(task_id, "queued", {
            "current_phase": "plan",
            "assignee": None,
            "assigned_at": None,
            "started_at": None,
            "worktree": None,
            "workspace_type": None
        })
        self.log.info(f"Task {task_id} reset to queued for restart")
        return True
    
    def recover_zombie_tasks(self):
        """HARDENING: Detect and recover zombie tasks using database queries"""
        # Query database for tasks that are in_progress but not actively managed
        in_progress_tasks = hive_core_db.get_tasks_by_status("in_progress")
        if not in_progress_tasks:
            return

        for task in in_progress_tasks:
            task_id = task["id"]
            # Check if task is stuck in progress without active worker
            if task_id not in self.active_workers:
                started_at = task.get("started_at")
                if started_at:
                    start_time = datetime.fromisoformat(started_at.replace('Z', '+00:00'))
                    age_minutes = (datetime.now(timezone.utc) - start_time).total_seconds() / 60
                    age_str = f"{age_minutes:.1f} minutes"
                else:
                    age_str = "unknown duration"

                # Recover zombie tasks immediately (no waiting)
                self.log.info(f"[RECOVER] Recovering zombie task: {task_id} (stale for {age_str})")

                # Reset to queued for retry
                hive_core_db.update_task_status(task_id, "queued", {
                    "current_phase": "plan",
                    "assignee": None,
                    "assigned_at": None,
                    "started_at": None,
                    "worktree": None,
                    "workspace_type": None
                })
    
    def monitor_workers(self):
        """Monitor active workers with zombie recovery and timeout detection"""
        # First, detect and recover zombie tasks
        self.recover_zombie_tasks()
        
        # Check for timed-out workers
        self._check_worker_timeouts()
        
        completed = []
        
        for task_id, metadata in list(self.active_workers.items()):
            if self._process_finished_worker(task_id, metadata, completed):
                continue
        
        # Clean up completed workers
        self._cleanup_completed_workers(completed)
    
    def _process_finished_worker(self, task_id: str, metadata: Dict[str, Any], completed: List[str]) -> bool:
        """Process a finished worker and return True if processing should continue to next worker"""
        process = metadata["process"]
        poll = process.poll()
        
        if poll is None:
            return True  # Worker still running, continue to next
        
        # Worker finished - load task
        task = hive_core_db.get_task(task_id)
        if not task:
            completed.append(task_id)
            return True
        
        # Handle worker failure (non-zero exit code)
        if poll != 0:
            self._handle_worker_failure(task_id, task, completed)
            return True
        
        # Handle successful worker completion
        return self._handle_worker_success(task_id, task, metadata, completed)
    
    def _handle_worker_failure(self, task_id: str, task: Dict[str, Any], completed: List[str]):
        """Handle worker process failure"""
        self.log.info(f"Worker failed for {task_id} - reverting to queued")

        # Revert task to queued status for retry
        hive_core_db.update_task_status(task_id, "queued", {
            "assignee": None,
            "assigned_at": None,
            "current_phase": None,
            "started_at": None
        })
        completed.append(task_id)
    
    def _handle_worker_success(self, task_id: str, task: Dict[str, Any], metadata: Dict[str, Any], completed: List[str]) -> bool:
        """Handle successful worker completion. Returns True if processing should continue to next worker"""
        run_id = metadata.get("run_id")
        if not run_id:
            self.log.warning(f"Worker for {task_id} finished successfully but no run_id was found.")
            return self._handle_task_failure(task_id, task, metadata.get("phase", "apply"), completed)

        run_data = hive_core_db.get_run(run_id)
        if not run_data:
            self.log.warning(f"Worker for {task_id} finished successfully but no run data was found for run_id: {run_id}")
            # Treat as failure to allow for retries
            return self._handle_task_failure(task_id, task, metadata.get("phase", "apply"), completed)
        
        try:
            status = run_data.get("result", {}).get("status", "failed")
            current_phase = metadata.get("phase", "apply")
            
            if status == "success":
                return self._handle_task_success(task_id, task, current_phase, completed)
            else:
                return self._handle_task_failure(task_id, task, current_phase, completed)
                
        except Exception as e:
            self.log.info(f"Error processing result for {task_id}: {e}")
            completed.append(task_id)
            return True
    
    
    def _handle_task_success(self, task_id: str, task: Dict[str, Any], current_phase: str, completed: List[str]) -> bool:
        """Handle successful task completion"""
        if current_phase == "apply":
            # Advance to TEST phase
            self.log.info(f"✅ Task {task_id} APPLY succeeded, starting TEST phase")
            if self.live_output:
                print("-" * 70)
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
                # CRITICAL: Update task status for the new phase
                hive_core_db.update_task_status(task_id, "in_progress", {
                    "current_phase": Phase.TEST.value,
                    "started_at": datetime.now(timezone.utc).isoformat()
                })
                return True  # Don't mark as completed yet - TEST phase is running
            else:
                # Spawn failed for TEST phase - mark as failed
                self.log.error(f"Failed to spawn TEST phase for {task_id}")
                hive_core_db.update_task_status(task_id, "failed", {
                    "failure_reason": "Failed to spawn TEST phase"
                })
                completed.append(task_id)
                return True
        else:
            # TEST phase completed successfully
            hive_core_db.update_task_status(task_id, "completed", {})
            self.log.info(f"✅ Task {task_id} TEST succeeded - COMPLETED")
            if self.live_output:
                print("-" * 70)
            completed.append(task_id)
        
        return True
    
    def _handle_task_failure(self, task_id: str, task: Dict[str, Any], current_phase: str, completed: List[str]) -> bool:
        """Handle task failure with retry logic"""
        retry_count = task.get("retry_count", 0)
        max_retries = self.hive.config["orchestration"]["task_retry_limit"]
        
        if retry_count < max_retries:
            # Retry the task
            self.log.info(f"Task {task_id} {current_phase} failed - retrying (attempt {retry_count + 1}/{max_retries})")
            hive_core_db.update_task_status(task_id, "queued", {
                "retry_count": retry_count + 1,
                "current_phase": "plan",
                "assignee": None,
                "assigned_at": None,
                "started_at": None,
                "worktree": None,
                "workspace_type": None
            })
        else:
            # Max retries reached
            hive_core_db.update_task_status(task_id, "failed", {})
            self.log.info(f"Task {task_id} {current_phase} failed after {retry_count} retries")

        completed.append(task_id)
        return True
    
    def _check_worker_timeouts(self):
        """Check for timed-out workers and kill them"""
        current_time = datetime.now(timezone.utc)
        timeout_minutes = self.hive.config.get("worker_timeout_minutes", 30)
        timeout_threshold = timeout_minutes * 60  # Convert to seconds
        
        for task_id, metadata in list(self.active_workers.items()):
            # Get task to check start time
            task = hive_core_db.get_task(task_id)
            if not task or "started_at" not in task:
                continue
            
            try:
                started_at = datetime.fromisoformat(task["started_at"].replace('Z', '+00:00'))
                elapsed_seconds = (current_time - started_at).total_seconds()
                
                if elapsed_seconds > timeout_threshold:
                    self.log.warning(f"Worker for {task_id} timed out after {elapsed_seconds/60:.1f} minutes")
                    
                    # Kill the timed-out worker
                    process = metadata["process"]
                    try:
                        process.terminate()
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                    except:
                        pass
                    
                    # Reset task to queued for retry
                    hive_core_db.update_task_status(task_id, "queued", {
                        "current_phase": "plan",
                        "assignee": None,
                        "assigned_at": None,
                        "started_at": None,
                        "worktree": None,
                        "workspace_type": None
                    })
                    
                    # Remove from active workers
                    if task_id in self.active_workers:
                        del self.active_workers[task_id]
                        
            except Exception as e:
                self.log.error(f"Error checking timeout for {task_id}: {e}")
    
    def _cleanup_completed_workers(self, completed: List[str]):
        """Clean up completed workers from active_workers dict"""
        for task_id in completed:
            if task_id in self.active_workers:
                del self.active_workers[task_id]
    
    def print_status(self):
        """Print clean status update with clear separation"""
        stats = self.hive.get_task_stats()
        active_count = len(self.active_workers)
        
        # Get queued workers for display
        queued_tasks = hive_core_db.get_queued_tasks()
        queued_workers = []
        for task in queued_tasks:
            task_id = task["id"]
            worker = task.get("tags", [None])[0] if task.get("tags") else "backend"
            queued_workers.append(f"[{worker.upper()}] {task_id}")
        
        # Clean status update
        self.log.info(f"\n[STATUS] Q:{stats['queued']} I:{stats['in_progress']} P:{stats['assigned']} C:{stats['completed']} F:{stats['failed']} | Active: {active_count}")
        
        # Show active workers
        if self.active_workers:
            for task_id, metadata in self.active_workers.items():
                worker_type = metadata["worker_type"]
                phase = metadata["phase"]
                pid = metadata["process"].pid
                
                # Simple runtime calc
                task = hive_core_db.get_task(task_id)
                if task and "started_at" in task:
                    try:
                        started = datetime.fromisoformat(task["started_at"].replace('Z', '+00:00'))
                        runtime_sec = int((datetime.now(timezone.utc) - started).total_seconds())
                        runtime_str = f"{runtime_sec//60}m {runtime_sec%60}s"
                    except:
                        runtime_str = "?"
                else:
                    runtime_str = "?"
                
                # Handle phase as either string or Enum
                phase_str = phase.value if hasattr(phase, 'value') else phase
                print(f"  [WORK] [{worker_type.upper()}] {task_id} ({phase_str}, {runtime_str}, PID: {pid})")
        
        # Show queued workers
        if queued_workers:
            queued_str = ', '.join(queued_workers[:3])  # Show max 3
            if len(queued_workers) > 3:
                queued_str += f"+{len(queued_workers)-3}"
            print(f"  [QUEUE] Queued: {queued_str}")
        
        # Clear separator for worker output
        print("-" * 70)
    
    def run_forever(self):
        """Main orchestration loop"""
        self.log.info("QueenLite starting...")
        print("Task-driven workspace management enabled")
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
                        self.log.info("All tasks completed. Exiting...")
                        break
                
                time.sleep(self.hive.config["orchestration"]["status_refresh_seconds"])
                
        except KeyboardInterrupt:
            self.log.info("\nQueenLite shutting down...")
            
            # Terminate workers
            for task_id, metadata in self.active_workers.items():
                self.log.info(f"Terminating {task_id}")
                process = metadata["process"]
                process.terminate()
            
            self.log.info("QueenLite stopped")

def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(description="QueenLite - Streamlined Queen Orchestrator")
    parser.add_argument("--live", action="store_true",
                       help="Enable live streaming output from workers")
    args = parser.parse_args()
    
    # Configure logging for Queen
    setup_logging(
        name="queen",
        log_to_file=True,
        log_file_path="logs/queen.log"
    )
    log = get_logger(__name__)
    
    # Create tightly integrated components
    hive_core = HiveCore()
    queen = QueenLite(hive_core, live_output=args.live)
    
    # Start orchestration
    queen.run_forever()

if __name__ == "__main__":
    main()
