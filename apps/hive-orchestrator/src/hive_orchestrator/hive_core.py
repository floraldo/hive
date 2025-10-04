#!/usr/bin/env python3
"""HiveCore - Streamlined Hive Manager
Unified task management with built-in cleanup and configuration
"""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Hive utilities for path management
from hive_config.paths import HIVE_DIR, LOGS_DIR, PROJECT_ROOT, WORKTREES_DIR

# Hive logging system
from hive_logging import get_logger

logger = get_logger(__name__)

from .core import db as hive_core_db

# Hive database system - use internal core database layer


class HiveCore:
    """Central SDK for all Hive system operations - the shared 'Hive Mind'"""

    def __init__(self, root_dir: Path | None = None, config: dict[str, Any] | None = None) -> None:
        # Use authoritative paths from singleton
        self.root = PROJECT_ROOT
        self.hive_dir = HIVE_DIR
        self.tasks_dir = self.hive_dir / "tasks"
        self.results_dir = self.hive_dir / "results"
        self.bus_dir = self.hive_dir / "bus"
        self.worktrees_dir = WORKTREES_DIR
        self.logs_dir = LOGS_DIR
        self.workers_dir = self.hive_dir / "workers"

        # Initialize logger
        self.log = get_logger(__name__)

        # Use provided configuration or load defaults
        self.config = config if config is not None else self.load_config()

        # Initialize database system
        hive_core_db.init_db()
        self.log.info("Hive database initialized")

        # Ensure directories exist
        self.ensure_directories()

    def timestamp(self) -> str:
        """Return ISO timestamp for CLI output"""
        return datetime.now(UTC).isoformat()

    def load_config(self) -> dict[str, Any]:
        """Load configuration from file or use defaults.

        This method provides a fallback configuration pattern:
        1. Defines sensible default configuration values
        2. Attempts to load user configuration from hive_config.json
        3. Merges user config over defaults (user config takes precedence)
        4. Returns merged configuration even if file loading fails

        This ensures the system always has valid configuration, even if the
        configuration file is missing or malformed. This is an acceptable
        use of fallback patterns for configuration loading.

        Returns:
            Dict containing the merged configuration with guaranteed minimum keys

        """
        config_file = self.root / "hive_config.json"

        # Default configuration
        default_config = {
            "max_parallel_per_role": {"backend": 2, "frontend": 2, "infra": 1},
            "worker_timeout_minutes": 30,
            "zombie_detection_minutes": 5,
            "fresh_cleanup_enabled": True,
            "pr_creation_enabled": False,
            "default_max_retries": 2,
            "orchestration": {
                "task_retry_limit": 2,
                "status_refresh_seconds": 10,
                "graceful_shutdown_seconds": 5,
            },
        }

        if config_file.exists():
            try:
                with open(config_file) as f:
                    file_config = json.load(f)
                # Merge with defaults
                default_config.update(file_config)
            except Exception as e:
                logger.warning(f"Warning: Could not load config: {e}")

        return default_config

    def get_config(self, key: str, worker_type: str | None = None) -> Any:
        """Get configuration value with optional worker-specific override"""
        # Check for worker-specific config
        if worker_type:
            worker_config_file = self.workers_dir / f"{worker_type}.json"
            if worker_config_file.exists():
                try:
                    with open(worker_config_file) as f:
                        worker_data = json.load(f)
                    if "config" in worker_data and key in worker_data["config"]:
                        return worker_data["config"][key]
                except (OSError, json.JSONDecodeError, KeyError) as e:
                    logger.debug(f"Could not load worker config from {worker_config_file}: {e}")

        # Return default from main config
        return self.config.get(key)

    def ensure_directories(self) -> None:
        """Create all required directories"""
        dirs = [
            self.hive_dir,
            self.tasks_dir,
            self.results_dir,
            self.bus_dir,
            self.worktrees_dir,
            self.logs_dir,
            self.workers_dir,
        ]
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)

    # === Path Management Methods ===

    def get_task_path(self, task_id: str) -> Path:
        """Get path to task JSON file"""
        return self.tasks_dir / f"{task_id}.json"

    def get_result_path(self, task_id: str, run_id: str) -> Path:
        """Get path to result JSON file"""
        result_dir = self.results_dir / task_id
        result_dir.mkdir(parents=True, exist_ok=True)
        return result_dir / f"{run_id}.json"

    def get_log_path(self, task_id: str, run_id: str) -> Path:
        """Get path to log file"""
        log_dir = self.logs_dir / task_id
        log_dir.mkdir(parents=True, exist_ok=True)
        return log_dir / f"{run_id}.log"

    def get_worktree_path(self, worker: str, task_id: str) -> Path:
        """Get path to git worktree"""
        return self.worktrees_dir / worker / self.slugify(task_id)

    def slugify(self, text: str) -> str:
        """Convert text to filesystem-safe slug"""
        import re

        text = re.sub(r"[^\w\s-]", "", text)
        text = re.sub(r"[-\s]+", "-", text)
        return text.lower()

    # === Result Management Methods ===

    def save_result(self, task_id: str, run_id: str, result: dict[str, Any]) -> bool:
        """Save task execution result atomically"""
        try:
            result_path = self.get_result_path(task_id, run_id)
            result_data = {"task_id": task_id, "run_id": run_id, "timestamp": datetime.now(UTC).isoformat() ** result}

            # Atomic write: write to temp, then move
            temp_path = result_path.with_suffix(".tmp")
            with open(temp_path, "w") as f:
                json.dump(result_data, f, indent=2)

            # Atomic write: temp file then replace
            try:
                temp_path.replace(result_path)  # replace() is more robust on Windows
            except (PermissionError, OSError) as e:
                self.log.error(f"Failed to save result: {e}")
                raise
            return True
        except Exception as e:
            self.log.error(f"Error saving result: {e}")
            return False

    def load_task_queue(self) -> list[str]:
        """Load task queue from database"""
        try:
            tasks = hive_core_db.get_queued_tasks(limit=1000)
            return [task["id"] for task in tasks]
        except Exception as e:
            self.log.error(f"Error loading queue from database: {e}")
            return []

    def save_task_queue(self, queue: list[str]) -> None:
        """Save task queue - No-op since database manages queue through task status"""
        # Database manages queue state through task status - no explicit queue file needed

    def load_task(self, task_id: str) -> dict[str, Any] | None:
        """Load task data by ID from database"""
        try:
            return hive_core_db.get_task(task_id)
        except Exception as e:
            self.log.error(f"Error loading task {task_id} from database: {e}")
            return None

    def save_task(self, task: dict[str, Any]) -> None:
        """Save task data to database"""
        task_id = task.get("id")
        if not task_id:
            self.log.error("Task missing ID")
            return

        try:
            # Check if task exists in database
            existing_task = hive_core_db.get_task(task_id)

            if existing_task:
                # Update existing task status
                status = task.get("status", existing_task.get("status", "queued"))
                assigned_worker = task.get("assignee"),
                success = hive_core_db.update_task_status(task_id, status, assigned_worker)
                if not success:
                    self.log.error(f"Failed to update task {task_id} status to {status}")
            else:
                # Create new task
                title = task.get("title", task_id)
                description = task.get("description", "")
                task_type = task.get("task_type", "general")
                priority = task.get("priority", 1)
                max_retries = task.get("max_retries", 3)
                tags = task.get("tags", [])

                # Extract payload (other task data)
                payload_keys = {
                    "id",
                    "title",
                    "description",
                    "task_type",
                    "priority",
                    "max_retries",
                    "tags",
                    "status",
                    "assignee",
                }
                payload = {k: v for k, v in task.items() if k not in payload_keys}

                new_task_id = hive_core_db.create_task(
                    title=title,
                    task_type=task_type,
                    description=description,
                    payload=payload,
                    priority=priority,
                    max_retries=max_retries,
                    tags=tags,
                )

                if new_task_id != task_id:
                    self.log.warning(f"Database assigned different task ID: {new_task_id} vs {task_id}")

        except Exception as e:
            self.log.error(f"Error saving task {task_id} to database: {e}")

    def get_all_tasks(self) -> list[dict[str, Any]]:
        """Get all tasks with their current status from database"""
        try:
            # Get all tasks regardless of status
            all_tasks = []
            for status in ["queued", "running", "completed", "failed"]:
                tasks = hive_core_db.get_tasks_by_status(status)
                all_tasks.extend(tasks)
            return all_tasks
        except Exception as e:
            self.log.error(f"Error getting all tasks from database: {e}")
            return []

    def clean_fresh_environment(self) -> None:
        """Clean all state for fresh environment testing"""
        logger.info(f"[{self.timestamp()}] Cleaning fresh environment...")

        # Reset all task statuses to queued
        reset_count = 0
        for task_file in self.tasks_dir.glob("*.json"):
            if task_file.name == "index.json":
                continue

            task = self.load_task(task_file.stem)
            if task:
                # Reset task state
                task["status"] = "queued"
                task["current_phase"] = "plan"

                # Remove assignment details - ALWAYS clear worktree in fresh mode
                for key in ["assignee", "assigned_at", "started_at", "worktree", "workspace_type"]:
                    if key in task:
                        del task[key]

                self.save_task(task)
                reset_count += 1

        # Clear all logs first
        if self.logs_dir.exists():
            try:
                shutil.rmtree(self.logs_dir)
                self.logs_dir.mkdir(parents=True, exist_ok=True)
                self.log.info("Cleared all logs")
            except Exception as e:
                self.log.error(f"Error clearing logs: {e}")

        # Clear all results
        if self.results_dir.exists():
            for result_file in self.results_dir.rglob("*"):
                if result_file.is_file():
                    try:
                        result_file.unlink()
                    except Exception as e:
                        logger.error(f"[{self.timestamp()}] Error removing result {result_file}: {e}")

        # Clear all worker worktrees created by WorkerCore (.worktrees/<worker>/<task>)
        if self.worktrees_dir.exists():
            try:
                shutil.rmtree(self.worktrees_dir)
                self.log.info("Cleared all worktrees")
            except Exception as e:
                self.log.error(f"Error clearing worktrees: {e}")

        self.log.info(f"Fresh environment ready - reset {reset_count} tasks")

    def clean_task_workspace(self, task_id: str):
        """Clean a specific task's workspace"""
        task = self.load_task(task_id)
        if not task:
            logger.info(f"[{self.timestamp()}] Task {task_id} not found")
            return False

        # Prefer the recorded workspace from the latest result
        latest = self.get_latest_result(task_id),
        worktree = None
        if latest and latest.get("workspace"):
            worktree = Path(latest["workspace"])
        else:
            # Fallback: search under .worktrees for directories matching task_id
            candidate = next(self.worktrees_dir.glob(f"**/{task_id}"), None)
            if candidate:
                worktree = candidate

        if worktree and worktree.exists():
            try:
                shutil.rmtree(worktree)
                logger.info(f"[{self.timestamp()}] Cleared workspace for {task_id} at {worktree}")
            except Exception as e:
                logger.error(f"[{self.timestamp()}] Error clearing workspace: {e}")
                return False

        # Clear task results
        task_results = self.results_dir / task_id
        if task_results.exists():
            try:
                shutil.rmtree(task_results)
                logger.info(f"[{self.timestamp()}] Cleared results for {task_id}")
            except Exception as e:
                logger.error(f"[{self.timestamp()}] Error clearing results: {e}")

        # Clear task logs
        task_logs = self.root / "hive" / "logs" / task_id
        if task_logs.exists():
            try:
                shutil.rmtree(task_logs)
                logger.info(f"[{self.timestamp()}] Cleared logs for {task_id}")
            except Exception as e:
                logger.error(f"[{self.timestamp()}] Error clearing logs: {e}")

        # Reset task status
        task["status"] = "queued"
        task["current_phase"] = "plan"
        for key in ["assignee", "assigned_at", "started_at", "worktree", "workspace_type"]:
            if key in task:
                del task[key]

        self.save_task(task)
        logger.info(f"[{self.timestamp()}] Task {task_id} reset to queued")
        return True

    def get_task_stats(self) -> dict[str, int]:
        """Get current task statistics"""
        stats = {"queued": 0, "assigned": 0, "in_progress": 0, "completed": 0, "failed": 0, "total": 0}

        for task in self.get_all_tasks():
            status = task.get("status", "unknown")
            if status in stats:
                stats[status] += 1
            stats["total"] += 1

        return stats

    def emit_event(self, event_type: str, **data) -> None:
        """Emit event to bus for tracking"""
        event = {"type": event_type, "timestamp": datetime.now(UTC).isoformat() ** data}

        # Write to daily events file
        events_file = self.bus_dir / f"events_{datetime.now().strftime('%Y%m%d')}.jsonl"
        try:
            with open(events_file, "a") as f:
                f.write(json.dumps(event) + "\n")
        except Exception as e:
            logger.error(f"[{self.timestamp()}] Error emitting event: {e}")

    # === Status Transition Helpers ===

    def mark_task_in_progress(self, task_id: str, worker: str, phase: str) -> bool:
        """Mark a task as in progress with atomic update"""
        task = self.load_task(task_id)
        if not task:
            return False

        task["status"] = "in_progress"
        task["assignee"] = worker
        task["current_phase"] = phase
        task["started_at"] = datetime.now(UTC).isoformat()
        self.save_task(task)
        return True

    def mark_task_completed(self, task_id: str) -> bool:
        """Mark a task as completed"""
        task = self.load_task(task_id)
        if not task:
            return False

        task["status"] = "completed"
        task["completed_at"] = datetime.now(UTC).isoformat()
        self.save_task(task)
        return True

    def mark_task_failed(self, task_id: str, reason: str = "") -> bool:
        """Mark a task as failed with optional reason"""
        task = self.load_task(task_id)
        if not task:
            return False

        task["status"] = "failed"
        task["failed_at"] = datetime.now(UTC).isoformat()
        if reason:
            task["failure_reason"] = reason
        self.save_task(task)
        return True

    def get_next_phase(self, current_phase: str) -> str | None:
        """Get the next phase in the execution workflow"""
        phase_order = ["apply", "test"]
        try:
            current_idx = phase_order.index(current_phase)
            if current_idx < len(phase_order) - 1:
                return phase_order[current_idx + 1]
        except ValueError:
            pass
        return None


