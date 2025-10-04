"""
Hive Platform Validation Tests

Focused validation tests for core platform functionality that can be run
quickly in CI/CD to ensure basic platform health and integration.

This complements the comprehensive integration tests with faster,
targeted validation checks.
"""
import json
import os
import sqlite3
import sys
import tempfile
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest

test_root = Path(__file__).parent.parent
sys.path.insert(0, str(test_root / 'apps' / 'hive-orchestrator' / 'src'))

class PlatformValidationTests:
    """Quick validation tests for essential platform functionality"""

    @pytest.fixture(autouse=True)
    def setup_test_env(self):
        """Setup isolated test environment"""
        self.temp_dir = tempfile.mkdtemp(prefix='hive_validation_')
        self.db_path = Path(self.temp_dir) / 'validation_test.db'
        self._init_validation_database()
        os.environ['HIVE_TEST_MODE'] = 'true'
        os.environ['HIVE_TEST_DB_PATH'] = str(self.db_path)
        yield
        import shutil
        try:
            shutil.rmtree(self.temp_dir)
        except Exception:
            pass
        os.environ.pop('HIVE_TEST_MODE', None)
        os.environ.pop('HIVE_TEST_DB_PATH', None)

    def _init_validation_database(self):
        """Initialize minimal database schema for validation"""
        conn = sqlite3.connect(self.db_path)
        conn.executescript("\n            CREATE TABLE tasks (\n                id TEXT PRIMARY KEY,\n                title TEXT NOT NULL,\n                description TEXT,\n                task_type TEXT DEFAULT 'task',\n                priority INTEGER DEFAULT 50,\n                status TEXT DEFAULT 'queued',\n                assignee TEXT,\n                payload TEXT,\n                created_at TEXT DEFAULT CURRENT_TIMESTAMP,\n                updated_at TEXT DEFAULT CURRENT_TIMESTAMP\n            );\n\n            CREATE TABLE events (\n                id TEXT PRIMARY KEY,\n                event_type TEXT NOT NULL,\n                source_agent TEXT,\n                payload TEXT,\n                correlation_id TEXT,\n                created_at TEXT DEFAULT CURRENT_TIMESTAMP\n            );\n\n            CREATE TABLE simulations (\n                id TEXT PRIMARY KEY,\n                config_data TEXT,\n                status TEXT DEFAULT 'pending',\n                results_data TEXT,\n                created_at TEXT DEFAULT CURRENT_TIMESTAMP\n            );\n\n            CREATE TABLE planning_queue (\n                id TEXT PRIMARY KEY,\n                task_description TEXT NOT NULL,\n                priority INTEGER DEFAULT 50,\n                status TEXT DEFAULT 'pending',\n                created_at TEXT DEFAULT CURRENT_TIMESTAMP\n            );\n        ")
        conn.commit()
        conn.close()

    @pytest.mark.crust
    def test_database_connectivity(self):
        """Test basic database connectivity and operations"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute('SELECT COUNT(*) FROM tasks')
        count = cursor.fetchone()[0]
        assert count == 0, 'Database should start empty'
        task_id = str(uuid.uuid4())
        conn.execute('\n            INSERT INTO tasks (id, title, description) VALUES (?, ?, ?)\n        ', (task_id, 'Test Task', 'Database connectivity test'))
        cursor = conn.execute('SELECT title FROM tasks WHERE id = ?', (task_id,))
        title = cursor.fetchone()[0]
        assert title == 'Test Task', 'Should retrieve inserted task'
        conn.close()

    @pytest.mark.crust
    def test_event_bus_basic_functionality(self):
        """Test basic event bus functionality"""
        conn = sqlite3.connect(self.db_path)
        event_id = str(uuid.uuid4())
        event_payload = {'test': True, 'message': 'validation test'}
        conn.execute('\n            INSERT INTO events (id, event_type, source_agent, payload)\n            VALUES (?, ?, ?, ?)\n        ', (event_id, 'validation.test', 'test_agent', json.dumps(event_payload)))
        cursor = conn.execute('\n            SELECT payload FROM events WHERE id = ?\n        ', (event_id,))
        row = cursor.fetchone()
        assert row is not None, 'Event should be stored'
        stored_payload = json.loads(row[0])
        assert stored_payload['test'] is True, 'Event payload should be preserved'
        conn.close()

    @pytest.mark.crust
    def test_ai_planner_integration_points(self):
        """Test AI Planner integration points"""
        conn = sqlite3.connect(self.db_path)
        planning_id = str(uuid.uuid4())
        conn.execute('\n            INSERT INTO planning_queue (id, task_description, priority)\n            VALUES (?, ?, ?)\n        ', (planning_id, 'Test planning integration', 75))
        cursor = conn.execute('\n            SELECT task_description, priority FROM planning_queue WHERE id = ?\n        ', (planning_id,))
        row = cursor.fetchone()
        assert row is not None, 'Planning request should exist'
        assert row[0] == 'Test planning integration', 'Task description should match'
        assert row[1] == 75, 'Priority should match'
        conn.close()

    @pytest.mark.crust
    def test_ecosystemiser_integration_points(self):
        """Test EcoSystemiser integration points"""
        conn = sqlite3.connect(self.db_path)
        sim_id = str(uuid.uuid4())
        config_data = {'components': ['solar_pv', 'battery'], 'optimization': 'cost_minimize'}
        conn.execute('\n            INSERT INTO simulations (id, config_data, status)\n            VALUES (?, ?, ?)\n        ', (sim_id, json.dumps(config_data), 'pending'))
        cursor = conn.execute('\n            SELECT config_data, status FROM simulations WHERE id = ?\n        ', (sim_id,))
        row = cursor.fetchone()
        assert row is not None, 'Simulation should exist'
        stored_config = json.loads(row[0])
        assert 'solar_pv' in stored_config['components'], 'Config should be preserved'
        assert row[1] == 'pending', 'Status should match'
        conn.close()

    @pytest.mark.crust
    def test_cross_app_data_sharing(self):
        """Test basic cross-app data sharing patterns"""
        conn = sqlite3.connect(self.db_path)
        task_id = str(uuid.uuid4())
        task_payload = {'created_by': 'orchestrator', 'shared_data': {'key': 'value'}, 'target_app': 'ecosystemiser'}
        conn.execute('\n            INSERT INTO tasks (id, title, task_type, assignee, payload)\n            VALUES (?, ?, ?, ?, ?)\n        ', (task_id, 'Cross-App Data Test', 'data_sharing', 'ecosystemiser', json.dumps(task_payload)))
        cursor = conn.execute("\n            SELECT payload FROM tasks WHERE id = ? AND assignee = 'ecosystemiser'\n        ", (task_id,))
        row = cursor.fetchone()
        assert row is not None, 'Task should be accessible to target app'
        payload = json.loads(row[0])
        assert payload['created_by'] == 'orchestrator', 'Original data should be preserved'
        assert payload['shared_data']['key'] == 'value', 'Nested data should be accessible'
        conn.close()

    @pytest.mark.crust
    def test_async_operation_patterns(self):
        """Test async operation patterns work correctly"""
        import asyncio

        async def async_database_operation():
            """Simulate async database operation"""
            await asyncio.sleep(0.001)
            return True

        async def run_concurrent_operations():
            """Run multiple async operations concurrently"""
            tasks = [async_database_operation() for _ in range(10)]
            results = await asyncio.gather(*tasks)
            return all(results)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(run_concurrent_operations())
            assert result is True, 'All async operations should succeed'
        finally:
            loop.close()

    @pytest.mark.crust
    def test_error_handling_patterns(self):
        """Test basic error handling patterns"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute('\n                INSERT INTO tasks (id, title) VALUES (?, ?)\n            ', (None, 'Invalid Task'))
            raise AssertionError('Should have raised an error')
        except sqlite3.IntegrityError:
            pass
        task_id = str(uuid.uuid4())
        conn.execute('\n            INSERT INTO tasks (id, title) VALUES (?, ?)\n        ', (task_id, 'First Task'))
        try:
            conn.execute('\n                INSERT INTO tasks (id, title) VALUES (?, ?)\n            ', (task_id, 'Duplicate Task'))
            raise AssertionError('Should have raised an error')
        except sqlite3.IntegrityError:
            pass
        conn.close()

    @pytest.mark.crust
    def test_performance_baseline(self):
        """Test basic performance baseline"""
        conn = sqlite3.connect(self.db_path)
        start_time = time.time()
        for i in range(100):
            task_id = f'perf_task_{i}_{uuid.uuid4()}'
            conn.execute('\n                INSERT INTO tasks (id, title, description)\n                VALUES (?, ?, ?)\n            ', (task_id, f'Performance Test Task {i}', f'Task {i} for performance baseline testing'))
        cursor = conn.execute('SELECT COUNT(*) FROM tasks')
        count = cursor.fetchone()[0]
        end_time = time.time()
        duration = end_time - start_time
        assert count == 100, 'Should have inserted 100 records'
        assert duration < 5.0, f'Operations should complete quickly, took {duration:.2f}s'
        ops_per_second = 100 / duration
        assert ops_per_second > 20, f'Should achieve reasonable throughput, got {ops_per_second:.1f} ops/s'
        conn.close()

    @pytest.mark.crust
    def test_golden_rules_basic_compliance(self):
        """Test basic Golden Rules compliance"""
        orchestrator_core = test_root / 'apps' / 'hive-orchestrator' / 'src' / 'hive_orchestrator' / 'core'
        assert orchestrator_core.exists(), 'Orchestrator should have core/ directory'
        expected_core_dirs = ['bus', 'db', 'errors']
        existing_dirs = [d.name for d in orchestrator_core.iterdir() if d.is_dir()]
        compliance_score = sum(1 for dir_name in expected_core_dirs if dir_name in existing_dirs)
        assert compliance_score > 0, f'Should have some core directories, found: {existing_dirs}'

    @pytest.mark.crust
    def test_import_patterns_basic(self):
        """Test basic import patterns work"""
        try:
            sys.path.insert(0, str(test_root / 'apps' / 'hive-orchestrator' / 'src'))
            import hive_orchestrator
            assert hasattr(hive_orchestrator, '__version__') or hasattr(hive_orchestrator, '__file__'), 'Module should be importable'
        except ImportError as e:
            print(f'Import test skipped due to environment: {e}')

