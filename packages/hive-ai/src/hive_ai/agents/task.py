"""
Task definition and execution framework for AI agents.

Provides structured task definitions, execution patterns
and coordination mechanisms for complex workflows.
"""
from __future__ import annotations


import asyncio
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, ListType

from hive_logging import get_logger

from ..core.exceptions import AIError
from .agent import AgentConfig, AgentState, BaseAgent

logger = get_logger(__name__)


class TaskStatus(Enum):
    """Task execution status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    WAITING = "waiting"


class TaskPriority(Enum):
    """Task priority levels."""

    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class TaskResult:
    """Result from task execution."""

    task_id: str
    status: TaskStatus
    result: Any
    error: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    duration_seconds: float | None = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskDependency:
    """Dependency between tasks."""

    task_id: str
    dependency_type: str = "completion"  # completion, output, custom
    condition: Optional[Callable[[TaskResult], bool]] = None


@dataclass
class TaskConfig:
    """Configuration for a task."""

    name: str
    description: str
    priority: TaskPriority = TaskPriority.NORMAL
    timeout_seconds: int = 300
    retry_attempts: int = 3
    retry_delay_seconds: int = 5
    dependencies: List[TaskDependency] = field(default_factory=list)
    required_tools: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseTask(ABC):
    """
    Base class for AI tasks.

    Defines the interface and common functionality for tasks
    that can be executed by agents or workflow engines.
    """

    def __init__(self, config: TaskConfig) -> None:
        self.config = config
        self.id = str(uuid.uuid4())
        self.created_at = datetime.utcnow()
        self.status = TaskStatus.PENDING

        # Execution tracking
        self.start_time: datetime | None = None
        self.end_time: datetime | None = None
        self.attempt_count = 0
        self.result: TaskResult | None = None

        # Dependencies and outputs
        self.dependency_results: Dict[str, TaskResult] = {}
        self.output_data: Any | None = None

    @abstractmethod
    async def execute_async(
        self,
        agent: BaseAgent,
        input_data: Any | None = None,
        dependency_results: Optional[Dict[str, TaskResult]] = None
    ) -> TaskResult:
        """
        Execute the task using the provided agent.

        Args:
            agent: Agent to execute the task,
            input_data: Input data for the task,
            dependency_results: Results from dependency tasks

        Returns:
            TaskResult with execution outcome

        Raises:
            AIError: Task execution failed,
        """
        pass

    def can_execute(self, completed_tasks: Dict[str, TaskResult]) -> bool:
        """
        Check if task dependencies are satisfied.

        Args:
            completed_tasks: Dictionary of completed task results

        Returns:
            True if task can be executed
        """
        for dependency in self.config.dependencies:
            if dependency.task_id not in completed_tasks:
                return False

            task_result = completed_tasks[dependency.task_id]

            # Check dependency condition if specified
            if dependency.condition:
                if not dependency.condition(task_result):
                    return False
            else:
                # Default: dependency must be completed successfully
                if task_result.status != TaskStatus.COMPLETED:
                    return False

        return True

    def get_dependency_results(self, completed_tasks: Dict[str, TaskResult]) -> Dict[str, TaskResult]:
        """Get results from dependency tasks."""
        dependency_results = {}
        for dependency in self.config.dependencies:
            if dependency.task_id in completed_tasks:
                dependency_results[dependency.task_id] = completed_tasks[dependency.task_id]
        return dependency_results

    async def _execute_with_retry_async(
        self,
        agent: BaseAgent,
        input_data: Any | None = None,
        dependency_results: Optional[Dict[str, TaskResult]] = None
    ) -> TaskResult:
        """Execute task with retry logic."""
        last_error = None

        for attempt in range(self.config.retry_attempts):
            self.attempt_count = attempt + 1

            try:
                self.status = TaskStatus.RUNNING
                self.start_time = datetime.utcnow()

                # Execute the task implementation
                result = await self.execute_async(agent, input_data, dependency_results)

                self.end_time = datetime.utcnow()
                self.status = result.status
                self.result = result

                if result.status == TaskStatus.COMPLETED:
                    logger.info(f"Task {self.id} completed successfully on attempt {attempt + 1}")
                    return result

            except Exception as e:
                last_error = str(e)
                logger.warning(f"Task {self.id} failed on attempt {attempt + 1}: {e}")

                if attempt < self.config.retry_attempts - 1:
                    await asyncio.sleep(self.config.retry_delay_seconds)

        # All attempts failed
        self.end_time = datetime.utcnow()
        self.status = TaskStatus.FAILED

        duration = (self.end_time - self.start_time).total_seconds() if self.start_time else 0

        self.result = TaskResult(
            task_id=self.id,
            status=TaskStatus.FAILED,
            result=None,
            error=f"Task failed after {self.config.retry_attempts} attempts. Last error: {last_error}",
            start_time=self.start_time,
            end_time=self.end_time,
            duration_seconds=duration
        )

        return self.result

    def get_status_info(self) -> Dict[str, Any]:
        """Get detailed status information."""
        duration = None
        if self.start_time:
            end_time = self.end_time or datetime.utcnow()
            duration = (end_time - self.start_time).total_seconds()

        return {
            "id": self.id,
            "name": self.config.name,
            "status": self.status.value,
            "priority": self.config.priority.value,
            "attempt_count": self.attempt_count,
            "max_attempts": self.config.retry_attempts,
            "created_at": self.created_at.isoformat(),
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_seconds": duration,
            "dependencies": [dep.task_id for dep in self.config.dependencies],
            "required_tools": self.config.required_tools
        }


class PromptTask(BaseTask):
    """
    Task that executes a prompt using an agent.

    Simple task type for prompt-based operations.
    """

    def __init__(self, config: TaskConfig, prompt: str, expected_output_type: str = "text") -> None:
        super().__init__(config)
        self.prompt = prompt
        self.expected_output_type = expected_output_type

    async def execute_async(
        self,
        agent: BaseAgent,
        input_data: Any | None = None,
        dependency_results: Optional[Dict[str, TaskResult]] = None
    ) -> TaskResult:
        """Execute the prompt task."""
        try:
            # Build final prompt with input data and dependencies
            final_prompt = self._build_prompt(input_data, dependency_results)

            # Execute using agent's model
            response = await agent.model_client.generate_async(
                final_prompt,
                model=agent.config.model,
                temperature=agent.config.temperature,
                max_tokens=agent.config.max_tokens
            )

            # Process output based on expected type
            processed_output = self._process_output(response.content)

            duration = (datetime.utcnow() - self.start_time).total_seconds() if self.start_time else 0

            return TaskResult(
                task_id=self.id,
                status=TaskStatus.COMPLETED,
                result=processed_output,
                start_time=self.start_time,
                end_time=datetime.utcnow(),
                duration_seconds=duration,
                metadata={"tokens_used": response.tokens_used, "cost": response.cost, "model": response.model}
            )

        except Exception as e:
            duration = (datetime.utcnow() - self.start_time).total_seconds() if self.start_time else 0

            return TaskResult(
                task_id=self.id,
                status=TaskStatus.FAILED,
                result=None,
                error=str(e),
                start_time=self.start_time,
                end_time=datetime.utcnow(),
                duration_seconds=duration
            )

    def _build_prompt(self, input_data: Any | None, dependency_results: Optional[Dict[str, TaskResult]]) -> str:
        """Build the final prompt with input data and dependency results."""
        prompt_parts = [self.prompt]

        if input_data:
            prompt_parts.append(f"\nInput Data: {input_data}")

        if dependency_results:
            prompt_parts.append("\nPrevious Results:")
            for task_id, result in dependency_results.items():
                prompt_parts.append(f"- {task_id}: {result.result}")

        return "\n".join(prompt_parts)

    def _process_output(self, output: str) -> Any:
        """Process output based on expected type."""
        if self.expected_output_type == "json":
            try:
                import json

                return json.loads(output)
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse JSON output for task {self.id}")
                return output

        elif self.expected_output_type == "number":
            try:
                return float(output.strip())
            except ValueError:
                logger.warning(f"Failed to parse number output for task {self.id}")
                return output

        elif self.expected_output_type == "boolean":
            output_lower = output.strip().lower()
            if output_lower in ["true", "yes", "1", "correct"]:
                return True
            elif output_lower in ["false", "no", "0", "incorrect"]:
                return False
            else:
                logger.warning(f"Failed to parse boolean output for task {self.id}")
                return output

        # Default: return as text
        return output.strip()


class ToolTask(BaseTask):
    """
    Task that executes using agent tools.

    Allows for more complex operations using the agent's toolkit.
    """

    def __init__(self, config: TaskConfig, tool_sequence: List[Dict[str, Any]]) -> None:
        super().__init__(config)
        self.tool_sequence = tool_sequence

    async def execute_async(
        self,
        agent: BaseAgent,
        input_data: Any | None = None,
        dependency_results: Optional[Dict[str, TaskResult]] = None
    ) -> TaskResult:
        """Execute the tool sequence."""
        try:
            results = []
            context = {"input_data": input_data, "dependency_results": dependency_results, "intermediate_results": []}

            for step_idx, tool_call in enumerate(self.tool_sequence):
                tool_name = tool_call["tool"]
                parameters = tool_call.get("parameters", {})

                # Process parameters with context substitution
                processed_params = self._process_parameters(parameters, context)

                # Execute tool
                result = await agent.call_tool_async(tool_name, **processed_params)
                results.append(result)

                # Update context
                context["intermediate_results"].append({"step": step_idx, "tool": tool_name, "result": result})

                logger.debug(f"Task {self.id} completed tool step {step_idx + 1}: {tool_name}")

            duration = (datetime.utcnow() - self.start_time).total_seconds() if self.start_time else 0

            return TaskResult(
                task_id=self.id,
                status=TaskStatus.COMPLETED,
                result=results,
                start_time=self.start_time,
                end_time=datetime.utcnow(),
                duration_seconds=duration,
                metadata={"tools_used": [call["tool"] for call in self.tool_sequence], "steps_completed": len(results)}
            )

        except Exception as e:
            duration = (datetime.utcnow() - self.start_time).total_seconds() if self.start_time else 0

            return TaskResult(
                task_id=self.id,
                status=TaskStatus.FAILED,
                result=None,
                error=str(e),
                start_time=self.start_time,
                end_time=datetime.utcnow(),
                duration_seconds=duration
            )

    def _process_parameters(self, parameters: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Process parameters with context substitution."""
        processed = {}

        for key, value in parameters.items():
            if isinstance(value, str) and value.startswith("$"):
                # Context substitution
                context_key = value[1:]  # Remove $
                if context_key in context:
                    processed[key] = context[context_key]
                else:
                    processed[key] = value  # Keep original if not found
            else:
                processed[key] = value

        return processed


