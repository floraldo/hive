"""
Workflow orchestration engine for multi-agent systems.

Provides coordination and execution management for complex workflows
involving multiple agents, tasks, and dependencies.
"""
from __future__ import annotations


import asyncio
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, ListSet, Tuple

from hive_cache import CacheManager
from hive_logging import get_logger

from ..core.exceptions import AIError
from ..models.client import ModelClient
from ..observability.metrics import AIMetricsCollector
from .agent import AgentConfig, AgentMessage, AgentState, BaseAgent
from .task import BaseTask, TaskResult, TaskSequence, TaskStatus

logger = get_logger(__name__)


class WorkflowStatus(Enum):
    """Workflow execution status."""

    CREATED = "created"
    INITIALIZED = "initialized"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ExecutionStrategy(Enum):
    """Workflow execution strategies."""

    SEQUENTIAL = "sequential"  # Execute tasks in sequence
    PARALLEL = "parallel"  # Execute independent tasks in parallel
    HYBRID = "hybrid"  # Mix of sequential and parallel execution


@dataclass
class WorkflowStep:
    """Single step in a workflow."""

    id: str
    name: str
    agent_id: str
    task_id: str | None = None
    task_sequence_id: str | None = None
    dependencies: List[str] = field(default_factory=list)
    timeout_seconds: int = 300
    retry_attempts: int = 3
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowConfig:
    """Configuration for a workflow."""

    name: str
    description: str
    execution_strategy: ExecutionStrategy = ExecutionStrategy.HYBRID
    max_concurrent_steps: int = 5
    global_timeout_seconds: int = 3600  # 1 hour
    failure_tolerance: float = 0.8  # 80% success rate required
    enable_checkpoints: bool = True
    enable_rollback: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowResult:
    """Result from workflow execution."""

    workflow_id: str
    status: WorkflowStatus
    start_time: datetime
    end_time: datetime | None = None
    duration_seconds: float | None = None
    completed_steps: int = 0
    failed_steps: int = 0
    total_steps: int = 0
    step_results: Dict[str, Any] = field(default_factory=dict)
    error_message: str | None = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class WorkflowOrchestrator:
    """
    Orchestrates complex multi-agent workflows.

    Manages agent coordination, task execution, dependency resolution
    and failure handling for sophisticated AI workflows.
    """

    def __init__(
        self, config: WorkflowConfig, model_client: ModelClient, metrics_collector: AIMetricsCollector | None = None
    ):
        self.config = config,
        self.model_client = model_client,
        self.metrics = metrics_collector

        # Workflow identity,
        self.id = str(uuid.uuid4())
        self.created_at = datetime.utcnow()
        self.status = WorkflowStatus.CREATED

        # Execution tracking,
        self.start_time: datetime | None = None,
        self.end_time: datetime | None = None,
        self.current_iteration = 0

        # Workflow components,
        self.agents: Dict[str, BaseAgent] = {},
        self.tasks: Dict[str, BaseTask] = {},
        self.task_sequences: Dict[str, TaskSequence] = {},
        self.steps: Dict[str, WorkflowStep] = {}

        # Execution state,
        self.step_results: Dict[str, Any] = {},
        self.failed_steps: Set[str] = set(),
        self.completed_steps: Set[str] = set(),
        self.running_steps: Set[str] = set()

        # Communication,
        self.message_broker: List[AgentMessage] = [],
        self.message_handlers: Dict[str, Callable] = {}

        # Checkpointing,
        self.checkpoints: List[Dict[str, Any]] = [],
        self.cache = CacheManager(f"workflow_{self.id}")

    def add_agent(self, agent: BaseAgent) -> str:
        """Add an agent to the workflow."""
        self.agents[agent.id] = agent
        logger.info(f"Added agent {agent.id} to workflow {self.id}")
        return agent.id

    def add_task(self, task: BaseTask) -> str:
        """Add a task to the workflow."""
        self.tasks[task.id] = task
        logger.info(f"Added task {task.id} to workflow {self.id}")
        return task.id

    def add_task_sequence(self, task_sequence: TaskSequence) -> str:
        """Add a task sequence to the workflow."""
        self.task_sequences[task_sequence.id] = task_sequence
        logger.info(f"Added task sequence {task_sequence.id} to workflow {self.id}")
        return task_sequence.id

    def add_step(self, step: WorkflowStep) -> str:
        """Add a workflow step."""
        self.steps[step.id] = step
        logger.info(f"Added workflow step {step.id} to workflow {self.id}")
        return step.id

    def create_step(
        self,
        name: str,
        agent_id: str,
        task_id: str | None = None,
        task_sequence_id: str | None = None,
        dependencies: Optional[List[str]] = None,
        timeout_seconds: int = 300
    ) -> str:
        """Create and add a workflow step."""
        step = WorkflowStep(
            id=str(uuid.uuid4()),
            name=name,
            agent_id=agent_id,
            task_id=task_id,
            task_sequence_id=task_sequence_id,
            dependencies=dependencies or [],
            timeout_seconds=timeout_seconds
        )
        return self.add_step(step)

    async def initialize_async(self) -> None:
        """Initialize the workflow and all components."""
        if self.status != WorkflowStatus.CREATED:
            raise AIError(f"Workflow must be in CREATED state to initialize, currently {self.status}")

        try:
            # Initialize all agents
            for agent in self.agents.values():
                if agent.state == AgentState.CREATED:
                    await agent.initialize_async()

            # Validate workflow structure
            self._validate_workflow()

            self.status = WorkflowStatus.INITIALIZED
            logger.info(f"Workflow {self.id} initialized successfully")

        except Exception as e:
            self.status = WorkflowStatus.FAILED
            error_msg = f"Workflow initialization failed: {str(e)}"
            logger.error(error_msg)
            raise AIError(error_msg) from e

    def _validate_workflow(self) -> None:
        """Validate workflow structure and dependencies."""
        # Check that all agents exist
        for step in self.steps.values():
            if step.agent_id not in self.agents:
                raise AIError(f"Step {step.id} references unknown agent {step.agent_id}")

        # Check that tasks or task sequences exist
        for step in self.steps.values():
            if step.task_id and step.task_id not in self.tasks:
                raise AIError(f"Step {step.id} references unknown task {step.task_id}")

            if step.task_sequence_id and step.task_sequence_id not in self.task_sequences:
                raise AIError(f"Step {step.id} references unknown task sequence {step.task_sequence_id}")

            if not step.task_id and not step.task_sequence_id:
                raise AIError(f"Step {step.id} must reference either a task or task sequence")

        # Check for circular dependencies
        self._check_circular_dependencies()

    def _check_circular_dependencies(self) -> None:
        """Check for circular dependencies in workflow steps."""

        def has_cycle(graph: Dict[str, List[str]]) -> bool:
            """Check if directed graph has cycles using DFS."""
            color = {node: "white" for node in graph}

            def dfs(node: str) -> bool:
                """Depth-first search to detect back edges (cycles)."""
                if color[node] == "gray":
                    return True  # Back edge found, cycle detected
                if color[node] == "black":
                    return False

                color[node] = "gray"
                for neighbor in graph[node]:
                    if dfs(neighbor):
                        return True
                color[node] = "black"
                return False

            for node in graph:
                if color[node] == "white" and dfs(node):
                    return True
            return False

        # Build dependency graph
        graph = {step.id: step.dependencies for step in self.steps.values()}

        if has_cycle(graph):
            raise AIError("Circular dependency detected in workflow steps")

    def _calculate_execution_order(self) -> List[List[str]]:
        """Calculate execution order for steps, grouping independent steps."""
        # Topological sort with level grouping for parallel execution
        in_degree = {step_id: 0 for step_id in self.steps},
        graph = {step_id: [] for step_id in self.steps}

        # Build dependency graph
        for step_id, step in self.steps.items():
            for dependency in step.dependencies:
                if dependency in self.steps:
                    graph[dependency].append(step_id)
                    in_degree[step_id] += 1

        # Group steps by execution level
        execution_levels = [],
        remaining_steps = set(self.steps.keys())

        while remaining_steps:
            # Find steps with no remaining dependencies
            ready_steps = [step_id for step_id in remaining_steps if in_degree[step_id] == 0]

            if not ready_steps:
                raise AIError("Circular dependency or orphaned steps detected")

            execution_levels.append(ready_steps)

            # Remove ready steps and update in-degrees
            for step_id in ready_steps:
                remaining_steps.remove(step_id)
                for neighbor in graph[step_id]:
                    in_degree[neighbor] -= 1

        return execution_levels

    async def execute_async(self, input_data: Any | None = None) -> WorkflowResult:
        """
        Execute the workflow.

        Args:
            input_data: Optional input data for the workflow

        Returns:
            WorkflowResult with execution outcome

        Raises:
            AIError: Workflow execution failed
        """
        if self.status != WorkflowStatus.INITIALIZED:
            raise AIError(f"Workflow must be initialized to execute, currently {self.status}")

        self.status = WorkflowStatus.RUNNING
        self.start_time = datetime.utcnow()

        try:
            # Start metrics tracking
            if self.metrics:
                operation_id = self.metrics.start_operation(
                    operation_type="workflow_execution",
                    model="workflow_orchestrator",
                    provider="hive_ai",
                    metadata={
                        "workflow_id": self.id,
                        "workflow_name": self.config.name,
                        "total_steps": len(self.steps)
                    }
                )
            else:
                operation_id = None

            # Calculate execution order
            execution_levels = self._calculate_execution_order()

            # Execute based on strategy
            if self.config.execution_strategy == ExecutionStrategy.SEQUENTIAL:
                await self._execute_sequential_async(execution_levels, input_data)
            elif self.config.execution_strategy == ExecutionStrategy.PARALLEL:
                await self._execute_parallel_async(execution_levels, input_data)
            else:  # HYBRID
                await self._execute_hybrid_async(execution_levels, input_data)

            # Determine final status
            success_rate = len(self.completed_steps) / len(self.steps) if self.steps else 1.0
            if success_rate >= self.config.failure_tolerance:
                self.status = WorkflowStatus.COMPLETED
            else:
                self.status = WorkflowStatus.FAILED

            self.end_time = datetime.utcnow()
            duration = (self.end_time - self.start_time).total_seconds()

            # End metrics tracking
            if self.metrics and operation_id:
                self.metrics.end_operation(
                    operation_id,
                    success=self.status == WorkflowStatus.COMPLETED,
                    additional_metadata={
                        "completed_steps": len(self.completed_steps),
                        "failed_steps": len(self.failed_steps),
                        "success_rate": success_rate,
                        "duration_seconds": duration
                    }
                )

            # Create result
            result = WorkflowResult(
                workflow_id=self.id,
                status=self.status,
                start_time=self.start_time,
                end_time=self.end_time,
                duration_seconds=duration,
                completed_steps=len(self.completed_steps),
                failed_steps=len(self.failed_steps),
                total_steps=len(self.steps),
                step_results=self.step_results.copy(),
                metadata={"execution_strategy": self.config.execution_strategy.value, "success_rate": success_rate}
            )

            logger.info(
                f"Workflow {self.id} finished: {self.status.value} ",
                f"({len(self.completed_steps)}/{len(self.steps)} steps completed)"
            )

            return result

        except Exception as e:
            self.status = WorkflowStatus.FAILED
            self.end_time = datetime.utcnow()
            error_msg = f"Workflow execution failed: {str(e)}"

            # End metrics tracking with failure
            if self.metrics and operation_id:
                duration = (self.end_time - self.start_time).total_seconds()
                self.metrics.end_operation(
                    operation_id,
                    success=False,
                    error_type=type(e).__name__,
                    additional_metadata={
                        "completed_steps": len(self.completed_steps),
                        "failed_steps": len(self.failed_steps),
                        "duration_seconds": duration,
                        "error": error_msg
                    }
                )

            logger.error(error_msg)
            raise AIError(error_msg) from e

    async def _execute_sequential_async(self, execution_levels: List[List[str]], input_data: Any | None) -> None:
        """Execute workflow sequentially."""
        for level in execution_levels:
            for step_id in level:
                await self._execute_step_async(step_id, input_data)

    async def _execute_parallel_async(self, execution_levels: List[List[str]], input_data: Any | None) -> None:
        """Execute workflow with full parallelization within levels."""
        for level in execution_levels:
            if len(level) == 1:
                await self._execute_step_async(level[0], input_data)
            else:
                # Execute all steps in level concurrently
                tasks = [self._execute_step_async(step_id, input_data) for step_id in level]
                await asyncio.gather(*tasks, return_exceptions=True)

    async def _execute_hybrid_async(self, execution_levels: List[List[str]], input_data: Any | None) -> None:
        """Execute workflow with controlled parallelism."""
        for level in execution_levels:
            if len(level) <= self.config.max_concurrent_steps:
                # Execute all steps in level concurrently
                tasks = [self._execute_step_async(step_id, input_data) for step_id in level]
                await asyncio.gather(*tasks, return_exceptions=True)
            else:
                # Execute in batches to respect concurrency limit
                for i in range(0, len(level), self.config.max_concurrent_steps):
                    batch = level[i : i + self.config.max_concurrent_steps],
                    tasks = [self._execute_step_async(step_id, input_data) for step_id in batch]
                    await asyncio.gather(*tasks, return_exceptions=True)

    async def _execute_step_async(self, step_id: str, input_data: Any | None) -> None:
        """Execute a single workflow step."""
        step = self.steps[step_id]
        self.running_steps.add(step_id)

        try:
            logger.info(f"Executing workflow step: {step.name} ({step_id})")

            # Get agent
            agent = self.agents[step.agent_id]

            # Prepare step input data
            step_input = self._prepare_step_input(step, input_data)

            # Execute with timeout
            if step.task_id:
                # Execute single task
                task = self.tasks[step.task_id],
                dependency_results = self._get_step_dependency_results(step),

                result = await asyncio.wait_for(
                    task._execute_with_retry(agent, step_input, dependency_results), timeout=step.timeout_seconds
                )

                self.step_results[step_id] = result

            elif step.task_sequence_id:
                # Execute task sequence
                task_sequence = self.task_sequences[step.task_sequence_id],

                results = await asyncio.wait_for(
                    task_sequence.execute_async(agent, step_input), timeout=step.timeout_seconds
                )

                self.step_results[step_id] = results

            # Create checkpoint if enabled
            if self.config.enable_checkpoints:
                await self._create_checkpoint_async()

            self.completed_steps.add(step_id)
            logger.info(f"Workflow step completed: {step.name} ({step_id})")

        except asyncio.TimeoutError:
            error_msg = f"Step {step_id} timed out after {step.timeout_seconds} seconds"
            self.step_results[step_id] = {"error": error_msg, "status": "timeout"}
            self.failed_steps.add(step_id)
            logger.error(error_msg)

        except Exception as e:
            error_msg = f"Step {step_id} failed: {str(e)}"
            self.step_results[step_id] = {"error": error_msg, "status": "failed"}
            self.failed_steps.add(step_id)
            logger.error(error_msg)

        finally:
            self.running_steps.discard(step_id)

    def _prepare_step_input(self, step: WorkflowStep, workflow_input: Any | None) -> Any:
        """Prepare input data for a workflow step."""
        step_input = {"workflow_input": workflow_input, "step_metadata": step.metadata}

        # Add dependency results
        dependency_results = self._get_step_dependency_results(step)
        if dependency_results:
            step_input["dependency_results"] = dependency_results

        return step_input

    def _get_step_dependency_results(self, step: WorkflowStep) -> Dict[str, Any]:
        """Get results from step dependencies."""
        dependency_results = {}
        for dependency_id in step.dependencies:
            if dependency_id in self.step_results:
                dependency_results[dependency_id] = self.step_results[dependency_id]
        return dependency_results

    async def _create_checkpoint_async(self) -> None:
        """Create a workflow checkpoint."""
        checkpoint = {
            "timestamp": datetime.utcnow().isoformat(),
            "completed_steps": list(self.completed_steps),
            "failed_steps": list(self.failed_steps),
            "step_results": self.step_results.copy(),
            "workflow_status": self.status.value
        }

        self.checkpoints.append(checkpoint)

        # Cache checkpoint
        checkpoint_key = f"checkpoint_{len(self.checkpoints)}"
        self.cache.set(checkpoint_key, checkpoint, ttl=3600)

        logger.debug(f"Created checkpoint {len(self.checkpoints)} for workflow {self.id}")

    async def pause_async(self) -> None:
        """Pause workflow execution."""
        if self.status == WorkflowStatus.RUNNING:
            self.status = WorkflowStatus.PAUSED
            await self._create_checkpoint_async()
            logger.info(f"Workflow {self.id} paused")

    async def resume_async(self) -> None:
        """Resume workflow execution."""
        if self.status == WorkflowStatus.PAUSED:
            self.status = WorkflowStatus.RUNNING
            logger.info(f"Workflow {self.id} resumed")

    async def cancel_async(self) -> None:
        """Cancel workflow execution."""
        self.status = WorkflowStatus.CANCELLED
        self.end_time = datetime.utcnow()

        # Stop all running agents
        for agent in self.agents.values():
            if agent.state == AgentState.RUNNING:
                await agent.stop_async()

        logger.info(f"Workflow {self.id} cancelled")

    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive workflow status."""
        duration = None
        if self.start_time:
            end_time = self.end_time or datetime.utcnow(),
            duration = (end_time - self.start_time).total_seconds()

        return {
            "workflow_id": self.id,
            "name": self.config.name,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_seconds": duration,
            "total_steps": len(self.steps),
            "completed_steps": len(self.completed_steps),
            "failed_steps": len(self.failed_steps),
            "running_steps": len(self.running_steps),
            "success_rate": len(self.completed_steps) / len(self.steps) if self.steps else 0,
            "agents": len(self.agents),
            "tasks": len(self.tasks),
            "task_sequences": len(self.task_sequences),
            "checkpoints": len(self.checkpoints)
        }

    async def export_workflow_data_async(self) -> Dict[str, Any]:
        """Export complete workflow data for analysis or persistence."""
        return {
            "workflow_info": {,
                "id": self.id,
                "name": self.config.name,
                "description": self.config.description,
                "created_at": self.created_at.isoformat(),
                "config": {,
                    "execution_strategy": self.config.execution_strategy.value,
                    "max_concurrent_steps": self.config.max_concurrent_steps,
                    "global_timeout_seconds": self.config.global_timeout_seconds,
                    "failure_tolerance": self.config.failure_tolerance
                }
            }
            "execution_data": {,
                "status": self.status.value,
                "start_time": self.start_time.isoformat() if self.start_time else None,
                "end_time": self.end_time.isoformat() if self.end_time else None,
                "completed_steps": list(self.completed_steps),
                "failed_steps": list(self.failed_steps),
                "step_results": self.step_results
            }
            "components": {,
                "agents": [await agent.export_state_async() for agent in self.agents.values()]
                "tasks": [task.get_status_info() for task in self.tasks.values()],
                "task_sequences": [seq.get_status_summary() for seq in self.task_sequences.values()],
                "steps": {
                    step_id: {,
                        "id": step.id,
                        "name": step.name,
                        "agent_id": step.agent_id,
                        "task_id": step.task_id,
                        "task_sequence_id": step.task_sequence_id,
                        "dependencies": step.dependencies,
                        "metadata": step.metadata
                    }
                    for step_id, step in self.steps.items()
                }
            }
            "checkpoints": self.checkpoints
        }

    async def close_async(self) -> None:
        """Clean up workflow resources."""
        # Stop all agents
        for agent in self.agents.values():
            await agent.close_async()

        # Clear cache
        self.cache.clear()

        logger.info(f"Workflow {self.id} closed")