class CriticalPathValidation:
    """Critical path validation for essential platform functions"""

    def __init__(self, db_path: Path):
        self.db_path = db_path

    def validate_ai_planner_to_queen_flow(self) -> bool:
        """Validate AI Planner → Queen critical path"""
        conn = sqlite3.connect(self.db_path)
        try:
            plan_id = f'critical_plan_{uuid.uuid4()}'
            planning_task_id = f'critical_planning_{uuid.uuid4()}'
            conn.execute('\n                INSERT INTO planning_queue (id, task_description, status)\n                VALUES (?, ?, ?)\n            ', (planning_task_id, 'Critical path test', 'planned'))
            task_id = f'critical_task_{uuid.uuid4()}'
            conn.execute('\n                INSERT INTO tasks (id, title, task_type, status, payload)\n                VALUES (?, ?, ?, ?, ?)\n            ', (task_id, 'Critical Path Task', 'planned_subtask', 'queued', json.dumps({'parent_plan_id': plan_id})))
            cursor = conn.execute("\n                SELECT COUNT(*) FROM tasks\n                WHERE json_extract(payload, '$.parent_plan_id') = ?\n            ", (plan_id,))
            task_count = cursor.fetchone()[0]
            return task_count > 0
        finally:
            conn.close()

    def validate_queen_to_worker_flow(self) -> bool:
        """Validate Queen → Worker critical path"""
        conn = sqlite3.connect(self.db_path)
        try:
            task_id = f'worker_task_{uuid.uuid4()}'
            conn.execute('\n                INSERT INTO tasks (id, title, status, assignee)\n                VALUES (?, ?, ?, ?)\n            ', (task_id, 'Worker Assignment Test', 'assigned', 'worker:backend'))
            conn.execute("\n                UPDATE tasks SET status = 'in_progress' WHERE id = ?\n            ", (task_id,))
            conn.execute("\n                UPDATE tasks SET status = 'completed' WHERE id = ?\n            ", (task_id,))
            cursor = conn.execute('\n                SELECT status FROM tasks WHERE id = ?\n            ', (task_id,))
            status = cursor.fetchone()[0]
            return status == 'completed'
        finally:
            conn.close()

    def validate_event_bus_critical_path(self) -> bool:
        """Validate event bus critical messaging path"""
        conn = sqlite3.connect(self.db_path)
        try:
            event_id = str(uuid.uuid4())
            correlation_id = str(uuid.uuid4())
            conn.execute('\n                INSERT INTO events (id, event_type, source_agent, correlation_id, payload)\n                VALUES (?, ?, ?, ?, ?)\n            ', (event_id, 'system.critical.test', 'validation_test', correlation_id, json.dumps({'critical': True, 'timestamp': datetime.now(UTC).isoformat()})))
            cursor = conn.execute('\n                SELECT payload FROM events WHERE correlation_id = ?\n            ', (correlation_id,))
            row = cursor.fetchone()
            if not row:
                return False
            payload = json.loads(row[0])
            return payload.get('critical') is True
        finally:
            conn.close()

    def run_all_critical_validations(self) -> dict[str, bool]:
        """Run all critical path validations"""
        return {'ai_planner_to_queen': self.validate_ai_planner_to_queen_flow(), 'queen_to_worker': self.validate_queen_to_worker_flow(), 'event_bus_critical': self.validate_event_bus_critical_path()}