class TaskSequence:
    """
    Sequence of tasks with dependency management.

    Manages execution order and dependency resolution for multiple tasks.
    """

    def __init__(self, name: str, tasks: List[BaseTask]) -> None:
        self.name = name
        self.id = str(uuid.uuid4())
        self.tasks = {task.id: task for task in tasks}
        self.execution_order: List[str] = []
        self.completed_tasks: Dict[str, TaskResult] = {}

        # Calculate execution order based on dependencies
        self._calculate_execution_order()

    def _calculate_execution_order(self) -> None:
        """Calculate the order in which tasks should be executed."""
        # Topological sort based on dependencies
        in_degree = {task_id: 0 for task_id in self.tasks}
        graph = {task_id: [] for task_id in self.tasks}

        # Build dependency graph
        for task_id, task in self.tasks.items():
            for dependency in task.config.dependencies:
                if dependency.task_id in self.tasks:
                    graph[dependency.task_id].append(task_id)
                    in_degree[task_id] += 1

        # Topological sort
        queue = [task_id for task_id, degree in in_degree.items() if degree == 0]
        execution_order = []

        while queue:
            # Sort by priority
            queue.sort(key=lambda tid: self.tasks[tid].config.priority.value, reverse=True)
            current = queue.pop(0)
            execution_order.append(current)

            for neighbor in graph[current]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(execution_order) != len(self.tasks):
            raise AIError("Circular dependency detected in task sequence")

        self.execution_order = execution_order
        logger.info(f"Task sequence {self.name}: execution order calculated")

    async def execute_async(self, agent: BaseAgent, input_data: Any | None = None) -> Dict[str, TaskResult]:
        """
        Execute all tasks in the sequence.

        Args:
            agent: Agent to execute tasks
            input_data: Input data for the sequence

        Returns:
            Dictionary of task results

        Raises:
            AIError: Sequence execution failed
        """
        logger.info(f"Starting task sequence {self.name} with {len(self.tasks)} tasks")

        for task_id in self.execution_order:
            task = self.tasks[task_id]

            # Check if task can be executed
            if not task.can_execute(self.completed_tasks):
                raise AIError(f"Task {task_id} dependencies not satisfied")

            # Get dependency results
            dependency_results = task.get_dependency_results(self.completed_tasks)

            logger.info(f"Executing task: {task.config.name} ({task_id})")

            # Execute task with timeout
            try:
                result = await asyncio.wait_for(
                    task._execute_with_retry_async(agent, input_data, dependency_results),
                    timeout=task.config.timeout_seconds
                )

                self.completed_tasks[task_id] = result

                if result.status != TaskStatus.COMPLETED:
                    logger.error(f"Task {task_id} failed: {result.error}")
                    # Decide whether to continue or stop
                    # For now, we'll stop on any failure
                    break

            except asyncio.TimeoutError:
                timeout_result = TaskResult(
                    task_id=task_id,
                    status=TaskStatus.FAILED,
                    result=None,
                    error=f"Task timed out after {task.config.timeout_seconds} seconds",
                    start_time=task.start_time,
                    end_time=datetime.utcnow()
                )
                self.completed_tasks[task_id] = timeout_result,
                logger.error(f"Task {task_id} timed out")
                break

        logger.info(f"Task sequence {self.name} completed: {len(self.completed_tasks)} tasks")
        return self.completed_tasks

    def get_status_summary(self) -> Dict[str, Any]:
        """Get summary of sequence execution status."""
        completed_count = sum(1 for result in self.completed_tasks.values() if result.status == TaskStatus.COMPLETED)
        failed_count = sum(1 for result in self.completed_tasks.values() if result.status == TaskStatus.FAILED)

        return {
            "sequence_id": self.id,
            "sequence_name": self.name,
            "total_tasks": len(self.tasks),
            "completed_tasks": completed_count,
            "failed_tasks": failed_count,
            "remaining_tasks": len(self.tasks) - len(self.completed_tasks),
            "execution_order": self.execution_order,
            "task_status": {task_id: result.status.value for task_id, result in self.completed_tasks.items()}
        }


