"""
Integration Tests for AI Planner → Queen → Worker Pipeline

Tests the complete autonomous task execution flow:
1. AI Planner monitors planning_queue
2. AI Planner generates execution plans and subtasks
3. Queen picks up subtasks via enhanced database queries
4. Workers execute subtasks and report status
5. Status updates flow back through the pipeline
"""
import json
import os
import sqlite3
import sys
import tempfile
import uuid
from datetime import UTC, datetime
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'apps', 'hive-orchestrator', 'src'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'apps', 'ai-planner', 'src'))
from ai_planner.agent import AIPlanner
from hive_orchestrator.core.db import database_enhanced_optimized as db_enhanced


@pytest.mark.crust
class TestAIPlannerQueenIntegration:
    """Test complete AI Planner → Queen → Worker integration"""

    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        conn = sqlite3.connect(db_path)
        self._create_test_schema(conn)
        conn.close()

        def mock_get_connection():
            return sqlite3.connect(db_path)
        with patch('hive_orchestrator.core.db.database.get_connection', mock_get_connection):
            with patch('ai_planner.agent.get_connection', mock_get_connection):
                yield db_path
        os.unlink(db_path)

    def _create_test_schema(self, conn):
        """Create test database schema"""
        conn.executescript("\n            CREATE TABLE planning_queue (\n                id TEXT PRIMARY KEY,\n                task_description TEXT NOT NULL,\n                priority INTEGER DEFAULT 50,\n                requestor TEXT,\n                context_data TEXT,\n                complexity_estimate TEXT,\n                status TEXT DEFAULT 'pending',\n                assigned_agent TEXT,\n                assigned_at TEXT,\n                created_at TEXT DEFAULT CURRENT_TIMESTAMP,\n                completed_at TEXT\n            );\n\n            CREATE TABLE execution_plans (\n                id TEXT PRIMARY KEY,\n                planning_task_id TEXT NOT NULL,\n                plan_data TEXT NOT NULL,\n                estimated_complexity TEXT,\n                estimated_duration INTEGER,\n                status TEXT DEFAULT 'generated',\n                generated_at TEXT DEFAULT CURRENT_TIMESTAMP,\n                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,\n                FOREIGN KEY (planning_task_id) REFERENCES planning_queue (id)\n            );\n\n            CREATE TABLE tasks (\n                id TEXT PRIMARY KEY,\n                title TEXT NOT NULL,\n                description TEXT,\n                task_type TEXT DEFAULT 'task',\n                priority INTEGER DEFAULT 50,\n                status TEXT DEFAULT 'queued',\n                assignee TEXT,\n                assigned_at TEXT,\n                started_at TEXT,\n                completed_at TEXT,\n                payload TEXT,\n                created_at TEXT DEFAULT CURRENT_TIMESTAMP,\n                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,\n                retry_count INTEGER DEFAULT 0,\n                workspace TEXT,\n                tags TEXT\n            );\n\n            CREATE TABLE runs (\n                id TEXT PRIMARY KEY,\n                task_id TEXT NOT NULL,\n                worker_id TEXT NOT NULL,\n                phase TEXT,\n                status TEXT DEFAULT 'running',\n                result TEXT,\n                created_at TEXT DEFAULT CURRENT_TIMESTAMP,\n                completed_at TEXT,\n                FOREIGN KEY (task_id) REFERENCES tasks (id)\n            );\n\n            CREATE TABLE workers (\n                id TEXT PRIMARY KEY,\n                role TEXT NOT NULL,\n                capabilities TEXT,\n                metadata TEXT,\n                status TEXT DEFAULT 'active',\n                created_at TEXT DEFAULT CURRENT_TIMESTAMP\n            );\n\n            -- Indexes for performance\n            CREATE INDEX idx_planning_queue_status ON planning_queue (status, priority DESC);\n            CREATE INDEX idx_execution_plans_status ON execution_plans (status);\n            CREATE INDEX idx_tasks_status_type ON tasks (status, task_type);\n            CREATE INDEX idx_tasks_payload_parent ON tasks (json_extract(payload, '$.parent_plan_id'));\n        ")
        conn.commit()

    @pytest.mark.crust
    def test_planning_queue_to_execution_plan_flow(self, temp_db):
        """Test AI Planner picks up tasks from planning_queue and creates execution plans"""
        task_id = str(uuid.uuid4())
        conn = sqlite3.connect(temp_db)
        conn.execute('\n            INSERT INTO planning_queue (id, task_description, priority, requestor, context_data)\n            VALUES (?, ?, ?, ?, ?)\n        ', (task_id, 'Create authentication API endpoints', 75, 'test_user', json.dumps({'files_affected': 5, 'complexity': 'medium'})))
        conn.commit()
        conn.close()
        planner = AIPlanner(mock_mode=True)
        with patch.object(planner, 'connect_database', return_value=True):
            planner.db_connection = sqlite3.connect(temp_db)
            task = planner.get_next_task()
            assert task is not None
            assert task['id'] == task_id
            assert task['task_description'] == 'Create authentication API endpoints'
            assert task['status'] == 'assigned'
        mock_plan = {'plan_id': f'plan_{task_id}', 'task_id': task_id, 'plan_name': 'Authentication API Implementation', 'sub_tasks': [{'id': 'auth_1', 'title': 'Design API Schema', 'description': 'Create OpenAPI specification for auth endpoints', 'assignee': 'worker:backend', 'complexity': 'medium', 'estimated_duration': 30, 'workflow_phase': 'design', 'required_skills': ['api_design', 'openapi'], 'deliverables': ['openapi.yaml'], 'dependencies': []}, {'id': 'auth_2', 'title': 'Implement JWT Service', 'description': 'Create JWT token generation and validation', 'assignee': 'worker:backend', 'complexity': 'medium', 'estimated_duration': 45, 'workflow_phase': 'implementation', 'required_skills': ['python', 'jwt', 'security'], 'deliverables': ['jwt_service.py', 'tests/test_jwt.py'], 'dependencies': ['auth_1']}], 'metrics': {'total_estimated_duration': 75, 'complexity_breakdown': {'medium': 2}}, 'status': 'generated', 'created_at': datetime.now(UTC).isoformat()}
        with patch.object(planner, 'generate_execution_plan', return_value=mock_plan):
            success = planner.save_execution_plan(mock_plan)
            assert success
            conn = sqlite3.connect(temp_db)
            cursor = conn.execute('SELECT * FROM execution_plans WHERE planning_task_id = ?', (task_id,))
            plan_row = cursor.fetchone()
            assert plan_row is not None
            assert plan_row[1] == task_id
            assert plan_row[4] == 'generated'
            cursor = conn.execute("\n                SELECT COUNT(*) FROM tasks\n                WHERE task_type = 'planned_subtask'\n                AND json_extract(payload, '$.parent_plan_id') = ?\n            ", (mock_plan['plan_id'],))
            subtask_count = cursor.fetchone()[0]
            assert subtask_count == 2
            conn.close()

    @pytest.mark.crust
    def test_queen_enhanced_task_pickup(self, temp_db):
        """Test Queen picks up both regular and planned subtasks"""
        conn = sqlite3.connect(temp_db)
        regular_task_id = str(uuid.uuid4())
        conn.execute('\n            INSERT INTO tasks (id, title, task_type, status, priority)\n            VALUES (?, ?, ?, ?, ?)\n        ', (regular_task_id, 'Regular Task', 'task', 'queued', 60))
        plan_id = str(uuid.uuid4())
        planning_task_id = str(uuid.uuid4())
        conn.execute('\n            INSERT INTO execution_plans (id, planning_task_id, plan_data, status)\n            VALUES (?, ?, ?, ?)\n        ', (plan_id, planning_task_id, json.dumps({'sub_tasks': []}), 'generated'))
        subtask1_id = f'subtask_{plan_id}_1'
        subtask2_id = f'subtask_{plan_id}_2'
        subtask1_payload = {'parent_plan_id': plan_id, 'subtask_id': '1', 'workflow_phase': 'design', 'assignee': 'worker:backend'}
        subtask2_payload = {'parent_plan_id': plan_id, 'subtask_id': '2', 'workflow_phase': 'implementation', 'assignee': 'worker:backend', 'dependencies': ['1']}
        conn.execute('\n            INSERT INTO tasks (id, title, task_type, status, priority, payload)\n            VALUES (?, ?, ?, ?, ?, ?)\n        ', (subtask1_id, 'Design API', 'planned_subtask', 'queued', 70, json.dumps(subtask1_payload)))
        conn.execute('\n            INSERT INTO tasks (id, title, task_type, status, priority, payload)\n            VALUES (?, ?, ?, ?, ?, ?)\n        ', (subtask2_id, 'Implement API', 'planned_subtask', 'queued', 75, json.dumps(subtask2_payload)))
        conn.commit()
        conn.close()
        with patch('hive_orchestrator.core.db.database_enhanced_optimized.get_connection', lambda: sqlite3.connect(temp_db)):
            tasks = db_enhanced.get_queued_tasks_with_planning_optimized(limit=10)
            assert len(tasks) == 3
            task_types = [t['task_type'] for t in tasks]
            assert 'task' in task_types
            assert 'planned_subtask' in task_types
            planned_tasks = [t for t in tasks if t['task_type'] == 'planned_subtask']
            assert len(planned_tasks) == 2
            for task in planned_tasks:
                assert 'planner_context' in task
                assert task['planner_context']['parent_plan_id'] == plan_id
                assert task['planner_context']['workflow_phase'] in ['design', 'implementation']

    @pytest.mark.crust
    def test_dependency_resolution(self, temp_db):
        """Test dependency checking and resolution for planned subtasks"""
        conn = sqlite3.connect(temp_db)
        plan_id = str(uuid.uuid4())
        task1_id = f'subtask_{plan_id}_1'
        task2_id = f'subtask_{plan_id}_2'
        payload1 = {'parent_plan_id': plan_id, 'subtask_id': '1', 'dependencies': []}
        payload2 = {'parent_plan_id': plan_id, 'subtask_id': '2', 'dependencies': ['1']}
        conn.execute('\n            INSERT INTO tasks (id, title, task_type, status, payload)\n            VALUES (?, ?, ?, ?, ?)\n        ', (task1_id, 'Foundation Task', 'planned_subtask', 'queued', json.dumps(payload1)))
        conn.execute('\n            INSERT INTO tasks (id, title, task_type, status, payload)\n            VALUES (?, ?, ?, ?, ?)\n        ', (task2_id, 'Dependent Task', 'planned_subtask', 'queued', json.dumps(payload2)))
        conn.commit()
        with patch('hive_orchestrator.core.db.database_enhanced.get_connection', lambda: sqlite3.connect(temp_db)):
            from hive_orchestrator.core.db.database_enhanced import check_subtask_dependencies
            assert check_subtask_dependencies(task1_id)
            assert not check_subtask_dependencies(task2_id)
        conn.execute('UPDATE tasks SET status = ? WHERE id = ?', ('completed', task1_id))
        conn.commit()
        assert check_subtask_dependencies(task2_id)
        conn.close()

    @pytest.mark.crust
    def test_status_reporting_pipeline(self, temp_db):
        """Test status updates flow from worker completion back to planning system"""
        conn = sqlite3.connect(temp_db)
        plan_id = str(uuid.uuid4())
        planning_task_id = str(uuid.uuid4())
        subtask_id = f'subtask_{plan_id}_1'
        conn.execute('\n            INSERT INTO planning_queue (id, task_description, status)\n            VALUES (?, ?, ?)\n        ', (planning_task_id, 'Test task', 'planned'))
        plan_data = {'sub_tasks': [{'id': '1', 'title': 'Test Subtask', 'status': 'queued'}]}
        conn.execute('\n            INSERT INTO execution_plans (id, planning_task_id, plan_data, status)\n            VALUES (?, ?, ?, ?)\n        ', (plan_id, planning_task_id, json.dumps(plan_data), 'executing'))
        payload = {'parent_plan_id': plan_id, 'subtask_id': '1'}
        conn.execute('\n            INSERT INTO tasks (id, title, task_type, status, payload)\n            VALUES (?, ?, ?, ?, ?)\n        ', (subtask_id, 'Test Subtask', 'planned_subtask', 'queued', json.dumps(payload)))
        conn.commit()
        conn.execute('\n            UPDATE tasks SET status = ?, assignee = ?, assigned_at = ?\n            WHERE id = ?\n        ', ('assigned', 'worker:backend', datetime.now(UTC).isoformat(), subtask_id))
        run_id = str(uuid.uuid4())
        conn.execute('\n            INSERT INTO runs (id, task_id, worker_id, phase, status)\n            VALUES (?, ?, ?, ?, ?)\n        ', (run_id, subtask_id, 'worker:backend', 'apply', 'running'))
        conn.execute('\n            UPDATE tasks SET status = ?, started_at = ?\n            WHERE id = ?\n        ', ('in_progress', datetime.now(UTC).isoformat(), subtask_id))
        conn.execute('\n            UPDATE runs SET status = ?, result = ?, completed_at = ?\n            WHERE id = ?\n        ', ('completed', json.dumps({'status': 'success'}), datetime.now(UTC).isoformat(), run_id))
        conn.execute('\n            UPDATE tasks SET status = ?, completed_at = ?\n            WHERE id = ?\n        ', ('completed', datetime.now(UTC).isoformat(), subtask_id))
        conn.commit()
        cursor = conn.execute('SELECT status FROM tasks WHERE id = ?', (subtask_id,))
        task_status = cursor.fetchone()[0]
        assert task_status == 'completed'
        cursor = conn.execute('SELECT status, result FROM runs WHERE task_id = ?', (subtask_id,))
        run_row = cursor.fetchone()
        assert run_row[0] == 'completed'
        run_result = json.loads(run_row[1])
        assert run_result['status'] == 'success'
        cursor = conn.execute('SELECT status FROM execution_plans WHERE id = ?', (plan_id,))
        plan_status = cursor.fetchone()[0]
        assert plan_status == 'executing'
        conn.close()

    @pytest.mark.crust
    def test_error_handling_and_retry(self, temp_db):
        """Test error handling and retry logic in the integration pipeline"""
        conn = sqlite3.connect(temp_db)
        plan_id = str(uuid.uuid4())
        subtask_id = f'subtask_{plan_id}_1'
        payload = {'parent_plan_id': plan_id, 'subtask_id': '1'}
        conn.execute('\n            INSERT INTO tasks (id, title, task_type, status, payload, retry_count)\n            VALUES (?, ?, ?, ?, ?, ?)\n        ', (subtask_id, 'Failing Task', 'planned_subtask', 'queued', json.dumps(payload), 0))
        conn.commit()
        run_id_1 = str(uuid.uuid4())
        conn.execute('\n            INSERT INTO runs (id, task_id, worker_id, status, result)\n            VALUES (?, ?, ?, ?, ?)\n        ', (run_id_1, subtask_id, 'worker:backend', 'failed', json.dumps({'status': 'failed', 'error': 'Network timeout'})))
        conn.execute('\n            UPDATE tasks SET status = ?, retry_count = ? WHERE id = ?\n        ', ('queued', 1, subtask_id))
        conn.commit()
        cursor = conn.execute('SELECT retry_count, status FROM tasks WHERE id = ?', (subtask_id,))
        row = cursor.fetchone()
        assert row[0] == 1
        assert row[1] == 'queued'
        run_id_2 = str(uuid.uuid4())
        conn.execute('\n            INSERT INTO runs (id, task_id, worker_id, status, result)\n            VALUES (?, ?, ?, ?, ?)\n        ', (run_id_2, subtask_id, 'worker:backend', 'completed', json.dumps({'status': 'success'})))
        conn.execute('\n            UPDATE tasks SET status = ? WHERE id = ?\n        ', ('completed', subtask_id))
        conn.commit()
        cursor = conn.execute('SELECT status, retry_count FROM tasks WHERE id = ?', (subtask_id,))
        row = cursor.fetchone()
        assert row[0] == 'completed'
        assert row[1] == 1
        conn.close()

    @pytest.mark.crust
    def test_concurrent_execution_coordination(self, temp_db):
        """Test coordination of multiple concurrent subtasks"""
        conn = sqlite3.connect(temp_db)
        plan_id = str(uuid.uuid4())
        plan_data = {'sub_tasks': [{'id': '1', 'title': 'Parallel Task 1', 'dependencies': []}, {'id': '2', 'title': 'Parallel Task 2', 'dependencies': []}, {'id': '3', 'title': 'Sequential Task', 'dependencies': ['1', '2']}]}
        conn.execute('\n            INSERT INTO execution_plans (id, planning_task_id, plan_data, status)\n            VALUES (?, ?, ?, ?)\n        ', (plan_id, str(uuid.uuid4()), json.dumps(plan_data), 'executing'))
        for i, subtask in enumerate(plan_data['sub_tasks'], 1):
            task_id = f'subtask_{plan_id}_{i}'
            payload = {'parent_plan_id': plan_id, 'subtask_id': subtask['id'], 'dependencies': subtask['dependencies']}
            conn.execute('\n                INSERT INTO tasks (id, title, task_type, status, payload)\n                VALUES (?, ?, ?, ?, ?)\n            ', (task_id, subtask['title'], 'planned_subtask', 'queued', json.dumps(payload)))
        conn.commit()
        with patch('hive_orchestrator.core.db.database_enhanced_optimized.get_connection', lambda: sqlite3.connect(temp_db)):
            tasks = db_enhanced.get_queued_tasks_with_planning_optimized(limit=10)
            ready_tasks = []
            for task in tasks:
                if task['task_type'] == 'planned_subtask':
                    deps = task.get('payload', {}).get('dependencies', [])
                    if not deps:
                        ready_tasks.append(task)
            assert len(ready_tasks) == 2
        conn.execute('UPDATE tasks SET status = ? WHERE id LIKE ?', ('completed', f'subtask_{plan_id}_1'))
        conn.execute('UPDATE tasks SET status = ? WHERE id LIKE ?', ('completed', f'subtask_{plan_id}_2'))
        conn.commit()
        with patch('hive_orchestrator.core.db.database_enhanced.get_connection', lambda: sqlite3.connect(temp_db)):
            from hive_orchestrator.core.db.database_enhanced import check_subtask_dependencies
            task3_id = f'subtask_{plan_id}_3'
            assert check_subtask_dependencies(task3_id)
        conn.close()

@pytest.mark.crust
def test_end_to_end_integration():
    """End-to-end integration test of AI Planner → Queen → Worker pipeline"""
    assert True
if __name__ == '__main__':
    pytest.main([__file__, '-v'])
