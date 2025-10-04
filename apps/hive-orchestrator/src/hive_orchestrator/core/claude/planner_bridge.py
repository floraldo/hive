from __future__ import annotations

from hive_logging import get_logger

logger = get_logger(__name__)

"""
Specialized Claude Bridge for AI Planning
"""

import json
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from .bridge import BaseClaludeBridge, ClaudeBridgeConfig
from .validators import PydanticValidator


# Pydantic models for planning
class SubTask(BaseModel):
    """Individual sub-task within an execution plan"""

    id: str = Field(description="Unique identifier for the sub-task")
    title: str = Field(max_length=100, description="Concise sub-task title")
    description: str = Field(max_length=500, description="Detailed sub-task description")
    assignee: str = Field(description="Target assignee (worker:backend, app:ecosystemiser, etc.)")
    estimated_duration: int = Field(ge=1, le=480, description="Estimated duration in minutes")
    complexity: Literal["simple", "medium", "complex"] = Field(description="Task complexity level")
    dependencies: list[str] = Field(default_factory=list, description="List of sub-task IDs this depends on")
    workflow_phase: Literal["analysis", "design", "implementation", "testing", "validation"] = Field(
        description="Primary workflow phase for this sub-task",
    )
    required_skills: list[str] = Field(default_factory=list, description="Required skills/technologies")
    deliverables: list[str] = Field(default_factory=list, description="Expected outputs/deliverables")


class DependencyMap(BaseModel):
    """Dependency relationships between sub-tasks"""

    critical_path: list[str] = Field(description="Ordered list of sub-task IDs on critical path")
    parallel_groups: list[list[str]] = Field(
        default_factory=list, description="Groups of tasks that can run in parallel",
    )
    blocking_dependencies: dict[str, list[str]] = Field(
        default_factory=dict, description="Map of task_id -> blocking_task_ids",
    )


class WorkflowDefinition(BaseModel):
    """Complete workflow definition for the execution plan"""

    lifecycle_phases: list[str] = Field(description="Ordered list of lifecycle phases")
    phase_transitions: dict[str, str] = Field(description="Map of phase -> next_phase")
    validation_gates: dict[str, list[str]] = Field(description="Map of phase -> validation criteria")
    rollback_strategy: str = Field(description="Strategy for handling failures and rollbacks")


class PlanningMetrics(BaseModel):
    """Metrics and estimates for the execution plan"""

    total_estimated_duration: int = Field(ge=1, description="Total estimated duration in minutes")
    critical_path_duration: int = Field(ge=1, description="Critical path duration in minutes")
    complexity_breakdown: dict[str, int] = Field(description="Count of tasks by complexity level")
    skill_requirements: dict[str, int] = Field(description="Count of tasks requiring each skill")
    confidence_score: float = Field(ge=0.0, le=1.0, description="Confidence in the plan accuracy")
    risk_factors: list[str] = Field(default_factory=list, description="Identified risk factors")


class ClaudePlanningResponse(BaseModel):
    """Structured response contract for Claude planning"""

    plan_id: str = Field(description="Unique identifier for the execution plan")
    plan_name: str = Field(max_length=100, description="Human-readable plan name")
    plan_summary: str = Field(max_length=500, description="Executive summary of the plan")
    sub_tasks: list[SubTask] = Field(description="List of decomposed sub-tasks")
    dependencies: DependencyMap = Field(description="Dependency relationships between tasks")
    workflow: WorkflowDefinition = Field(description="Complete workflow definition")
    metrics: PlanningMetrics = Field(description="Planning metrics and estimates")
    recommendations: list[str] = Field(default_factory=list, description="Strategic recommendations")
    considerations: list[str] = Field(default_factory=list, description="Important considerations and constraints")


class PlanningResponseValidator(PydanticValidator):
    """Validator for planning responses"""

    def __init__(self) -> None:
        super().__init__(ClaudePlanningResponse)

    def create_fallback(self, error_message: str, context: dict[str, Any]) -> ClaudePlanningResponse:
        """Create a fallback planning response"""
        task_description = context.get("task_description", "Unknown task")

        return ClaudePlanningResponse(
            plan_id=f"fallback-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
            plan_name=f"Fallback Plan: {task_description[:50]}...",
            plan_summary="Fallback plan generated due to Claude unavailability",
            sub_tasks=[
                SubTask(
                    id="fallback-001",
                    title="Analyze Requirements",
                    description=f"Analyze and understand: {task_description}",
                    assignee="worker:backend",
                    estimated_duration=30,
                    complexity="medium",
                    dependencies=[],
                    workflow_phase="analysis",
                    required_skills=["analysis"],
                    deliverables=["requirements.md"],
                ),
                SubTask(
                    id="fallback-002",
                    title="Implement Solution",
                    description="Implement the requested functionality",
                    assignee="worker:backend",
                    estimated_duration=120,
                    complexity="medium",
                    dependencies=["fallback-001"],
                    workflow_phase="implementation",
                    required_skills=["programming"],
                    deliverables=["implementation.py"],
                ),
                SubTask(
                    id="fallback-003",
                    title="Test and Validate",
                    description="Test the implementation and validate requirements",
                    assignee="worker:backend",
                    estimated_duration=60,
                    complexity="simple",
                    dependencies=["fallback-002"],
                    workflow_phase="testing",
                    required_skills=["testing"],
                    deliverables=["test_results.md"],
                ),
            ],
            dependencies=DependencyMap(
                critical_path=["fallback-001", "fallback-002", "fallback-003"],
                parallel_groups=[],
                blocking_dependencies={
                    "fallback-002": ["fallback-001"],
                    "fallback-003": ["fallback-002"],
                },
            ),
            workflow=WorkflowDefinition(
                lifecycle_phases=["analysis", "implementation", "testing"],
                phase_transitions={
                    "analysis": "implementation",
                    "implementation": "testing",
                },
                validation_gates={
                    "analysis": ["requirements_clear"],
                    "implementation": ["code_complete"],
                    "testing": ["tests_pass"],
                },
                rollback_strategy="manual rollback with git revert",
            ),
            metrics=PlanningMetrics(
                total_estimated_duration=210,
                critical_path_duration=210,
                complexity_breakdown={"simple": 1, "medium": 2, "complex": 0},
                skill_requirements={"programming": 2, "testing": 1, "analysis": 1},
                confidence_score=0.6,
                risk_factors=["claude_unavailable", "simplified_planning"],
            ),
            recommendations=[
                "Validate requirements before implementation",
                "Test thoroughly before deployment",
            ],
            considerations=[
                "This is a fallback plan - consider human review",
                "Claude integration should be restored for better planning",
            ],
        )


