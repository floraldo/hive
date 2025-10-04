"""Chimera Workflow Executor - Autonomous TDD Loop Execution

Executes Chimera workflow state machine through orchestrator integration.
"""

from __future__ import annotations

import asyncio
from typing import Any

from hive_logging import get_logger

from ..models.task import Task, TaskStatus
from .chimera import ChimeraPhase, ChimeraWorkflow

logger = get_logger(__name__)


class ChimeraExecutor:
    """Execute Chimera workflow through orchestrator agent coordination.

    Manages workflow state transitions and agent delegation for autonomous
    E2E test-driven development loop.

    Example:
        executor = ChimeraExecutor(agents_registry)
        result = await executor.execute_phase(task, workflow)

    """

    def __init__(self, agents_registry: dict[str, Any] | None = None) -> None:
        """Initialize Chimera executor.

        Args:
            agents_registry: Registry of available agents for task execution

        """
        self.logger = logger
        self.agents = agents_registry or {}

        self.logger.info("Chimera executor initialized")

    async def execute_workflow(
        self,
        task: Task,
        max_iterations: int = 10,
    ) -> ChimeraWorkflow:
        """Execute complete Chimera workflow until terminal state.

        Args:
            task: Orchestrator task containing workflow state
            max_iterations: Maximum workflow iterations (prevent infinite loops)

        Returns:
            Final workflow state

        Example:
            workflow = await executor.execute_workflow(task)
            if workflow.current_phase == ChimeraPhase.COMPLETE:
                print("Feature delivered!")

        """
        # Load workflow from task
        workflow = ChimeraWorkflow(**task.workflow)

        self.logger.info(
            f"Starting Chimera workflow: {workflow.feature_description} "
            f"(phase: {workflow.current_phase})",
        )

        iterations = 0

        while not workflow.is_terminal() and iterations < max_iterations:
            # Execute current phase
            phase_result = await self.execute_phase(task, workflow)

            # Determine next phase based on result
            next_phase = self._determine_next_phase(workflow, phase_result)

            # Transition to next phase
            workflow.transition_to(next_phase, phase_result)

            # Update task with workflow state
            task.workflow = workflow.model_dump()
            task.current_phase = workflow.current_phase.value

            self.logger.info(
                f"Chimera workflow transitioned: {workflow.current_phase} "
                f"(iteration {iterations + 1}/{max_iterations})",
            )

            iterations += 1

        # Final status update
        if workflow.current_phase == ChimeraPhase.COMPLETE:
            task.status = TaskStatus.COMPLETED
            self.logger.info(
                f"Chimera workflow COMPLETE: {workflow.feature_description}",
            )
        elif workflow.current_phase == ChimeraPhase.FAILED:
            task.status = TaskStatus.FAILED
            self.logger.error(
                f"Chimera workflow FAILED: {workflow.error_message}",
            )
        else:
            task.status = TaskStatus.IN_PROGRESS
            self.logger.warning(
                f"Chimera workflow incomplete after {max_iterations} iterations",
            )

        return workflow

    async def execute_phase(
        self,
        task: Task,
        workflow: ChimeraWorkflow,
    ) -> dict[str, Any]:
        """Execute single workflow phase.

        Args:
            task: Orchestrator task
            workflow: Current workflow state

        Returns:
            Phase execution result

        Example:
            result = await executor.execute_phase(task, workflow)
            if result["status"] == "success":
                workflow.transition_to(next_phase, result)

        """
        # Get next action from workflow state machine
        action = workflow.get_next_action()

        if action.get("terminal"):
            return {"status": "terminal", "phase": workflow.current_phase.value}

        agent_name = action["agent"]
        action_name = action["action"]
        params = action["params"]
        timeout = action["timeout"]

        self.logger.info(
            f"Executing phase {workflow.current_phase}: "
            f"{agent_name}.{action_name}()",
        )

        # Execute agent action
        try:
            result = await self._execute_agent_action(
                agent_name=agent_name,
                action_name=action_name,
                params=params,
                timeout=timeout,
            )

            self.logger.info(
                f"Phase {workflow.current_phase} completed: "
                f"{result.get('status', 'unknown')}",
            )

            return result

        except Exception as e:
            self.logger.error(
                f"Phase {workflow.current_phase} failed: {e}",
                exc_info=True,
            )

            return {
                "status": "error",
                "error": str(e),
                "phase": workflow.current_phase.value,
            }

    async def _execute_agent_action(
        self,
        agent_name: str,
        action_name: str,
        params: dict[str, Any],
        timeout: int,
    ) -> dict[str, Any]:
        """Execute agent action with timeout.

        Args:
            agent_name: Agent identifier (e.g., "e2e-tester-agent")
            action_name: Action method name (e.g., "generate_test")
            params: Action parameters
            timeout: Timeout in seconds

        Returns:
            Action execution result

        Raises:
            TimeoutError: If action exceeds timeout
            ValueError: If agent or action not found

        """
        # Get agent from registry
        agent = self.agents.get(agent_name)

        if agent is None:
            msg = f"Agent not found: {agent_name}"
            raise ValueError(msg)

        # Get action method
        action_method = getattr(agent, action_name, None)

        if action_method is None:
            msg = f"Action not found: {agent_name}.{action_name}"
            raise ValueError(msg)

        # Execute with timeout
        try:
            result = await asyncio.wait_for(
                action_method(**params),
                timeout=timeout,
            )

            return {"status": "success", **result}

        except TimeoutError as e:
            msg = f"Action timed out after {timeout}s: {agent_name}.{action_name}"
            raise TimeoutError(msg) from e

    def _determine_next_phase(
        self,
        workflow: ChimeraWorkflow,
        phase_result: dict[str, Any],
    ) -> ChimeraPhase:
        """Determine next workflow phase based on current result.

        Args:
            workflow: Current workflow state
            phase_result: Result from current phase execution

        Returns:
            Next phase to transition to

        Example:
            next_phase = executor._determine_next_phase(workflow, result)
            # Returns on_success or on_failure based on result status

        """
        state_machine = workflow.get_state_machine()
        current_state = state_machine["states"][workflow.current_phase]

        # Check if terminal state
        if current_state.get("terminal"):
            return workflow.current_phase

        # Determine success/failure
        status = phase_result.get("status", "error")

        if status in ("success", "passed"):
            next_phase_str = current_state["on_success"]
        else:
            next_phase_str = current_state["on_failure"]

        return ChimeraPhase(next_phase_str)


