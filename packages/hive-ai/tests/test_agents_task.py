"""Tests for hive_ai.agents.task module."""
from __future__ import annotations

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest

from hive_ai.agents.agent import AgentConfig, BaseAgent, SimpleTaskAgent
from hive_ai.agents.task import (
    BaseTask,
    PromptTask,
    TaskBuilder,
    TaskConfig,
    TaskDependency,
    TaskPriority,
    TaskResult,
    TaskSequence,
    TaskStatus,
    ToolTask,
)
from hive_ai.core.exceptions import AIError


class TestTaskStatus:
    """Test cases for TaskStatus enum."""

    def test_task_status_values(self):
        """Test TaskStatus enum has all expected values."""
        expected_statuses = ["PENDING", "RUNNING", "COMPLETED", "FAILED", "CANCELLED", "WAITING"]
        actual_statuses = [status.name for status in TaskStatus]
        for expected in expected_statuses:
            assert expected in actual_statuses


class TestTaskPriority:
    """Test cases for TaskPriority enum."""

    def test_task_priority_values(self):
        """Test TaskPriority enum has correct priority levels."""
        assert TaskPriority.LOW.value == 1
        assert TaskPriority.NORMAL.value == 2
        assert TaskPriority.HIGH.value == 3
        assert TaskPriority.CRITICAL.value == 4

    def test_task_priority_ordering(self):
        """Test TaskPriority enum values can be compared."""
        assert TaskPriority.LOW.value < TaskPriority.NORMAL.value
        assert TaskPriority.NORMAL.value < TaskPriority.HIGH.value
        assert TaskPriority.HIGH.value < TaskPriority.CRITICAL.value


class TestTaskResult:
    """Test cases for TaskResult dataclass."""

    def test_task_result_creation_minimal(self):
        """Test creating TaskResult with minimal fields."""
        result = TaskResult(
            task_id="task-123",
            status=TaskStatus.COMPLETED,
            result={"output": "success"},
        )
        assert result.task_id == "task-123"
        assert result.status == TaskStatus.COMPLETED
        assert result.result == {"output": "success"}
        assert result.error is None
        assert result.start_time is None
        assert result.end_time is None
        assert result.duration_seconds is None
        assert result.metadata == {}

    def test_task_result_creation_complete(self):
        """Test creating TaskResult with all fields."""
        start_time = datetime.utcnow()
        end_time = datetime.utcnow()
        metadata = {"tokens": 150, "cost": 0.002}

        result = TaskResult(
            task_id="task-456",
            status=TaskStatus.FAILED,
            result=None,
            error="Execution failed",
            start_time=start_time,
            end_time=end_time,
            duration_seconds=3.5,
            metadata=metadata,
        )
        assert result.error == "Execution failed"
        assert result.start_time == start_time
        assert result.end_time == end_time
        assert result.duration_seconds == 3.5
        assert result.metadata == metadata


class TestTaskDependency:
    """Test cases for TaskDependency dataclass."""

    def test_task_dependency_creation_basic(self):
        """Test creating TaskDependency with required fields."""
        dependency = TaskDependency(task_id="task-1")
        assert dependency.task_id == "task-1"
        assert dependency.dependency_type == "completion"
        assert dependency.condition is None

    def test_task_dependency_with_condition(self):
        """Test creating TaskDependency with custom condition."""

        def custom_condition(result: TaskResult) -> bool:
            return result.result is not None

        dependency = TaskDependency(
            task_id="task-2",
            dependency_type="output",
            condition=custom_condition,
        )
        assert dependency.task_id == "task-2"
        assert dependency.dependency_type == "output"
        assert dependency.condition == custom_condition


class TestTaskConfig:
    """Test cases for TaskConfig dataclass."""

    def test_task_config_creation_minimal(self):
        """Test creating TaskConfig with required fields."""
        config = TaskConfig(
            name="test_task",
            description="Test task description",
        )
        assert config.name == "test_task"
        assert config.description == "Test task description"
        assert config.priority == TaskPriority.NORMAL
        assert config.timeout_seconds == 300
        assert config.retry_attempts == 3
        assert config.retry_delay_seconds == 5
        assert config.dependencies == []
        assert config.required_tools == []
        assert config.metadata == {}

    def test_task_config_creation_complete(self):
        """Test creating TaskConfig with all fields."""
        dependencies = [TaskDependency(task_id="dep-1")]
        required_tools = ["tool1", "tool2"]
        metadata = {"version": "1.0"}

        config = TaskConfig(
            name="complex_task",
            description="Complex task",
            priority=TaskPriority.HIGH,
            timeout_seconds=600,
            retry_attempts=5,
            retry_delay_seconds=10,
            dependencies=dependencies,
            required_tools=required_tools,
            metadata=metadata,
        )
        assert config.priority == TaskPriority.HIGH
        assert config.timeout_seconds == 600
        assert config.retry_attempts == 5
        assert config.retry_delay_seconds == 10
        assert len(config.dependencies) == 1
        assert config.required_tools == required_tools
        assert config.metadata == metadata


