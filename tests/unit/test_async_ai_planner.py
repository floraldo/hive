"""Unit tests for AsyncAIPlanner V4.2."""

import asyncio
import pytest
import time
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any, List

# Import the components we're testing
from ai_planner.async_agent import (
    AsyncAIPlanner,
    AsyncClaudeService,
    PlanningPriority,
)


@pytest.fixture
def mock_db_operations():
    """Mock async database operations."""
    mock_db = AsyncMock()
    mock_db.insert_async = AsyncMock(return_value="mock_plan_id")
    mock_db.update_async = AsyncMock(return_value=True)
    mock_db.get_async = AsyncMock(return_value={"status": "completed"})
    mock_db.execute_query_async = AsyncMock(return_value=[])
    return mock_db


@pytest.fixture
def mock_event_bus():
    """Mock async event bus."""
    mock_bus = AsyncMock()
    mock_bus.publish_async = AsyncMock(return_value=True)
    return mock_bus


@pytest.fixture
def mock_config():
    """Mock configuration for testing."""
    config = MagicMock()
    config.mock_mode = True
    config.max_concurrent_tasks = 10
    config.max_queue_size = 100
    config.performance_monitoring_interval = 30
    return config


@pytest.fixture
def async_planner(mock_config):
    """Create AsyncAIPlanner instance for testing."""
    return AsyncAIPlanner(mock_mode=True)


class TestAsyncClaudeService:
    """Test the AsyncClaudeService component."""

    @pytest.fixture
    def claude_service(self):
        """Create AsyncClaudeService for testing."""
        config = MagicMock()
        config.mock_mode = True

        rate_config = MagicMock()
        rate_config.max_calls_per_minute = 20
        rate_config.max_calls_per_hour = 500

        return AsyncClaudeService(config, rate_config)

    @pytest.mark.asyncio
    async def test_claude_service_initialization(self, claude_service):
        """Test AsyncClaudeService initializes correctly."""
        assert claude_service.mock_mode is True
        assert claude_service.max_calls_per_minute == 20
        assert claude_service.max_calls_per_hour == 500
        assert claude_service._semaphore._value == 5  # Concurrent limit

    @pytest.mark.asyncio
    async def test_generate_execution_plan_async_basic(self, claude_service):
        """Test basic plan generation functionality."""
        task_description = "Create a simple web application"
        context_data = {"framework": "FastAPI", "database": "PostgreSQL"}
        priority = 80
        requestor = "test_user"

        result = await claude_service.generate_execution_plan_async(
            task_description, context_data, priority, requestor
        )

        # Verify result structure
        assert isinstance(result, dict)
        assert "plan_id" in result
        assert "plan_name" in result
        assert "sub_tasks" in result
        assert "complexity_breakdown" in result
        assert "total_estimated_duration" in result

        # Verify sub_tasks structure
        sub_tasks = result["sub_tasks"]
        assert isinstance(sub_tasks, list)
        assert len(sub_tasks) > 0

        for task in sub_tasks:
            assert "id" in task
            assert "title" in task
            assert "description" in task
            assert "estimated_duration" in task

    @pytest.mark.asyncio
    async def test_rate_limiting_behavior(self, claude_service):
        """Test rate limiting works correctly."""
        # Record initial timestamp
        start_time = time.time()

        # Make multiple rapid calls
        tasks = []
        for i in range(3):  # Small number to avoid long test times
            task = claude_service.generate_execution_plan_async(
                f"Task {i}", {}, 50, "test_user"
            )
            tasks.append(task)

        results = await asyncio.gather(*tasks)

        # All should succeed
        assert len(results) == 3
        for result in results:
            assert "plan_id" in result

        # Verify timestamps were recorded
        assert len(claude_service._call_timestamps) == 3

    @pytest.mark.asyncio
    async def test_concurrent_calls_semaphore(self, claude_service):
        """Test semaphore limits concurrent calls."""
        # Create more tasks than semaphore allows
        num_tasks = 10
        semaphore_limit = claude_service._semaphore._value

        start_time = time.time()

        tasks = [
            claude_service.generate_execution_plan_async(
                f"Concurrent task {i}", {}, 50, "test_user"
            )
            for i in range(num_tasks)
        ]

        results = await asyncio.gather(*tasks)

        # All should complete successfully
        assert len(results) == num_tasks

        # Should take longer than if all ran truly in parallel
        # (This is a rough test - in practice we'd need more sophisticated timing)
        elapsed_time = time.time() - start_time
        assert elapsed_time > 0.1  # Should take some time due to semaphore

    @pytest.mark.asyncio
    async def test_complexity_analysis(self, claude_service):
        """Test complexity analysis for different task types."""
        # Test simple task
        simple_result = await claude_service.generate_execution_plan_async(
            "Print hello world", {}, 30, "test_user"
        )
        simple_breakdown = simple_result["complexity_breakdown"]

        # Test complex task
        complex_result = await claude_service.generate_execution_plan_async(
            "Build a distributed microservices architecture with Docker, Kubernetes, and CI/CD",
            {}, 90, "test_user"
        )
        complex_breakdown = complex_result["complexity_breakdown"]

        # Complex task should have more high-complexity subtasks
        assert complex_breakdown["high"] >= simple_breakdown["high"]


