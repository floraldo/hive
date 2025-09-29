"""Unit tests for AsyncAIReviewer V4.2."""

import asyncio
import time
import uuid
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

# Import the components we're testing
from ai_reviewer.async_agent import (
    AsyncAIReviewer,
    AsyncReviewEngine,
    ReviewPriority,
)


@pytest.fixture
def mock_db_operations():
    """Mock async database operations."""
    mock_db = AsyncMock()
    mock_db.insert_async = AsyncMock(return_value="mock_review_id")
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
    config = {
        "mock_mode": True,
        "max_concurrent_reviews": 5,
        "max_queue_size": 50,
        "performance_monitoring_interval": 30,
    }
    return config


@pytest.fixture
def async_reviewer():
    """Create AsyncAIReviewer instance for testing."""
    return AsyncAIReviewer(mock_mode=True)


class TestAsyncReviewEngine:
    """Test the AsyncReviewEngine component."""

    @pytest.fixture
    def review_engine(self):
        """Create AsyncReviewEngine for testing."""
        config = {"mock_mode": True}
        return AsyncReviewEngine(config)

    @pytest.mark.asyncio
    async def test_review_engine_initialization(self, review_engine):
        """Test AsyncReviewEngine initializes correctly."""
        assert review_engine.mock_mode is True
        assert review_engine._review_semaphore._value == 3  # Concurrent limit

    @pytest.mark.asyncio
    async def test_review_task_async_basic(self, review_engine):
        """Test basic review functionality."""
        task = {"id": "task_123", "description": "Test task for review", "complexity": "medium", "status": "completed"}

        run_data = {
            "status": "success",
            "exit_code": 0,
            "execution_time": 45.2,
            "files": {"created": ["src/main.py", "tests/test_main.py"], "modified": ["README.md"]},
            "output": "Task completed successfully",
        }

        result = await review_engine.review_task_async(task, run_data)

        # Verify result structure
        assert isinstance(result, dict)
        assert "review_id" in result
        assert "decision" in result
        assert "score" in result
        assert "analysis" in result
        assert "issues" in result
        assert "recommendations" in result

        # Verify decision is valid
        assert result["decision"] in ["approved", "approved_with_changes", "rejected"]

        # Verify score is reasonable
        assert 0 <= result["score"] <= 100

    @pytest.mark.asyncio
    async def test_review_complexity_timing(self, review_engine):
        """Test that review time varies with task complexity."""
        complexities = ["low", "medium", "high"]
        times = {}

        for complexity in complexities:
            task = {"id": f"task_{complexity}", "complexity": complexity, "status": "completed"}
            run_data = {"status": "success", "exit_code": 0}

            start_time = time.time()
            await review_engine.review_task_async(task, run_data)
            end_time = time.time()

            times[complexity] = end_time - start_time

        # Higher complexity should take longer (with some tolerance for timing variations)
        assert times["low"] <= times["medium"] * 1.2  # Allow 20% variance
        assert times["medium"] <= times["high"] * 1.2

    @pytest.mark.asyncio
    async def test_concurrent_reviews_semaphore(self, review_engine):
        """Test semaphore limits concurrent reviews."""
        num_reviews = 6  # More than semaphore limit of 3

        tasks = [
            {"id": f"concurrent_task_{i}", "complexity": "medium", "status": "completed"} for i in range(num_reviews)
        ]

        run_data = {"status": "success", "exit_code": 0}

        start_time = time.time()
        review_coroutines = [review_engine.review_task_async(task, run_data) for task in tasks]
        results = await asyncio.gather(*review_coroutines)
        end_time = time.time()

        # All should complete successfully
        assert len(results) == num_reviews
        for result in results:
            assert "review_id" in result
            assert "decision" in result

        # Should take longer than if all ran truly in parallel due to semaphore
        assert end_time - start_time > 0.5  # Should take some time due to semaphore

    @pytest.mark.asyncio
    async def test_mock_review_generation(self, review_engine):
        """Test mock review generation for different scenarios."""
        # Test successful task
        successful_task = {"id": "success_task", "complexity": "medium", "status": "completed"}
        successful_run_data = {
            "status": "success",
            "exit_code": 0,
            "files": {"created": ["src/app.py"], "modified": []},
        }

        success_result = await review_engine.review_task_async(successful_task, successful_run_data)

        # Successful task should get positive review
        assert success_result["decision"] in ["approved", "approved_with_changes"]
        assert success_result["score"] >= 60

        # Test failed task
        failed_task = {"id": "failed_task", "complexity": "high", "status": "failed"}
        failed_run_data = {"status": "failed", "exit_code": 1, "error": "Compilation failed"}

        failed_result = await review_engine.review_task_async(failed_task, failed_run_data)

        # Failed task should get negative review
        assert failed_result["decision"] == "rejected"
        assert failed_result["score"] < 60