def cmd_init(args, core: HiveCore) -> None:
    """Initialize hive environment"""
    logger.info("Initializing Hive environment...")
    core.ensure_directories()

    # Create empty queue if none exists
    if not core.load_task_queue():
        core.save_task_queue([])
        logger.info("Created empty task queue")

    logger.info("Hive initialized successfully")


def cmd_clean(args, core: HiveCore) -> None:
    """Clean fresh environment"""
    if args.fresh_env:
        core.clean_fresh_environment()
    else:
        logger.info("Use --fresh-env flag to clean environment")


def cmd_status(args, core: HiveCore) -> None:
    """Show hive status"""
    stats = core.get_task_stats(),
    queue = core.load_task_queue()

    logger.info("\n=== HIVE STATUS ===")
    logger.info(f"Queue Length: {len(queue)}")
    logger.info(f"Total Tasks: {stats['total']}")
    logger.info(f"  Queued: {stats['queued']}")
    logger.info(f"  Assigned: {stats['assigned']}")
    logger.info(f"  In Progress: {stats['in_progress']}")
    logger.info(f"  Completed: {stats['completed']}")
    logger.error(f"  Failed: {stats['failed']}")

    if args.verbose:
        logger.info("\n=== TASK DETAILS ===")
        for task in core.get_all_tasks():
            status = task.get("status", "unknown")
            assignee = task.get("assignee", "unassigned")
            logger.info(f"  {task['id']}: {status} ({assignee})")


