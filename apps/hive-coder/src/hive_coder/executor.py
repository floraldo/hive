"""
Task execution engine for code generation.

Executes individual tasks from ExecutionPlan using hive-app-toolkit.
"""

from __future__ import annotations

import subprocess
import time
from pathlib import Path

from hive_architect.models import ExecutionTask, TaskType
from hive_errors import BaseError
from hive_logging import get_logger

from .models import ExecutionStatus, TaskResult

logger = get_logger(__name__)


class TaskExecutionError(BaseError):
    """Raised when task execution fails"""

    pass


class TaskExecutor:
    """
    Executes individual tasks from ExecutionPlan.

    Each task type maps to specific actions:
    - SCAFFOLD: Generate project using hive-app-toolkit
    - DATABASE_MODEL: Add database schemas
    - API_ENDPOINT: Create API routes
    - SERVICE_LOGIC: Implement business logic
    - TEST_SUITE: Generate tests
    - DEPLOYMENT: Add Docker/K8s manifests
    - DOCUMENTATION: Generate README/docs
    """

    def __init__(self, output_dir: Path) -> None:
        """
        Initialize task executor.

        Args:
            output_dir: Base directory for generated code
        """
        self.output_dir = Path(output_dir)
        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logger

    def execute_task(self, task: ExecutionTask, service_name: str) -> TaskResult:
        """
        Execute a single task from ExecutionPlan.

        Args:
            task: ExecutionTask to execute
            service_name: Name of service being generated

        Returns:
            TaskResult with execution status and file changes
        """
        self.logger.info(f"Executing task {task.task_id}: {task.task_type}")
        start_time = time.time()

        try:
            # Route to appropriate handler
            handler = self._get_task_handler(task.task_type)
            files_created, files_modified = handler(task, service_name)

            duration = time.time() - start_time
            result = TaskResult(
                task_id=task.task_id,
                task_type=task.task_type.value,
                status=ExecutionStatus.COMPLETED,
                files_created=files_created,
                files_modified=files_modified,
                duration_seconds=duration,
            )

            self.logger.info(f"Task {task.task_id} completed in {duration:.2f}s")
            return result

        except Exception as e:
            duration = time.time() - start_time
            self.logger.error(f"Task {task.task_id} failed: {e!s}")

            return TaskResult(
                task_id=task.task_id,
                task_type=task.task_type.value,
                status=ExecutionStatus.FAILED,
                duration_seconds=duration,
                error_message=str(e),
                validation_passed=False,
            )

    def _get_task_handler(self, task_type: TaskType):
        """Get the appropriate handler for task type"""
        handlers = {
            TaskType.SCAFFOLD: self._execute_scaffold,
            TaskType.API_ENDPOINT: self._execute_api_endpoint,
            TaskType.DATABASE_MODEL: self._execute_database_model,
            TaskType.SERVICE_LOGIC: self._execute_service_logic,
            TaskType.TEST_SUITE: self._execute_test_suite,
            TaskType.DEPLOYMENT: self._execute_deployment,
            TaskType.DOCUMENTATION: self._execute_documentation,
        }

        handler = handlers.get(task_type)
        if not handler:
            raise TaskExecutionError(f"Unknown task type: {task_type}")

        return handler

    def _execute_scaffold(self, task: ExecutionTask, service_name: str) -> tuple[list[str], list[str]]:
        """
        Execute SCAFFOLD task using hive-app-toolkit.

        Generates project structure with:
        - pyproject.toml
        - Main entry point
        - API/Worker/Batch structure
        - Tests
        - Docker/K8s manifests
        """
        self.logger.info(f"Scaffolding {service_name} using template: {task.template}")

        # Build hive-toolkit command
        cmd = ["hive-toolkit", "init", service_name, "--type", task.template or "api"]

        # Add optional flags from parameters
        if task.parameters.get("enable_database"):
            cmd.append("--enable-database")
        if task.parameters.get("enable_cache"):
            cmd.append("--enable-cache")

        # Execute command
        try:
            result = subprocess.run(  # noqa: S603, S607
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=60,
                cwd=self.output_dir,
            )

            self.logger.info(f"Scaffold complete: {result.stdout.strip()}")

            # List created files
            service_dir = self.output_dir / service_name
            if service_dir.exists():
                files = [str(f.relative_to(self.output_dir)) for f in service_dir.rglob("*") if f.is_file()]
                return files, []
            else:
                raise TaskExecutionError(f"Service directory not created: {service_dir}")

        except subprocess.CalledProcessError as e:
            raise TaskExecutionError(f"Scaffold failed: {e.stderr}") from e
        except subprocess.TimeoutExpired as e:
            raise TaskExecutionError("Scaffold timeout") from e

    def _execute_api_endpoint(self, task: ExecutionTask, service_name: str) -> tuple[list[str], list[str]]:
        """Execute API_ENDPOINT task - create API routes"""
        self.logger.info(f"Creating API endpoint: {task.description}")

        # Use hive-toolkit to add API route
        service_dir = self.output_dir / service_name
        endpoint_name = task.parameters.get("endpoint_name", "default")

        cmd = ["hive-toolkit", "add-api", endpoint_name]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=30, cwd=service_dir)  # noqa: S603, S607

            self.logger.info(f"API endpoint created: {result.stdout.strip()}")

            # Track modified files (API routes)
            api_dir = service_dir / "src" / service_name.replace("-", "_") / "api"
            files = [str(f.relative_to(self.output_dir)) for f in api_dir.rglob("*.py")]

            return [], files

        except subprocess.CalledProcessError as e:
            self.logger.warning(f"API endpoint creation skipped: {e.stderr}")
            # Non-critical - continue execution
            return [], []

    def _execute_database_model(self, task: ExecutionTask, service_name: str) -> tuple[list[str], list[str]]:
        """Execute DATABASE_MODEL task - create database schemas"""
        self.logger.info(f"Creating database model: {task.description}")

        # Database models would be added via template expansion
        # For now, log the intent (full implementation in later milestones)
        self.logger.info("Database model task logged (full implementation pending)")

        return [], []

    def _execute_service_logic(self, task: ExecutionTask, service_name: str) -> tuple[list[str], list[str]]:
        """Execute SERVICE_LOGIC task - implement business logic"""
        self.logger.info(f"Creating service logic: {task.description}")

        # Business logic would be generated from specifications
        # For now, log the intent (full implementation in later milestones)
        self.logger.info("Service logic task logged (full implementation pending)")

        return [], []

    def _execute_test_suite(self, task: ExecutionTask, service_name: str) -> tuple[list[str], list[str]]:
        """Execute TEST_SUITE task - generate tests"""
        self.logger.info(f"Creating test suite: {task.description}")

        # Additional tests beyond those generated by scaffold
        # For now, scaffold already includes basic tests
        self.logger.info("Test suite task logged (scaffold includes basic tests)")

        return [], []

    def _execute_deployment(self, task: ExecutionTask, service_name: str) -> tuple[list[str], list[str]]:
        """Execute DEPLOYMENT task - add K8s/Docker configs"""
        self.logger.info(f"Creating deployment configs: {task.description}")

        service_dir = self.output_dir / service_name

        # Add K8s manifests if not already present
        cmd = ["hive-toolkit", "add-k8s", "--namespace", task.parameters.get("namespace", "hive-platform")]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=30, cwd=service_dir)  # noqa: S603, S607

            self.logger.info(f"Deployment configs created: {result.stdout.strip()}")

            k8s_dir = service_dir / "k8s"
            if k8s_dir.exists():
                files = [str(f.relative_to(self.output_dir)) for f in k8s_dir.rglob("*.yaml")]
                return files, []

            return [], []

        except subprocess.CalledProcessError as e:
            self.logger.warning(f"Deployment config creation skipped: {e.stderr}")
            return [], []

    def _execute_documentation(self, task: ExecutionTask, service_name: str) -> tuple[list[str], list[str]]:
        """Execute DOCUMENTATION task - generate README/docs"""
        self.logger.info(f"Creating documentation: {task.description}")

        # Documentation is already generated by scaffold
        # This task could enhance it with API docs
        self.logger.info("Documentation task logged (scaffold includes README)")

        return [], []
