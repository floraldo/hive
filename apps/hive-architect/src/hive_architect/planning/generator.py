"""
Execution Plan Generator.

Converts ParsedRequirement into ExecutionPlan with task breakdown.
Selects appropriate templates from hive-app-toolkit based on service type.
"""

from __future__ import annotations

import uuid
from typing import Any

from hive_logging import get_logger

from ..models import ExecutionPlan, ExecutionTask, ParsedRequirement, ServiceType, TaskDependency, TaskType

logger = get_logger(__name__)


class PlanGenerator:
    """
    Generate execution plans from parsed requirements.

    Example:
        generator = PlanGenerator()
        plan = generator.generate(parsed_requirement)
        plan.to_json_file("execution_plan.json")
    """

    # Template mappings for hive-app-toolkit
    TEMPLATE_MAP = {
        ServiceType.API: "api",
        ServiceType.WORKER: "worker",
        ServiceType.BATCH: "batch",
    }

    def __init__(self) -> None:
        """Initialize the plan generator"""
        self.logger = logger

    def generate(self, requirement: ParsedRequirement) -> ExecutionPlan:
        """
        Generate execution plan from parsed requirement.

        Args:
            requirement: Parsed natural language requirement

        Returns:
            ExecutionPlan with ordered tasks
        """
        self.logger.info(
            f"Generating execution plan for: {requirement.service_name}"
        )

        plan_id = str(uuid.uuid4())
        tasks = self._generate_tasks(requirement)

        plan = ExecutionPlan(
            plan_id=plan_id,
            service_name=requirement.service_name,
            service_type=requirement.service_type.value,
            tasks=tasks,
            metadata={
                "confidence_score": requirement.confidence_score,
                "features": requirement.features,
                "enable_database": requirement.enable_database,
                "enable_caching": requirement.enable_caching,
                "enable_async": requirement.enable_async,
            },
        )

        self.logger.info(
            f"Generated plan {plan_id} with {len(tasks)} tasks "
            f"(est. {plan.total_estimated_duration_minutes} minutes)"
        )

        return plan

    def _generate_tasks(self, requirement: ParsedRequirement) -> list[ExecutionTask]:
        """Generate task list based on requirement"""
        tasks = []

        # Task 1: Scaffold project structure
        tasks.append(
            ExecutionTask(
                task_id="T001",
                task_type=TaskType.SCAFFOLD,
                description=f"Generate {requirement.service_name} using hive-app-toolkit",
                template=self._get_template(requirement.service_type),
                parameters={
                    "service_name": requirement.service_name,
                    "service_type": requirement.service_type.value,
                    "enable_database": requirement.enable_database,
                },
                estimated_duration_minutes=2,
            )
        )

        # Task 2: Define database models (if needed)
        if requirement.enable_database:
            tasks.append(
                ExecutionTask(
                    task_id="T002",
                    task_type=TaskType.DATABASE_MODEL,
                    description="Define database models and schemas",
                    parameters=self._extract_model_params(requirement),
                    dependencies=[TaskDependency(task_id="T001")],
                    estimated_duration_minutes=5,
                )
            )

        # Task 3-N: Implement features
        feature_tasks = self._generate_feature_tasks(
            requirement,
            start_id=3,
            depends_on="T002" if requirement.enable_database else "T001",
        )
        tasks.extend(feature_tasks)

        # Task: Generate tests (use next available ID)
        next_id = max([int(t.task_id[1:]) for t in tasks]) + 1
        test_task_id = f"T{next_id:03d}"
        tasks.append(
            ExecutionTask(
                task_id=test_task_id,
                task_type=TaskType.TEST_SUITE,
                description="Generate comprehensive test suite",
                parameters={
                    "test_coverage_target": 80,
                    "include_integration_tests": True,
                },
                dependencies=[
                    TaskDependency(task_id=task.task_id) for task in feature_tasks
                ],
                estimated_duration_minutes=8,
            )
        )

        # Task: Documentation (use next available ID)
        next_id = max([int(t.task_id[1:]) for t in tasks]) + 1
        doc_task_id = f"T{next_id:03d}"
        tasks.append(
            ExecutionTask(
                task_id=doc_task_id,
                task_type=TaskType.DOCUMENTATION,
                description="Generate API documentation and README",
                parameters={
                    "include_api_docs": requirement.service_type == ServiceType.API,
                    "include_deployment_guide": True,
                },
                dependencies=[TaskDependency(task_id=test_task_id)],
                estimated_duration_minutes=5,
            )
        )

        return tasks

    def _generate_feature_tasks(
        self,
        requirement: ParsedRequirement,
        start_id: int,
        depends_on: str,
    ) -> list[ExecutionTask]:
        """Generate tasks for each feature"""
        tasks = []

        for i, feature in enumerate(requirement.features, start=start_id):
            task_id = f"T{i:03d}"
            task_type = (
                TaskType.API_ENDPOINT
                if requirement.service_type == ServiceType.API
                else TaskType.SERVICE_LOGIC
            )

            tasks.append(
                ExecutionTask(
                    task_id=task_id,
                    task_type=task_type,
                    description=f"Implement: {feature}",
                    parameters={
                        "feature_description": feature,
                        "requires_database": requirement.enable_database,
                    },
                    dependencies=[TaskDependency(task_id=depends_on)],
                    estimated_duration_minutes=10,
                )
            )

        return tasks

    def _get_template(self, service_type: ServiceType) -> str:
        """Get hive-app-toolkit template for service type"""
        return self.TEMPLATE_MAP.get(service_type, "api")

    def _extract_model_params(self, requirement: ParsedRequirement) -> dict[str, Any]:
        """Extract database model parameters from requirement"""
        # Simple extraction for MVP - can be enhanced with NLP
        params = {
            "models": [],
        }

        # Infer models from features
        for feature in requirement.features:
            if "user" in feature.lower():
                params["models"].append({"name": "User", "fields": ["id", "name", "email"]})
            elif "feedback" in feature.lower():
                params["models"].append(
                    {"name": "Feedback", "fields": ["id", "content", "user_id"]}
                )

        return params