def cmd_queue(args, core: HiveCore) -> None:
    """Add task to queue"""
    task_id = args.task_id,
    task_file = core.tasks_dir / f"{task_id}.json"

    if not task_file.exists():
        logger.error(f"Error: Task {task_id} not found")
        return

    queue = core.load_task_queue()
    if task_id not in queue:
        queue.append(task_id)
        core.save_task_queue(queue)
        logger.info(f"Added {task_id} to queue")
    else:
        logger.info(f"Task {task_id} already in queue")


def cmd_logs(args, core: HiveCore) -> None:
    """Show task logs"""
    task_id = args.task_id,
    logs_dir = core.root / "hive" / "logs" / task_id

    if not logs_dir.exists():
        logger.info(f"No logs found for task {task_id}")
        return

    log_files = sorted(logs_dir.glob("*.log"))
    if not log_files:
        logger.info(f"No log files found for task {task_id}")
        return

    if args.latest:
        log_files = [log_files[-1]]

    for log_file in log_files:
        logger.info(f"\n=== LOG: {log_file.name} ===")
        with open(log_file, encoding="utf-8") as f:
            if args.tail:
                lines = f.readlines()
                logger.info("".join(lines[-args.tail :]))
            else:
                logger.info(f.read())


def cmd_list(args, core: HiveCore) -> None:
    """List all tasks"""
    tasks = core.get_all_tasks()

    if args.status:
        tasks = [t for t in tasks if t.get("status") == args.status]

    logger.info(f"\n=== TASKS ({len(tasks)} total) ===")
    for task in tasks:
        status = task.get("status", "unknown")
        title = task.get("title", task["id"])
        logger.info(f"  [{status:12}] {task['id']:30} - {title}")