class TestPromptTask:
    """Test cases for PromptTask."""

    @pytest.fixture
    def mock_agent(self):
        """Create a mock agent for testing."""
        agent = Mock(spec=SimpleTaskAgent)
        agent.config = Mock(model="claude-3-sonnet", temperature=0.7, max_tokens=4096)
        agent.model_client = Mock()
        agent.model_client.generate_async = AsyncMock(
            return_value=Mock(
                content="Test response",
                tokens_used=50,
                cost=0.001,
                model="claude-3-sonnet",
            )
        )
        return agent

    @pytest.fixture
    def basic_task_config(self):
        """Create a basic TaskConfig."""
        return TaskConfig(
            name="prompt_task",
            description="Test prompt task",
        )

    def test_prompt_task_creation(self, basic_task_config):
        """Test creating PromptTask."""
        task = PromptTask(
            config=basic_task_config,
            prompt="Analyze this data",
        )
        assert task.prompt == "Analyze this data"
        assert task.expected_output_type == "text"
        assert task.status == TaskStatus.PENDING
        assert task.id is not None

    def test_prompt_task_creation_with_output_type(self, basic_task_config):
        """Test creating PromptTask with specific output type."""
        task = PromptTask(
            config=basic_task_config,
            prompt="Calculate sum",
            expected_output_type="number",
        )
        assert task.expected_output_type == "number"

    @pytest.mark.asyncio
    async def test_prompt_task_execute_basic(self, basic_task_config, mock_agent):
        """Test executing PromptTask with basic setup."""
        task = PromptTask(
            config=basic_task_config,
            prompt="Test prompt",
        )
        task.start_time = datetime.utcnow()

        result = await task.execute_async(mock_agent)

        assert result.status == TaskStatus.COMPLETED
        assert result.task_id == task.id
        assert result.result == "Test response"
        assert "tokens_used" in result.metadata
        assert "cost" in result.metadata

    @pytest.mark.asyncio
    async def test_prompt_task_execute_with_input_data(self, basic_task_config, mock_agent):
        """Test executing PromptTask with input data."""
        task = PromptTask(
            config=basic_task_config,
            prompt="Process data",
        )
        task.start_time = datetime.utcnow()

        result = await task.execute_async(mock_agent, input_data="Sample input")

        assert result.status == TaskStatus.COMPLETED
        mock_agent.model_client.generate_async.assert_called_once()

    @pytest.mark.asyncio
    async def test_prompt_task_execute_with_dependencies(self, basic_task_config, mock_agent):
        """Test executing PromptTask with dependency results."""
        task = PromptTask(
            config=basic_task_config,
            prompt="Summarize results",
        )
        task.start_time = datetime.utcnow()

        dependency_results = {
            "dep-1": TaskResult(
                task_id="dep-1",
                status=TaskStatus.COMPLETED,
                result="Previous result",
            )
        }

        result = await task.execute_async(mock_agent, dependency_results=dependency_results)

        assert result.status == TaskStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_prompt_task_process_json_output(self, basic_task_config, mock_agent):
        """Test PromptTask processes JSON output correctly."""
        mock_agent.model_client.generate_async = AsyncMock(
            return_value=Mock(
                content='{"key": "value"}',
                tokens_used=30,
                cost=0.0005,
                model="claude-3-sonnet",
            )
        )

        task = PromptTask(
            config=basic_task_config,
            prompt="Generate JSON",
            expected_output_type="json",
        )
        task.start_time = datetime.utcnow()

        result = await task.execute_async(mock_agent)

        assert result.status == TaskStatus.COMPLETED
        assert isinstance(result.result, dict)
        assert result.result["key"] == "value"

    @pytest.mark.asyncio
    async def test_prompt_task_process_number_output(self, basic_task_config, mock_agent):
        """Test PromptTask processes number output correctly."""
        mock_agent.model_client.generate_async = AsyncMock(
            return_value=Mock(
                content="42.5",
                tokens_used=10,
                cost=0.0001,
                model="claude-3-sonnet",
            )
        )

        task = PromptTask(
            config=basic_task_config,
            prompt="Calculate value",
            expected_output_type="number",
        )
        task.start_time = datetime.utcnow()

        result = await task.execute_async(mock_agent)

        assert result.status == TaskStatus.COMPLETED
        assert result.result == 42.5

    @pytest.mark.asyncio
    async def test_prompt_task_process_boolean_output(self, basic_task_config, mock_agent):
        """Test PromptTask processes boolean output correctly."""
        mock_agent.model_client.generate_async = AsyncMock(
            return_value=Mock(
                content="true",
                tokens_used=5,
                cost=0.00005,
                model="claude-3-sonnet",
            )
        )

        task = PromptTask(
            config=basic_task_config,
            prompt="Is valid?",
            expected_output_type="boolean",
        )
        task.start_time = datetime.utcnow()

        result = await task.execute_async(mock_agent)

        assert result.status == TaskStatus.COMPLETED
        assert result.result is True

    @pytest.mark.asyncio
    async def test_prompt_task_execute_failure(self, basic_task_config, mock_agent):
        """Test PromptTask handles execution failures."""
        mock_agent.model_client.generate_async = AsyncMock(side_effect=Exception("API error"))

        task = PromptTask(
            config=basic_task_config,
            prompt="Test prompt",
        )
        task.start_time = datetime.utcnow()

        result = await task.execute_async(mock_agent)

        assert result.status == TaskStatus.FAILED
        assert result.error is not None
        assert "API error" in result.error