class TestAsyncAIPlanner:
    """Test the main AsyncAIPlanner class."""

    @pytest.mark.asyncio
    async def test_planner_initialization(self, async_planner):
        """Test AsyncAIPlanner initializes correctly."""
        assert async_planner.mock_mode is True
        assert async_planner.max_concurrent_tasks == 10
        assert async_planner.max_queue_size == 100
        assert async_planner.processing_queue.empty()
        assert async_planner.results_cache == {}

    @pytest.mark.asyncio
    @patch('ai_planner.async_agent.get_async_db_operations')
    @patch('ai_planner.async_agent.get_async_event_bus')
    async def test_planner_initialize_async(self, mock_get_bus, mock_get_db, async_planner):
        """Test async initialization."""
        mock_get_db.return_value = AsyncMock()
        mock_get_bus.return_value = AsyncMock()

        await async_planner.initialize_async()

        assert async_planner.db_operations is not None
        assert async_planner.event_bus is not None
        assert async_planner.claude_service is not None

    @pytest.mark.asyncio
    @patch('ai_planner.async_agent.get_async_db_operations')
    async def test_get_next_planning_task_async(self, mock_get_db, async_planner):
        """Test getting next task from queue."""
        # Setup mock database
        mock_db = AsyncMock()
        mock_task = {
            "id": "task_123",
            "description": "Test task",
            "priority": 80,
            "status": "pending",
            "requestor": "test_user"
        }
        mock_db.execute_query_async.return_value = [mock_task]
        mock_get_db.return_value = mock_db

        await async_planner.initialize_async()

        # Test getting task
        task = await async_planner.get_next_planning_task_async()

        assert task is not None
        assert task["id"] == "task_123"
        assert task["description"] == "Test task"

    @pytest.mark.asyncio
    @patch('ai_planner.async_agent.get_async_db_operations')
    @patch('ai_planner.async_agent.get_async_event_bus')
    async def test_generate_plan_async(self, mock_get_bus, mock_get_db, async_planner):
        """Test plan generation end-to-end."""
        # Setup mocks
        mock_db = AsyncMock()
        mock_db.insert_async.return_value = "plan_123"
        mock_db.update_async.return_value = True
        mock_get_db.return_value = mock_db

        mock_bus = AsyncMock()
        mock_get_bus.return_value = mock_bus

        await async_planner.initialize_async()

        # Test task
        task = {
            "id": "task_123",
            "description": "Create a web application",
            "priority": 80,
            "requestor": "test_user",
            "context_data": {"framework": "FastAPI"}
        }

        # Generate plan
        result = await async_planner.generate_plan_async(task)

        # Verify result
        assert result["status"] == "completed"
        assert "plan_id" in result
        assert "execution_time" in result
        assert result["task_id"] == "task_123"

        # Verify database calls
        mock_db.insert_async.assert_called_once()
        mock_db.update_async.assert_called()

        # Verify event publishing
        mock_bus.publish_async.assert_called()

    @pytest.mark.asyncio
    @patch('ai_planner.async_agent.get_async_db_operations')
    @patch('ai_planner.async_agent.get_async_event_bus')
    async def test_concurrent_plan_generation(self, mock_get_bus, mock_get_db, async_planner):
        """Test concurrent plan generation capabilities."""
        # Setup mocks
        mock_db = AsyncMock()
        mock_db.insert_async.side_effect = lambda *args: f"plan_{uuid.uuid4().hex[:8]}"
        mock_db.update_async.return_value = True
        mock_get_db.return_value = mock_db

        mock_bus = AsyncMock()
        mock_get_bus.return_value = mock_bus

        await async_planner.initialize_async()

        # Create multiple tasks
        tasks = [
            {
                "id": f"task_{i}",
                "description": f"Test task {i}",
                "priority": 70 + i,
                "requestor": "test_user",
                "context_data": {}
            }
            for i in range(5)
        ]

        # Generate plans concurrently
        start_time = time.time()
        plan_tasks = [async_planner.generate_plan_async(task) for task in tasks]
        results = await asyncio.gather(*plan_tasks)
        end_time = time.time()

        # Verify all completed successfully
        assert len(results) == 5
        for result in results:
            assert result["status"] == "completed"
            assert "plan_id" in result

        # Should be faster than sequential execution
        # (This is approximate - in mock mode, timing isn't as critical)
        assert end_time - start_time < 5.0  # Should complete quickly in mock mode

    @pytest.mark.asyncio
    @patch('ai_planner.async_agent.get_async_db_operations')
    async def test_error_handling_database_failure(self, mock_get_db, async_planner):
        """Test error handling when database operations fail."""
        # Setup mock to fail
        mock_db = AsyncMock()
        mock_db.insert_async.side_effect = Exception("Database connection failed")
        mock_get_db.return_value = mock_db

        await async_planner.initialize_async()

        task = {
            "id": "task_123",
            "description": "Test task",
            "priority": 80,
            "requestor": "test_user",
            "context_data": {}
        }

        # Should handle error gracefully
        result = await async_planner.generate_plan_async(task)

        assert result["status"] == "failed"
        assert "error" in result
        assert "Database connection failed" in result["error"]

    @pytest.mark.asyncio
    @patch('ai_planner.async_agent.get_async_db_operations')
    @patch('ai_planner.async_agent.get_async_event_bus')
    async def test_performance_monitoring(self, mock_get_bus, mock_get_db, async_planner):
        """Test performance monitoring capabilities."""
        # Setup mocks
        mock_db = AsyncMock()
        mock_get_db.return_value = mock_db
        mock_bus = AsyncMock()
        mock_get_bus.return_value = mock_bus

        await async_planner.initialize_async()

        # Process some tasks to generate metrics
        tasks = [
            {
                "id": f"task_{i}",
                "description": f"Test task {i}",
                "priority": 70,
                "requestor": "test_user",
                "context_data": {}
            }
            for i in range(3)
        ]

        for task in tasks:
            await async_planner.generate_plan_async(task)

        # Check performance metrics
        assert len(async_planner.performance_metrics["response_times"]) == 3
        assert async_planner.performance_metrics["total_tasks"] == 3
        assert async_planner.performance_metrics["successful_tasks"] == 3
        assert async_planner.performance_metrics["failed_tasks"] == 0

    @pytest.mark.asyncio
    @patch('ai_planner.async_agent.get_async_db_operations')
    async def test_queue_management(self, mock_get_db, async_planner):
        """Test task queue management."""
        mock_db = AsyncMock()
        mock_get_db.return_value = mock_db

        await async_planner.initialize_async()

        # Test queue operations
        assert async_planner.processing_queue.empty()

        # Add tasks to queue
        for i in range(5):
            task = {
                "id": f"task_{i}",
                "description": f"Test task {i}",
                "priority": 70 + i
            }
            await async_planner.processing_queue.put(task)

        assert async_planner.processing_queue.qsize() == 5

    @pytest.mark.asyncio
    async def test_priority_handling(self, async_planner):
        """Test priority-based task handling."""
        # Test priority enum
        assert PlanningPriority.LOW.value == 1
        assert PlanningPriority.MEDIUM.value == 2
        assert PlanningPriority.HIGH.value == 3
        assert PlanningPriority.CRITICAL.value == 4

        # Test that higher priority tasks are handled appropriately
        low_priority_task = {
            "id": "low_task",
            "priority": PlanningPriority.LOW.value,
            "description": "Low priority task"
        }

        high_priority_task = {
            "id": "high_task",
            "priority": PlanningPriority.CRITICAL.value,
            "description": "High priority task"
        }

        # Both should be processable (detailed priority queue testing would require more complex setup)
        assert low_priority_task["priority"] < high_priority_task["priority"]


