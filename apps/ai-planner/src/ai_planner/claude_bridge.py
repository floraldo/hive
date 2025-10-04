# Security: subprocess calls in this module use sys.executable or controlled CLI tools
# with hardcoded, trusted arguments only. No user input is passed to subprocess.

"""Robust Claude CLI bridge for AI Planning
Production-ready implementation for intelligent task decomposition and workflow generation
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError

from hive_logging import get_logger

logger = get_logger(__name__)


# Pydantic models for strict contract enforcement
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
        default_factory=list,
        description="Groups of tasks that can run in parallel",
    )
    blocking_dependencies: dict[str, list[str]] = Field(
        default_factory=dict,
        description="Map of task_id -> blocking_task_ids",
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


class RobustClaudePlannerBridge:
    """Production-ready Claude CLI integration for intelligent planning"""

    def __init__(self, mock_mode: bool = False) -> None:
        """Initialize the robust planning bridge

        Args:
            mock_mode: If True, use mock responses instead of calling Claude

        """
        self.mock_mode = mock_mode
        if mock_mode:
            logger.info("Running in mock mode - will not call Claude CLI")
            self.claude_cmd = "mock"
        else:
            self.claude_cmd = self._find_claude_cmd()
            if not self.claude_cmd:
                logger.warning("Claude CLI not found - planning will use fallback mode")

    def _find_claude_cmd(self) -> str | None:
        """Find Claude CLI command - same implementation as AI reviewer"""
        # Check common locations
        possible_paths = [
            Path.home() / ".npm-global" / "claude.cmd",
            Path.home() / ".npm-global" / "claude",
            Path("claude.cmd"),
            Path("claude"),
        ]

        for path in possible_paths:
            if path.exists():
                logger.info(f"Using Claude from: {path}")
                return str(path)

        # Try system PATH
        result = subprocess.run(["where" if os.name == "nt" else "which", "claude"], check=False, capture_output=True, text=True)
        claude_path = result.stdout.strip().split("\n")[0] if result.returncode == 0 else None

        if claude_path:
            logger.info(f"Using Claude from PATH: {claude_path}")
            return claude_path

        return None

    def _create_planning_prompt(
        self,
        task_description: str,
        context_data: dict[str, Any],
        priority: int,
        requestor: str,
    ) -> str:
        """Create comprehensive planning prompt for Claude"""
        context_info = ("",)
        if context_data:
            context_info = f""",
## Context Information:
- Files affected: {context_data.get("files_affected", "unknown")}
- Dependencies: {context_data.get("dependencies", [])}
- Technology stack: {context_data.get("tech_stack", [])}
- Constraints: {context_data.get("constraints", [])}
- Resources: {context_data.get("resources", [])}
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
You MUST respond with a valid JSON object that strictly follows this schema. Do not include any text before or after the JSON.

```json,
{{
    "plan_id": "unique-plan-identifier",
    "plan_name": "Human-readable plan name (max 100 chars)",
    "plan_summary": "Executive summary of the plan (max 500 chars)",
    "sub_tasks": [
        {{
            "id": "task-001",
            "title": "Concise task title",
            "description": "Detailed task description with specific deliverables",
            "assignee": "worker:backend|worker:frontend|app:ecosystemiser|worker:infra",
            "estimated_duration": 30,
            "complexity": "simple|medium|complex",
            "dependencies": ["task-000"],
            "workflow_phase": "analysis|design|implementation|testing|validation",
            "required_skills": ["python", "api-design", "testing"],
            "deliverables": ["api_endpoints.py", "unit_tests.py", "integration_tests.py"]
        }}
    ]
    "dependencies": {{
        "critical_path": ["task-001", "task-002", "task-003"],
        "parallel_groups": [["task-004", "task-005"], ["task-006", "task-007"]]
        "blocking_dependencies": {{
            "task-002": ["task-001"],
            "task-003": ["task-002"]
        }}
    }},
    "workflow": {{
        "lifecycle_phases": ["analysis", "design", "implementation", "testing", "validation"],
        "phase_transitions": {{
            "analysis": "design",
            "design": "implementation",
            "implementation": "testing",
            "testing": "validation",
        }},
        "validation_gates": {{
            "design": ["architecture_review", "stakeholder_approval"],
            "implementation": ["code_review", "unit_tests_pass"],
            "testing": ["integration_tests_pass", "performance_benchmarks"],
            "validation": ["user_acceptance", "deployment_ready"]
        }},
        "rollback_strategy": "checkpoint-based rollback with automated reversion",
    }},
    "metrics": {{
        "total_estimated_duration": 240,
        "critical_path_duration": 180,
        "complexity_breakdown": {{"simple": 3, "medium": 4, "complex": 2}},
        "skill_requirements": {{"python": 5, "frontend": 3, "database": 2}},
        "confidence_score": 0.85,
        "risk_factors": ["external_api_dependency", "complex_data_migration"]
    }},
    "recommendations": [
        "Start with architecture review to validate approach",
        "Implement robust error handling early",
        "Set up comprehensive monitoring"
    ],
    "considerations": [
        "Performance impact on existing systems",
        "Security implications of new endpoints",
        "Backwards compatibility requirements"
    ]
}}
```

