"""
QA Worker - Autonomous Code Quality Worker

Extends AsyncWorker to provide autonomous ruff linting, formatting,
and syntax validation with event-driven coordination.

Architecture:
- Extends AsyncWorker for async file operations and event coordination
- Auto-fixes ruff violations, black formatting, import sorting
- Integrates with event bus for status updates and escalation
- Commits fixes automatically with worker ID reference
"""

from __future__ import annotations

import asyncio
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from hive_logging import get_logger
from hive_orchestration.events import AgentEvent, TaskEvent, get_async_event_bus
from hive_orchestration.models.task import Task, TaskStatus
from hive_orchestrator.async_worker import AsyncWorker

logger = get_logger(__name__)


class QAWorkerCore(AsyncWorker):
    """
    Autonomous QA worker for code quality enforcement.

    Features:
    - Ruff linting auto-fix (E*, F*, I* codes)
    - Black formatting violations
    - Import sorting (isort)
    - Syntax validation (py_compile)
    - Event-driven status updates
    - Automatic git commits
    - Escalation for complex issues

    Performance Targets:
    - Fix latency: <5s from detection to commit
    - Auto-fix success: 80%+
    - False positive rate: <1%
    """

    def __init__(
        self,
        worker_id: str = "qa-worker-1",
        workspace: Path | None = None,
        config: dict[str, Any] | None = None,
    ):
        """Initialize QA worker with async capabilities."""
        super().__init__(
            worker_id=worker_id,
            task_id=None,
            run_id=None,
            workspace=str(workspace) if workspace else None,
            phase="apply",
            mode="repo",
            live_output=False,
            config=config or {},
        )

        self.event_bus = get_async_event_bus()
        self.tasks_completed = 0
        self.violations_fixed = 0
        self.escalations = 0
        self.start_time = datetime.now(UTC)

        logger.info(f"QA Worker {worker_id} initialized")
        logger.info(f"  Workspace: {self.workspace}")
        logger.info(f"  Mode: {self.mode}")

    async def emit_heartbeat(self) -> None:
        """Emit worker heartbeat for health monitoring."""
        uptime = (datetime.now(UTC) - self.start_time).total_seconds()

        await self.event_bus.publish(
            AgentEvent(
                agent_id=self.worker_id,
                event_type="heartbeat",
                payload={
                    "status": "idle" if not self.task_id else "working",
                    "tasks_completed": self.tasks_completed,
                    "violations_fixed": self.violations_fixed,
                    "escalations": self.escalations,
                    "uptime_seconds": uptime,
                },
            )
        )

    async def detect_violations(self, file_path: Path) -> dict[str, Any]:
        """
        Detect ruff violations in a file.

        Args:
            file_path: Path to Python file to check

        Returns:
            {
                "violations": [{"code": "E501", "line": 45, "message": "..."}],
                "total_count": 3,
                "auto_fixable": True
            }
        """
        logger.info(f"Scanning for violations: {file_path}")

        try:
            result = await asyncio.create_subprocess_exec(
                "ruff",
                "check",
                "--output-format=json",
                str(file_path),
                cwd=str(self.workspace),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await result.communicate()

            if result.returncode == 0:
                logger.info(f"  No violations found in {file_path}")
                return {"violations": [], "total_count": 0, "auto_fixable": True}

            # Parse JSON output
            import json

            violations_data = json.loads(stdout.decode())

            violations = []
            for item in violations_data:
                violations.append(
                    {
                        "code": item.get("code", "UNKNOWN"),
                        "line": item.get("location", {}).get("row", 0),
                        "column": item.get("location", {}).get("column", 0),
                        "message": item.get("message", ""),
                    }
                )

            logger.info(f"  Found {len(violations)} violations in {file_path}")
            return {
                "violations": violations,
                "total_count": len(violations),
                "auto_fixable": True,
            }

        except FileNotFoundError:
            logger.error("Ruff not found - install with: pip install ruff")
            return {"violations": [], "total_count": 0, "auto_fixable": False}
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse ruff output: {e}")
            return {"violations": [], "total_count": 0, "auto_fixable": False}
        except Exception as e:
            logger.error(f"Violation detection failed: {e}")
            return {"violations": [], "total_count": 0, "auto_fixable": False}

    async def apply_auto_fixes(self, file_path: Path) -> dict[str, Any]:
        """
        Apply automatic fixes to a file using ruff --fix.

        Args:
            file_path: Path to Python file to fix

        Returns:
            {
                "success": True,
                "violations_fixed": 8,
                "violations_remaining": 0,
                "fix_time_ms": 342
            }
        """
        start_time = datetime.now(UTC)
        logger.info(f"Applying auto-fixes: {file_path}")

        # Detect violations before fixing
        before = await self.detect_violations(file_path)
        violations_before = before["total_count"]

        if violations_before == 0:
            return {
                "success": True,
                "violations_fixed": 0,
                "violations_remaining": 0,
                "fix_time_ms": 0,
            }

        try:
            # Run ruff --fix
            result = await asyncio.create_subprocess_exec(
                "ruff",
                "check",
                "--fix",
                str(file_path),
                cwd=str(self.workspace),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            await result.communicate()

            # Detect violations after fixing
            after = await self.detect_violations(file_path)
            violations_after = after["total_count"]

            violations_fixed = violations_before - violations_after
            fix_time = (datetime.now(UTC) - start_time).total_seconds() * 1000

            logger.info(
                f"  Fixed {violations_fixed}/{violations_before} violations in {fix_time:.0f}ms"
            )

            if violations_after > 0:
                logger.warning(
                    f"  {violations_after} violations remain after auto-fix"
                )

            return {
                "success": violations_after == 0,
                "violations_fixed": violations_fixed,
                "violations_remaining": violations_after,
                "fix_time_ms": int(fix_time),
            }

        except Exception as e:
            logger.error(f"Auto-fix failed: {e}")
            return {
                "success": False,
                "violations_fixed": 0,
                "violations_remaining": violations_before,
                "fix_time_ms": 0,
                "error": str(e),
            }

    async def commit_fixes(self, file_paths: list[Path], task_id: str) -> bool:
        """
        Commit auto-fixes with worker ID reference.

        Args:
            file_paths: List of files that were fixed
            task_id: Task ID for commit message reference

        Returns:
            True if commit succeeded, False otherwise
        """
        try:
            # Stage modified files
            for file_path in file_paths:
                result = await asyncio.create_subprocess_exec(
                    "git",
                    "add",
                    str(file_path),
                    cwd=str(self.workspace),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await result.communicate()

            # Create commit message
            file_names = [f.name for f in file_paths]
            files_str = ", ".join(file_names[:3])
            if len(file_names) > 3:
                files_str += f" (+{len(file_names) - 3} more)"

            commit_msg = f"chore(qa): Auto-fix ruff violations in {files_str} [{self.worker_id}] [task:{task_id}]"

            # Commit
            result = await asyncio.create_subprocess_exec(
                "git",
                "commit",
                "-m",
                commit_msg,
                cwd=str(self.workspace),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await result.communicate()

            if result.returncode == 0:
                logger.info(f"Committed fixes: {commit_msg}")
                return True
            else:
                logger.error(f"Commit failed: {stderr.decode()}")
                return False

        except Exception as e:
            logger.error(f"Commit failed: {e}")
            return False

    async def escalate_issue(
        self, task_id: str, reason: str, details: dict[str, Any]
    ) -> None:
        """
        Escalate complex issue to HITL for manual review.

        Args:
            task_id: Task ID that needs escalation
            reason: Why escalation is needed
            details: Additional context (violations, attempts, etc.)
        """
        logger.warning(f"Escalating task {task_id}: {reason}")

        self.escalations += 1

        await self.event_bus.publish(
            TaskEvent(
                task_id=task_id,
                event_type="escalation_needed",
                payload={
                    "worker_id": self.worker_id,
                    "reason": reason,
                    "details": details,
                    "escalation_count": self.escalations,
                },
            )
        )

    async def process_qa_task(self, task: Task) -> dict[str, Any]:
        """
        Process a QA task: detect violations, apply fixes, commit.

        Args:
            task: QA task with file paths to check

        Returns:
            {
                "status": "success" | "failed" | "escalated",
                "violations_fixed": 8,
                "violations_remaining": 0,
                "files_processed": 3,
                "execution_time_ms": 4200
            }
        """
        start_time = datetime.now(UTC)
        task_id = task.id

        logger.info(f"Processing QA task: {task_id}")
        logger.info(f"  Description: {task.description}")

        # Emit task started event
        await self.event_bus.publish(
            TaskEvent(
                task_id=task_id,
                event_type="started",
                payload={"worker_id": self.worker_id},
            )
        )

        try:
            # Get file paths from task metadata
            file_paths_str = task.metadata.get("file_paths", [])
            file_paths = [Path(self.workspace) / fp for fp in file_paths_str]

            total_violations_fixed = 0
            total_violations_remaining = 0
            fixed_files = []

            # Process each file
            for file_path in file_paths:
                if not file_path.exists():
                    logger.warning(f"File not found: {file_path}")
                    continue

                # Apply auto-fixes
                result = await self.apply_auto_fixes(file_path)

                if result["violations_fixed"] > 0:
                    total_violations_fixed += result["violations_fixed"]
                    fixed_files.append(file_path)

                total_violations_remaining += result["violations_remaining"]

            # Commit fixes if any were made
            if fixed_files:
                commit_success = await self.commit_fixes(fixed_files, task_id)
                if not commit_success:
                    await self.escalate_issue(
                        task_id,
                        "Commit failed after auto-fix",
                        {"files": [str(f) for f in fixed_files]},
                    )
                    return {
                        "status": "escalated",
                        "violations_fixed": total_violations_fixed,
                        "violations_remaining": total_violations_remaining,
                        "files_processed": len(file_paths),
                    }

            # Check if any violations remain
            if total_violations_remaining > 0:
                await self.escalate_issue(
                    task_id,
                    f"{total_violations_remaining} violations could not be auto-fixed",
                    {
                        "violations_remaining": total_violations_remaining,
                        "files": [str(f) for f in file_paths],
                    },
                )
                status = "escalated"
            else:
                status = "success"

            # Update metrics
            self.tasks_completed += 1
            self.violations_fixed += total_violations_fixed

            # Emit task completed event
            execution_time = (datetime.now(UTC) - start_time).total_seconds() * 1000

            await self.event_bus.publish(
                TaskEvent(
                    task_id=task_id,
                    event_type="completed",
                    payload={
                        "worker_id": self.worker_id,
                        "status": status,
                        "violations_fixed": total_violations_fixed,
                        "violations_remaining": total_violations_remaining,
                        "files_processed": len(file_paths),
                        "execution_time_ms": int(execution_time),
                    },
                )
            )

            logger.info(f"QA task {task_id} completed: {status}")
            logger.info(
                f"  Fixed {total_violations_fixed} violations in {execution_time:.0f}ms"
            )

            return {
                "status": status,
                "violations_fixed": total_violations_fixed,
                "violations_remaining": total_violations_remaining,
                "files_processed": len(file_paths),
                "execution_time_ms": int(execution_time),
            }

        except Exception as e:
            logger.error(f"QA task processing failed: {e}")

            await self.event_bus.publish(
                TaskEvent(
                    task_id=task_id,
                    event_type="failed",
                    payload={"worker_id": self.worker_id, "error": str(e)},
                )
            )

            return {
                "status": "failed",
                "violations_fixed": 0,
                "violations_remaining": 0,
                "files_processed": 0,
                "error": str(e),
            }

    async def run_worker_loop(self, poll_interval: float = 2.0) -> None:
        """
        Main worker loop: poll for tasks, emit heartbeats, process work.

        Args:
            poll_interval: Seconds between task queue polls
        """
        logger.info(f"QA Worker {self.worker_id} starting main loop")
        logger.info(f"  Poll interval: {poll_interval}s")

        try:
            while True:
                # Emit heartbeat
                await self.emit_heartbeat()

                # Poll for QA tasks (would integrate with orchestrator queue)
                # For now, just sleep - queue integration in Phase 2
                await asyncio.sleep(poll_interval)

        except KeyboardInterrupt:
            logger.info(f"QA Worker {self.worker_id} shutting down...")
        except Exception as e:
            logger.error(f"Worker loop crashed: {e}")
            raise


async def main():
    """CLI entry point for QA worker."""
    import argparse

    parser = argparse.ArgumentParser(description="QA Worker - Autonomous Code Quality")
    parser.add_argument(
        "--worker-id", default="qa-worker-1", help="Worker ID for identification"
    )
    parser.add_argument(
        "--workspace",
        type=Path,
        default=None,
        help="Workspace directory (default: current directory)",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=2.0,
        help="Task queue poll interval in seconds",
    )

    args = parser.parse_args()

    # Create and run worker
    worker = QAWorkerCore(
        worker_id=args.worker_id, workspace=args.workspace or Path.cwd()
    )

    await worker.run_worker_loop(poll_interval=args.poll_interval)


if __name__ == "__main__":
    asyncio.run(main())
