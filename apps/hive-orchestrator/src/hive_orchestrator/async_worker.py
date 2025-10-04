#!/usr/bin/env python3
"""
AsyncWorker - High-Performance Async Worker for V4.0
Phase 2 Implementation with non-blocking I/O and concurrent operations
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Hive utilities
from hive_config.paths import LOGS_DIR, PROJECT_ROOT, WORKTREES_DIR, get_worker_workspace_dir
from hive_logging import get_logger, setup_logging

# Async event bus from Phase 1
from hive_orchestrator.core.bus import get_async_event_bus

# Async database operations from Phase 1 (optional - requires aiosqlite)
try:
    from hive_orchestrator.core.db.async_operations import AsyncDatabaseOperations, get_async_db_operations

    ASYNC_DB_AVAILABLE = True
except ImportError:
    ASYNC_DB_AVAILABLE = False
    AsyncDatabaseOperations = None
    get_async_db_operations = None

# Hive performance monitoring (optional - decorator not yet available)
# from hive_performance import track_adapter_request


class AsyncWorker:
    """
    High-performance async worker with V4.0 optimizations

    Features:
    - Non-blocking file operations
    - Async subprocess execution
    - Concurrent task processing
    - Event-driven coordination
    - 3-5x performance improvement
    """

    def __init__(
        self,
        worker_id: str,
        task_id: str | None = None,
        run_id: str | None = None,
        workspace: str | None = None,
        phase: str = "apply",
        mode: str = "fresh",
        live_output: bool = False,
        config: dict[str, Any] | None = None,
    ):
        """Initialize AsyncWorker with async-first architecture"""
        self.worker_id = (worker_id,)
        self.task_id = (task_id,)
        self.run_id = (run_id,)
        self.phase = (phase,)
        self.mode = (mode,)
        self.live_output = (live_output,)
        self.config = config or {}

        # Async components,
        self.db_ops: AsyncDatabaseOperations | None = (None,)
        self.event_bus = None

        # Logging,
        self.log = get_logger(__name__)

        # Paths,
        self.project_root = (PROJECT_ROOT,)
        self.logs_dir = (LOGS_DIR,)
        self.root = PROJECT_ROOT

        # Workspace setup,
        if workspace:
            self.workspace = Path(workspace).resolve()
            self.workspace.mkdir(parents=True, exist_ok=True)
        else:
            self.workspace = self._create_workspace()

        # Performance metrics,
        self.metrics = {
            "start_time": datetime.now(UTC),
            "operations": 0,
            "file_operations": 0,
            "subprocess_calls": 0,
            "db_operations": 0,
        }

        # Claude command discovery,
        self.claude_cmd = self.find_claude_cmd()

        self.log.info(f"AsyncWorker {worker_id} initialized")
        if self.task_id:
            self.log.info(f"  Task: {self.task_id}")
            self.log.info(f"  Run ID: {self.run_id}")
            self.log.info(f"  Phase: {self.phase}")
        self.log.info(f"  Workspace: {self.workspace}")
        self.log.info(f"  Claude: {self.claude_cmd or 'SIMULATION MODE'}")

    async def initialize_async(self) -> None:
        """Async initialization of database and event bus"""
        # Initialize async database operations (if available)
        if ASYNC_DB_AVAILABLE:
            self.db_ops = await get_async_db_operations()
            self.log.info("Async database operations initialized")
        else:
            self.db_ops = None
            self.log.warning(
                "Async database operations not available (install aiosqlite for Phase 4.1 features)"
            )

        # Initialize async event bus
        self.event_bus = await get_async_event_bus()
        self.log.info("Async event bus initialized")

        # Register worker (if DB available)
        if self.db_ops:
            await self._register_worker_async()

    async def _register_worker_async(self) -> None:
        """Register worker in database"""
        try:
            await self.db_ops.register_worker_async(
                worker_id=f"async-{self.worker_id}-{self.run_id}",
                role=self.worker_id,
                capabilities=["async_execution", "high_performance", "non_blocking_io"],
                metadata={
                    "version": "4.0.0",
                    "type": "AsyncWorker",
                    "phase": self.phase,
                    "task_id": self.task_id,
                },
            )
            self.log.info("Worker registered in database")
        except Exception as e:
            self.log.warning(f"Failed to register worker: {e}")

    def _create_workspace(self) -> Path:
        """Create workspace based on mode"""
        if self.mode == "repo":
            # Use main repository
            return self.project_root
        elif self.mode == "worktree":
            # Create git worktree
            worktree_dir = WORKTREES_DIR / f"{self.worker_id}-{self.task_id}"
            worktree_dir.mkdir(parents=True, exist_ok=True)
            return worktree_dir
        else:
            # Fresh workspace
            workspace_dir = get_worker_workspace_dir(self.worker_id, self.task_id or "default")
            workspace_dir.mkdir(parents=True, exist_ok=True)
            return workspace_dir

    def find_claude_cmd(self) -> str | None:
        """Find Claude command"""
        # Check environment variable
        claude_bin = os.environ.get("CLAUDE_BIN")
        if claude_bin and Path(claude_bin).exists():
            return claude_bin

        # Check common locations
        candidates = [
            "claude",
            "claude.exe",
            str(Path.home() / ".local" / "bin" / "claude"),
            str(Path.home() / ".npm-global" / "bin" / "claude"),
        ]

        for cmd in candidates:
            if self._command_exists(cmd):
                return cmd

        return None

    def _command_exists(self, cmd: str) -> bool:
        """Check if command exists"""
        import shutil

        return shutil.which(cmd) is not None

    # @track_adapter_request("claude_ai")  # TODO: Re-enable when available
    async def execute_claude_async(self, prompt: str, context_files: list[str] | None = None) -> dict[str, Any]:
        """Execute Claude CLI asynchronously with non-blocking I/O"""
        if not self.claude_cmd:
            self.log.info("Claude not available - simulating response")
            await asyncio.sleep(1)  # Simulate processing time
            return {
                "status": "simulated",
                "output": f"Simulated response for: {prompt[:100]}",
                "files_created": [],
                "files_modified": [],
            }

        # Build command
        cmd = [self.claude_cmd]

        # Add context files
        if context_files:
            for file in context_files:
                cmd.extend(["--file", file])

        # Add prompt
        cmd.append(prompt)

        self.log.info(f"Executing Claude async: {' '.join(cmd[:3])}...")
        self.metrics["subprocess_calls"] += 1

        try:
            # Create async subprocess
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.workspace),
            )

            # Wait for completion with timeout
            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=300)  # 5 minute timeout
            except TimeoutError:
                process.kill()
                await process.wait()
                return {"status": "timeout", "error": "Claude execution timed out after 5 minutes"}

            # Parse output
            if process.returncode == 0:
                return {
                    "status": "success",
                    "output": stdout.decode() if stdout else "",
                    "files_created": self._parse_created_files(stdout.decode() if stdout else ""),
                    "files_modified": self._parse_modified_files(stdout.decode() if stdout else ""),
                }
            else:
                return {
                    "status": "error",
                    "error": stderr.decode() if stderr else "Unknown error",
                    "return_code": process.returncode,
                }

        except Exception as e:
            self.log.error(f"Failed to execute Claude: {e}")
            return {"status": "error", "error": str(e)}

    def _parse_created_files(self, output: str) -> list[str]:
        """Parse created files from Claude output"""
        # Simple pattern matching for created files
        files = []
        for line in output.split("\n"):
            if "created" in line.lower() or "new file" in line.lower():
                # Extract file path (simplified)
                parts = line.split()
                for part in parts:
                    if "/" in part or "\\" in part:
                        files.append(part.strip())
        return files

    def _parse_modified_files(self, output: str) -> list[str]:
        """Parse modified files from Claude output"""
        # Simple pattern matching for modified files
        files = []
        for line in output.split("\n"):
            if "modified" in line.lower() or "updated" in line.lower():
                # Extract file path (simplified)
                parts = line.split()
                for part in parts:
                    if "/" in part or "\\" in part:
                        files.append(part.strip())
        return files

    async def execute_phase_async(self) -> dict[str, Any]:
        """Execute task phase asynchronously"""
        self.log.info(f"Executing phase: {self.phase}")
        start_time = datetime.now(UTC)

        try:
            # Load task from database (if DB available)
            if not self.task_id:
                return {"status": "error", "error": "No task_id provided"}

            task = None
            if self.db_ops:
                task = await self.db_ops.get_task_async(self.task_id)

            if not task:
                # Fallback: task provided in metadata or run without DB
                task = {"description": "No DB available - running in standalone mode", "payload": {}}

            # Get task description and payload
            description = task.get("description", "")
            payload = task.get("payload", {})

            # Execute based on phase
            if self.phase == "apply":
                result = await self._execute_apply_phase_async(description, payload)
            elif self.phase == "test":
                result = await self._execute_test_phase_async(description, payload)
            elif self.phase == "plan":
                result = await self._execute_plan_phase_async(description, payload)
            else:
                result = {"status": "error", "error": f"Unknown phase: {self.phase}"}

            # Calculate execution time
            execution_time = (datetime.now(UTC) - start_time).total_seconds()
            result["execution_time"] = execution_time

            # Save result to database
            if self.run_id:
                await self._save_run_result_async(result)

            # Publish completion event
            await self.event_bus.publish_async(
                event_type=f"worker.{self.phase}.completed",
                task_id=self.task_id,
                worker_id=self.worker_id,
                result=result.get("status"),
                priority=2,
            )

            return result

        except Exception as e:
            self.log.error(f"Phase execution failed: {e}")
            return {"status": "error", "error": str(e), "phase": self.phase}

    async def _execute_apply_phase_async(self, description: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Execute APPLY phase asynchronously"""
        self.log.info("Executing APPLY phase")

        # Build prompt
        prompt = f"""
        Task: {description}

        Requirements:
        {json.dumps(payload.get("requirements", []), indent=2)}

        Please implement the required functionality.
        Create clean, well-tested code following best practices.
        """

        # Execute Claude
        result = await self.execute_claude_async(prompt)

        if result["status"] == "success":
            self.log.info("# OK APPLY phase completed successfully")
            self.log.info(f"  Files created: {len(result.get('files_created', []))}")
            self.log.info(f"  Files modified: {len(result.get('files_modified', []))}")
        else:
            self.log.error(f"# FAIL APPLY phase failed: {result.get('error')}")

        return result

    async def _execute_test_phase_async(self, description: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Execute TEST phase asynchronously"""
        self.log.info("Executing TEST phase")

        # Build prompt
        prompt = f"""
        Task: {description}

        Please write comprehensive tests for the implemented functionality.
        Include unit tests, integration tests, and edge cases.
        Ensure high code coverage.
        """

        # Get implementation files for context
        context_files = [],
        workspace_files = list(self.workspace.glob("**/*.py"))
        for file in workspace_files[:10]:  # Limit to 10 files
            if "test" not in file.name.lower():
                context_files.append(str(file))

        # Execute Claude
        result = await self.execute_claude_async(prompt, context_files)

        if result["status"] == "success":
            # Run tests asynchronously
            test_result = await self._run_tests_async()
            result["test_result"] = test_result

            if test_result.get("passed"):
                self.log.info("# OK TEST phase completed, all tests passed")
            else:
                self.log.info("# WARN TEST phase completed with failures")
        else:
            self.log.error(f"# FAIL TEST phase failed: {result.get('error')}")

        return result

    async def _execute_plan_phase_async(self, description: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Execute PLAN phase asynchronously"""
        self.log.info("Executing PLAN phase")

        # Build prompt
        prompt = f"""
        Task: {description}

        Please create a detailed implementation plan.
        Break down the task into clear steps.
        Identify potential challenges and solutions.
        """

        # Execute Claude
        result = await self.execute_claude_async(prompt)

        if result["status"] == "success":
            self.log.info("# OK PLAN phase completed successfully")
        else:
            self.log.error(f"# FAIL PLAN phase failed: {result.get('error')}")

        return result

    async def _run_tests_async(self) -> dict[str, Any]:
        """Run tests asynchronously"""
        self.log.info("Running tests asynchronously")

        # Find test files
        test_files = list(self.workspace.glob("**/test_*.py"))
        test_files.extend(self.workspace.glob("**/*_test.py"))

        if not test_files:
            return {"passed": True, "message": "No tests found"}

        try:
            # Run pytest asynchronously
            process = await asyncio.create_subprocess_exec(
                sys.executable,
                "-m",
                "pytest",
                "-v",
                "--tb=short",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.workspace),
            )

            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=60)  # 1 minute timeout for tests

            if process.returncode == 0:
                return {
                    "passed": True,
                    "output": stdout.decode() if stdout else "",
                }
            else:
                return {
                    "passed": False,
                    "output": stdout.decode() if stdout else "",
                    "error": stderr.decode() if stderr else "",
                }

        except TimeoutError:
            return {
                "passed": False,
                "error": "Test execution timed out after 1 minute",
            }
        except Exception as e:
            return {
                "passed": False,
                "error": str(e),
            }

    async def _save_run_result_async(self, result: dict[str, Any]) -> None:
        """Save run result to database asynchronously"""
        try:
            self.metrics["db_operations"] += 1

            # Calculate metrics
            execution_time = (datetime.now(UTC) - self.metrics["start_time"]).total_seconds()

            # Save result (if DB available)
            if self.db_ops:
                await self.db_ops.update_run_async(
                    run_id=self.run_id,
                    status=result.get("status", "unknown"),
                    result=result,
                    metadata={
                        "execution_time": execution_time,
                        "operations": self.metrics["operations"],
                        "file_operations": self.metrics["file_operations"],
                        "subprocess_calls": self.metrics["subprocess_calls"],
                        "db_operations": self.metrics["db_operations"],
                    },
                )

            self.log.info(f"Run result saved: {result.get('status')}")

        except Exception as e:
            self.log.error(f"Failed to save run result: {e}")

    async def run_async(self) -> int:
        """Main async execution entry point"""
        try:
            # Initialize async components
            await self.initialize_async()

            # Execute phase
            result = await self.execute_phase_async()

            # Log final metrics
            self.log.info(
                f"[METRICS] Operations: {self.metrics['operations']} | ",
                f"Files: {self.metrics['file_operations']} | ",
                f"Subprocesses: {self.metrics['subprocess_calls']} | ",
                f"DB: {self.metrics['db_operations']}",
            )

            # Return exit code
            if result.get("status") == "success":
                return 0
            else:
                return 1

        except Exception as e:
            self.log.error(f"Worker execution failed: {e}")
            return 1

        finally:
            # Cleanup
            if self.db_ops:
                await self.db_ops.close()