async def create_and_execute_chimera_workflow(
    feature_description: str,
    target_url: str,
    staging_url: str | None = None,
    agents_registry: dict[str, Any] | None = None,
) -> ChimeraWorkflow:
    """Helper function to create and execute Chimera workflow.

    Args:
        feature_description: Natural language feature description
        target_url: Production URL for E2E testing
        staging_url: Staging URL for validation (optional)
        agents_registry: Registry of available agents

    Returns:
        Completed workflow state

    Example:
        workflow = await create_and_execute_chimera_workflow(
            feature_description="User can login with Google OAuth",
            target_url="https://myapp.dev/login",
            staging_url="https://staging.myapp.dev/login"
        )

    """
    from .chimera import create_chimera_task

    # Create task
    task_data = create_chimera_task(
        feature_description=feature_description,
        target_url=target_url,
        staging_url=staging_url,
    )

    # Convert to Task model
    task = Task(
        id="chimera-" + str(hash(feature_description))[:8],
        title=task_data["title"],
        description=task_data["description"],
        task_type=task_data["task_type"],
        priority=task_data["priority"],
        workflow=task_data["workflow"],
        payload=task_data["payload"],
        status=TaskStatus.PENDING,
    )

    # Execute workflow
    executor = ChimeraExecutor(agents_registry=agents_registry)
    workflow = await executor.execute_workflow(task)

    return workflow


__all__ = [
    "ChimeraExecutor",
    "create_and_execute_chimera_workflow",
]
