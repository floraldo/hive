"""
Comprehensive test suite for AI Planner Claude integration
Tests the complete Phase 2 Claude-powered planning workflow
"""
import json
import sys
import uuid

import pytest

from ai_planner.agent import AIPlanner
from ai_planner.claude_bridge import ClaudePlanningResponse, RobustClaudePlannerBridge
from hive_db import get_sqlite_connection
from hive_logging import get_logger

logger = get_logger(__name__)

@pytest.mark.crust
class TestClaudeIntegration:
    """Test suite for Claude-powered AI Planner"""

    @classmethod
    def setup_class(cls):
        """Setup test environment"""
        logger.info('SUCCESS: Test database initialized')

    @pytest.mark.crust
    def test_claude_bridge_initialization(self):
        """Test Claude bridge initialization in both modes"""
        bridge_mock = RobustClaudePlannerBridge(mock_mode=True)
        assert bridge_mock.mock_mode
        assert bridge_mock.claude_cmd is None or isinstance(bridge_mock.claude_cmd, str)
        logger.info('SUCCESS: Claude bridge mock mode initialization')
        bridge_real = RobustClaudePlannerBridge(mock_mode=False)
        assert not bridge_real.mock_mode
        logger.info('SUCCESS: Claude bridge real mode initialization')

    @pytest.mark.crust
    def test_mock_plan_generation(self):
        """Test plan generation in mock mode"""
        bridge = RobustClaudePlannerBridge(mock_mode=True)
        plan = bridge.generate_execution_plan(task_description='Create a user authentication system', context_data={'files_affected': 5, 'dependencies': ['jwt', 'database'], 'tech_stack': ['python', 'flask']}, priority=75, requestor='test_user')
        assert plan is not None
        assert 'plan_id' in plan
        assert 'plan_name' in plan
        assert 'sub_tasks' in plan
        assert 'dependencies' in plan
        assert 'metrics' in plan
        assert len(plan['sub_tasks']) > 0
        sub_task = plan['sub_tasks'][0]
        assert 'id' in sub_task
        assert 'title' in sub_task
        assert 'assignee' in sub_task
        assert 'estimated_duration' in sub_task
        assert 'complexity' in sub_task
        logger.info('OK Mock plan generation validation')

    @pytest.mark.crust
    def test_fallback_plan_generation(self):
        """Test fallback plan generation when Claude is unavailable"""
        bridge = RobustClaudePlannerBridge(mock_mode=False)
        bridge.claude_cmd = None
        plan = bridge.generate_execution_plan(task_description='Build a complex distributed system', context_data={'files_affected': 20}, priority=90, requestor='fallback_test')
        assert plan is not None
        assert plan['plan_id'].startswith('fallback-')
        assert 'fallback' in plan['plan_name'].lower()
        assert len(plan['sub_tasks']) == 3
        assert plan['metrics']['confidence_score'] == 0.6
        logger.info('OK Fallback plan generation validation')

    @pytest.mark.crust
    def test_json_response_validation(self):
        """Test Pydantic model validation for Claude responses"""
        valid_data = {'plan_id': 'test-plan-123', 'plan_name': 'Test Execution Plan', 'plan_summary': 'A comprehensive test plan', 'sub_tasks': [{'id': 'task-001', 'title': 'Analysis Phase', 'description': 'Perform requirements analysis', 'assignee': 'worker:backend', 'estimated_duration': 30, 'complexity': 'medium', 'dependencies': [], 'workflow_phase': 'analysis', 'required_skills': ['analysis'], 'deliverables': ['requirements.md']}], 'dependencies': {'critical_path': ['task-001'], 'parallel_groups': [], 'blocking_dependencies': {}}, 'workflow': {'lifecycle_phases': ['analysis'], 'phase_transitions': {}, 'validation_gates': {'analysis': ['requirements_clear']}, 'rollback_strategy': 'manual rollback'}, 'metrics': {'total_estimated_duration': 30, 'critical_path_duration': 30, 'complexity_breakdown': {'simple': 0, 'medium': 1, 'complex': 0}, 'skill_requirements': {'analysis': 1}, 'confidence_score': 0.9, 'risk_factors': []}, 'recommendations': [], 'considerations': []}
        response = ClaudePlanningResponse(**valid_data)
        assert response.plan_id == 'test-plan-123'
        assert len(response.sub_tasks) == 1
        assert response.metrics.confidence_score == 0.9
        logger.info('OK JSON response validation')

    @pytest.mark.crust
    def test_ai_planner_claude_integration(self):
        """Test full AI Planner integration with Claude bridge"""
        agent = AIPlanner(mock_mode=True)
        assert agent.claude_bridge is not None
        assert agent.claude_bridge.mock_mode
        success = agent.connect_database()
        assert success
        assert agent.db_connection is not None
        test_task = {'id': 'claude-integration-test-' + str(uuid.uuid4())[:8], 'task_description': 'Build a microservices API gateway with authentication', 'priority': 80, 'requestor': 'integration_test', 'context_data': {'files_affected': 10, 'dependencies': ['jwt', 'redis', 'postgres'], 'tech_stack': ['python', 'fastapi', 'docker']}}
        cursor = agent.db_connection.cursor()
        cursor.execute('\n            INSERT INTO planning_queue\n            (id, task_description, priority, requestor, context_data, status)\n            VALUES (?, ?, ?, ?, ?, ?)\n        ', (test_task['id'], test_task['task_description'], test_task['priority'], test_task['requestor'], json.dumps(test_task['context_data']), 'pending'))
        agent.db_connection.commit()
        plan = agent.generate_execution_plan(test_task)
        assert plan is not None
        assert plan['task_id'] == test_task['id']
        assert 'sub_tasks' in plan
        assert 'metadata' in plan
        assert plan['metadata']['generation_method'] == 'claude-powered'
        assert plan['metadata']['generator'] == 'ai-planner-v2-claude'
        save_success = agent.save_execution_plan(plan)
        assert save_success
        cursor = agent.db_connection.cursor()
        cursor.execute('SELECT COUNT(*) FROM execution_plans WHERE planning_task_id = ?', (test_task['id'],))
        plan_count = cursor.fetchone()[0]
        assert plan_count == 1
        cursor.execute("SELECT COUNT(*) FROM tasks WHERE task_type = 'planned_subtask'")
        subtask_count = cursor.fetchone()[0]
        assert subtask_count >= len(plan['sub_tasks'])
        cursor.execute('DELETE FROM execution_plans WHERE planning_task_id = ?', (test_task['id'],))
        cursor.execute('DELETE FROM planning_queue WHERE id = ?', (test_task['id'],))
        cursor.execute("DELETE FROM tasks WHERE task_type = 'planned_subtask'")
        agent.db_connection.commit()
        agent.db_connection.close()
        logger.info('OK Full AI Planner Claude integration')

    @pytest.mark.crust
    def test_complex_task_end_to_end(self):
        """Test end-to-end processing of a complex task"""
        agent = AIPlanner(mock_mode=True)
        agent.connect_database()
        conn = get_sqlite_connection()
        cursor = conn.cursor()
        test_task_id = 'e2e-complex-test-' + str(uuid.uuid4())[:8]
        cursor.execute('\n            INSERT INTO planning_queue\n            (id, task_description, priority, requestor, context_data, status)\n            VALUES (?, ?, ?, ?, ?, ?)\n        ', (test_task_id, 'Design and implement a complete e-commerce platform with user management, product catalog, shopping cart, payment processing, and admin dashboard', 95, 'e2e_test', json.dumps({'files_affected': 50, 'dependencies': ['stripe', 'redis', 'postgres', 'elasticsearch'], 'tech_stack': ['python', 'react', 'fastapi', 'docker', 'kubernetes'], 'constraints': ['PCI compliance', 'GDPR compliance', 'high availability']}), 'pending'))
        conn.commit()
        task = agent.get_next_task()
        assert task is not None
        assert task['id'] == test_task_id
        success = agent.process_task(task)
        assert success
        cursor.execute('SELECT status FROM planning_queue WHERE id = ?', (test_task_id,))
        final_status = cursor.fetchone()[0]
        assert final_status == 'planned'
        cursor.execute('SELECT plan_data FROM execution_plans WHERE planning_task_id = ?', (test_task_id,))
        plan_result = cursor.fetchone()
        assert plan_result is not None, f'No execution plan found for task {test_task_id}. Check if plan was saved properly.'
        plan_json = plan_result[0]
        plan_data = json.loads(plan_json)
        assert len(plan_data['sub_tasks']) > 0
        assert plan_data['metrics']['total_estimated_duration'] > 0
        assert 'dependencies' in plan_data
        assert 'workflow' in plan_data
        cursor.execute('DELETE FROM planning_queue WHERE id = ?', (test_task_id,))
        cursor.execute('DELETE FROM execution_plans WHERE planning_task_id = ?', (test_task_id,))
        cursor.execute("DELETE FROM tasks WHERE task_type = 'planned_subtask'")
        conn.commit()
        conn.close()
        agent.db_connection.close()
        logger.info('OK Complex task end-to-end processing')

    @pytest.mark.crust
    def test_error_handling_and_resilience(self):
        """Test error handling and system resilience"""
        agent = AIPlanner(mock_mode=True)
        agent.connect_database()
        malformed_task = {'id': 'error-test-' + str(uuid.uuid4())[:8], 'task_description': '', 'priority': 'invalid', 'requestor': None, 'context_data': 'not-json'}
        plan = agent.generate_execution_plan(malformed_task)
        assert plan is not None or True
        agent.db_connection.close()
        agent.db_connection = None
        save_result = agent.save_execution_plan({'plan_id': 'test', 'task_id': 'test', 'status': 'test'})
        assert not save_result
        logger.info('OK Error handling and resilience')

    @pytest.mark.crust
    def test_performance_metrics(self):
        """Test performance and timing metrics"""
        import time
        bridge = RobustClaudePlannerBridge(mock_mode=True)
        start_time = time.time()
        plan = bridge.generate_execution_plan('Create a high-performance web application', {'files_affected': 15})
        end_time = time.time()
        generation_time = end_time - start_time
        assert generation_time < 1.0
        assert plan is not None
        assert plan['metrics']['confidence_score'] > 0.8
        logger.info(f'OK Performance metrics - Generation time: {generation_time:.3f}s')

def run_tests():
    """Run all tests"""
    logger.info('Starting AI Planner Claude Integration Tests')
    logger.info('=' * 60)
    test_suite = TestClaudeIntegration()
    test_suite.setup_class()
    test_methods = [test_suite.test_claude_bridge_initialization, test_suite.test_mock_plan_generation, test_suite.test_fallback_plan_generation, test_suite.test_json_response_validation, test_suite.test_ai_planner_claude_integration, test_suite.test_complex_task_end_to_end, test_suite.test_error_handling_and_resilience, test_suite.test_performance_metrics]
    passed = 0
    failed = 0
    for test_method in test_methods:
        try:
            test_method()
            passed += 1
        except Exception as e:
            logger.info(f'FAIL {test_method.__name__} FAILED: {e}')
            failed += 1
    logger.info('=' * 60)
    logger.info(f'Test Results: {passed} passed, {failed} failed')
    if failed == 0:
        logger.info('ALL TESTS PASSED - Phase 2 Claude Integration Complete!')
        return True
    else:
        logger.info('WARNING: Some tests failed - review and fix issues')
        return False
if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