async def main_async() -> None:
    """Main entry point for AsyncWorker"""
    parser = argparse.ArgumentParser(description="AsyncWorker - V4.0 High-Performance Worker")
    parser.add_argument("role", choices=["backend", "frontend", "infra"], help="Worker role")
    parser.add_argument("--task-id", help="Task ID to execute")
    parser.add_argument("--run-id", help="Run ID for tracking")
    parser.add_argument("--phase", default="apply", choices=["plan", "apply", "test"], help="Execution phase")
    parser.add_argument("--mode", default="fresh", choices=["fresh", "repo", "worktree"], help="Workspace mode")
    parser.add_argument("--workspace", help="Custom workspace path")
    parser.add_argument("--one-shot", action="store_true", help="Execute once and exit")
    parser.add_argument("--live", action="store_true", help="Enable live output")
    parser.add_argument("--async", dest="async_mode", action="store_true", help="Enable async mode")

    args = parser.parse_args()

    # Configure logging
    log_name = f"async-worker-{args.role}"
    if args.task_id:
        log_name += f"-{args.task_id}"
    setup_logging(name=log_name, log_to_file=True, log_file_path=f"logs/{log_name}.log")

    # Create worker
    worker = AsyncWorker(
        worker_id=args.role,
        task_id=args.task_id,
        run_id=args.run_id,
        workspace=args.workspace,
        phase=args.phase,
        mode=args.mode,
        live_output=args.live,
    )

    # Run worker,
    exit_code = await worker.run_async()
    sys.exit(exit_code)


if __name__ == "__main__":
    asyncio.run(main_async())
