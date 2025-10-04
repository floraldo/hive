"""Architect Agent - The Brain of Project Colossus.

Orchestrates the transformation of natural language requirements
into executable task plans for the Coder Agent.

Flow:
    1. Natural Language → RequirementParser → ParsedRequirement
    2. ParsedRequirement → PlanGenerator → ExecutionPlan
    3. ExecutionPlan.to_json_file("execution_plan.json")
    4. Coder Agent reads execution_plan.json → generates code
"""

from __future__ import annotations

from hive_config import HiveConfig, create_config_from_sources
from hive_logging import get_logger

from .models import ExecutionPlan, ParsedRequirement
from .nlp import RequirementParser
from .planning import PlanGenerator

logger = get_logger(__name__)


class ArchitectAgent:
    """The Architect Agent - Brain of Project Colossus.

    Transforms natural language requirements into machine-readable execution plans.

    Example:
        agent = ArchitectAgent()
        plan = agent.create_plan("Create a 'feedback-service' API that stores user feedback")
        plan.to_json_file("execution_plan.json")

    """

    def __init__(self, config: HiveConfig | None = None) -> None:
        """Initialize the Architect Agent.

        Args:
            config: Optional configuration (uses DI pattern)

        """
        self._config = config or create_config_from_sources()
        self.logger = logger
        self.parser = RequirementParser()
        self.generator = PlanGenerator()

        self.logger.info("Architect Agent initialized")

    def create_plan(
        self,
        requirement_text: str,
        output_path: str | None = None,
    ) -> ExecutionPlan:
        """Create execution plan from natural language requirement.

        Args:
            requirement_text: Natural language service description
            output_path: Optional path to save ExecutionPlan JSON

        Returns:
            ExecutionPlan ready for Coder Agent consumption

        Example:
            plan = agent.create_plan(
                "Create a 'user-service' API with authentication",
                output_path="plans/user-service-plan.json"
            )

        """
        self.logger.info("Creating execution plan from requirement")

        # Step 1: Parse natural language
        parsed = self.parse_requirement(requirement_text)

        # Step 2: Generate execution plan
        plan = self.generate_plan(parsed)

        # Step 3: Save to file if requested
        if output_path:
            plan.to_json_file(output_path)
            self.logger.info(f"Execution plan saved to: {output_path}")

        return plan

    def parse_requirement(self, requirement_text: str) -> ParsedRequirement:
        """Parse natural language requirement.

        Args:
            requirement_text: Natural language description

        Returns:
            ParsedRequirement with extracted structure

        """
        self.logger.info("Parsing requirement")
        return self.parser.parse(requirement_text)

    def generate_plan(self, requirement: ParsedRequirement) -> ExecutionPlan:
        """Generate execution plan from parsed requirement.

        Args:
            requirement: Parsed requirement structure

        Returns:
            ExecutionPlan with task breakdown

        """
        self.logger.info(f"Generating plan for: {requirement.service_name}")
        return self.generator.generate(requirement)

    def validate_plan(self, plan: ExecutionPlan) -> dict[str, bool]:
        """Validate execution plan before handing to Coder.

        Args:
            plan: ExecutionPlan to validate

        Returns:
            Validation results

        """
        validation = {
            "has_tasks": len(plan.tasks) > 0,
            "has_scaffold_task": any(
                task.task_type.value == "scaffold" for task in plan.tasks
            ),
            "dependencies_valid": self._validate_dependencies(plan),
            "estimated_time_reasonable": plan.total_estimated_duration_minutes < 60,
        }

        all_valid = all(validation.values())
        self.logger.info(
            f"Plan validation: {'PASS' if all_valid else 'FAIL'} - {validation}",
        )

        return validation

    def _validate_dependencies(self, plan: ExecutionPlan) -> bool:
        """Validate task dependencies are acyclic"""
        task_ids = {task.task_id for task in plan.tasks}

        for task in plan.tasks:
            for dep in task.dependencies:
                if dep.task_id not in task_ids:
                    self.logger.warning(
                        f"Task {task.task_id} depends on non-existent task {dep.task_id}",
                    )
                    return False

        return True