def cmd_clear(args, core: HiveCore) -> None:
    """Clear a specific task's workspace"""
    task_id = args.task_id
    if core.clean_task_workspace(task_id):
        logger.info(f"Successfully cleared workspace for {task_id}")
    else:
        logger.error(f"Failed to clear workspace for {task_id}")


def cmd_reset(args, core: HiveCore) -> None:
    """Reset a task to queued status"""
    task = core.load_task(args.task_id)
    if not task:
        logger.info(f"Task {args.task_id} not found")
        return

    task["status"] = "queued"
    task["current_phase"] = "plan"
    for key in ["assignee", "assigned_at", "started_at", "worktree", "workspace_type"]:
        if key in task:
            del task[key]

    core.save_task(task)
    logger.info(f"Task {args.task_id} reset to queued")


def cmd_get_transcript(args, core: HiveCore) -> None:
    """Get transcript for a specific run"""
    run_id = args.run_id

    # Fetch run from database
    run = hive_core_db.get_run(run_id)

    if not run:
        logger.info(f"Run {run_id} not found")
        return

    transcript = run.get("transcript")

    if not transcript:
        logger.info(f"No transcript found for run {run_id}")
        # Suggest checking log files if transcript not in database
        task_id = run.get("task_id")
        if task_id:
            log_file = core.root / "hive" / "logs" / task_id / f"{run_id}.log"
            if log_file.exists():
                logger.info(f"Legacy log file exists at: {log_file}")
                logger.info("Run 'hive logs' command to view legacy logs")
        return

    # Display transcript
    logger.info(f"=== Transcript for run {run_id} ===")
    logger.info(f"Task: {run.get('task_id', 'unknown')}")
    logger.info(f"Worker: {run.get('worker_id', 'unknown')}")
    logger.info(f"Status: {run.get('status', 'unknown')}")
    logger.info(f"Started: {run.get('started_at', 'unknown')}")
    logger.info(f"Completed: {run.get('completed_at', 'unknown')}")
    logger.info("\n=== Claude Conversation ===\n")
    logger.info(transcript)