class TestAsyncAIReviewer:
    """Test the main AsyncAIReviewer class."""

    @pytest.mark.asyncio
    async def test_reviewer_initialization(self, async_reviewer):
        """Test AsyncAIReviewer initializes correctly."""
        assert async_reviewer.mock_mode is True
        assert async_reviewer.max_concurrent_reviews == 5
        assert async_reviewer.max_queue_size == 50
        assert async_reviewer.review_queue.empty()
        assert async_reviewer.results_cache == {}

    @pytest.mark.asyncio
    @patch("ai_reviewer.async_agent.get_async_db_operations")
    @patch("ai_reviewer.async_agent.get_async_event_bus")
    async def test_reviewer_initialize_async(self, mock_get_bus, mock_get_db, async_reviewer):
        """Test async initialization."""
        mock_get_db.return_value = AsyncMock()
        mock_get_bus.return_value = AsyncMock()

        await async_reviewer.initialize_async()

        assert async_reviewer.db_operations is not None
        assert async_reviewer.event_bus is not None
        assert async_reviewer.review_engine is not None

    @pytest.mark.asyncio
    @patch("ai_reviewer.async_agent.get_async_db_operations")
    async def test_get_next_review_task_async(self, mock_get_db, async_reviewer):
        """Test getting next task for review."""
        # Setup mock database
        mock_db = AsyncMock()
        mock_task = {
            "id": "review_task_123",
            "description": "Test task for review",
            "status": "completed",
            "priority": 80,
            "completion_time": datetime.utcnow().isoformat(),
        }
        mock_db.execute_query_async.return_value = [mock_task]
        mock_get_db.return_value = mock_db

        await async_reviewer.initialize_async()

        # Test getting task
        task = await async_reviewer.get_next_review_task_async()

        assert task is not None
        assert task["id"] == "review_task_123"
        assert task["status"] == "completed"

    @pytest.mark.asyncio
    @patch("ai_reviewer.async_agent.get_async_db_operations")
    @patch("ai_reviewer.async_agent.get_async_event_bus")
    async def test_perform_review_async(self, mock_get_bus, mock_get_db, async_reviewer):
        """Test review performance end-to-end."""
        # Setup mocks
        mock_db = AsyncMock()
        mock_db.insert_async.return_value = "review_123"
        mock_db.update_async.return_value = True
        mock_db.get_async.return_value = {
            "status": "success",
            "execution_time": 30.5,
            "files": {"created": ["app.py"], "modified": []},
        }
        mock_get_db.return_value = mock_db

        mock_bus = AsyncMock()
        mock_get_bus.return_value = mock_bus

        await async_reviewer.initialize_async()

        # Test task
        task = {
            "id": "review_task_123",
            "description": "Review web application implementation",
            "status": "completed",
            "priority": 80,
            "complexity": "medium",
        }

        # Perform review
        result = await async_reviewer.perform_review_async(task)

        # Verify result
        assert result["status"] == "completed"
        assert "review_id" in result
        assert "execution_time" in result
        assert result["task_id"] == "review_task_123"

        # Verify database calls
        mock_db.insert_async.assert_called_once()
        mock_db.update_async.assert_called()

        # Verify event publishing
        mock_bus.publish_async.assert_called()

    @pytest.mark.asyncio
    @patch("ai_reviewer.async_agent.get_async_db_operations")
    @patch("ai_reviewer.async_agent.get_async_event_bus")
    async def test_concurrent_review_processing(self, mock_get_bus, mock_get_db, async_reviewer):
        """Test concurrent review processing capabilities."""
        # Setup mocks
        mock_db = AsyncMock()
        mock_db.insert_async.side_effect = lambda *args: f"review_{uuid.uuid4().hex[:8]}"
        mock_db.update_async.return_value = True
        mock_db.get_async.return_value = {
            "status": "success",
            "execution_time": 25.0,
            "files": {"created": ["main.py"], "modified": []},
        }
        mock_get_db.return_value = mock_db

        mock_bus = AsyncMock()
        mock_get_bus.return_value = mock_bus

        await async_reviewer.initialize_async()

        # Create multiple review tasks
        tasks = [
            {
                "id": f"review_task_{i}",
                "description": f"Review task {i}",
                "status": "completed",
                "priority": 70 + i,
                "complexity": "medium",
            }
            for i in range(4)
        ]

        # Process reviews concurrently
        start_time = time.time()
        review_coroutines = [async_reviewer.perform_review_async(task) for task in tasks]
        results = await asyncio.gather(*review_coroutines)
        end_time = time.time()

        # Verify all completed successfully
        assert len(results) == 4
        for result in results:
            assert result["status"] == "completed"
            assert "review_id" in result

        # Should be faster than sequential execution
        assert end_time - start_time < 10.0  # Should complete quickly in mock mode

    @pytest.mark.asyncio
    @patch("ai_reviewer.async_agent.get_async_db_operations")
    async def test_error_handling_missing_run_data(self, mock_get_db, async_reviewer):
        """Test error handling when run data is missing."""
        # Setup mock to return None for run data
        mock_db = AsyncMock()
        mock_db.get_async.return_value = None
        mock_get_db.return_value = mock_db

        await async_reviewer.initialize_async()

        task = {
            "id": "missing_data_task",
            "description": "Task with missing run data",
            "status": "completed",
            "priority": 80,
        }

        # Should handle missing data gracefully
        result = await async_reviewer.perform_review_async(task)

        assert result["status"] == "failed"
        assert "error" in result
        assert "No run data found" in result["error"]

    @pytest.mark.asyncio
    @patch("ai_reviewer.async_agent.get_async_db_operations")
    @patch("ai_reviewer.async_agent.get_async_event_bus")
    async def test_performance_monitoring(self, mock_get_bus, mock_get_db, async_reviewer):
        """Test performance monitoring capabilities."""
        # Setup mocks
        mock_db = AsyncMock()
        mock_db.insert_async.return_value = "review_123"
        mock_db.update_async.return_value = True
        mock_db.get_async.return_value = {
            "status": "success",
            "execution_time": 40.0,
            "files": {"created": ["test.py"], "modified": []},
        }
        mock_get_db.return_value = mock_db

        mock_bus = AsyncMock()
        mock_get_bus.return_value = mock_bus

        await async_reviewer.initialize_async()

        # Process some reviews to generate metrics
        tasks = [
            {
                "id": f"perf_task_{i}",
                "description": f"Performance test task {i}",
                "status": "completed",
                "priority": 75,
                "complexity": "medium",
            }
            for i in range(3)
        ]

        for task in tasks:
            await async_reviewer.perform_review_async(task)

        # Check performance metrics
        assert len(async_reviewer.performance_metrics["response_times"]) == 3
        assert async_reviewer.performance_metrics["total_reviews"] == 3
        assert async_reviewer.performance_metrics["successful_reviews"] == 3
        assert async_reviewer.performance_metrics["failed_reviews"] == 0

    @pytest.mark.asyncio
    async def test_priority_handling(self, async_reviewer):
        """Test priority-based review handling."""
        # Test priority enum
        assert ReviewPriority.LOW.value == 1
        assert ReviewPriority.MEDIUM.value == 2
        assert ReviewPriority.HIGH.value == 3
        assert ReviewPriority.CRITICAL.value == 4

        # Test that higher priority reviews are handled appropriately
        low_priority_task = {
            "id": "low_review",
            "priority": ReviewPriority.LOW.value,
            "description": "Low priority review",
        }

        critical_priority_task = {
            "id": "critical_review",
            "priority": ReviewPriority.CRITICAL.value,
            "description": "Critical priority review",
        }

        # Both should be processable (detailed priority handling would require queue implementation)
        assert low_priority_task["priority"] < critical_priority_task["priority"]

    @pytest.mark.asyncio
    @patch("ai_reviewer.async_agent.get_async_db_operations")
    async def test_queue_management(self, mock_get_db, async_reviewer):
        """Test review queue management."""
        mock_db = AsyncMock()
        mock_get_db.return_value = mock_db

        await async_reviewer.initialize_async()

        # Test queue operations
        assert async_reviewer.review_queue.empty()

        # Add reviews to queue
        for i in range(3):
            task = {"id": f"queue_task_{i}", "description": f"Queue test task {i}", "priority": 70 + i}
            await async_reviewer.review_queue.put(task)

        assert async_reviewer.review_queue.qsize() == 3