class TestToolTask:
    """Test cases for ToolTask."""

    @pytest.fixture
    def mock_agent(self):
        """Create a mock agent for testing."""
        agent = Mock(spec=SimpleTaskAgent)

        async def mock_call_tool(tool_name, **kwargs):
            if tool_name == "add":
                return kwargs.get("x", 0) + kwargs.get("y", 0)
            elif tool_name == "multiply":
                return kwargs.get("x", 1) * kwargs.get("y", 1)
            else:
                return f"{tool_name}_result"

        agent.call_tool_async = mock_call_tool
        return agent

    @pytest.fixture
    def basic_task_config(self):
        """Create a basic TaskConfig."""
        return TaskConfig(
            name="tool_task",
            description="Test tool task",
        )

    def test_tool_task_creation(self, basic_task_config):
        """Test creating ToolTask."""
        tool_sequence = [{"tool": "tool1", "parameters": {"param1": "value1"}}]

        task = ToolTask(
            config=basic_task_config,
            tool_sequence=tool_sequence,
        )
        assert task.tool_sequence == tool_sequence
        assert task.status == TaskStatus.PENDING

    @pytest.mark.asyncio
    async def test_tool_task_execute_single_tool(self, basic_task_config, mock_agent):
        """Test executing ToolTask with single tool."""
        tool_sequence = [{"tool": "add", "parameters": {"x": 5, "y": 3}}]

        task = ToolTask(
            config=basic_task_config,
            tool_sequence=tool_sequence,
        )
        task.start_time = datetime.utcnow()

        result = await task.execute_async(mock_agent)

        assert result.status == TaskStatus.COMPLETED
        assert result.result == [8]

    @pytest.mark.asyncio
    async def test_tool_task_execute_multiple_tools(self, basic_task_config, mock_agent):
        """Test executing ToolTask with multiple tools in sequence."""
        tool_sequence = [
            {"tool": "add", "parameters": {"x": 5, "y": 3}},
            {"tool": "multiply", "parameters": {"x": 2, "y": 4}},
        ]

        task = ToolTask(
            config=basic_task_config,
            tool_sequence=tool_sequence,
        )
        task.start_time = datetime.utcnow()

        result = await task.execute_async(mock_agent)

        assert result.status == TaskStatus.COMPLETED
        assert len(result.result) == 2
        assert result.result[0] == 8
        assert result.result[1] == 8

    @pytest.mark.asyncio
    async def test_tool_task_execute_failure(self, basic_task_config):
        """Test ToolTask handles execution failures."""
        mock_agent = Mock(spec=SimpleTaskAgent)
        mock_agent.call_tool_async = AsyncMock(side_effect=Exception("Tool error"))

        tool_sequence = [{"tool": "failing_tool", "parameters": {}}]

        task = ToolTask(
            config=basic_task_config,
            tool_sequence=tool_sequence,
        )
        task.start_time = datetime.utcnow()

        result = await task.execute_async(mock_agent)

        assert result.status == TaskStatus.FAILED
        assert "Tool error" in result.error


