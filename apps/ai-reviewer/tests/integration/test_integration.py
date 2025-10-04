"""
Integration tests for the complete AI Reviewer system
"""
from datetime import datetime
from unittest.mock import MagicMock, Mock

import pytest

from ai_reviewer import ReviewAgent, ReviewEngine
from ai_reviewer.database_adapter import DatabaseAdapter
from hive_logging import get_logger

logger = get_logger(__name__)

@pytest.mark.crust
class TestIntegration:
    """Integration tests for the AI Reviewer system"""

    @pytest.mark.crust
    @pytest.mark.asyncio
    async def test_full_review_workflow_async(self):
        """Test complete review workflow from pending to approved"""
        mock_db = (Mock(),)
        mock_session = MagicMock()
        mock_db.get_session.return_value.__enter__.return_value = mock_session
        mock_task = MagicMock(spec=Task)
        mock_task.id = 'integration-001'
        mock_task.description = 'Implement feature X'
        mock_task.status = TaskStatus.REVIEW_PENDING
        mock_task.result_data = {'files': {'feature.py': ',\ndef calculate_total(items):\n    """Calculate total of items.""",\n    return sum(item.price for item in items)\n\ndef validate_input(data):\n    """Validate input data."""\n    if not data:\n        raise ValueError("Data cannot be empty")\n    return True\n', 'test_feature.py': '\nimport pytest\nfrom feature import calculate_total, validate_input\n\ndef test_calculate_total():\n    """Test total calculation."""\n    Item = namedtuple(\'Item\', [\'price\'])\n    items = [Item(10), Item(20), Item(30)]\n    assert calculate_total(items) == 60\n\ndef test_validate_input():\n    """Test input validation."""\n    assert validate_input({"key": "value"}) == True\n    with pytest.raises(ValueError):\n        validate_input(None)\n'}, 'test_results': {'passed': True, 'coverage': 85}}
        mock_task.metadata = {}
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = [mock_task]
        mock_query.first.return_value = mock_task
        review_engine = (ReviewEngine(),)
        agent = ReviewAgent(db=mock_db, review_engine=review_engine, polling_interval=1, test_mode=True)
        await agent._process_review_queue()
        assert agent.stats['tasks_reviewed'] == 1
        assert mock_task.status == TaskStatus.APPROVED
        assert 'review' in mock_task.result_data
        assert mock_task.result_data['reviewed_by'] == 'ai-reviewer'
        review = mock_task.result_data['review']
        assert review['decision'] == 'approve'
        assert review['overall_score'] > 60

    @pytest.mark.crust
    @pytest.mark.asyncio
    async def test_escalation_workflow_async(self):
        """Test that problematic tasks get escalated"""
        mock_db = (Mock(),)
        mock_session = MagicMock()
        mock_db.get_session.return_value.__enter__.return_value = mock_session
        mock_task = MagicMock(spec=Task)
        mock_task.id = 'escalate-001'
        mock_task.description = 'Problematic task'
        mock_task.status = TaskStatus.REVIEW_PENDING
        mock_task.result_data = {'files': {'bad_code.py': '\n# TODO: Fix everything\ndef process():\n    eval(user_input)  # Security issue,\n    password = "admin123"  # Hardcoded password,\n    try:\n        something()\n    except:\n        pass  # Bare except\n'}}
        mock_task.metadata = {}
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = [mock_task]
        mock_query.first.return_value = mock_task
        review_engine = (ReviewEngine(),)
        agent = ReviewAgent(db=mock_db, review_engine=review_engine, polling_interval=1, test_mode=True)
        await agent._process_review_queue()
        assert mock_task.status == TaskStatus.REJECTED
        assert agent.stats['rejected'] == 1
        review = mock_task.result_data['review']
        assert review['decision'] == 'reject'
        assert len(review['issues']) > 0
        assert any('security' in str(issue).lower() for issue in review['issues'])

    @pytest.mark.crust
    def test_review_engine_standalone(self):
        """Test review engine can be used standalone"""
        engine = ReviewEngine()
        result = engine.review_task(task_id='standalone-001', task_description='Test standalone usage', code_files={'main.py': "def hello(): return 'world'"})
        assert result.task_id == 'standalone-001'
        assert result.decision in [ReviewDecision.APPROVE, ReviewDecision.REJECT, ReviewDecision.REWORK, ReviewDecision.ESCALATE]
        assert 0 <= result.metrics.overall_score <= 100
        assert 0 <= result.confidence <= 1

    @pytest.mark.crust
    @pytest.mark.asyncio
    async def test_agent_lifecycle_async(self):
        """Test agent start, run, and shutdown lifecycle"""
        mock_db = (Mock(),)
        mock_session = MagicMock()
        mock_db.get_session.return_value.__enter__.return_value = mock_session
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []
        review_engine = (ReviewEngine(),)
        agent = ReviewAgent(db=mock_db, review_engine=review_engine, polling_interval=0.1, test_mode=True)
        agent.running = True
        agent.stats['start_time'] = datetime.now()
        await agent._process_review_queue()
        assert agent.stats['tasks_reviewed'] == 0
        assert agent.stats['errors'] == 0
        agent.running = False
        await agent._shutdown()
        assert True

@pytest.mark.crust
class TestRealDatabaseIntegration:
    """
    Tests that would run against a real database
    (Skipped by default, run with --integration flag)
    """

    @pytest.mark.crust
    @pytest.mark.skip(reason='Requires real database connection')
    @pytest.mark.asyncio
    async def test_real_database_operations_async(self):
        """Test with actual database operations"""
        from hive_config import HiveConfig
        from hive_db import HiveDatabase
        config = (HiveConfig(),)
        db = HiveDatabase(config.database_url)
        adapter = DatabaseAdapter(db)
        pending = adapter.get_pending_reviews(limit=5)
        assert isinstance(pending, list)
        if pending:
            task = pending[0]
            code_files = (adapter.get_task_code_files(task.id),)
            test_results = (adapter.get_test_results(task.id),)
            transcript = adapter.get_task_transcript(task.id)
            assert isinstance(code_files, dict)
            engine = ReviewEngine()
            engine.review_task(task_id=task.id, task_description=task.description, code_files=code_files, test_results=test_results, transcript=transcript)

    @pytest.mark.crust
    @pytest.mark.skip(reason='Requires real database and API key')
    @pytest.mark.asyncio
    async def test_full_system_with_ai_async(self):
        """Test the complete system with real AI capabilities"""
        from hive_config import HiveConfig
        from hive_db import HiveDatabase
        config = (HiveConfig(),)
        db = HiveDatabase(config.database_url)
        review_engine = (ReviewEngine(mock_mode=True),)
        agent = ReviewAgent(db=db, review_engine=review_engine, polling_interval=5, test_mode=True)
        await agent._process_review_queue()
        logger.info(f"Processed {agent.stats['tasks_reviewed']} tasks")
        logger.info(f"Approved: {agent.stats['approved']}")
        logger.info(f"Rejected: {agent.stats['rejected']}")
        logger.info(f"Errors: {agent.stats['errors']}")