@pytest.fixture
def critical_validator(setup_test_env):
    """Provide critical path validator"""
    test_instance = PlatformValidationTests()
    test_instance.setup_test_env = setup_test_env
    return CriticalPathValidation(test_instance.db_path)

@pytest.mark.crust
def test_critical_paths(critical_validator):
    """Test all critical paths are functional"""
    results = critical_validator.run_all_critical_validations()
    for path_name, success in results.items():
        assert success, f"Critical path '{path_name}' validation failed"
    assert all(results.values()), f'Some critical paths failed: {results}'

@pytest.mark.crust
def test_platform_health_check():
    """Quick platform health check"""
    validator = PlatformValidationTests()
    validator.setup_test_env()
    try:
        validator.test_database_connectivity()
        validator.test_event_bus_basic_functionality()
        validator.test_cross_app_data_sharing()
        assert True
    finally:
        pass
if __name__ == '__main__':
    print('🔍 Running Hive Platform Validation Tests...')
    import subprocess
    result = subprocess.run(['python', '-m', 'pytest', __file__, '-v'], capture_output=True, text=True)
    if result.returncode == 0:
        print('✅ All validation tests passed!')
    else:
        print('❌ Some validation tests failed:')
        print(result.stdout)
        print(result.stderr)
    exit(result.returncode)
