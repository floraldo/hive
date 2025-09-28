"""
Integration tests for the complete AI Reviewer system
"""

import asyncio
from datetime import datetime
from unittest.mock import MagicMock, Mock, patch

import pytest
from ai_reviewer import ReviewAgent, ReviewEngine
from ai_reviewer.database_adapter import DatabaseAdapter
from hive_db import Task, TaskStatus


class TestIntegration:
    """Integration tests for the AI Reviewer system"""

    @pytest.mark.asyncio
    async def test_full_review_workflow(self):
        """Test complete review workflow from pending to approved"""
        # Create mock database
        mock_db = Mock()
        mock_session = MagicMock()
        mock_db.get_session.return_value.__enter__.return_value = mock_session

        # Create mock task
        mock_task = MagicMock(spec=Task)
        mock_task.id = "integration-001"
        mock_task.description = "Implement feature X"
        mock_task.status = TaskStatus.REVIEW_PENDING
        mock_task.result_data = {
            "files": {
                "feature.py": '''
def calculate_total(items):
    """Calculate total of items."""
    return sum(item.price for item in items)

def validate_input(data):
    """Validate input data."""
    if not data:
        raise ValueError("Data cannot be empty")
    return True
''',
                "test_feature.py": '''
import pytest
from feature import calculate_total, validate_input

def test_calculate_total():
    """Test total calculation."""
    Item = namedtuple('Item', ['price'])
    items = [Item(10), Item(20), Item(30)]
    assert calculate_total(items) == 60

def test_validate_input():
    """Test input validation."""
    assert validate_input({"key": "value"}) == True
    with pytest.raises(ValueError):
        validate_input(None)
''',
            },
            "test_results": {"passed": True, "coverage": 85},
        }
        mock_task.metadata = {}

        # Setup mock query chain
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = [mock_task]
        mock_query.first.return_value = mock_task

        # Create real components
        review_engine = ReviewEngine()
        agent = ReviewAgent(
            db=mock_db, review_engine=review_engine, polling_interval=1, test_mode=True
        )

        # Run one review cycle
        await agent._process_review_queue()

        # Verify task was processed
        assert agent.stats["tasks_reviewed"] == 1

        # Check that status was updated (approved due to good code)
        assert mock_task.status == TaskStatus.APPROVED
        assert "review" in mock_task.result_data
        assert mock_task.result_data["reviewed_by"] == "ai-reviewer"

        # Verify review quality
        review = mock_task.result_data["review"]
        assert review["decision"] == "approve"
        assert review["overall_score"] > 60

    @pytest.mark.asyncio
    async def test_escalation_workflow(self):
        """Test that problematic tasks get escalated"""
        # Create mock database
        mock_db = Mock()
        mock_session = MagicMock()
        mock_db.get_session.return_value.__enter__.return_value = mock_session

        # Create task with problematic code
        mock_task = MagicMock(spec=Task)
        mock_task.id = "escalate-001"
        mock_task.description = "Problematic task"
        mock_task.status = TaskStatus.REVIEW_PENDING
        mock_task.result_data = {
            "files": {
                "bad_code.py": """
# TODO: Fix everything
def process():
    eval(user_input)  # Security issue
    password = "admin123"  # Hardcoded password
    try:
        something()
    except:
        pass  # Bare except
"""
            }
        }
        mock_task.metadata = {}

        # Setup mock query
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = [mock_task]
        mock_query.first.return_value = mock_task

        # Create components
        review_engine = ReviewEngine()
        agent = ReviewAgent(
            db=mock_db, review_engine=review_engine, polling_interval=1, test_mode=True
        )

        # Process the task
        await agent._process_review_queue()

        # Should be rejected due to security issues
        assert mock_task.status == TaskStatus.REJECTED
        assert agent.stats["rejected"] == 1

        # Check review details
        review = mock_task.result_data["review"]
        assert review["decision"] == "reject"
        assert len(review["issues"]) > 0
        assert any("security" in str(issue).lower() for issue in review["issues"])

    def test_review_engine_standalone(self):
        """Test review engine can be used standalone"""
        engine = ReviewEngine()

        # Review some code
        result = engine.review_task(
            task_id="standalone-001",
            task_description="Test standalone usage",
            code_files={"main.py": "def hello(): return 'world'"},
        )

        # Should produce valid result
        assert result.task_id == "standalone-001"
        assert result.decision in [
            ReviewDecision.APPROVE,
            ReviewDecision.REJECT,
            ReviewDecision.REWORK,
            ReviewDecision.ESCALATE,
        ]
        assert 0 <= result.metrics.overall_score <= 100
        assert 0 <= result.confidence <= 1

    @pytest.mark.asyncio
    async def test_agent_lifecycle(self):
        """Test agent start, run, and shutdown lifecycle"""
        mock_db = Mock()
        mock_session = MagicMock()
        mock_db.get_session.return_value.__enter__.return_value = mock_session

        # Setup empty queue
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []  # Empty queue

        # Create agent
        review_engine = ReviewEngine()
        agent = ReviewAgent(
            db=mock_db,
            review_engine=review_engine,
            polling_interval=0.1,  # Very short for testing
            test_mode=True,
        )

        # Start agent in background
        agent.running = True
        agent.stats["start_time"] = datetime.now()

        # Process one cycle
        await agent._process_review_queue()

        # Should handle empty queue gracefully
        assert agent.stats["tasks_reviewed"] == 0
        assert agent.stats["errors"] == 0

        # Shutdown
        agent.running = False
        await agent._shutdown()

        # Should complete without errors
        assert True