class TestBaseTask:
    """Test cases for BaseTask dependency management."""

    @pytest.fixture
    def basic_task_config(self):
        """Create a basic TaskConfig."""
        return TaskConfig(
            name="test_task",
            description="Test task",
        )

    @pytest.fixture
    def mock_agent(self):
        """Create a mock agent."""
        agent = Mock(spec=SimpleTaskAgent)
        agent.model_client = Mock()
        agent.model_client.generate_async = AsyncMock(
            return_value=Mock(content="Result", tokens_used=50, cost=0.001, model="test-model")
        )
        agent.config = Mock(model="test-model", temperature=0.7, max_tokens=4096)
        return agent

    def test_base_task_can_execute_no_dependencies(self, basic_task_config):
        """Test task with no dependencies can execute immediately."""
        task = PromptTask(config=basic_task_config, prompt="Test")
        assert task.can_execute({}) is True

    def test_base_task_can_execute_dependency_met(self, basic_task_config):
        """Test task can execute when dependencies are met."""
        dep_config = TaskConfig(
            name="dep_task",
            description="Dependency task",
        )
        task_config = TaskConfig(
            name="main_task",
            description="Main task",
            dependencies=[TaskDependency(task_id="dep-1")],
        )

        task = PromptTask(config=task_config, prompt="Test")
        completed_tasks = {
            "dep-1": TaskResult(
                task_id="dep-1",
                status=TaskStatus.COMPLETED,
                result="Dependency result",
            )
        }

        assert task.can_execute(completed_tasks) is True

    def test_base_task_cannot_execute_dependency_missing(self, basic_task_config):
        """Test task cannot execute when dependencies are missing."""
        task_config = TaskConfig(
            name="main_task",
            description="Main task",
            dependencies=[TaskDependency(task_id="dep-1")],
        )

        task = PromptTask(config=task_config, prompt="Test")
        assert task.can_execute({}) is False

    def test_base_task_cannot_execute_dependency_failed(self, basic_task_config):
        """Test task cannot execute when dependency failed."""
        task_config = TaskConfig(
            name="main_task",
            description="Main task",
            dependencies=[TaskDependency(task_id="dep-1")],
        )

        task = PromptTask(config=task_config, prompt="Test")
        completed_tasks = {
            "dep-1": TaskResult(
                task_id="dep-1",
                status=TaskStatus.FAILED,
                result=None,
                error="Dependency failed",
            )
        }

        assert task.can_execute(completed_tasks) is False

    def test_base_task_get_dependency_results(self, basic_task_config):
        """Test getting dependency results."""
        task_config = TaskConfig(
            name="main_task",
            description="Main task",
            dependencies=[TaskDependency(task_id="dep-1"), TaskDependency(task_id="dep-2")],
        )

        task = PromptTask(config=task_config, prompt="Test")
        completed_tasks = {
            "dep-1": TaskResult(task_id="dep-1", status=TaskStatus.COMPLETED, result="Result 1"),
            "dep-2": TaskResult(task_id="dep-2", status=TaskStatus.COMPLETED, result="Result 2"),
            "other": TaskResult(task_id="other", status=TaskStatus.COMPLETED, result="Other result"),
        }

        dep_results = task.get_dependency_results(completed_tasks)
        assert len(dep_results) == 2
        assert "dep-1" in dep_results
        assert "dep-2" in dep_results
        assert "other" not in dep_results

    @pytest.mark.asyncio
    async def test_base_task_execute_with_retry_success_first_attempt(self, basic_task_config, mock_agent):
        """Test task succeeds on first attempt."""
        task = PromptTask(config=basic_task_config, prompt="Test")

        result = await task._execute_with_retry_async(mock_agent)

        assert result.status == TaskStatus.COMPLETED
        assert task.attempt_count == 1

    @pytest.mark.asyncio
    async def test_base_task_execute_with_retry_success_after_failures(self, basic_task_config):
        """Test task succeeds after retry attempts."""
        mock_agent = Mock(spec=SimpleTaskAgent)
        attempts = []

        async def mock_generate(prompt, **kwargs):
            attempts.append(1)
            if len(attempts) < 2:
                raise Exception("Temporary failure")
            return Mock(content="Success", tokens_used=50, cost=0.001, model="test-model")

        mock_agent.model_client = Mock()
        mock_agent.model_client.generate_async = mock_generate
        mock_agent.config = Mock(model="test-model", temperature=0.7, max_tokens=4096)

        config = TaskConfig(
            name="retry_task",
            description="Retry test",
            retry_attempts=3,
            retry_delay_seconds=0.01,
        )
        task = PromptTask(config=config, prompt="Test")

        result = await task._execute_with_retry_async(mock_agent)

        assert result.status == TaskStatus.COMPLETED
        assert task.attempt_count == 2

    @pytest.mark.asyncio
    async def test_base_task_execute_with_retry_all_attempts_fail(self, basic_task_config):
        """Test task fails after all retry attempts."""
        mock_agent = Mock(spec=SimpleTaskAgent)
        mock_agent.model_client = Mock()
        mock_agent.model_client.generate_async = AsyncMock(side_effect=Exception("Persistent failure"))
        mock_agent.config = Mock(model="test-model", temperature=0.7, max_tokens=4096)

        config = TaskConfig(
            name="fail_task",
            description="Fail test",
            retry_attempts=2,
            retry_delay_seconds=0.01,
        )
        task = PromptTask(config=config, prompt="Test")

        result = await task._execute_with_retry_async(mock_agent)

        assert result.status == TaskStatus.FAILED
        assert task.attempt_count == 2
        assert "failed after 2 attempts" in result.error

    def test_base_task_get_status_info(self, basic_task_config):
        """Test getting task status information."""
        task = PromptTask(config=basic_task_config, prompt="Test")

        status_info = task.get_status_info()

        assert status_info["id"] == task.id
        assert status_info["name"] == "test_task"
        assert status_info["status"] == "pending"
        assert status_info["priority"] == TaskPriority.NORMAL.value
        assert status_info["attempt_count"] == 0
        assert status_info["max_attempts"] == 3