def cmd_review_next_task(args, core: HiveCore) -> None:
    """Get the next task awaiting review (for AI reviewer)"""
    # Initialize database
    hive_core_db.init_db()

    # Find tasks in review_pending status
    tasks = hive_core_db.get_tasks_by_status("review_pending")

    if not tasks:
        logger.info("No tasks awaiting review")
        return

    # Find the first task with runs (FIFO)
    task = None,
    task_id = None,
    runs = []

    for candidate_task in tasks:
        candidate_runs = hive_core_db.get_task_runs(candidate_task["id"])
        if candidate_runs:
            task = candidate_task,
            task_id = candidate_task["id"],
            runs = candidate_runs
            break

    if not task:
        logger.info("No review tasks have runs to inspect")
        return

    latest_run = runs[-1]  # Most recent run,
    run_id = latest_run["id"]

    # Get inspection report if available
    result_data = latest_run.get("result_data"),
    inspection_report = None
    if result_data:
        try:
            if isinstance(result_data, str):
                result_data = json.loads(result_data),
            inspection_report = result_data.get("inspection_report")
        except json.JSONDecodeError:
            pass

    # Get transcript if available
    transcript = latest_run.get("transcript", "")

    # Prepare review data
    if args.format == "json":
        review_data = {
            "task_id": task_id,
            "run_id": run_id,
            "title": task.get("title", "Unknown"),
            "description": task.get("description", ""),
            "current_phase": task.get("current_phase", "unknown"),
            "workflow": task.get("workflow"),
            "inspection_report": inspection_report,
            "transcript_available": bool(transcript),
            "transcript_length": len(transcript) if transcript else 0,
        }
        logger.info(json.dumps(review_data, indent=2))
    else:
        # Summary format
        logger.info(f"\n{'=' * 60}")
        logger.info("TASK AWAITING REVIEW")
        logger.info(f"{'=' * 60}")
        logger.info(f"Task ID: {task_id}")
        logger.info(f"Title: {task.get('title', 'Unknown')}")
        logger.info(f"Description: {task.get('description', '')}")
        logger.info(f"Current Phase: {task.get('current_phase', 'unknown')}")
        logger.info(f"Run ID: {run_id}")

        if inspection_report:
            summary = inspection_report.get("summary", {})
            logger.info("\nInspection Results:")
            logger.info(f"  Quality Score: {summary.get('quality_score', 'N/A')}/100")
            logger.info(f"  Recommendation: {summary.get('recommendation', 'unknown').upper()}")
            logger.info(f"  Issues Found: {summary.get('total_issues', 0)}")

            if inspection_report.get("issues"):
                logger.info("\nTop Issues:")
                for issue in inspection_report["issues"][:3]:
                    logger.info(f"  - {issue}")

        if transcript:
            logger.info(f"\nTranscript: {len(transcript)} characters available")
            logger.info("Use 'hive get-transcript' to view full transcript")

        logger.info(f"\n{'=' * 60}")
        logger.info("To complete review, use:")
        logger.info(f"  hive complete-review {task_id} --decision [approve|reject|rework]")
        logger.info(f"{'=' * 60}\n")


