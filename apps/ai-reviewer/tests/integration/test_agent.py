"""
Tests for the AI Reviewer autonomous agent
"""

from datetime import datetime
from unittest.mock import MagicMock, Mock

import pytest

from ai_reviewer.agent import ReviewAgent
from ai_reviewer.database_adapter import DatabaseAdapter
from ai_reviewer.reviewer import QualityMetrics, ReviewDecision, ReviewEngine, ReviewResult

# TODO: Task and TaskStatus models need to be defined or imported from correct location
# from hive_db import Task, TaskStatus


@pytest.fixture
def mock_db():
    """Create a mock database"""
    return Mock()


@pytest.fixture
def mock_review_engine():
    """Create a mock review engine"""
    engine = Mock(spec=ReviewEngine)

    # Create a default review result
    metrics = QualityMetrics(code_quality=80, test_coverage=75, documentation=70, security=85, architecture=80)

    engine.review_task.return_value = ReviewResult(
        task_id="test-123",
        decision=ReviewDecision.APPROVE,
        metrics=metrics,
        summary="Code meets quality standards",
        issues=[],
        suggestions=[],
        confidence=0.85,
    )

    return engine


@pytest.fixture
def mock_adapter():
    """Create a mock database adapter"""
    adapter = Mock(spec=DatabaseAdapter)
    adapter.get_pending_reviews.return_value = []
    adapter.get_task_code_files.return_value = {"main.py": "def test(): pass"}
    adapter.get_test_results.return_value = {"passed": True}
    adapter.get_task_transcript.return_value = "Task completed successfully"
    adapter.update_task_status.return_value = True
    return adapter


@pytest.fixture
def agent(mock_db, mock_review_engine, mock_adapter):
    """Create a ReviewAgent instance with mocks"""
    agent = ReviewAgent(db=mock_db, review_engine=mock_review_engine, polling_interval=1, test_mode=True)
    agent.adapter = mock_adapter
    return agent