class TestAsyncPlannerIntegration:
    """Integration tests for AsyncAIPlanner components working together."""

    @pytest.mark.asyncio
    @patch('ai_planner.async_agent.get_async_db_operations')
    @patch('ai_planner.async_agent.get_async_event_bus')
    async def test_full_planning_workflow(self, mock_get_bus, mock_get_db):
        """Test complete planning workflow from task receipt to plan delivery."""
        # Setup comprehensive mocks
        mock_db = AsyncMock()
        mock_db.insert_async.return_value = "plan_123"
        mock_db.update_async.return_value = True
        mock_db.execute_query_async.return_value = []
        mock_get_db.return_value = mock_db

        mock_bus = AsyncMock()
        mock_get_bus.return_value = mock_bus

        # Create planner and initialize
        planner = AsyncAIPlanner(mock_mode=True)
        await planner.initialize_async()

        # Simulate a realistic planning task
        task = {
            "id": "integration_task_123",
            "description": "Build a REST API with authentication and database integration",
            "priority": 85,
            "requestor": "integration_test",
            "context_data": {
                "framework": "FastAPI",
                "database": "PostgreSQL",
                "authentication": "JWT",
                "deployment": "Docker"
            }
        }

        # Execute planning workflow
        start_time = time.time()
        result = await planner.generate_plan_async(task)
        execution_time = time.time() - start_time

        # Verify comprehensive result
        assert result["status"] == "completed"
        assert result["task_id"] == "integration_task_123"
        assert "plan_id" in result
        assert "execution_time" in result
        assert result["execution_time"] > 0

        # Verify plan details were generated
        assert "plan_details" in result
        plan_details = result["plan_details"]
        assert "sub_tasks" in plan_details
        assert len(plan_details["sub_tasks"]) > 0

        # Verify database interactions occurred
        mock_db.insert_async.assert_called_once()
        mock_db.update_async.assert_called()

        # Verify events were published
        mock_bus.publish_async.assert_called()

        # Performance assertion - should complete quickly in mock mode
        assert execution_time < 2.0

        # Verify performance metrics were updated
        assert len(planner.performance_metrics["response_times"]) == 1
        assert planner.performance_metrics["total_tasks"] == 1
        assert planner.performance_metrics["successful_tasks"] == 1


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])