class TestTaskSequence:
    """Test cases for TaskSequence."""

    @pytest.fixture
    def mock_agent(self):
        """Create a mock agent."""
        agent = Mock(spec=SimpleTaskAgent)
        agent.model_client = Mock()
        agent.model_client.generate_async = AsyncMock(
            return_value=Mock(content="Result", tokens_used=50, cost=0.001, model="test-model")
        )
        agent.config = Mock(model="test-model", temperature=0.7, max_tokens=4096)
        return agent

    def test_task_sequence_creation(self):
        """Test creating TaskSequence."""
        task1 = PromptTask(
            config=TaskConfig(name="task1", description="Task 1"),
            prompt="First task",
        )
        task2 = PromptTask(
            config=TaskConfig(name="task2", description="Task 2"),
            prompt="Second task",
        )

        sequence = TaskSequence(name="test_sequence", tasks=[task1, task2])

        assert sequence.name == "test_sequence"
        assert len(sequence.tasks) == 2
        assert task1.id in sequence.tasks
        assert task2.id in sequence.tasks

    def test_task_sequence_execution_order_no_dependencies(self):
        """Test execution order calculation with no dependencies."""
        task1 = PromptTask(
            config=TaskConfig(name="task1", description="Task 1"),
            prompt="First",
        )
        task2 = PromptTask(
            config=TaskConfig(name="task2", description="Task 2"),
            prompt="Second",
        )

        sequence = TaskSequence(name="sequence", tasks=[task1, task2])

        assert len(sequence.execution_order) == 2

    def test_task_sequence_execution_order_with_dependencies(self):
        """Test execution order calculation with dependencies."""
        task1_id = "task-1"
        task1 = PromptTask(
            config=TaskConfig(name="task1", description="Task 1"),
            prompt="First",
        )
        task1.id = task1_id

        task2 = PromptTask(
            config=TaskConfig(
                name="task2",
                description="Task 2",
                dependencies=[TaskDependency(task_id=task1_id)],
            ),
            prompt="Second",
        )

        sequence = TaskSequence(name="sequence", tasks=[task1, task2])

        assert len(sequence.execution_order) == 2
        assert sequence.execution_order[0] == task1.id
        assert sequence.execution_order[1] == task2.id

    def test_task_sequence_circular_dependency_detection(self):
        """Test that circular dependencies are detected."""
        task1 = PromptTask(
            config=TaskConfig(
                name="task1",
                description="Task 1",
                dependencies=[TaskDependency(task_id="task-2")],
            ),
            prompt="First",
        )
        task1.id = "task-1"

        task2 = PromptTask(
            config=TaskConfig(
                name="task2",
                description="Task 2",
                dependencies=[TaskDependency(task_id="task-1")],
            ),
            prompt="Second",
        )
        task2.id = "task-2"

        with pytest.raises(AIError) as exc_info:
            TaskSequence(name="circular_sequence", tasks=[task1, task2])
        assert "circular dependency" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_task_sequence_execute_sequential(self, mock_agent):
        """Test executing task sequence sequentially."""
        task1 = PromptTask(
            config=TaskConfig(name="task1", description="Task 1"),
            prompt="First",
        )
        task2 = PromptTask(
            config=TaskConfig(name="task2", description="Task 2"),
            prompt="Second",
        )

        sequence = TaskSequence(name="sequence", tasks=[task1, task2])

        results = await sequence.execute_async(mock_agent)

        assert len(results) == 2
        assert all(result.status == TaskStatus.COMPLETED for result in results.values())

    def test_task_sequence_get_status_summary(self):
        """Test getting status summary."""
        task1 = PromptTask(
            config=TaskConfig(name="task1", description="Task 1"),
            prompt="First",
        )
        task2 = PromptTask(
            config=TaskConfig(name="task2", description="Task 2"),
            prompt="Second",
        )

        sequence = TaskSequence(name="test_sequence", tasks=[task1, task2])

        summary = sequence.get_status_summary()

        assert summary["sequence_name"] == "test_sequence"
        assert summary["total_tasks"] == 2
        assert summary["completed_tasks"] == 0
        assert summary["failed_tasks"] == 0