class ClaudePlannerBridge(BaseClaludeBridge):
    """Specialized Claude bridge for AI planning tasks"""

    def __init__(self, config: ClaudeBridgeConfig | None = None) -> None:
        super().__init__(config)
        self.validator = PlanningResponseValidator()

    def generate_execution_plan(
        self,
        task_description: str,
        context_data: dict[str, Any] = None,
        priority: int = 50,
        requestor: str = "system",
    ) -> dict[str, Any]:
        """Generate intelligent execution plan using Claude API

        Args:
            task_description: High-level task description,
            context_data: Additional context and constraints,
            priority: Task priority (0-100)
            requestor: Who requested the task

        Returns:
            Validated planning response or fallback on failure,

        """
        prompt = self._create_planning_prompt(task_description, context_data or {}, priority, requestor)

        context = {
            "task_description": task_description,
            "priority": priority,
            "requestor": requestor,
            "context_data": context_data,
        }

        return self.call_claude(prompt, validator=self.validator, context=context)

    def _create_planning_prompt(
        self,
        task_description: str,
        context_data: dict[str, Any],
        priority: int,
        requestor: str,
    ) -> str:
        """Create comprehensive planning prompt for Claude"""
        context_info = "",
        if context_data:
            context_info = f""",
## Context Information:
- Files affected: {context_data.get('files_affected', 'unknown')}
- Dependencies: {context_data.get('dependencies', [])}
- Technology stack: {context_data.get('tech_stack', [])}
- Constraints: {context_data.get('constraints', [])}
- Resources: {context_data.get('resources', [])}
"""

        prompt = f"""# AI Planning Engine - Senior Software Architect Mode

You are an expert Senior Software Architect with deep experience in system design, project management, and software engineering best practices. Your task is to analyze the given requirement and create a comprehensive, actionable execution plan.

## Task Analysis:
**Primary Objective:** {task_description}
**Priority Level:** {priority}/100,
**Requestor:** {requestor}
{context_info}

## Your Mission:
Transform this high-level requirement into a detailed, executable plan with proper task decomposition, dependency mapping, and workflow definition.

## Response Requirements:
You MUST respond with a valid JSON object that strictly follows the schema. Do not include any text before or after the JSON.

Generate a JSON response with the following structure:
- plan_id: unique identifier,
- plan_name: human-readable name (max 100 chars)
- plan_summary: executive summary (max 500 chars)
- sub_tasks: array of tasks with id, title, description, assignee, estimated_duration, complexity, dependencies, workflow_phase, required_skills, deliverables,
- dependencies: object with critical_path, parallel_groups, blocking_dependencies,
- workflow: object with lifecycle_phases, phase_transitions, validation_gates, rollback_strategy,
- metrics: object with total_estimated_duration, critical_path_duration, complexity_breakdown, skill_requirements, confidence_score, risk_factors,
- recommendations: array of strategic recommendations,
- considerations: array of important considerations

Generate the execution plan now:"""

        return prompt

    def _create_mock_response(self, prompt: str) -> str:
        """Create a mock response for testing"""
        import uuid

        mock_plan = ClaudePlanningResponse(
            plan_id=f"mock-plan-{uuid.uuid4().hex[:8]}",
            plan_name="Mock Execution Plan",
            plan_summary="Mock plan for testing purposes",
            sub_tasks=[
                SubTask(
                    id="mock-001",
                    title="Mock Analysis Task",
                    description="Mock task for testing",
                    assignee="worker:backend",
                    estimated_duration=30,
                    complexity="medium",
                    dependencies=[],
                    workflow_phase="analysis",
                    required_skills=["testing"],
                    deliverables=["mock_output.txt"],
                ),
            ],
            dependencies=DependencyMap(critical_path=["mock-001"], parallel_groups=[], blocking_dependencies={}),
            workflow=WorkflowDefinition(
                lifecycle_phases=["analysis"],
                phase_transitions={},
                validation_gates={"analysis": ["mock_validation"]},
                rollback_strategy="mock rollback",
            ),
            metrics=PlanningMetrics(
                total_estimated_duration=30,
                critical_path_duration=30,
                complexity_breakdown={"simple": 0, "medium": 1, "complex": 0},
                skill_requirements={"testing": 1},
                confidence_score=0.9,
                risk_factors=["mock_risk"],
            ),
            recommendations=["Mock recommendation"],
            considerations=["Mock consideration"],
        )
        return json.dumps(mock_plan.dict())

    def _create_fallback_response(self, error_message: str, context: dict[str, Any] | None) -> dict[str, Any]:
        """Create a fallback response when Claude is unavailable"""
        fallback = self.validator.create_fallback(error_message, context or {})
        return fallback.dict()
