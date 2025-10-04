"""Coder Agent - The Hands of Project Colossus.

Executes ExecutionPlans from Architect Agent to generate production-ready services.

Flow:
    1. Load ExecutionPlan from JSON file
    2. Validate plan structure and dependencies
    3. Resolve task execution order
    4. Execute tasks using hive-app-toolkit
    5. Validate generated code
    6. Return execution results
"""

from __future__ import annotations

import time
from pathlib import Path

from hive_architect.models import ExecutionPlan
from hive_config import HiveConfig, create_config_from_sources
from hive_logging import get_logger

from .executor import TaskExecutor
from .models import ExecutionResult, ExecutionStatus
from .resolver import DependencyResolver
from .validator import CodeValidator

logger = get_logger(__name__)


class CoderAgent:
    """The Coder Agent - Hands of Project Colossus.

    Transforms ExecutionPlans into production-ready services using hive-app-toolkit.

    Example:
        agent = CoderAgent()
        result = agent.execute_plan("execution_plan.json", output_dir="generated/my-service")

    """

    def __init__(self, config: HiveConfig | None = None) -> None:
        """Initialize the Coder Agent.

        Args:
            config: Optional configuration (uses DI pattern)

        """
        self._config = config or create_config_from_sources()
        self.logger = logger
        self.resolver = DependencyResolver()
        self.validator = CodeValidator()

        self.logger.info("Coder Agent initialized")

    def execute_plan(
        self,
        plan_file: str | Path,
        output_dir: str | Path,
        validate_output: bool = True,
        run_tests: bool = False,
    ) -> ExecutionResult:
        """Execute an ExecutionPlan to generate a service.

        Args:
            plan_file: Path to ExecutionPlan JSON file
            output_dir: Directory where service will be generated
            validate_output: Whether to validate generated code
            run_tests: Whether to run test suite after generation

        Returns:
            ExecutionResult with detailed execution status

        Example:
            result = agent.execute_plan(
                plan_file="plans/feedback-service.json",
                output_dir="generated/feedback-service",
                validate_output=True,
                run_tests=True
            )

        """
        self.logger.info(f"Starting execution of plan: {plan_file}")
        start_time = time.time()

        # Load execution plan
        plan = self._load_plan(plan_file)
        self.logger.info(f"Loaded plan: {plan.plan_id} for service {plan.service_name}")

        # Initialize result
        output_path = Path(output_dir)
        result = ExecutionResult(
            plan_id=plan.plan_id,
            service_name=plan.service_name,
            status=ExecutionStatus.IN_PROGRESS,
            output_directory=output_path,
            total_tasks=len(plan.tasks),
        )

        try:
            # Resolve task execution order
            ordered_tasks = self.resolver.resolve_order(plan)
            self.logger.info(f"Task execution order resolved: {len(ordered_tasks)} tasks")

            # Execute tasks
            executor = TaskExecutor(output_path)
            for task in ordered_tasks:
                task_result = executor.execute_task(task, plan.service_name)
                result.task_results.append(task_result)

                if task_result.status == ExecutionStatus.COMPLETED:
                    result.tasks_completed += 1
                    result.files_created.extend(task_result.files_created)
                    result.files_modified.extend(task_result.files_modified)
                else:
                    result.tasks_failed += 1
                    self.logger.error(f"Task {task.task_id} failed: {task_result.error_message}")

                    # Continue with other tasks or fail fast?
                    # For now, continue to get as much generated as possible

            # Validate generated code
            if validate_output and result.tasks_completed > 0:
                service_dir = output_path / plan.service_name
                if service_dir.exists():
                    self.logger.info("Running validation checks...")
                    result.validation = self.validator.validate(
                        service_dir, run_tests=run_tests, run_type_check=False,
                    )

                    if not result.validation.is_valid():
                        result.status = ExecutionStatus.VALIDATION_FAILED
                        self.logger.warning("Validation failed - service generated but has quality issues")
                    else:
                        result.status = ExecutionStatus.COMPLETED
                        self.logger.info("Validation passed - service is production-ready")
                else:
                    result.status = ExecutionStatus.FAILED
                    result.error_message = f"Service directory not found: {service_dir}"
            else:
                result.status = ExecutionStatus.COMPLETED if result.tasks_failed == 0 else ExecutionStatus.FAILED

        except Exception as e:
            result.status = ExecutionStatus.FAILED
            result.error_message = str(e)
            self.logger.error(f"Execution failed: {e!s}")

        # Finalize result
        result.total_duration_seconds = time.time() - start_time
        self.logger.info(
            f"Execution complete: {result.status} - "
            f"{result.tasks_completed}/{result.total_tasks} tasks completed "
            f"in {result.total_duration_seconds:.2f}s",
        )

        return result

    def _load_plan(self, plan_file: str | Path) -> ExecutionPlan:
        """Load ExecutionPlan from JSON file"""
        plan_path = Path(plan_file)
        if not plan_path.exists():
            raise FileNotFoundError(f"Plan file not found: {plan_file}")

        return ExecutionPlan.from_json_file(str(plan_path))

    def validate_plan(self, plan: ExecutionPlan) -> dict[str, bool]:
        """Validate ExecutionPlan before execution.

        Args:
            plan: ExecutionPlan to validate

        Returns:
            Validation results

        """
        return self.resolver.validate_dependencies(plan)
