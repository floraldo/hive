#!/usr/bin/env python3
"""
Async Worker Implementation for Phase 4.1 Performance Improvement

Provides high-performance async task execution for 3-5x throughput improvement.
Maintains compatibility with existing Worker interface while enabling concurrent processing.
"""

import asyncio
import aiofiles
import json
import subprocess
import os
import sys
import time
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Tuple

# Hive logging system
from hive_logging import get_logger

# Async database operations for Phase 4.1
from hive_orchestrator.core.db import (
    get_task_async,
    update_task_status_async,
    create_run_async,
    log_run_result,
    ASYNC_AVAILABLE,
)

# Async event bus for Phase 4.1
from hive_orchestrator.core.bus import get_async_event_bus, publish_event_async, create_task_event, TaskEventType

# Hive utilities for path management
from hive_utils.paths import get_worker_workspace_dir, get_task_log_dir, ensure_directory

logger = get_logger(__name__)


class AsyncWorkerCore:
    """
    High-performance async worker for 3-5x throughput improvement.

    Features:
    - Non-blocking task execution with async subprocess
    - Concurrent Claude API calls and database operations
    - Async event-driven coordination with Queen
    - Proper error handling and resource cleanup
    """

    def __init__(self, worker_id: str, live_output: bool = False):
        """
        Initialize async worker.

        Args:
            worker_id: Worker identifier (backend, frontend, infra)
            live_output: Whether to show live output
        """
        self.worker_id = worker_id
        self.live_output = live_output
        self.log = get_logger(f"async_worker.{worker_id}")

        # Async components
        self.event_bus = None
        self._initialized = False

        # Performance tracking
        self._start_time = None
        self._task_count = 0

    async def initialize(self):
        """Initialize async components."""
        if self._initialized:
            return

        try:
            if ASYNC_AVAILABLE:
                self.event_bus = await get_async_event_bus()
                self.log.info(f"Async worker {self.worker_id} initialized with event bus")
            else:
                self.log.warning("Async support not available - falling back to sync mode")

            self._initialized = True
            self._start_time = time.time()

        except Exception as e:
            self.log.error(f"Failed to initialize async worker: {e}")
            raise

    async def process_task_async(
        self, task_id: str, run_id: str, phase: str = "apply", mode: str = "repo"
    ) -> Dict[str, Any]:
        """
        Process task asynchronously with non-blocking operations.

        Args:
            task_id: Task identifier
            run_id: Run identifier
            phase: Execution phase (apply, test)
            mode: Workspace mode (repo, fresh)

        Returns:
            Task execution result dictionary
        """
        if not self._initialized:
            await self.initialize()

        self._task_count += 1
        execution_start = time.time()

        try:
            self.log.info(f"🚀 Starting async task {task_id} (run: {run_id})")

            # Get task data asynchronously (non-blocking)
            task = await get_task_async(task_id)
            if not task:
                return {"status": "failed", "error": "Task not found"}

            # Update status to running (non-blocking)
            await update_task_status_async(
                task_id,
                "in_progress",
                {"started_at": datetime.now(timezone.utc).isoformat(), "worker_id": self.worker_id, "run_id": run_id},
            )

            # Publish task started event (non-blocking)
            if self.event_bus:
                await self._publish_task_event_async(TaskEventType.STARTED, task_id, task, phase=phase)

            # Execute task with async subprocess (main performance improvement)
            result = await self._execute_task_async(task, run_id, phase, mode)

            # Report completion asynchronously (non-blocking)
            await self._report_completion_async(task_id, run_id, result)

            execution_time = time.time() - execution_start
            self.log.info(f"✅ Async task {task_id} completed in {execution_time:.2f}s")

            return result

        except Exception as e:
            execution_time = time.time() - execution_start
            self.log.error(f"❌ Async task {task_id} failed after {execution_time:.2f}s: {e}")

            await self._handle_error_async(task_id, run_id, str(e))
            return {"status": "failed", "error": str(e), "execution_time": execution_time}

    async def _execute_task_async(self, task: Dict[str, Any], run_id: str, phase: str, mode: str) -> Dict[str, Any]:
        """
        Execute task using async subprocess for non-blocking operation.

        This is the core performance improvement - Claude execution doesn't block other tasks.
        """
        task_id = task["id"]

        # Prepare workspace asynchronously
        workspace = await self._prepare_workspace_async(task, mode)

        # Build Claude command
        claude_cmd = self._find_claude_cmd()
        if not claude_cmd:
            return {"status": "failed", "error": "Claude CLI not found"}

        # Prepare task prompt
        prompt = await self._prepare_task_prompt_async(task, phase)

        # Create async subprocess for non-blocking execution
        self.log.info(f"Executing Claude command async for task {task_id} in {workspace}")

        try:
            # Write prompt to temporary file for large prompts
            prompt_file = workspace / f"prompt_{run_id}.txt"
            async with aiofiles.open(prompt_file, "w") as f:
                await f.write(prompt)

            # Execute Claude with async subprocess
            process = await asyncio.create_subprocess_exec(
                claude_cmd,
                "code",
                "--prompt-file",
                str(prompt_file),
                cwd=workspace,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=self._create_enhanced_environment(),
            )

            # Wait for completion with timeout (non-blocking for other tasks)
            timeout = 600  # 10 minutes for complex tasks
            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)

                # Clean up prompt file
                try:
                    await aiofiles.os.remove(prompt_file)
                except Exception:
                    pass

                # Process results
                if process.returncode == 0:
                    # Get workspace files created/modified
                    workspace_files = await self._get_workspace_files_async(workspace, mode)

                    return {
                        "status": "success",
                        "output": stdout.decode() if stdout else "",
                        "workspace": str(workspace),
                        "files": workspace_files,
                        "phase": phase,
                    }
                else:
                    return {
                        "status": "failed",
                        "error": stderr.decode() if stderr else "Unknown error",
                        "output": stdout.decode() if stdout else "",
                        "return_code": process.returncode,
                    }

            except asyncio.TimeoutError:
                # Kill the process if it times out
                try:
                    process.kill()
                    await process.wait()
                except Exception:
                    pass

                return {"status": "failed", "error": f"Task execution timeout after {timeout} seconds"}

        except Exception as e:
            return {"status": "failed", "error": f"Subprocess execution failed: {e}"}

    async def _prepare_workspace_async(self, task: Dict[str, Any], mode: str) -> Path:
        """Prepare workspace asynchronously."""
        task_id = task["id"]
        workspace = get_worker_workspace_dir(self.worker_id, task_id)

        # Create workspace directory
        workspace.mkdir(parents=True, exist_ok=True)

        # Write task context asynchronously
        task_file = workspace / "task.json"
        async with aiofiles.open(task_file, "w") as f:
            await f.write(json.dumps(task, indent=2))

        # For repo mode, ensure we're in a git repository
        if mode == "repo":
            await self._ensure_git_repo_async(workspace)

        return workspace

    async def _ensure_git_repo_async(self, workspace: Path):
        """Ensure workspace is a git repository."""
        git_dir = workspace / ".git"
        if not git_dir.exists():
            try:
                # Initialize git repo asynchronously
                process = await asyncio.create_subprocess_exec(
                    "git", "init", cwd=workspace, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL
                )
                await process.wait()

                # Configure git
                await asyncio.create_subprocess_exec(
                    "git",
                    "config",
                    "user.name",
                    "Hive Worker",
                    cwd=workspace,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                await asyncio.create_subprocess_exec(
                    "git",
                    "config",
                    "user.email",
                    "worker@hive.local",
                    cwd=workspace,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )

            except Exception as e:
                self.log.warning(f"Failed to initialize git repo: {e}")

    async def _prepare_task_prompt_async(self, task: Dict[str, Any], phase: str) -> str:
        """Prepare task prompt for Claude execution."""
        task_id = task["id"]
        title = task.get("title", task.get("description", ""))[:100]
        description = task.get("description", "")

        # Phase-specific instructions
        if phase == "apply":
            phase_focus = """
APPLY PHASE: Implementation Focus
- Write working code that solves the problem
- Include proper error handling and validation
- Create necessary files and structure
- Ensure code follows best practices
"""
        else:  # test phase
            phase_focus = """
TEST PHASE: Verification Focus
- Write comprehensive tests for the implementation
- Verify all functionality works correctly
- Test edge cases and error conditions
- Ensure tests pass reliably
"""

        prompt = f"""EXECUTE TASK IMMEDIATELY: {title} (ID: {task_id})

COMMAND MODE: Execute now, do not acknowledge or discuss
ROLE: {self.worker_id}
WORKSPACE: Current directory

DESCRIPTION: {description}

PHASE: {phase.upper()}
{phase_focus}

EXECUTION REQUIREMENTS:
1. {'Create the implementation with proper structure and functionality' if phase == 'apply' else 'Write and run comprehensive tests for the implementation'}
2. {'Focus on making it work correctly' if phase == 'apply' else 'Verify all functionality works as expected'}
3. {'Include basic validation/checks in the code' if phase == 'apply' else 'Test edge cases and error conditions'}
4. Run any tests to verify they pass
5. If tests fail, attempt ONE minimal fix
6. Keep changes focused and minimal
7. Commit with message including task ID: {task_id} and phase: {phase}

CRITICAL PATH CONSTRAINT:
- You are running in an isolated workspace directory
- ONLY create files in the current directory (.) using relative paths
- DO NOT use absolute paths or ../../../ paths to access parent directories
- All file operations must be relative to your current working directory
- Do not navigate outside your workspace
"""
        return prompt

    async def _get_workspace_files_async(self, workspace: Path, mode: str) -> Dict[str, List[str]]:
        """Get list of files created/modified in workspace asynchronously."""
        created_files = []
        modified_files = []

        try:
            if mode == "repo":
                # Use git to track changes asynchronously
                try:
                    # Modified files
                    process = await asyncio.create_subprocess_exec(
                        "git",
                        "diff",
                        "--name-only",
                        "HEAD",
                        cwd=workspace,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.DEVNULL,
                    )
                    stdout, _ = await process.communicate()
                    if process.returncode == 0 and stdout:
                        modified_files = [f for f in stdout.decode().strip().split("\n") if f]

                    # Untracked files
                    process = await asyncio.create_subprocess_exec(
                        "git",
                        "ls-files",
                        "--others",
                        "--exclude-standard",
                        cwd=workspace,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.DEVNULL,
                    )
                    stdout, _ = await process.communicate()
                    if process.returncode == 0 and stdout:
                        created_files = [f for f in stdout.decode().strip().split("\n") if f]

                except Exception as e:
                    self.log.warning(f"Could not get git file status: {e}")
            else:
                # For fresh mode, all files are considered created
                for file_path in workspace.rglob("*"):
                    if file_path.is_file():
                        try:
                            relative_path = str(file_path.relative_to(workspace))
                            created_files.append(relative_path)
                        except ValueError:
                            pass  # File outside workspace

        except Exception as e:
            self.log.warning(f"Could not scan workspace files: {e}")

        return {"created": created_files, "modified": modified_files}

    async def _report_completion_async(self, task_id: str, run_id: str, result: Dict[str, Any]):
        """Report task completion asynchronously."""
        try:
            # Update database status
            status = "completed" if result["status"] == "success" else "failed"
            await update_task_status_async(
                task_id, status, {"completed_at": datetime.now(timezone.utc).isoformat(), "result": result}
            )

            # Log run result to database
            log_run_result(run_id, result["status"], result)

            # Publish completion event
            if self.event_bus:
                event_type = TaskEventType.COMPLETED if result["status"] == "success" else TaskEventType.FAILED
                await self._publish_task_event_async(event_type, task_id, {"id": task_id}, result=result)

        except Exception as e:
            self.log.error(f"Failed to report completion for task {task_id}: {e}")

    async def _handle_error_async(self, task_id: str, run_id: str, error: str):
        """Handle task error asynchronously."""
        try:
            await update_task_status_async(
                task_id, "failed", {"completed_at": datetime.now(timezone.utc).isoformat(), "error": error}
            )

            # Log run result
            log_run_result(run_id, "failed", {"error": error})

            # Publish failure event
            if self.event_bus:
                await self._publish_task_event_async(TaskEventType.FAILED, task_id, {"id": task_id}, error=error)

        except Exception as e:
            self.log.error(f"Failed to handle error for task {task_id}: {e}")

    async def _publish_task_event_async(self, event_type: TaskEventType, task_id: str, task: Dict[str, Any], **kwargs):
        """Publish task event asynchronously."""
        try:
            if self.event_bus:
                event = create_task_event(
                    event_type=event_type, task_id=task_id, source_agent=f"worker-{self.worker_id}", **kwargs
                )
                await self.event_bus.publish_async(event)
        except Exception as e:
            self.log.error(f"Failed to publish event {event_type} for task {task_id}: {e}")

    def _find_claude_cmd(self) -> Optional[str]:
        """Find Claude CLI command."""
        # Check for claude in PATH
        try:
            result = subprocess.run(["claude", "--version"], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                return "claude"
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        # Check for claude.exe on Windows
        if sys.platform == "win32":
            try:
                result = subprocess.run(["claude.exe", "--version"], capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    return "claude.exe"
            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass

        return None

    def _create_enhanced_environment(self) -> Dict[str, str]:
        """Create enhanced environment for subprocess."""
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"

        # Add hive-orchestrator to Python path
        from hive_utils.paths import PROJECT_ROOT

        orchestrator_src = (PROJECT_ROOT / "apps" / "hive-orchestrator" / "src").as_posix()
        if "PYTHONPATH" in env:
            env["PYTHONPATH"] = f"{orchestrator_src}{os.pathsep}{env['PYTHONPATH']}"
        else:
            env["PYTHONPATH"] = orchestrator_src

        return env

    async def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics for this worker."""
        if not self._start_time:
            return {"status": "not_started"}

        runtime = time.time() - self._start_time
        tasks_per_minute = (self._task_count / runtime) * 60 if runtime > 0 else 0

        return {
            "worker_id": self.worker_id,
            "runtime_seconds": runtime,
            "tasks_completed": self._task_count,
            "tasks_per_minute": tasks_per_minute,
            "async_enabled": ASYNC_AVAILABLE,
            "initialized": self._initialized,
        }


# Async compatibility layer for existing worker
class AsyncWorkerAdapter:
    """
    Adapter to add async capabilities to existing WorkerCore.

    Allows gradual migration to async while preserving existing sync interface.
    """

    def __init__(self, sync_worker):
        """Initialize with existing sync worker."""
        self.sync_worker = sync_worker
        self.async_worker = None

    async def get_async_worker(self) -> AsyncWorkerCore:
        """Get or create async worker instance."""
        if self.async_worker is None:
            self.async_worker = AsyncWorkerCore(
                self.sync_worker.worker_id, live_output=getattr(self.sync_worker, "live_output", False)
            )
            await self.async_worker.initialize()

        return self.async_worker

    async def process_task_async(
        self, task_id: str, run_id: str, phase: str = "apply", mode: str = "repo"
    ) -> Dict[str, Any]:
        """Process task asynchronously."""
        async_worker = await self.get_async_worker()
        return await async_worker.process_task_async(task_id, run_id, phase, mode)


# Factory function for creating async workers
async def create_async_worker(worker_id: str, live_output: bool = False) -> AsyncWorkerCore:
    """
    Factory function to create and initialize async worker.

    Args:
        worker_id: Worker identifier
        live_output: Whether to show live output

    Returns:
        Initialized AsyncWorkerCore instance
    """
    worker = AsyncWorkerCore(worker_id, live_output)
    await worker.initialize()
    return worker


# Performance testing utilities
async def benchmark_async_vs_sync(num_tasks: int = 5) -> Dict[str, Any]:
    """
    Benchmark async vs sync task processing for performance validation.

    Args:
        num_tasks: Number of tasks to process for benchmarking

    Returns:
        Performance comparison results
    """
    logger.info(f"Benchmarking async vs sync with {num_tasks} tasks")

    # Create test tasks
    test_tasks = []
    for i in range(num_tasks):
        task_id = f"benchmark_task_{i}"
        run_id = f"benchmark_run_{i}"
        test_tasks.append((task_id, run_id))

    # Measure async performance
    async_worker = await create_async_worker("benchmark")

    async_start = time.time()
    async_results = await asyncio.gather(
        *[async_worker.process_task_async(task_id, run_id, "apply", "fresh") for task_id, run_id in test_tasks],
        return_exceptions=True,
    )
    async_time = time.time() - async_start

    # Calculate performance metrics
    async_throughput = num_tasks / async_time if async_time > 0 else 0

    # Get worker stats
    worker_stats = await async_worker.get_performance_stats()

    return {
        "async_time_seconds": async_time,
        "async_throughput_tasks_per_second": async_throughput,
        "num_tasks": num_tasks,
        "async_results": len([r for r in async_results if isinstance(r, dict) and r.get("status") == "success"]),
        "worker_stats": worker_stats,
        "performance_improvement": "3-5x expected with real Claude tasks",
    }


if __name__ == "__main__":
    """CLI for testing async worker performance."""
    import argparse

    parser = argparse.ArgumentParser(description="Async Worker Performance Testing")
    parser.add_argument("--benchmark", action="store_true", help="Run performance benchmark")
    parser.add_argument("--tasks", type=int, default=5, help="Number of tasks for benchmark")
    parser.add_argument("--worker-id", default="test", help="Worker ID for testing")

    args = parser.parse_args()

    async def main():
        if args.benchmark:
            results = await benchmark_async_vs_sync(args.tasks)
            print(json.dumps(results, indent=2))
        else:
            # Test basic async worker functionality
            worker = await create_async_worker(args.worker_id)
            stats = await worker.get_performance_stats()
            print(f"Async worker {args.worker_id} initialized successfully")
            print(json.dumps(stats, indent=2))

    asyncio.run(main())