## Planning Guidelines:
1. **Decomposition**: Break down into 3-15 discrete, actionable sub-tasks,
2. **Assignees**: Use realistic assignees (worker:backend, worker:frontend, app:ecosystemiser, worker:infra)
3. **Dependencies**: Map realistic dependencies - avoid circular dependencies,
4. **Estimates**: Provide realistic time estimates (5-480 minutes per task)
5. **Workflow**: Define clear lifecycle phases with validation gates,
6. **Risk Assessment**: Identify potential risks and mitigation strategies

## Quality Standards:
- Each sub-task must be independently executable,
- Dependencies must form a valid DAG (Directed Acyclic Graph)
- Estimates should account for complexity and unknowns,
- Assignees must align with their expertise domains,
- Workflow phases should follow software engineering best practices

Generate the execution plan now:"""

        return prompt

    def _extract_json_from_response(self, response_text: str) -> dict[str, Any] | None:
        """Extract JSON from Claude response with robust parsing"""
        try:
            # Try direct JSON parsing first,
            return json.loads(response_text.strip())
        except json.JSONDecodeError:
            pass

        # Try to find JSON within markdown code blocks,
        json_match = re.search(r"```json\s*(\{.*?\})\s*```", response_text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # Try to find JSON within the response,
        json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass

        logger.error("Failed to extract valid JSON from Claude response")
        return None

    def _create_fallback_response(self, task_description: str, error_message: str) -> dict[str, Any]:
        """Create fallback response when Claude is unavailable"""
        logger.warning(f"Creating fallback response due to: {error_message}")

        # Generate a simple, rule-based plan as fallback,
        fallback_response = ClaudePlanningResponse(
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
                blocking_dependencies={"fallback-002": ["fallback-001"], "fallback-003": ["fallback-002"]},
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
            recommendations=["Validate requirements before implementation", "Test thoroughly before deployment"],
            considerations=[
                "This is a fallback plan - consider human review",
                "Claude integration should be restored for better planning",
            ],
        )

        return fallback_response.dict()

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
        if self.mock_mode:
            # Return a mock response for testing,
            logger.info(f"Mock mode: generating mock plan for: {task_description}")
            import uuid

            mock_response = ClaudePlanningResponse(
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
            return mock_response.dict()

        if not self.claude_cmd:
            return self._create_fallback_response(task_description, "Claude CLI not available")

        try:
            # Create comprehensive prompt
            prompt = self._create_planning_prompt(task_description, context_data or {}, priority, requestor)

            # Execute Claude CLI with --print flag to ensure it exits after responding
            # Add --dangerously-skip-permissions for automated environments
            logger.info(f"Calling Claude for planning: {task_description[:100]}...")
            result = subprocess.run(
                [self.claude_cmd, "--print", "--dangerously-skip-permissions", prompt],
                check=False, capture_output=True,
                text=True,
                timeout=120,  # 2 minute timeout for complex planning
            )

            if result.returncode != 0:
                logger.error(f"Claude CLI failed with return code {result.returncode}")
                logger.error(f"Error output: {result.stderr}")
                return self._create_fallback_response(task_description, f"Claude CLI error: {result.stderr[:200]}")

            # Extract and validate JSON response
            response_json = self._extract_json_from_response(result.stdout)
            if not response_json:
                return self._create_fallback_response(task_description, "Failed to parse Claude response as JSON")

            # Validate response against schema
            try:
                validated_response = ClaudePlanningResponse(**response_json)
                logger.info(f"Claude planning successful: {validated_response.plan_name}")
                return validated_response.dict()
            except ValidationError as e:
                logger.error(f"Claude response validation failed: {e}")
                return self._create_fallback_response(task_description, f"Response validation error: {str(e)[:200]}")

        except subprocess.TimeoutExpired:
            logger.error("Claude CLI timeout during planning")
            return self._create_fallback_response(task_description, "Claude CLI timeout")
        except Exception as e:
            logger.error(f"Unexpected error during Claude planning: {e}")
            return self._create_fallback_response(task_description, f"Unexpected error: {str(e)[:200]}")