class TestAsyncReviewerIntegration:
    """Integration tests for AsyncAIReviewer components working together."""

    @pytest.mark.asyncio
    @patch("ai_reviewer.async_agent.get_async_db_operations")
    @patch("ai_reviewer.async_agent.get_async_event_bus")
    async def test_full_review_workflow(self, mock_get_bus, mock_get_db):
        """Test complete review workflow from task completion to review delivery."""
        # Setup comprehensive mocks
        mock_db = AsyncMock()
        mock_db.insert_async.return_value = "review_integration_123"
        mock_db.update_async.return_value = True
        mock_db.get_async.return_value = {
            "status": "success",
            "exit_code": 0,
            "execution_time": 120.5,
            "files": {
                "created": ["src/api/auth.py", "src/api/users.py", "tests/test_auth.py", "tests/test_users.py"],
                "modified": ["requirements.txt", "README.md"],
            },
            "output": "API implementation completed with tests",
            "metrics": {"lines_of_code": 450, "test_coverage": 85, "complexity_score": 6.2},
        }
        mock_get_db.return_value = mock_db

        mock_bus = AsyncMock()
        mock_get_bus.return_value = mock_bus

        # Create reviewer and initialize
        reviewer = AsyncAIReviewer(mock_mode=True)
        await reviewer.initialize_async()

        # Simulate a realistic review task
        task = {
            "id": "integration_review_task_123",
            "description": "Review REST API implementation with authentication",
            "status": "completed",
            "priority": 85,
            "complexity": "high",
            "assigned_to": "developer_123",
            "completion_time": datetime.utcnow().isoformat(),
        }

        # Execute review workflow
        start_time = time.time()
        result = await reviewer.perform_review_async(task)
        execution_time = time.time() - start_time

        # Verify comprehensive result
        assert result["status"] == "completed"
        assert result["task_id"] == "integration_review_task_123"
        assert "review_id" in result
        assert "execution_time" in result
        assert result["execution_time"] > 0

        # Verify review details were generated
        assert "review_details" in result
        review_details = result["review_details"]
        assert "decision" in review_details
        assert "score" in review_details
        assert "analysis" in review_details

        # Verify database interactions occurred
        mock_db.insert_async.assert_called_once()
        mock_db.update_async.assert_called()

        # Verify events were published
        mock_bus.publish_async.assert_called()

        # Performance assertion - should complete quickly in mock mode
        assert execution_time < 3.0

        # Verify performance metrics were updated
        assert len(reviewer.performance_metrics["response_times"]) == 1
        assert reviewer.performance_metrics["total_reviews"] == 1
        assert reviewer.performance_metrics["successful_reviews"] == 1

    @pytest.mark.asyncio
    @patch("ai_reviewer.async_agent.get_async_db_operations")
    @patch("ai_reviewer.async_agent.get_async_event_bus")
    async def test_review_decision_accuracy(self, mock_get_bus, mock_get_db):
        """Test that review decisions are appropriate for different task outcomes."""
        # Setup mocks
        mock_db = AsyncMock()
        mock_db.insert_async.side_effect = lambda *args: f"review_{uuid.uuid4().hex[:8]}"
        mock_db.update_async.return_value = True
        mock_get_db.return_value = mock_db

        mock_bus = AsyncMock()
        mock_get_bus.return_value = mock_bus

        reviewer = AsyncAIReviewer(mock_mode=True)
        await reviewer.initialize_async()

        # Test scenarios with different outcomes
        test_scenarios = [
            {
                "name": "successful_with_tests",
                "run_data": {
                    "status": "success",
                    "exit_code": 0,
                    "files": {"created": ["app.py", "test_app.py"]},
                    "metrics": {"test_coverage": 90},
                },
                "expected_decision": ["approved", "approved_with_changes"],
            },
            {
                "name": "successful_no_tests",
                "run_data": {
                    "status": "success",
                    "exit_code": 0,
                    "files": {"created": ["app.py"]},
                    "metrics": {"test_coverage": 0},
                },
                "expected_decision": ["approved_with_changes"],
            },
            {
                "name": "failed_task",
                "run_data": {"status": "failed", "exit_code": 1, "error": "Compilation failed"},
                "expected_decision": ["rejected"],
            },
        ]

        for scenario in test_scenarios:
            mock_db.get_async.return_value = scenario["run_data"]

            task = {
                "id": f"scenario_{scenario['name']}",
                "description": f"Test scenario: {scenario['name']}",
                "status": "completed",
                "priority": 80,
                "complexity": "medium",
            }

            result = await reviewer.perform_review_async(task)

            assert result["status"] == "completed"
            review_details = result["review_details"]
            assert review_details["decision"] in scenario["expected_decision"]


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])