class TestReviewAgent:
    """Test the ReviewAgent class"""

    def test_initialization(self, mock_db, mock_review_engine):
        """Test agent initialization"""
        agent = ReviewAgent(db=mock_db, review_engine=mock_review_engine, polling_interval=30)

        assert agent.db == mock_db
        assert agent.review_engine == mock_review_engine
        assert agent.polling_interval == 30
        assert not agent.running
        assert agent.stats["tasks_reviewed"] == 0

    def test_test_mode(self, mock_db, mock_review_engine):
        """Test that test mode uses shorter intervals"""
        agent = ReviewAgent(db=mock_db, review_engine=mock_review_engine, polling_interval=30, test_mode=True)

        assert agent.polling_interval == 5  # Should be reduced in test mode

    @pytest.mark.asyncio
    async def test_process_empty_queue_async(self, agent, mock_adapter):
        """Test processing when queue is empty"""
        mock_adapter.get_pending_reviews.return_value = []

        await agent._process_review_queue()

        mock_adapter.get_pending_reviews.assert_called_once()
        agent.review_engine.review_task.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_single_task_async(self, agent, mock_adapter):
        """Test processing a single task"""
        # Create a mock task
        mock_task = Mock(spec=Task)
        mock_task.id = "task-001"
        mock_task.description = "Test task"
        mock_task.status = TaskStatus.REVIEW_PENDING

        mock_adapter.get_pending_reviews.return_value = [mock_task]

        await agent._process_review_queue()

        # Verify the task was processed
        mock_adapter.get_pending_reviews.assert_called_once()
        agent.review_engine.review_task.assert_called_once()
        mock_adapter.update_task_status.assert_called_once()

        # Check statistics
        assert agent.stats["tasks_reviewed"] == 1
        assert agent.stats["approved"] == 1  # Based on mock review result

    @pytest.mark.asyncio
    async def test_review_task_approve_async(self, agent, mock_adapter):
        """Test reviewing a task that gets approved"""
        mock_task = Mock(spec=Task)
        mock_task.id = "approve-001"
        mock_task.description = "Good code"

        await agent._review_task(mock_task)

        # Verify review was performed
        agent.review_engine.review_task.assert_called_once_with(
            task_id="approve-001",
            task_description="Good code",
            code_files={"main.py": "def test(): pass"},
            test_results={"passed": True},
            transcript="Task completed successfully",
        )

        # Verify status was updated
        mock_adapter.update_task_status.assert_called_once()
        call_args = mock_adapter.update_task_status.call_args[0]
        assert call_args[0] == "approve-001"
        assert call_args[1] == TaskStatus.APPROVED

    @pytest.mark.asyncio
    async def test_review_task_reject_async(self, agent, mock_adapter, mock_review_engine):
        """Test reviewing a task that gets rejected"""
        # Override the review result to reject
        metrics = QualityMetrics(code_quality=40, test_coverage=30, documentation=20, security=50, architecture=40)

        mock_review_engine.review_task.return_value = ReviewResult(
            task_id="reject-001",
            decision=ReviewDecision.REJECT,
            metrics=metrics,
            summary="Code quality too low",
            issues=["No tests", "Security issues"],
            suggestions=["Add tests", "Fix security"],
            confidence=0.9,
        )

        mock_task = Mock(spec=Task)
        mock_task.id = "reject-001"
        mock_task.description = "Poor code"

        await agent._review_task(mock_task)

        # Verify status was updated to rejected
        mock_adapter.update_task_status.assert_called_once()
        call_args = mock_adapter.update_task_status.call_args[0]
        assert call_args[1] == TaskStatus.REJECTED

        # Check statistics
        assert agent.stats["rejected"] == 1

    @pytest.mark.asyncio
    async def test_review_task_no_code_files_async(self, agent, mock_adapter):
        """Test handling task with no code files"""
        mock_task = Mock(spec=Task)
        mock_task.id = "empty-001"
        mock_task.description = "Empty task"

        mock_adapter.get_task_code_files.return_value = {}

        await agent._review_task(mock_task)

        # Should escalate when no code files found
        mock_adapter.update_task_status.assert_called_once()
        call_args = mock_adapter.update_task_status.call_args[0]
        assert call_args[1] == TaskStatus.ESCALATED
        assert agent.stats["escalated"] == 1

    @pytest.mark.asyncio
    async def test_review_task_error_handling_async(self, agent, mock_adapter, mock_review_engine):
        """Test error handling during review"""
        mock_task = Mock(spec=Task)
        mock_task.id = "error-001"
        mock_task.description = "Error task"

        # Make review engine raise an error
        mock_review_engine.review_task.side_effect = Exception("Review failed")

        await agent._review_task(mock_task)

        # Should escalate on error
        mock_adapter.update_task_status.assert_called()
        call_args = mock_adapter.update_task_status.call_args[0]
        assert call_args[1] == TaskStatus.ESCALATED
        assert agent.stats["errors"] == 1

    def test_update_stats_for_decision(self, agent):
        """Test statistics update for different decisions"""
        agent._update_stats_for_decision(ReviewDecision.APPROVE)
        assert agent.stats["approved"] == 1

        agent._update_stats_for_decision(ReviewDecision.REJECT)
        assert agent.stats["rejected"] == 1

        agent._update_stats_for_decision(ReviewDecision.REWORK)
        assert agent.stats["rework"] == 1

        agent._update_stats_for_decision(ReviewDecision.ESCALATE)
        assert agent.stats["escalated"] == 1

    def test_percentage_calculation(self, agent):
        """Test percentage calculation for statistics"""
        assert agent._pct("approved") == 0  # No tasks reviewed yet

        agent.stats["tasks_reviewed"] = 10
        agent.stats["approved"] = 7
        assert agent._pct("approved") == 70

        agent.stats["rejected"] = 2
        assert agent._pct("rejected") == 20

    @pytest.mark.asyncio
    async def test_shutdown_async(self, agent):
        """Test graceful shutdown"""
        agent.stats["start_time"] = datetime.now()
        agent.stats["tasks_reviewed"] = 5
        agent.stats["approved"] = 3
        agent.stats["rejected"] = 2

        await agent._shutdown()

        # Should complete without errors
        assert True  # If we get here, shutdown worked

    @pytest.mark.asyncio
    async def test_signal_handler_async(self, agent):
        """Test signal handler sets running to False"""
        agent.running = True
        agent._signal_handler(2, None)  # SIGINT
        assert not agent.running


class TestDatabaseAdapter:
    """Test the DatabaseAdapter class"""

    def test_get_pending_reviews(self, mock_db):
        """Test fetching pending reviews"""
        adapter = (DatabaseAdapter(mock_db),)

        mock_session = MagicMock()
        mock_db.get_session.return_value.__enter__.return_value = mock_session

        # Create mock query chain
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = ["task1", "task2"]

        result = adapter.get_pending_reviews(limit=5)

        assert result == ["task1", "task2"]
        mock_query.limit.assert_called_with(5)

    def test_update_task_status(self, mock_db):
        """Test updating task status"""
        adapter = (DatabaseAdapter(mock_db),)

        mock_session = MagicMock()
        mock_db.get_session.return_value.__enter__.return_value = mock_session

        # Create mock task
        mock_task = MagicMock(spec=Task)
        mock_task.id = "test-123"
        mock_task.result_data = {}
        mock_task.metadata = {}

        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = mock_task

        review_data = {"score": 85, "decision": "approve"}
        result = adapter.update_task_status("test-123", TaskStatus.APPROVED, review_data)

        assert result
        assert mock_task.status == TaskStatus.APPROVED
        assert mock_task.result_data["review"] == review_data
        mock_session.commit.assert_called_once()