class TestRealDatabaseIntegration:
    """
    Tests that would run against a real database
    (Skipped by default, run with --integration flag)
    """

    @pytest.mark.skip(reason="Requires real database connection")
    @pytest.mark.asyncio
    async def test_real_database_operations(self):
        """Test with actual database operations"""
        from hive_config import HiveConfig
        from hive_db import HiveDatabase

        config = HiveConfig()
        db = HiveDatabase(config.database_url)

        # Create adapter
        adapter = DatabaseAdapter(db)

        # Test fetching pending reviews
        pending = adapter.get_pending_reviews(limit=5)
        assert isinstance(pending, list)

        # If there are pending tasks, test processing one
        if pending:
            task = pending[0]

            # Get artifacts
            code_files = adapter.get_task_code_files(task.id)
            test_results = adapter.get_test_results(task.id)
            transcript = adapter.get_task_transcript(task.id)

            assert isinstance(code_files, dict)

            # Perform review
            engine = ReviewEngine()
            result = engine.review_task(
                task_id=task.id,
                task_description=task.description,
                code_files=code_files,
                test_results=test_results,
                transcript=transcript,
            )

            # Store results (but don't commit in test)
            # adapter.update_task_status(
            #     task.id,
            #     TaskStatus.APPROVED,
            #     result.to_dict()
            # )

    @pytest.mark.skip(reason="Requires real database and API key")
    @pytest.mark.asyncio
    async def test_full_system_with_ai(self):
        """Test the complete system with real AI capabilities"""
        from hive_config import HiveConfig
        from hive_db import HiveDatabase

        config = HiveConfig()
        db = HiveDatabase(config.database_url)

        # Create agent with mock mode for testing
        review_engine = ReviewEngine(mock_mode=True)
        agent = ReviewAgent(
            db=db, review_engine=review_engine, polling_interval=5, test_mode=True
        )

        # Run for one cycle
        await agent._process_review_queue()

        # Check results
        print(f"Processed {agent.stats['tasks_reviewed']} tasks")
        print(f"Approved: {agent.stats['approved']}")
        print(f"Rejected: {agent.stats['rejected']}")
        print(f"Errors: {agent.stats['errors']}")