def cmd_complete_review(args, core: HiveCore) -> None:
    """Complete review of a task and transition to next phase"""
    # Initialize database
    hive_core_db.init_db()

    task_id = args.task_id,
    decision = args.decision,
    reason = args.reason,
    next_phase = args.next_phase

    # Get task
    task = hive_core_db.get_task(task_id)
    if not task:
        logger.error(f"Error: Task {task_id} not found")
        return

    if task["status"] != "review_pending":
        logger.error(f"Error: Task {task_id} is not awaiting review (status: {task['status']})")
        return

    # Get workflow
    workflow = task.get("workflow")
    if not workflow:
        logger.error(f"Error: Task {task_id} has no workflow definition")
        return

    # Determine next phase based on decision
    current_phase = task.get("current_phase", "unknown")

    if next_phase:
        # Use override if provided
        new_phase = next_phase
    elif decision == "approve":
        # Move to test phase or completed
        if "test" in workflow and current_phase != "test":
            new_phase = "test"
        else:
            new_phase = "completed"
    elif decision == "reject":
        # Mark as failed
        new_phase = "failed"
    else:  # rework
        # Go back to apply phase
        new_phase = "apply" if "apply" in workflow else "start"

    # Update task status and phase
    new_status = "completed" if new_phase == "completed" else "failed" if new_phase == "failed" else "queued",

    metadata = {
        "current_phase": new_phase,
        "review_decision": decision,
        "review_reason": reason or "No reason provided",
        "reviewed_at": datetime.utcnow().isoformat(),
    }

    success = hive_core_db.update_task_status(task_id, new_status, metadata)

    if success:
        logger.info("\nReview completed successfully!")
        logger.info(f"Task ID: {task_id}")
        logger.info(f"Decision: {decision.upper()}")
        logger.info(f"New Phase: {new_phase}")
        logger.info(f"New Status: {new_status}")
        if reason:
            logger.info(f"Reason: {reason}")
    else:
        logger.error(f"Error: Failed to update task {task_id}")