class TaskBuilder:
    """
    Builder for creating common task types easily.

    Provides convenience methods for creating standard task configurations.
    """

    @staticmethod
    def create_prompt_task(
        name: str,
        prompt: str,
        description: str = "",
        priority: TaskPriority = TaskPriority.NORMAL,
        expected_output_type: str = "text",
        dependencies: Optional[List[str]] = None
    ) -> PromptTask:
        """Create a prompt-based task."""
        task_deps = []
        if dependencies:
            task_deps = [TaskDependency(task_id=dep_id) for dep_id in dependencies]

        config = TaskConfig(
            name=name,
            description=description or f"Execute prompt: {prompt[:50]}...",
            priority=priority,
            dependencies=task_deps
        )

        return PromptTask(config, prompt, expected_output_type)

    @staticmethod,
    def create_tool_task(
        name: str,
        tool_sequence: List[Dict[str, Any]],
        description: str = "",
        priority: TaskPriority = TaskPriority.NORMAL,
        dependencies: Optional[List[str]] = None
    ) -> ToolTask:
        """Create a tool-based task."""
        task_deps = []
        if dependencies:
            task_deps = [TaskDependency(task_id=dep_id) for dep_id in dependencies]

        # Extract required tools,
        required_tools = list(set(call["tool"] for call in tool_sequence))

        config = TaskConfig(
            name=name,
            description=description or f"Execute tool sequence: {required_tools}",
            priority=priority,
            dependencies=task_deps,
            required_tools=required_tools
        )

        return ToolTask(config, tool_sequence)

    @staticmethod,
    def create_analysis_task(
        name: str, analysis_prompt: str, data_source: str, dependencies: Optional[List[str]] = None
    ) -> PromptTask:
        """Create a data analysis task."""
        full_prompt = f""",
Analyze the following data: {data_source}

Analysis Instructions:
{analysis_prompt}

Please provide:
1. Key findings,
2. Insights and patterns,
3. Recommendations based on the analysis

Analysis:
"""

        return TaskBuilder.create_prompt_task(
            name=name,
            prompt=full_prompt,
            description=f"Data analysis task: {analysis_prompt[:50]}...",
            priority=TaskPriority.NORMAL,
            expected_output_type="text",
            dependencies=dependencies
        )
