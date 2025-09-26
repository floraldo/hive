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
import toml
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Tuple

# Hive logging system
from hive_logging import setup_logging, get_logger
from enum import Enum

# Import HiveCore for tight integration
from .hive_core import HiveCore
from .config import get_config

# Hive utilities for path management
from hive_utils.paths import PROJECT_ROOT, LOGS_DIR, ensure_directory

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

        # Load configuration
        self.config = get_config()

        # State management
        self.active_workers = {}  # task_id -> {process, run_id, phase}

        # Register Queen as a worker to satisfy foreign key constraints
        self._register_as_worker()

        # Simple mode toggle (optional environment-based simplification)
        self.simple_mode = os.environ.get("HIVE_SIMPLE_MODE", "false").lower() == "true"
        if self.simple_mode:
            self.log.info("Running in HIVE_SIMPLE_MODE - some features may be simplified")

    def _register_as_worker(self):
        """Register Queen as a worker in the database."""
        try:
            hive_core_db.register_worker(
                worker_id="queen-orchestrator",
                role="orchestrator",
                capabilities=["task_orchestration", "workflow_management", "worker_coordination"],
                metadata={
                    "version": "2.0.0",
                    "type": "QueenLite",
                    "features": ["stateful_workflows", "parallel_execution", "app_tasks"]
                }
            )
            self.log.info("Queen registered as worker: queen-orchestrator")
        except Exception as e:
            self.log.warning(f"Failed to register Queen as worker: {e}")
            # Continue anyway - registration might already exist

    def _create_enhanced_environment(self, root_path: Optional[Path] = None) -> Dict[str, str]:
        """
        Create enhanced environment with proper Python paths for worker processes.

        Args:
            root_path: Root path to use (defaults to self.hive.root)

        Returns:
            Enhanced environment dictionary with PYTHONPATH configured
        """
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"

        # Use provided root path or default to hive root
        if root_path is None:
            root_path = self.hive.root

        orchestrator_src = (root_path / "apps" / "hive-orchestrator" / "src").as_posix()
        if "PYTHONPATH" in env:
            env["PYTHONPATH"] = f"{orchestrator_src}{os.pathsep}{env['PYTHONPATH']}"
        else:
            env["PYTHONPATH"] = orchestrator_src

        return env

    def is_app_task(self, task: Dict[str, Any]) -> bool:
        """Check if a task is an app task based on assignee format"""
        assignee = task.get("assignee", "")
        return assignee is not None and assignee.startswith("app:")

    def parse_app_assignee(self, assignee: str) -> Tuple[str, str]:
        """Parse app assignee format: app:appname:taskname"""
        parts = assignee.split(":", 2)
        if len(parts) >= 3:
            return parts[1], parts[2]  # app_name, task_name
        elif len(parts) == 2:
            return parts[1], "default"  # app_name, default task
        else:
            raise ValueError(f"Invalid app assignee format: {assignee}")

    def load_app_config(self, app_name: str) -> Dict[str, Any]:
        """Load hive-app.toml configuration for an app"""
        app_dir = self.hive.root / "apps" / app_name
        config_file = app_dir / "hive-app.toml"

        if not config_file.exists():
            raise FileNotFoundError(f"App config not found: {config_file}")

        try:
            return toml.load(config_file)
        except Exception as e:
            raise RuntimeError(f"Failed to parse app config {config_file}: {e}")

    def execute_app_task(self, task: Dict[str, Any]) -> Optional[Tuple[subprocess.Popen, str]]:
        """Execute an app task based on its hive-app.toml configuration"""
        task_id = task["id"]
        assignee = task.get("assignee", "")

        try:
            app_name, task_name = self.parse_app_assignee(assignee)
            self.log.info(f"Executing app task: {app_name}:{task_name}")

            # Load app configuration
            app_config = self.load_app_config(app_name)

            # Get task definition
            tasks_config = app_config.get("tasks", {})
            if task_name not in tasks_config:
                raise ValueError(f"Task '{task_name}' not found in app '{app_name}' config")

            task_config = tasks_config[task_name]
            command_template = task_config.get("command", "")

            if not command_template:
                raise ValueError(f"No command defined for task '{task_name}' in app '{app_name}'")

            # For now, we'll execute the command as-is (without parameter substitution)
            # In the future, this can be enhanced to support parameter substitution
            command = command_template

            # Create run_id for tracking
            run_id = f"{task_id}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-app"

            # Execute in app directory
            app_dir = self.hive.root / "apps" / app_name

            self.log.info(f"Executing command in {app_dir}: {command}")

            # Execute the command
            process = subprocess.Popen(
                command,
                shell=True,
                cwd=app_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=os.environ.copy()
            )

            self.log.info(f"[APP-SPAWN] Started {app_name}:{task_name} for {task_id} (PID: {process.pid})")
            return process, run_id

        except Exception as e:
            self.log.error(f"Failed to execute app task {task_id}: {e}")
            return None
    

    
    
    
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

        # Build command - use -m flag to run as module for proper import resolution
        # This ensures the worker has correct package context for imports
        cmd = [
            sys.executable,
            "-m", "hive_orchestrator.worker",
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
        
        # Enhanced environment with proper Python paths
        env = self._create_enhanced_environment()
        
        try:
            # Windows-specific fix: pipes cause Claude CLI to hang due to buffering deadlock
            # Claude blocks waiting for pipe buffer space, but worker never reads pipes
            # Solution: Let Claude write directly to console (stdout=None, stderr=None)
            import platform

            if platform.system() == "Windows":
                # On Windows, use DEVNULL for stdout to prevent pipe deadlocks
                # But capture stderr briefly to catch initialization errors
                stdout_pipe = subprocess.DEVNULL
                stderr_pipe = subprocess.PIPE  # Capture errors during startup
                self.log.info(f"[DEBUG] Windows detected: using stdout=DEVNULL, stderr=PIPE for error capture")
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
    
    def get_next_command_from_workflow(self, task: Dict[str, Any]) -> Optional[str]:
        """Get the next command to execute based on task's current phase and workflow"""
        workflow = task.get("workflow")
        if not workflow:
            return None

        current_phase = task.get("current_phase", "start")
        phase_config = workflow.get(current_phase)

        if not phase_config:
            self.log.warning(f"No configuration found for phase '{current_phase}' in task {task['id']}")
            return None

        return phase_config.get("command_template")

    def _format_command(self, template: str, task: Dict[str, Any], run_id: Optional[str] = None) -> str:
        """Format command template with task data"""
        # Create format dictionary
        format_data = {
            "task_id": task["id"],
            "run_id": run_id or f"{task['id']}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
        }

        # Add payload data
        payload = task.get("payload", {})
        if isinstance(payload, dict):
            format_data.update(payload)

        # Format the command
        try:
            return template.format(**format_data)
        except KeyError as e:
            self.log.warning(f"Missing parameter {e} for command template: {template}")
            return template

    def _advance_task_phase(self, task: Dict[str, Any], success: bool = True) -> Optional[str]:
        """Advance task to the next phase based on workflow definition"""
        workflow = task.get("workflow")
        if not workflow:
            return None

        current_phase = task.get("current_phase", "start")
        phase_config = workflow.get(current_phase, {})

        # Determine next phase
        if success:
            next_phase = phase_config.get("next_phase_on_success")
        else:
            next_phase = phase_config.get("next_phase_on_failure", "failed")

        if not next_phase:
            self.log.warning(f"No next phase defined for task {task['id']} in phase {current_phase}")
            return None

        # Update task phase
        if next_phase == "completed":
            hive_core_db.update_task_status(task["id"], "completed", {})
            self.log.info(f"Task {task['id']} completed successfully")
        elif next_phase == "failed":
            hive_core_db.update_task_status(task["id"], "failed", {})
            self.log.info(f"Task {task['id']} failed")
        elif next_phase == "review_pending":
            # Special status for tasks awaiting intelligent review
            hive_core_db.update_task_status(task["id"], "review_pending", {
                "current_phase": current_phase
            })
            self.log.info(f"Task {task['id']} moved to review_pending for AI inspection")
        else:
            # Move to next phase and back to queued for processing
            hive_core_db.update_task_status(task["id"], "queued", {
                "current_phase": next_phase
            })
            self.log.info(f"Task {task['id']} advanced to phase '{next_phase}'")

        return next_phase

    def process_queued_tasks(self):
        """Process tasks in queued status by starting their workflows with PARALLEL execution"""
        # Calculate available slots for parallel execution
        max_parallel = sum(self.hive.config["max_parallel_per_role"].values())
        slots_free = max_parallel - len(self.active_workers)

        if slots_free <= 0:
            return  # No capacity for new tasks

        # Get multiple queued tasks up to available capacity
        queued_tasks = hive_core_db.get_queued_tasks(limit=slots_free)
        if not queued_tasks:
            return

        # Count active workers per role
        active_per_role = {"backend": 0, "frontend": 0, "infra": 0}
        for metadata in self.active_workers.values():
            worker_type = metadata.get("worker_type", "unknown")
            if worker_type in active_per_role:
                active_per_role[worker_type] += 1

        self.log.info(f"[PARALLEL] Processing {len(queued_tasks)} legacy tasks with {slots_free} free slots")
        
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
            
            # Check if this is an app task
            if self.is_app_task(task):
                self.log.info(f"Processing app task: {task_id}")

                # Set assigned status for app task
                assignee = task.get("assignee", "")
                hive_core_db.update_task_status(task_id, "assigned", {
                    "assignee": assignee,
                    "assigned_at": datetime.now(timezone.utc).isoformat(),
                    "current_phase": "execute"
                })

                # Execute app task
                result = self.execute_app_task(task)
                if result:
                    process, run_id = result
                    self.active_workers[task_id] = {
                        "process": process,
                        "run_id": run_id,
                        "phase": "execute",
                        "worker_type": "app"
                    }
                    hive_core_db.update_task_status(task_id, "in_progress", {
                        "started_at": datetime.now(timezone.utc).isoformat()
                    })
                    self.log.info(f"Successfully spawned app task for {task_id} (PID: {process.pid})")
                else:
                    # App task spawn failed - revert to queued
                    self.log.error(f"Failed to spawn app task {task_id} - reverting to queued")
                    hive_core_db.update_task_status(task_id, "queued", {
                        "assignee": None,
                        "assigned_at": None,
                        "current_phase": None
                    })
                continue  # Move to next task

            # Handle regular worker tasks
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
                current_assignee = task.get("assignee", "")

                # Preserve app task assignees (they have special format)
                should_preserve_assignee = current_assignee and current_assignee.startswith("app:")

                if started_at:
                    start_time = datetime.fromisoformat(started_at.replace('Z', '+00:00'))
                    age_minutes = (datetime.now(timezone.utc) - start_time).total_seconds() / 60

                    # Only recover if task has been stuck for more than zombie detection threshold
                    zombie_threshold = self.hive.config.get("zombie_detection_minutes", 5)
                    if age_minutes >= zombie_threshold:
                        age_str = f"{age_minutes:.1f} minutes"
                        self.log.info(f"[RECOVER] Recovering zombie task: {task_id} (stale for {age_str})")

                        # Reset to queued for retry, preserving assignee for app tasks
                        hive_core_db.update_task_status(task_id, "queued", {
                            "current_phase": "plan" if not should_preserve_assignee else "execute",
                            "assignee": current_assignee if should_preserve_assignee else None,
                            "assigned_at": None,
                            "started_at": None,
                            "worktree": None,
                            "workspace_type": None
                        })
                else:
                    # No start time means it's definitely stuck
                    self.log.info(f"[RECOVER] Recovering zombie task without start time: {task_id}")
                    hive_core_db.update_task_status(task_id, "queued", {
                        "current_phase": "plan" if not should_preserve_assignee else "execute",
                        "assignee": current_assignee if should_preserve_assignee else None,
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
            # Try to capture error output if available
            if process.stderr:
                try:
                    stderr_output = process.stderr.read()
                    if stderr_output:
                        self.log.error(f"Worker {task_id} stderr: {stderr_output[:500]}")
                except (IOError, OSError) as e:
                    self.log.debug(f"Could not read stderr for worker {task_id}: {e}")

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
        current_phase = metadata.get("phase", "apply")
        worker_type = metadata.get("worker_type", "unknown")

        # Handle app tasks (which don't save results to database)
        if worker_type == "app" or self.is_app_task(task):
            self.log.info(f"App task {task_id} completed with exit code 0")
            return self._handle_task_success(task_id, task, current_phase, completed)

        # Handle regular worker tasks
        run_id = metadata.get("run_id")
        if not run_id:
            self.log.warning(f"Worker for {task_id} finished successfully but no run_id was found.")
            return self._handle_task_failure(task_id, task, current_phase, completed)

        run_data = hive_core_db.get_run(run_id)
        if not run_data:
            self.log.warning(f"Worker for {task_id} finished successfully but no run data was found for run_id: {run_id}")
            # Treat as failure to allow for retries
            return self._handle_task_failure(task_id, task, current_phase, completed)

        try:
            status = run_data.get("result", {}).get("status", "failed")

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
        # Check if this is an app task (which don't have phases)
        if self.is_app_task(task) or current_phase == "execute":
            # App tasks are completed directly without phases
            hive_core_db.update_task_status(task_id, "completed", {})
            self.log.info(f"✅ App task {task_id} COMPLETED successfully")
            if self.live_output:
                print("-" * 70)
            completed.append(task_id)
            return True

        # Handle regular worker tasks with phases
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
    
    def process_workflow_tasks(self):
        """Process queued tasks using workflow definitions with PARALLEL execution"""
        # Calculate available slots for parallel execution
        max_parallel = sum(self.hive.config["max_parallel_per_role"].values())
        slots_free = max_parallel - len(self.active_workers)

        if slots_free <= 0:
            return  # No capacity for new tasks

        # Get multiple queued tasks up to available capacity
        queued_tasks = hive_core_db.get_queued_tasks(limit=slots_free)
        if not queued_tasks:
            return

        self.log.info(f"[PARALLEL] Processing {len(queued_tasks)} tasks with {slots_free} free slots")
        for task in queued_tasks:
            task_id = task["id"]

            # Skip if already running
            if task_id in self.active_workers:
                continue

            workflow = task.get("workflow")
            if not workflow:
                # Legacy task without workflow - use old method
                self.process_queued_tasks()  # Fall back to old method
                return

            current_phase = task.get("current_phase", "start")

            # Check if this phase has a command
            command_template = self.get_next_command_from_workflow(task)

            if not command_template:
                # No command means transition phase (like "start")
                # Advance to next phase
                self._advance_task_phase(task, success=True)
                continue

            # Format and execute command
            run_id = f"{task_id}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
            command = self._format_command(command_template, task, run_id)

            # Create run record if it's a worker task
            if "hive_orchestrator.worker" in command:
                actual_run_id = hive_core_db.create_run(
                    task_id=task_id,
                    worker_id="queen-orchestrator",  # Match the registered worker ID
                    phase=current_phase
                )
                # Use the actual run_id from database
                command = self._format_command(command_template, task, actual_run_id)

            # Update task to in_progress
            hive_core_db.update_task_status(task_id, "in_progress", {
                "started_at": datetime.now(timezone.utc).isoformat()
            })

            # Execute command
            try:
                # Enhanced environment with proper Python paths (same as spawn_worker)
                env = self._create_enhanced_environment(PROJECT_ROOT)

                # Debug logging for command execution
                self.log.info(f"[DEBUG] Executing workflow command: {command}")
                self.log.info(f"[DEBUG] Working directory: {PROJECT_ROOT}")
                self.log.info(f"[DEBUG] PYTHONPATH: {env.get('PYTHONPATH', 'not set')}")

                process = subprocess.Popen(
                    command,
                    shell=True,
                    cwd=str(PROJECT_ROOT),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    env=env
                )

                self.active_workers[task_id] = {
                    "process": process,
                    "run_id": run_id,
                    "phase": current_phase,
                    "worker_type": "workflow"
                }
                self.log.info(f"[PARALLEL] Spawned task {task_id} phase '{current_phase}' (PID: {process.pid})")

            except Exception as e:
                self.log.error(f"Failed to execute task {task_id}: {e}")
                hive_core_db.update_task_status(task_id, "failed", {
                    "failure_reason": str(e)
                })

            # Check capacity again
            if len(self.active_workers) >= max_parallel:
                self.log.info(f"[PARALLEL] Reached max capacity ({max_parallel}), stopping task spawn")
                break

    def process_review_tasks(self):
        """Process tasks awaiting intelligent review"""
        review_tasks = hive_core_db.get_tasks_by_status("review_pending")

        for task in review_tasks:
            task_id = task["id"]
            self.log.info(f"Task {task_id} is awaiting review")
            self.log.info(f"  Use: 'hive review-next-task' to see review details")
            self.log.info(f"  Use: 'hive complete-review {task_id} --decision [approve|reject|rework]' to complete review")
            # The AI Queen will handle this through the CLI tools
            # No auto-approval - this is the AI's decision point

    def monitor_workflow_processes(self):
        """Monitor running processes and handle completion"""
        completed = []

        for task_id, metadata in list(self.active_workers.items()):
            process = metadata["process"]
            poll = process.poll()

            if poll is None:
                continue  # Still running

            # Process finished
            task = hive_core_db.get_task(task_id)
            if not task:
                completed.append(task_id)
                continue

            success = (poll == 0)
            self.log.info(f"Task {task_id} phase '{metadata['phase']}' finished with exit code {poll}")

            # Advance to next phase based on success/failure
            self._advance_task_phase(task, success=success)
            completed.append(task_id)

        # Clean up completed workers
        for task_id in completed:
            if task_id in self.active_workers:
                del self.active_workers[task_id]

    def run_forever(self):
        """Main orchestration loop - event-driven state machine"""
        self.log.info("QueenLite starting (Stateful Workflow Mode)...")
        print("Workflow-driven task orchestration enabled")
        print("="*50)
        
        # Initialize database
        hive_core_db.init_db()

        try:
            while True:
                # Step 1: Process queued tasks (mechanical execution)
                self.process_workflow_tasks()

                # Step 2: Process review_pending tasks (intelligent decision-making)
                self.process_review_tasks()

                # Step 3: Monitor running processes (mechanical)
                self.monitor_workflow_processes()

                # Status update
                self.print_status()

                # Check if all work is done
                stats = self.hive.get_task_stats()
                review_pending = len(hive_core_db.get_tasks_by_status("review_pending"))

                if len(self.active_workers) == 0 and stats['queued'] == 0 and stats['assigned'] == 0 and stats['in_progress'] == 0 and review_pending == 0:
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

    # Initialize database before anything else
    hive_core_db.init_db()

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
