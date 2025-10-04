"""Coder Service - Autonomous ExecutionPlan → Production Code.

Wraps the Coder Agent for use within hive-orchestrator's service architecture.
Provides clean service interface following orchestrator patterns.

Architecture:
    ExecutionPlan → DependencyResolver → TaskExecutor → Service code → Validation

Integration:
    - Used by ProjectOrchestrator in hive-ui
    - Coordinates with ArchitectService for plan input
    - Leverages hive-app-toolkit for code scaffolding
    - Uses hive-bus for event communication
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from hive_architect.models import ExecutionPlan

# Import Coder Agent components
from hive_coder.agent import CoderAgent
from hive_coder.models import ExecutionResult

from hive_config import HiveConfig, create_config_from_sources
from hive_logging import get_logger

logger = get_logger(__name__)


class CoderService:
    """Orchestrator service wrapper for Coder Agent.

    Provides clean service interface for autonomous code generation
    from ExecutionPlans within hive-orchestrator.

    Example:
        service = CoderService()
        result = await service.execute_plan(
            plan_file="plans/feedback-service.json",
            output_dir="generated/feedback-service"
        )
    """

    def __init__(self, config: HiveConfig | None = None) -> None:
        """Initialize Coder Service.

        Args:
            config: Optional configuration (uses DI pattern)
        """
        self._config = config or create_config_from_sources()
        self._agent = CoderAgent(config=self._config)
        self.logger = logger

        self.logger.info("CoderService initialized (orchestrator integration)")

    async def execute_plan(
        self,
        plan_file: str | Path,
        output_dir: str | Path,
        validate_output: bool = True,
        run_tests: bool = False,
    ) -> ExecutionResult:
        """Execute ExecutionPlan to generate production-ready service.

        Args:
            plan_file: Path to ExecutionPlan JSON file
            output_dir: Directory where service will be generated
            validate_output: Whether to validate generated code
            run_tests: Whether to run test suite after generation

        Returns:
            ExecutionResult with detailed execution status
        """
        self.logger.info(f"Executing plan from: {plan_file}")

        # Delegate to Coder Agent
        result = self._agent.execute_plan(
            plan_file=plan_file,
            output_dir=output_dir,
            validate_output=validate_output,
            run_tests=run_tests,
        )

        self.logger.info(
            f"Execution complete: {result.status} - "
            f"{result.tasks_completed}/{result.total_tasks} tasks in "
            f"{result.total_duration_seconds:.2f}s"
        )

        return result

    async def execute_plan_from_object(
        self,
        plan: ExecutionPlan,
        output_dir: str | Path,
        validate_output: bool = True,
        run_tests: bool = False,
    ) -> ExecutionResult:
        """Execute ExecutionPlan object directly (without file I/O).

        Args:
            plan: ExecutionPlan object to execute
            output_dir: Directory where service will be generated
            validate_output: Whether to validate generated code
            run_tests: Whether to run test suite after generation

        Returns:
            ExecutionResult with detailed execution status
        """
        self.logger.info(f"Executing plan object: {plan.plan_id}")

        # Save plan to temporary file
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        temp_plan_file = output_path / f"{plan.plan_id}.json"
        plan.to_json_file(str(temp_plan_file))

        try:
            # Execute using file-based method
            result = await self.execute_plan(
                plan_file=temp_plan_file,
                output_dir=output_dir,
                validate_output=validate_output,
                run_tests=run_tests,
            )
        finally:
            # Cleanup temporary plan file
            if temp_plan_file.exists():
                temp_plan_file.unlink()

        return result

    async def validate_plan(self, plan: ExecutionPlan) -> dict[str, Any]:
        """Validate ExecutionPlan before execution.

        Args:
            plan: ExecutionPlan to validate

        Returns:
            Validation results with dependency checks
        """
        self.logger.info(f"Validating plan: {plan.plan_id}")
        validation = self._agent.validate_plan(plan)

        # Add service-level metadata
        validation["plan_id"] = plan.plan_id
        validation["service_name"] = plan.service_name
        validation["task_count"] = len(plan.tasks)

        return validation

    def get_service_info(self) -> dict[str, Any]:
        """Get service and agent information.

        Returns:
            Service metadata and capabilities
        """
        return {
            "service": "CoderService",
            "agent": "CoderAgent",
            "capabilities": [
                "ExecutionPlan execution",
                "Dependency resolution",
                "Task orchestration",
                "Code generation via hive-app-toolkit",
                "Generated code validation",
                "Test execution",
            ],
            "architecture": "ExecutionPlan → Resolver → Executor → Validation",
        }