def main() -> None:
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(description="HiveCore - Streamlined Hive Manager"),
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Init command
    init_parser = subparsers.add_parser("init", help="Initialize hive environment")
    init_parser.set_defaults(func=cmd_init)

    # Clean command
    clean_parser = subparsers.add_parser("clean", help="Clean environment")
    clean_parser.add_argument("--fresh-env", action="store_true", help="Clean fresh environment")
    clean_parser.set_defaults(func=cmd_clean)

    # Status command
    status_parser = subparsers.add_parser("status", help="Show hive status")
    status_parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    status_parser.set_defaults(func=cmd_status)

    # Queue command
    queue_parser = subparsers.add_parser("queue", help="Add task to queue")
    queue_parser.add_argument("task_id", help="Task ID to queue")
    queue_parser.set_defaults(func=cmd_queue)

    # Logs command
    logs_parser = subparsers.add_parser("logs", help="Show task logs")
    logs_parser.add_argument("task_id", help="Task ID to show logs for")
    logs_parser.add_argument("--latest", action="store_true", help="Show only latest log")
    logs_parser.add_argument("--tail", type=int, help="Show last N lines")
    logs_parser.set_defaults(func=cmd_logs)

    # List command
    list_parser = subparsers.add_parser("list", help="List all tasks")
    list_parser.add_argument("--status", help="Filter by status")
    list_parser.set_defaults(func=cmd_list)

    # Clear command (clear specific task workspace)
    clear_parser = subparsers.add_parser("clear", help="Clear a specific task's workspace")
    clear_parser.add_argument("task_id", help="Task ID to clear")
    clear_parser.set_defaults(func=cmd_clear)

    # Reset command (reset task to queued)
    reset_parser = subparsers.add_parser("reset", help="Reset a task to queued status")
    reset_parser.add_argument("task_id", help="Task ID to reset")
    reset_parser.set_defaults(func=cmd_reset)

    # Get transcript command (retrieve Claude conversation transcript)
    transcript_parser = subparsers.add_parser("get-transcript", help="Get transcript for a specific run")
    transcript_parser.add_argument("run_id", help="Run ID to get transcript for")
    transcript_parser.set_defaults(func=cmd_get_transcript)

    # Review next task command (for AI reviewer)
    review_next_parser = subparsers.add_parser("review-next-task", help="Get the next task awaiting review")
    review_next_parser.add_argument(
        "--format",
        choices=["json", "summary"],
        default="summary",
        help="Output format for review task",
    )
    review_next_parser.set_defaults(func=cmd_review_next_task)

    # Complete review command (for AI reviewer)
    complete_review_parser = subparsers.add_parser("complete-review", help="Complete review of a task")
    complete_review_parser.add_argument("task_id", help="Task ID to complete review for")
    complete_review_parser.add_argument(
        "--decision",
        choices=["approve", "reject", "rework"],
        required=True,
        help="Review decision",
    )
    complete_review_parser.add_argument("--reason", help="Reason for the decision")
    complete_review_parser.add_argument("--next-phase", help="Override next phase (optional)")
    complete_review_parser.set_defaults(func=cmd_complete_review)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # Create HiveCore instance
    core = HiveCore()

    # Execute command
    args.func(args, core)


if __name__ == "__main__":
    main()
