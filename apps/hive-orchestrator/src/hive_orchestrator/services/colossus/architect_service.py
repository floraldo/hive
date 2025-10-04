"""Architect Service - Autonomous NL Requirements → ExecutionPlan.

Wraps the Architect Agent for use within hive-orchestrator's service architecture.
Provides clean service interface following orchestrator patterns.

Architecture:
    Natural Language → RequirementParser → ExecutionPlan → JSON output

Integration:
    - Used by ProjectOrchestrator in hive-ui
    - Coordinates with CoderService for code generation
    - Leverages hive-bus for event communication
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

# Import Architect Agent components
from hive_architect.agent import ArchitectAgent
from hive_architect.models import ExecutionPlan, ParsedRequirement

from hive_config import HiveConfig, create_config_from_sources
from hive_logging import get_logger

logger = get_logger(__name__)


class ArchitectService:
    """Orchestrator service wrapper for Architect Agent.

    Provides clean service interface for autonomous requirement analysis
    and execution plan generation within hive-orchestrator.

    Example:
        service = ArchitectService()
        plan = await service.create_plan_from_requirement(
            requirement="Create a 'feedback-service' API that stores user feedback",
            output_path="plans/feedback-service.json"
        )
    """

    def __init__(self, config: HiveConfig | None = None) -> None:
        """Initialize Architect Service.

        Args:
            config: Optional configuration (uses DI pattern)
        """
        self._config = config or create_config_from_sources()
        self._agent = ArchitectAgent(config=self._config)
        self.logger = logger

        self.logger.info("ArchitectService initialized (orchestrator integration)")

    async def create_plan_from_requirement(
        self,
        requirement: str,
        output_path: str | Path | None = None,
    ) -> ExecutionPlan:
        """Create execution plan from natural language requirement.

        Args:
            requirement: Natural language service description
            output_path: Optional path to save ExecutionPlan JSON

        Returns:
            ExecutionPlan ready for CoderService consumption

        Raises:
            ValueError: If service name conflicts with Python built-ins
        """
        self.logger.info("Creating execution plan from NL requirement")

        # Delegate to Architect Agent (uses enhanced parser with built-ins validation)
        plan = self._agent.create_plan(
            requirement_text=requirement,
            output_path=str(output_path) if output_path else None,
        )

        self.logger.info(
            f"Execution plan created: {plan.service_name} "
            f"({len(plan.tasks)} tasks, {plan.total_estimated_duration_minutes}min)"
        )

        return plan

    async def parse_requirement(self, requirement: str) -> ParsedRequirement:
        """Parse natural language requirement into structured format.

        Args:
            requirement: Natural language description

        Returns:
            ParsedRequirement with extracted structure
        """
        self.logger.info("Parsing NL requirement")
        return self._agent.parse_requirement(requirement)

    async def validate_plan(self, plan: ExecutionPlan) -> dict[str, Any]:
        """Validate execution plan before handing to CoderService.

        Args:
            plan: ExecutionPlan to validate

        Returns:
            Validation results with detailed checks
        """
        self.logger.info(f"Validating execution plan: {plan.service_name}")
        validation = self._agent.validate_plan(plan)

        # Add service-level metadata
        validation["service_name"] = plan.service_name
        validation["task_count"] = len(plan.tasks)
        validation["estimated_minutes"] = plan.total_estimated_duration_minutes

        return validation

    def get_agent_info(self) -> dict[str, Any]:
        """Get service and agent information.

        Returns:
            Service metadata and capabilities
        """
        return {
            "service": "ArchitectService",
            "agent": "ArchitectAgent",
            "capabilities": [
                "Natural language requirement parsing",
                "Execution plan generation",
                "Python built-ins validation",
                "Context-aware service name extraction",
            ],
            "architecture": "NL → Parser → PlanGenerator → ExecutionPlan",
        }