class TestTaskBuilder:
    """Test cases for TaskBuilder."""

    def test_create_prompt_task_basic(self):
        """Test creating a basic prompt task with builder."""
        task = TaskBuilder.create_prompt_task(
            name="test_task",
            prompt="Test prompt",
        )

        assert isinstance(task, PromptTask)
        assert task.config.name == "test_task"
        assert task.prompt == "Test prompt"
        assert task.expected_output_type == "text"

    def test_create_prompt_task_with_options(self):
        """Test creating prompt task with all options."""
        task = TaskBuilder.create_prompt_task(
            name="advanced_task",
            prompt="Advanced prompt",
            description="Custom description",
            priority=TaskPriority.HIGH,
            expected_output_type="json",
            dependencies=["dep-1", "dep-2"],
        )

        assert task.config.priority == TaskPriority.HIGH
        assert task.expected_output_type == "json"
        assert len(task.config.dependencies) == 2

    def test_create_tool_task_basic(self):
        """Test creating a basic tool task with builder."""
        tool_sequence = [{"tool": "tool1", "parameters": {"param": "value"}}]

        task = TaskBuilder.create_tool_task(
            name="tool_task",
            tool_sequence=tool_sequence,
        )

        assert isinstance(task, ToolTask)
        assert task.config.name == "tool_task"
        assert task.tool_sequence == tool_sequence

    def test_create_tool_task_extracts_required_tools(self):
        """Test that create_tool_task extracts required tools."""
        tool_sequence = [
            {"tool": "tool1", "parameters": {}},
            {"tool": "tool2", "parameters": {}},
            {"tool": "tool1", "parameters": {}},
        ]

        task = TaskBuilder.create_tool_task(
            name="multi_tool_task",
            tool_sequence=tool_sequence,
        )

        assert len(task.config.required_tools) == 2
        assert "tool1" in task.config.required_tools
        assert "tool2" in task.config.required_tools

    def test_create_analysis_task(self):
        """Test creating an analysis task with builder."""
        task = TaskBuilder.create_analysis_task(
            name="analysis_task",
            analysis_prompt="Analyze the data",
            data_source="dataset.csv",
        )

        assert isinstance(task, PromptTask)
        assert task.config.name == "analysis_task"
        assert "Analyze the data" in task.prompt
        assert "dataset.csv" in task.prompt


if __name__ == "__main__":
    pytest.main([__file__, "-v"])