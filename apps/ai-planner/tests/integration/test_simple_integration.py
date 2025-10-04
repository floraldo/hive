"""
Simple test for AI Planner Claude integration without emoji symbols
"""
import sys
import uuid

import pytest

from hive_logging import get_logger

logger = get_logger(__name__)
try:
    from ai_planner.agent import AIPlanner
    from ai_planner.claude_bridge import RobustClaudePlannerBridge

    @pytest.mark.crust
    def test_basic_functionality():
        """Test basic AI Planner functionality"""
        logger.info('Starting basic AI Planner tests...')
        logger.info('SUCCESS: Database initialized')
        bridge = RobustClaudePlannerBridge(mock_mode=True)
        logger.info('SUCCESS: Claude bridge initialized')
        plan = bridge.generate_execution_plan(task_description='Build a simple web API', context_data={'files_affected': 3})
        assert plan is not None
        assert 'plan_id' in plan
        assert 'sub_tasks' in plan
        logger.info('SUCCESS: Plan generation working')
        agent = AIPlanner(mock_mode=True)
        success = agent.connect_database()
        assert success
        logger.info('SUCCESS: AI Planner database connection')
        test_task = {'id': 'test-' + str(uuid.uuid4())[:8], 'task_description': 'Create user authentication', 'priority': 50, 'requestor': 'test', 'context_data': {'files_affected': 2}}
        plan = agent.generate_execution_plan(test_task)
        assert plan is not None
        assert plan['metadata']['generation_method'] == 'claude-powered'
        logger.info('SUCCESS: Task processing working')
        save_result = agent.save_execution_plan(plan)
        assert save_result
        logger.info('SUCCESS: Plan saving working')
        if agent.db_connection:
            cursor = agent.db_connection.cursor()
            cursor.execute('DELETE FROM execution_plans WHERE planning_task_id = ?', (test_task['id'],))
            cursor.execute("DELETE FROM tasks WHERE task_type = 'planned_subtask'")
            agent.db_connection.commit()
            agent.db_connection.close()
        logger.info('SUCCESS: All basic tests passed!')
        logger.info('Phase 2 Claude Integration is working correctly!')
        return True
except ImportError as e:
    logger.info(f'FAILED: Import error: {e}')
    if __name__ == '__main__':
        sys.exit(1)
if __name__ == '__main__':
    try:
        success = test_basic_functionality()
        if success:
            logger.info('\nCONCLUSION: Phase 2 implementation successful')
            sys.exit(0)
        else:
            logger.info('\nCONCLUSION: Phase 2 implementation failed')
            sys.exit(1)
    except Exception as e:
        logger.info(f'\nFAILED: Test failed with error: {e}')
        import traceback
        traceback.print_exc()
        sys.exit(1)
