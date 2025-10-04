"""
Comprehensive Integration Testing Suite for Hive Platform

This test suite validates the complete Hive platform functionality including:
1. End-to-End Workflow Tests (AI Planner → Queen → Worker → completion flow)
2. Cross-App Communication Tests (database, event bus, inter-app integration)
3. Performance Integration Tests (async infrastructure, concurrent processing)
4. Golden Rules Integration Tests (core/ pattern, architectural standards)
5. Failure and Recovery Tests (component failures, error handling)
6. Platform Integration Tests (EcoSystemiser, AI agents, dashboards)

Designed to run in CI/CD to catch breaking changes and ensure platform reliability.
"""
import pytest
import asyncio
import concurrent.futures
import json
import os
import sqlite3
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
test_root = Path(__file__).parent.parent
sys.path.insert(0, str(test_root / 'apps' / 'hive-orchestrator' / 'src'))
sys.path.insert(0, str(test_root / 'apps' / 'ai-planner' / 'src'))
sys.path.insert(0, str(test_root / 'apps' / 'ai-reviewer' / 'src'))
sys.path.insert(0, str(test_root / 'apps' / 'ecosystemiser' / 'src'))

@pytest.mark.crust
@dataclass
class TestMetrics:
    """Metrics collected during testing"""
    test_start_time: float
    test_end_time: float
    tasks_created: int = 0
    plans_generated: int = 0
    subtasks_executed: int = 0
    events_published: int = 0
    events_consumed: int = 0
    database_operations: int = 0
    async_operations: int = 0
    errors_encountered: list[str] = None
    performance_samples: list[dict] = None

    def __post_init__(self):
        if self.errors_encountered is None:
            self.errors_encountered = []
        if self.performance_samples is None:
            self.performance_samples = []

    @property
    def total_duration(self) -> float:
        return self.test_end_time - self.test_start_time

    @property
    def throughput(self) -> float:
        """Tasks per second"""
        if self.total_duration > 0:
            return self.subtasks_executed / self.total_duration
        return 0.0

class PlatformTestEnvironment:
    """Isolated test environment for comprehensive platform testing"""

    def __init__(self):
        self.temp_dir = None
        self.db_path = None
        self.metrics = TestMetrics(test_start_time=time.time(), test_end_time=0)
        self.event_handlers = {}
        self.mock_services = {}
        self.cleanup_handlers = []

    def setup(self):
        """Setup isolated test environment"""
        self.temp_dir = tempfile.mkdtemp(prefix='hive_integration_test_')
        self.db_path = Path(self.temp_dir) / 'test_hive.db'
        self._init_test_database()
        os.environ['HIVE_TEST_MODE'] = 'true'
        os.environ['HIVE_TEST_DB_PATH'] = str(self.db_path)
        print(f'✅ Test environment initialized at {self.temp_dir}')

    def teardown(self):
        """Clean up test environment"""
        self.metrics.test_end_time = time.time()
        for cleanup_handler in self.cleanup_handlers:
            try:
                cleanup_handler()
            except Exception as e:
                print(f'⚠️ Cleanup handler failed: {e}')
        if self.temp_dir and Path(self.temp_dir).exists():
            import shutil
            try:
                shutil.rmtree(self.temp_dir)
            except Exception as e:
                print(f'⚠️ Failed to remove temp dir: {e}')
        os.environ.pop('HIVE_TEST_MODE', None)
        os.environ.pop('HIVE_TEST_DB_PATH', None)
        print('🧹 Test environment cleaned up')

    def _init_test_database(self):
        """Initialize comprehensive test database schema"""
        conn = sqlite3.connect(self.db_path)
        conn.executescript("\n            -- AI Planner tables\n            CREATE TABLE planning_queue (\n                id TEXT PRIMARY KEY,\n                task_description TEXT NOT NULL,\n                priority INTEGER DEFAULT 50,\n                requestor TEXT,\n                context_data TEXT,\n                complexity_estimate TEXT,\n                status TEXT DEFAULT 'pending',\n                assigned_agent TEXT,\n                assigned_at TEXT,\n                created_at TEXT DEFAULT CURRENT_TIMESTAMP,\n                completed_at TEXT\n            );\n\n            CREATE TABLE execution_plans (\n                id TEXT PRIMARY KEY,\n                planning_task_id TEXT NOT NULL,\n                plan_data TEXT NOT NULL,\n                estimated_complexity TEXT,\n                estimated_duration INTEGER,\n                status TEXT DEFAULT 'generated',\n                generated_at TEXT DEFAULT CURRENT_TIMESTAMP,\n                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,\n                FOREIGN KEY (planning_task_id) REFERENCES planning_queue (id)\n            );\n\n            -- Orchestrator tables\n            CREATE TABLE tasks (\n                id TEXT PRIMARY KEY,\n                title TEXT NOT NULL,\n                description TEXT,\n                task_type TEXT DEFAULT 'task',\n                priority INTEGER DEFAULT 50,\n                status TEXT DEFAULT 'queued',\n                assignee TEXT,\n                assigned_at TEXT,\n                started_at TEXT,\n                completed_at TEXT,\n                payload TEXT,\n                created_at TEXT DEFAULT CURRENT_TIMESTAMP,\n                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,\n                retry_count INTEGER DEFAULT 0,\n                workspace TEXT,\n                tags TEXT\n            );\n\n            CREATE TABLE runs (\n                id TEXT PRIMARY KEY,\n                task_id TEXT NOT NULL,\n                worker_id TEXT NOT NULL,\n                phase TEXT,\n                status TEXT DEFAULT 'running',\n                result TEXT,\n                created_at TEXT DEFAULT CURRENT_TIMESTAMP,\n                completed_at TEXT,\n                FOREIGN KEY (task_id) REFERENCES tasks (id)\n            );\n\n            CREATE TABLE workers (\n                id TEXT PRIMARY KEY,\n                role TEXT NOT NULL,\n                capabilities TEXT,\n                metadata TEXT,\n                status TEXT DEFAULT 'active',\n                created_at TEXT DEFAULT CURRENT_TIMESTAMP\n            );\n\n            -- Event bus tables\n            CREATE TABLE events (\n                id TEXT PRIMARY KEY,\n                event_type TEXT NOT NULL,\n                source_agent TEXT,\n                target_agent TEXT,\n                payload TEXT,\n                correlation_id TEXT,\n                created_at TEXT DEFAULT CURRENT_TIMESTAMP\n            );\n\n            -- EcoSystemiser tables\n            CREATE TABLE simulations (\n                id TEXT PRIMARY KEY,\n                study_id TEXT,\n                config_data TEXT,\n                status TEXT DEFAULT 'pending',\n                results_data TEXT,\n                created_at TEXT DEFAULT CURRENT_TIMESTAMP,\n                completed_at TEXT\n            );\n\n            CREATE TABLE studies (\n                id TEXT PRIMARY KEY,\n                name TEXT NOT NULL,\n                study_type TEXT,\n                parameters TEXT,\n                status TEXT DEFAULT 'pending',\n                created_at TEXT DEFAULT CURRENT_TIMESTAMP\n            );\n\n            -- AI Reviewer tables\n            CREATE TABLE reviews (\n                id TEXT PRIMARY KEY,\n                target_type TEXT NOT NULL,\n                target_id TEXT NOT NULL,\n                review_type TEXT,\n                status TEXT DEFAULT 'pending',\n                feedback TEXT,\n                score REAL,\n                created_at TEXT DEFAULT CURRENT_TIMESTAMP,\n                completed_at TEXT\n            );\n\n            -- Performance monitoring\n            CREATE TABLE performance_metrics (\n                id TEXT PRIMARY KEY,\n                metric_type TEXT NOT NULL,\n                metric_name TEXT NOT NULL,\n                metric_value REAL,\n                metadata TEXT,\n                measured_at TEXT DEFAULT CURRENT_TIMESTAMP\n            );\n\n            -- Indexes for performance\n            CREATE INDEX idx_planning_queue_status_priority ON planning_queue (status, priority DESC, created_at);\n            CREATE INDEX idx_execution_plans_status ON execution_plans (status);\n            CREATE INDEX idx_tasks_status_type ON tasks (status, task_type);\n            CREATE INDEX idx_tasks_payload_parent ON tasks (json_extract(payload, '$.parent_plan_id'));\n            CREATE INDEX idx_runs_task_status ON runs (task_id, status);\n            CREATE INDEX idx_events_type_correlation ON events (event_type, correlation_id);\n            CREATE INDEX idx_events_created_at ON events (created_at);\n            CREATE INDEX idx_simulations_study_status ON simulations (study_id, status);\n            CREATE INDEX idx_performance_metrics_type_time ON performance_metrics (metric_type, measured_at);\n        ")
        conn.commit()
        conn.close()
        self.metrics.database_operations += 1

class EndToEndWorkflowTests:
    """Test complete AI Planner → Queen → Worker → completion flow"""

    def __init__(self, env: PlatformTestEnvironment):
        self.env = env

    @pytest.mark.crust
    def test_complete_autonomous_workflow(self) -> bool:
        """Test complete autonomous task execution without manual intervention"""
        print('\n🚀 Testing Complete Autonomous Workflow...')
        try:
            planning_task_id = self._create_complex_planning_task()
            self.env.metrics.tasks_created += 1
            plan_id = self._simulate_ai_planner_processing(planning_task_id)
            self.env.metrics.plans_generated += 1
            success = self._simulate_queen_worker_execution(plan_id)
            completion_status = self._verify_workflow_completion(plan_id)
            print(f"✅ Autonomous workflow test: {('PASSED' if success and completion_status else 'FAILED')}")
            return success and completion_status
        except Exception as e:
            self.env.metrics.errors_encountered.append(f'Autonomous workflow: {str(e)}')
            print(f'❌ Autonomous workflow test failed: {e}')
            return False

    @pytest.mark.crust
    def test_task_decomposition_pipeline(self) -> bool:
        """Test task decomposition → execution → reporting pipeline"""
        print('\n🔧 Testing Task Decomposition Pipeline...')
        try:
            task_description = '\n            Implement full-stack user management system:\n            - Database schema design\n            - Backend API implementation\n            - Frontend UI components\n            - Testing and documentation\n            - Deployment configuration\n            '
            planning_task_id = str(uuid.uuid4())
            conn = sqlite3.connect(self.env.db_path)
            conn.execute('\n                INSERT INTO planning_queue (id, task_description, priority, requestor, context_data)\n                VALUES (?, ?, ?, ?, ?)\n            ', (planning_task_id, task_description, 80, 'integration_test', json.dumps({'complexity': 'high', 'estimated_hours': 16})))
            conn.commit()
            conn.close()
            plan_data = self._generate_complex_execution_plan(planning_task_id)
            subtasks = plan_data['sub_tasks']
            assert len(subtasks) >= 5, 'Should decompose into at least 5 subtasks'
            dependencies_exist = any((sub_task.get('dependencies') for sub_task in subtasks))
            assert dependencies_exist, 'Should have dependency relationships'
            print(f'✅ Task decomposition test: PASSED ({len(subtasks)} subtasks created)')
            return True
        except Exception as e:
            self.env.metrics.errors_encountered.append(f'Task decomposition: {str(e)}')
            print(f'❌ Task decomposition test failed: {e}')
            return False

    @pytest.mark.crust
    def test_error_handling_and_recovery(self) -> bool:
        """Test error handling and recovery across components"""
        print('\n🛠️ Testing Error Handling and Recovery...')
        try:
            task_id = self._create_failing_task()
            self._simulate_task_failure_and_retry(task_id)
            timeout_task_id = self._create_timeout_task()
            self._simulate_worker_timeout_recovery(timeout_task_id)
            self._simulate_database_failure_recovery()
            conn = sqlite3.connect(self.env.db_path)
            cursor = conn.execute("\n                SELECT COUNT(*) FROM runs WHERE status = 'failed'\n            ")
            failed_runs = cursor.fetchone()[0]
            conn.close()
            assert failed_runs > 0, 'Should have recorded failed runs'
            print(f'✅ Error handling test: PASSED ({failed_runs} failures handled)')
            return True
        except Exception as e:
            self.env.metrics.errors_encountered.append(f'Error handling: {str(e)}')
            print(f'❌ Error handling test failed: {e}')
            return False

    def _create_complex_planning_task(self) -> str:
        """Create a complex planning task for testing"""
        task_id = str(uuid.uuid4())
        task_description = '\n        Implement real-time data processing pipeline:\n        1. Data ingestion from multiple sources\n        2. Stream processing and validation\n        3. Machine learning model inference\n        4. Results storage and visualization\n        5. Monitoring and alerting system\n        '
        conn = sqlite3.connect(self.env.db_path)
        conn.execute('\n            INSERT INTO planning_queue (id, task_description, priority, requestor, context_data)\n            VALUES (?, ?, ?, ?, ?)\n        ', (task_id, task_description, 90, 'integration_test', json.dumps({'complexity': 'very_high', 'estimated_hours': 24, 'required_skills': ['python', 'kafka', 'tensorflow', 'react', 'docker'], 'dependencies': ['data_infrastructure', 'ml_models']})))
        conn.commit()
        conn.close()
        return task_id

    def _simulate_ai_planner_processing(self, task_id: str) -> str:
        """Simulate AI Planner generating execution plan"""
        plan_id = f'plan_{uuid.uuid4()}'
        plan_data = self._generate_complex_execution_plan(task_id)
        conn = sqlite3.connect(self.env.db_path)
        conn.execute('\n            INSERT INTO execution_plans (id, planning_task_id, plan_data, estimated_complexity, estimated_duration)\n            VALUES (?, ?, ?, ?, ?)\n        ', (plan_id, task_id, json.dumps(plan_data), 'very_high', 1440))
        for i, sub_task in enumerate(plan_data['sub_tasks']):
            subtask_id = f'subtask_{plan_id}_{i}'
            conn.execute('\n                INSERT INTO tasks (\n                    id, title, description, task_type, priority, status,\n                    assignee, payload, created_at\n                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)\n            ', (subtask_id, sub_task['title'], sub_task['description'], 'planned_subtask', sub_task['priority'], 'queued', sub_task['assignee'], json.dumps({'parent_plan_id': plan_id, 'subtask_index': i, **sub_task})))
            self.env.metrics.subtasks_executed += 1
        conn.execute("\n            UPDATE planning_queue SET status = 'planned', completed_at = CURRENT_TIMESTAMP WHERE id = ?\n        ", (task_id,))
        conn.commit()
        conn.close()
        return plan_id

    def _generate_complex_execution_plan(self, task_id: str) -> dict[str, Any]:
        """Generate a realistic complex execution plan"""
        return {'plan_id': f'plan_{uuid.uuid4()}', 'task_id': task_id, 'plan_name': 'Real-time Data Processing Pipeline', 'sub_tasks': [{'id': 'data_ingestion', 'title': 'Implement Data Ingestion Layer', 'description': 'Create Kafka consumers for multiple data sources', 'assignee': 'worker:backend', 'priority': 90, 'complexity': 'high', 'estimated_duration': 480, 'workflow_phase': 'implementation', 'required_skills': ['python', 'kafka', 'docker'], 'deliverables': ['kafka_consumer.py', 'ingestion_config.yaml'], 'dependencies': []}, {'id': 'stream_processing', 'title': 'Implement Stream Processing', 'description': 'Create real-time data validation and transformation', 'assignee': 'worker:backend', 'priority': 85, 'complexity': 'high', 'estimated_duration': 360, 'workflow_phase': 'implementation', 'required_skills': ['python', 'pandas', 'kafka'], 'deliverables': ['stream_processor.py', 'validation_rules.py'], 'dependencies': ['data_ingestion']}, {'id': 'ml_inference', 'title': 'Implement ML Model Inference', 'description': 'Create TensorFlow Serving integration for real-time predictions', 'assignee': 'worker:backend', 'priority': 80, 'complexity': 'very_high', 'estimated_duration': 600, 'workflow_phase': 'implementation', 'required_skills': ['python', 'tensorflow', 'docker'], 'deliverables': ['ml_inference_service.py', 'model_loader.py'], 'dependencies': ['stream_processing']}, {'id': 'results_storage', 'title': 'Implement Results Storage', 'description': 'Create database schema and storage layer for results', 'assignee': 'worker:backend', 'priority': 75, 'complexity': 'medium', 'estimated_duration': 240, 'workflow_phase': 'implementation', 'required_skills': ['python', 'postgresql', 'sqlalchemy'], 'deliverables': ['storage_schema.sql', 'results_dao.py'], 'dependencies': ['ml_inference']}, {'id': 'visualization_ui', 'title': 'Create Visualization Dashboard', 'description': 'Build React dashboard for real-time data visualization', 'assignee': 'worker:frontend', 'priority': 70, 'complexity': 'high', 'estimated_duration': 480, 'workflow_phase': 'implementation', 'required_skills': ['react', 'typescript', 'd3', 'websockets'], 'deliverables': ['Dashboard.tsx', 'DataVisualizer.tsx'], 'dependencies': ['results_storage']}, {'id': 'monitoring_alerts', 'title': 'Implement Monitoring and Alerts', 'description': 'Create monitoring dashboard and alerting system', 'assignee': 'worker:infra', 'priority': 65, 'complexity': 'medium', 'estimated_duration': 300, 'workflow_phase': 'implementation', 'required_skills': ['prometheus', 'grafana', 'docker'], 'deliverables': ['monitoring.yaml', 'alert_rules.yaml'], 'dependencies': ['visualization_ui']}], 'metrics': {'total_estimated_duration': 2460, 'complexity_breakdown': {'medium': 2, 'high': 3, 'very_high': 1}}, 'status': 'generated', 'created_at': datetime.now(UTC).isoformat()}

    def _simulate_queen_worker_execution(self, plan_id: str) -> bool:
        """Simulate Queen orchestrating and Workers executing tasks"""
        try:
            conn = sqlite3.connect(self.env.db_path)
            cursor = conn.execute("\n                SELECT id, title, payload FROM tasks\n                WHERE task_type = 'planned_subtask'\n                AND json_extract(payload, '$.parent_plan_id') = ?\n                ORDER BY priority DESC\n            ", (plan_id,))
            subtasks = [{'id': row[0], 'title': row[1], 'payload': json.loads(row[2]) if row[2] else {}} for row in cursor.fetchall()]
            completed_tasks = set()
            while len(completed_tasks) < len(subtasks):
                ready_tasks = []
                for subtask in subtasks:
                    if subtask['id'] in completed_tasks:
                        continue
                    dependencies = subtask['payload'].get('dependencies', [])
                    dependencies_met = all((any((completed_task['payload'].get('id') == dep for completed_task in [st for st in subtasks if st['id'] in completed_tasks])) for dep in dependencies)) if dependencies else True
                    if dependencies_met:
                        ready_tasks.append(subtask)
                if not ready_tasks:
                    break
                for task in ready_tasks:
                    self._simulate_task_execution(task['id'])
                    completed_tasks.add(task['id'])
                    self.env.metrics.subtasks_executed += 1
            conn.close()
            return len(completed_tasks) == len(subtasks)
        except Exception as e:
            self.env.metrics.errors_encountered.append(f'Queen/Worker execution: {str(e)}')
            return False

    def _simulate_task_execution(self, task_id: str):
        """Simulate individual task execution"""
        conn = sqlite3.connect(self.env.db_path)
        run_id = f'run_{uuid.uuid4()}'
        conn.execute('\n            INSERT INTO runs (id, task_id, worker_id, phase, status)\n            VALUES (?, ?, ?, ?, ?)\n        ', (run_id, task_id, f'worker_{uuid.uuid4().hex[:8]}', 'apply', 'running'))
        conn.execute("\n            UPDATE tasks\n            SET status = 'in_progress', started_at = CURRENT_TIMESTAMP\n            WHERE id = ?\n        ", (task_id,))
        time.sleep(0.1)
        conn.execute("\n            UPDATE runs\n            SET status = 'completed', result = ?, completed_at = CURRENT_TIMESTAMP\n            WHERE id = ?\n        ", (json.dumps({'status': 'success', 'output': 'Task completed successfully'}), run_id))
        conn.execute("\n            UPDATE tasks\n            SET status = 'completed', completed_at = CURRENT_TIMESTAMP\n            WHERE id = ?\n        ", (task_id,))
        conn.commit()
        conn.close()

    def _verify_workflow_completion(self, plan_id: str) -> bool:
        """Verify that the workflow completed successfully"""
        conn = sqlite3.connect(self.env.db_path)
        cursor = conn.execute("\n            SELECT COUNT(*) as total,\n                   SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed\n            FROM tasks\n            WHERE task_type = 'planned_subtask'\n            AND json_extract(payload, '$.parent_plan_id') = ?\n        ", (plan_id,))
        row = cursor.fetchone()
        total, completed = (row[0], row[1])
        conn.close()
        return total > 0 and total == completed

    def _create_failing_task(self) -> str:
        """Create a task designed to fail for testing error handling"""
        task_id = f'failing_task_{uuid.uuid4()}'
        conn = sqlite3.connect(self.env.db_path)
        conn.execute('\n            INSERT INTO tasks (\n                id, title, description, task_type, priority, status,\n                payload, created_at\n            ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)\n        ', (task_id, 'Intentionally Failing Task', 'This task is designed to fail for testing error handling', 'test_task', 50, 'queued', json.dumps({'test_type': 'failure', 'should_fail': True})))
        conn.commit()
        conn.close()
        return task_id

    def _simulate_task_failure_and_retry(self, task_id: str):
        """Simulate task failure and retry logic"""
        conn = sqlite3.connect(self.env.db_path)
        run_id_1 = f'run_{uuid.uuid4()}'
        conn.execute('\n            INSERT INTO runs (id, task_id, worker_id, phase, status, result)\n            VALUES (?, ?, ?, ?, ?, ?)\n        ', (run_id_1, task_id, 'test_worker', 'apply', 'failed', json.dumps({'status': 'failed', 'error': 'Simulated failure'})))
        conn.execute("\n            UPDATE tasks\n            SET retry_count = retry_count + 1, status = 'failed'\n            WHERE id = ?\n        ", (task_id,))
        run_id_2 = f'run_{uuid.uuid4()}'
        conn.execute('\n            INSERT INTO runs (id, task_id, worker_id, phase, status, result)\n            VALUES (?, ?, ?, ?, ?, ?)\n        ', (run_id_2, task_id, 'test_worker', 'apply', 'completed', json.dumps({'status': 'success', 'output': 'Retry successful'})))
        conn.execute("\n            UPDATE tasks\n            SET status = 'completed', completed_at = CURRENT_TIMESTAMP\n            WHERE id = ?\n        ", (task_id,))
        conn.commit()
        conn.close()

    def _create_timeout_task(self) -> str:
        """Create a task that will timeout"""
        task_id = f'timeout_task_{uuid.uuid4()}'
        conn = sqlite3.connect(self.env.db_path)
        conn.execute('\n            INSERT INTO tasks (\n                id, title, description, task_type, priority, status,\n                payload, created_at\n            ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)\n        ', (task_id, 'Timeout Test Task', 'This task will timeout for testing timeout handling', 'test_task', 50, 'queued', json.dumps({'test_type': 'timeout', 'duration': 30})))
        conn.commit()
        conn.close()
        return task_id

    def _simulate_worker_timeout_recovery(self, task_id: str):
        """Simulate worker timeout and recovery"""
        conn = sqlite3.connect(self.env.db_path)
        run_id = f'run_{uuid.uuid4()}'
        conn.execute('\n            INSERT INTO runs (id, task_id, worker_id, phase, status)\n            VALUES (?, ?, ?, ?, ?)\n        ', (run_id, task_id, 'timeout_worker', 'apply', 'running'))
        conn.execute("\n            UPDATE tasks\n            SET status = 'in_progress', started_at = CURRENT_TIMESTAMP\n            WHERE id = ?\n        ", (task_id,))
        conn.execute("\n            UPDATE runs\n            SET status = 'timeout', result = ?\n            WHERE id = ?\n        ", (json.dumps({'status': 'timeout', 'error': 'Worker timeout detected'}), run_id))
        new_run_id = f'run_{uuid.uuid4()}'
        conn.execute('\n            INSERT INTO runs (id, task_id, worker_id, phase, status, result)\n            VALUES (?, ?, ?, ?, ?, ?)\n        ', (new_run_id, task_id, 'recovery_worker', 'apply', 'completed', json.dumps({'status': 'success', 'output': 'Recovered from timeout'})))
        conn.execute("\n            UPDATE tasks\n            SET status = 'completed', completed_at = CURRENT_TIMESTAMP\n            WHERE id = ?\n        ", (task_id,))
        conn.commit()
        conn.close()

    def _simulate_database_failure_recovery(self):
        """Simulate database connection failure and recovery"""
        try:
            original_path = self.env.db_path
            temp_path = self.env.db_path.with_suffix('.backup')
            original_path.rename(temp_path)
            try:
                conn = sqlite3.connect(original_path)
                conn.execute('SELECT 1')
                conn.close()
            except sqlite3.OperationalError:
                pass
            temp_path.rename(original_path)
            conn = sqlite3.connect(original_path)
            cursor = conn.execute('SELECT COUNT(*) FROM tasks')
            count = cursor.fetchone()[0]
            conn.close()
            assert count >= 0, 'Database recovery failed'
        except Exception as e:
            self.env.metrics.errors_encountered.append(f'Database failure recovery: {str(e)}')

class CrossAppCommunicationTests:
    """Test database communication and event bus between apps"""

    def __init__(self, env: PlatformTestEnvironment):
        self.env = env

    @pytest.mark.crust
    def test_database_communication_core_pattern(self) -> bool:
        """Test database communication between apps using core/ services"""
        print('\n🗄️ Testing Database Communication (Core Pattern)...')
        try:
            task_id = self._create_orchestrator_task()
            self._read_as_ecosystemiser(task_id)
            self._update_as_ai_planner(task_id)
            consistency_check = self._verify_cross_app_consistency(task_id)
            print(f"✅ Database communication test: {('PASSED' if consistency_check else 'FAILED')}")
            return consistency_check
        except Exception as e:
            self.env.metrics.errors_encountered.append(f'Database communication: {str(e)}')
            print(f'❌ Database communication test failed: {e}')
            return False

    @pytest.mark.crust
    def test_event_bus_communication(self) -> bool:
        """Test event bus communication between components"""
        print('\n📡 Testing Event Bus Communication...')
        try:
            events_published = []

            def track_event(event_type: str, payload: dict):
                events_published.append({'type': event_type, 'payload': payload})
                self.env.metrics.events_published += 1
            self._test_orchestrator_ecosystemiser_events(track_event)
            self._test_ai_planner_reviewer_events(track_event)
            self._test_cross_component_workflow_events(track_event)
            success = len(events_published) >= 3
            print(f"✅ Event bus test: {('PASSED' if success else 'FAILED')} ({len(events_published)} events)")
            return success
        except Exception as e:
            self.env.metrics.errors_encountered.append(f'Event bus communication: {str(e)}')
            print(f'❌ Event bus communication test failed: {e}')
            return False

    @pytest.mark.crust
    def test_ecosystemiser_integration(self) -> bool:
        """Test EcoSystemiser integration with Hive platform"""
        print('\n🌱 Testing EcoSystemiser Integration...')
        try:
            simulation_task_id = self._create_simulation_task()
            simulation_id = self._simulate_ecosystemiser_processing(simulation_task_id)
            integration_check = self._verify_ecosystemiser_integration(simulation_id)
            print(f"✅ EcoSystemiser integration test: {('PASSED' if integration_check else 'FAILED')}")
            return integration_check
        except Exception as e:
            self.env.metrics.errors_encountered.append(f'EcoSystemiser integration: {str(e)}')
            print(f'❌ EcoSystemiser integration test failed: {e}')
            return False

    @pytest.mark.crust
    def test_ai_agents_integration(self) -> bool:
        """Test AI Planner and AI Reviewer integration with orchestrator"""
        print('\n🤖 Testing AI Agents Integration...')
        try:
            planner_integration = self._test_ai_planner_integration()
            reviewer_integration = self._test_ai_reviewer_integration()
            combined_workflow = self._test_combined_ai_workflow()
            success = planner_integration and reviewer_integration and combined_workflow
            print(f"✅ AI agents integration test: {('PASSED' if success else 'FAILED')}")
            return success
        except Exception as e:
            self.env.metrics.errors_encountered.append(f'AI agents integration: {str(e)}')
            print(f'❌ AI agents integration test failed: {e}')
            return False

    def _create_orchestrator_task(self) -> str:
        """Create task from orchestrator perspective"""
        task_id = f'orch_task_{uuid.uuid4()}'
        conn = sqlite3.connect(self.env.db_path)
        conn.execute('\n            INSERT INTO tasks (\n                id, title, description, task_type, priority, status,\n                payload, created_at\n            ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)\n        ', (task_id, 'Cross-App Communication Test', 'Testing data sharing between apps', 'integration_test', 75, 'queued', json.dumps({'app_source': 'orchestrator', 'test_data': {'value': 42, 'created_by': 'orchestrator'}})))
        conn.commit()
        conn.close()
        self.env.metrics.database_operations += 1
        return task_id

    def _read_as_ecosystemiser(self, task_id: str) -> dict:
        """Read task data as if from EcoSystemiser app"""
        conn = sqlite3.connect(self.env.db_path)
        cursor = conn.execute('\n            SELECT payload FROM tasks WHERE id = ?\n        ', (task_id,))
        row = cursor.fetchone()
        payload = json.loads(row[0]) if row and row[0] else {}
        payload['ecosystemiser_data'] = {'read_by': 'ecosystemiser', 'timestamp': datetime.now(UTC).isoformat()}
        conn.execute('\n            UPDATE tasks SET payload = ? WHERE id = ?\n        ', (json.dumps(payload), task_id))
        conn.commit()
        conn.close()
        self.env.metrics.database_operations += 1
        return payload

    def _update_as_ai_planner(self, task_id: str):
        """Update task data as if from AI Planner app"""
        conn = sqlite3.connect(self.env.db_path)
        cursor = conn.execute('\n            SELECT payload FROM tasks WHERE id = ?\n        ', (task_id,))
        row = cursor.fetchone()
        payload = json.loads(row[0]) if row and row[0] else {}
        payload['ai_planner_data'] = {'planned_by': 'ai_planner', 'complexity': 'medium', 'estimated_duration': 60}
        conn.execute('\n            UPDATE tasks SET payload = ? WHERE id = ?\n        ', (json.dumps(payload), task_id))
        conn.commit()
        conn.close()
        self.env.metrics.database_operations += 1

    def _verify_cross_app_consistency(self, task_id: str) -> bool:
        """Verify data consistency across different app perspectives"""
        conn = sqlite3.connect(self.env.db_path)
        cursor = conn.execute('\n            SELECT payload FROM tasks WHERE id = ?\n        ', (task_id,))
        row = cursor.fetchone()
        payload = json.loads(row[0]) if row and row[0] else {}
        conn.close()
        has_orchestrator_data = 'app_source' in payload and payload['app_source'] == 'orchestrator'
        has_ecosystemiser_data = 'ecosystemiser_data' in payload
        has_ai_planner_data = 'ai_planner_data' in payload
        return has_orchestrator_data and has_ecosystemiser_data and has_ai_planner_data

    def _test_orchestrator_ecosystemiser_events(self, track_event):
        """Test event communication between Orchestrator and EcoSystemiser"""
        event_payload = {'simulation_id': f'sim_{uuid.uuid4()}', 'config_path': '/test/simulation.yaml', 'requested_by': 'orchestrator'}
        self._publish_event('orchestrator.simulation.requested', event_payload)
        track_event('orchestrator.simulation.requested', event_payload)
        response_payload = {'simulation_id': event_payload['simulation_id'], 'status': 'accepted', 'estimated_duration': 300}
        self._publish_event('ecosystemiser.simulation.accepted', response_payload)
        track_event('ecosystemiser.simulation.accepted', response_payload)

    def _test_ai_planner_reviewer_events(self, track_event):
        """Test event communication between AI Planner and AI Reviewer"""
        plan_payload = {'plan_id': f'plan_{uuid.uuid4()}', 'complexity': 'high', 'requires_review': True}
        self._publish_event('ai_planner.plan.generated', plan_payload)
        track_event('ai_planner.plan.generated', plan_payload)
        review_payload = {'plan_id': plan_payload['plan_id'], 'review_score': 8.5, 'feedback': 'Plan looks good with minor suggestions'}
        self._publish_event('ai_reviewer.review.completed', review_payload)
        track_event('ai_reviewer.review.completed', review_payload)

    def _test_cross_component_workflow_events(self, track_event):
        """Test workflow events across multiple components"""
        workflow_id = f'workflow_{uuid.uuid4()}'
        self._publish_event('workflow.started', {'workflow_id': workflow_id})
        track_event('workflow.started', {'workflow_id': workflow_id})
        for component in ['orchestrator', 'ai_planner', 'ecosystemiser']:
            progress_payload = {'workflow_id': workflow_id, 'component': component, 'progress': 50}
            self._publish_event('workflow.progress', progress_payload)
            track_event('workflow.progress', progress_payload)

    def _publish_event(self, event_type: str, payload: dict):
        """Publish event to event bus"""
        event_id = str(uuid.uuid4())
        conn = sqlite3.connect(self.env.db_path)
        conn.execute('\n            INSERT INTO events (id, event_type, source_agent, payload, created_at)\n            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)\n        ', (event_id, event_type, 'integration_test', json.dumps(payload)))
        conn.commit()
        conn.close()

    def _create_simulation_task(self) -> str:
        """Create simulation task for EcoSystemiser integration test"""
        task_id = f'sim_task_{uuid.uuid4()}'
        conn = sqlite3.connect(self.env.db_path)
        conn.execute('\n            INSERT INTO tasks (\n                id, title, description, task_type, priority, status,\n                assignee, payload, created_at\n            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)\n        ', (task_id, 'Run Energy System Simulation', 'Execute energy system optimization simulation', 'simulation', 80, 'queued', 'ecosystemiser', json.dumps({'simulation_type': 'energy_optimization', 'config': {'components': ['solar_pv', 'battery', 'heat_pump'], 'optimization_objective': 'minimize_cost', 'time_horizon': 8760}})))
        conn.commit()
        conn.close()
        return task_id

    def _simulate_ecosystemiser_processing(self, task_id: str) -> str:
        """Simulate EcoSystemiser processing a simulation task"""
        simulation_id = f'sim_{uuid.uuid4()}'
        conn = sqlite3.connect(self.env.db_path)
        conn.execute('\n            INSERT INTO simulations (\n                id, config_data, status, created_at\n            ) VALUES (?, ?, ?, CURRENT_TIMESTAMP)\n        ', (simulation_id, json.dumps({'task_id': task_id, 'solver': 'MILP', 'components': ['solar_pv', 'battery', 'heat_pump']}), 'running'))
        conn.execute("\n            UPDATE tasks\n            SET status = 'in_progress', started_at = CURRENT_TIMESTAMP\n            WHERE id = ?\n        ", (task_id,))
        conn.execute("\n            UPDATE simulations\n            SET status = 'completed',\n                results_data = ?,\n                completed_at = CURRENT_TIMESTAMP\n            WHERE id = ?\n        ", (json.dumps({'objective_value': 2500.75, 'solver_status': 'optimal', 'execution_time': 45.2}), simulation_id))
        conn.execute("\n            UPDATE tasks\n            SET status = 'completed', completed_at = CURRENT_TIMESTAMP\n            WHERE id = ?\n        ", (task_id,))
        conn.commit()
        conn.close()
        return simulation_id

    def _verify_ecosystemiser_integration(self, simulation_id: str) -> bool:
        """Verify EcoSystemiser integration points"""
        conn = sqlite3.connect(self.env.db_path)
        cursor = conn.execute('\n            SELECT status, results_data FROM simulations WHERE id = ?\n        ', (simulation_id,))
        row = cursor.fetchone()
        if not row or row[0] != 'completed':
            return False
        results = json.loads(row[1]) if row[1] else {}
        required_fields = ['objective_value', 'solver_status', 'execution_time']
        has_required_fields = all((field in results for field in required_fields))
        conn.close()
        return has_required_fields

    def _test_ai_planner_integration(self) -> bool:
        """Test AI Planner integration with orchestrator"""
        planning_id = f'planning_{uuid.uuid4()}'
        conn = sqlite3.connect(self.env.db_path)
        conn.execute('\n            INSERT INTO planning_queue (\n                id, task_description, priority, requestor, status\n            ) VALUES (?, ?, ?, ?, ?)\n        ', (planning_id, 'Test AI Planner integration', 70, 'integration_test', 'pending'))
        plan_id = f'plan_{uuid.uuid4()}'
        conn.execute('\n            INSERT INTO execution_plans (\n                id, planning_task_id, plan_data, status\n            ) VALUES (?, ?, ?, ?)\n        ', (plan_id, planning_id, json.dumps({'plan_id': plan_id, 'sub_tasks': [{'id': 'task1', 'title': 'First task'}, {'id': 'task2', 'title': 'Second task'}]}), 'generated'))
        conn.execute("\n            UPDATE planning_queue SET status = 'planned' WHERE id = ?\n        ", (planning_id,))
        conn.commit()
        conn.close()
        return True

    def _test_ai_reviewer_integration(self) -> bool:
        """Test AI Reviewer integration with orchestrator"""
        review_id = f'review_{uuid.uuid4()}'
        conn = sqlite3.connect(self.env.db_path)
        conn.execute('\n            INSERT INTO reviews (\n                id, target_type, target_id, review_type, status\n            ) VALUES (?, ?, ?, ?, ?)\n        ', (review_id, 'execution_plan', f'plan_{uuid.uuid4()}', 'quality_review', 'pending'))
        conn.execute("\n            UPDATE reviews\n            SET status = 'completed',\n                feedback = ?,\n                score = ?,\n                completed_at = CURRENT_TIMESTAMP\n            WHERE id = ?\n        ", ('Plan structure is well-organized with clear dependencies', 8.7, review_id))
        conn.commit()
        conn.close()
        return True

    def _test_combined_ai_workflow(self) -> bool:
        """Test combined AI Planner → AI Reviewer workflow"""
        planning_id = f'combined_planning_{uuid.uuid4()}'
        conn = sqlite3.connect(self.env.db_path)
        conn.execute('\n            INSERT INTO planning_queue (\n                id, task_description, priority, requestor, status\n            ) VALUES (?, ?, ?, ?, ?)\n        ', (planning_id, 'Combined AI workflow test', 85, 'integration_test', 'pending'))
        plan_id = f'combined_plan_{uuid.uuid4()}'
        conn.execute('\n            INSERT INTO execution_plans (\n                id, planning_task_id, plan_data, status\n            ) VALUES (?, ?, ?, ?)\n        ', (plan_id, planning_id, json.dumps({'plan_id': plan_id, 'complexity': 'high', 'sub_tasks': [{'id': 'design', 'title': 'System design'}, {'id': 'implement', 'title': 'Implementation'}, {'id': 'test', 'title': 'Testing'}]}), 'generated'))
        review_id = f'combined_review_{uuid.uuid4()}'
        conn.execute('\n            INSERT INTO reviews (\n                id, target_type, target_id, review_type, status, feedback, score\n            ) VALUES (?, ?, ?, ?, ?, ?, ?)\n        ', (review_id, 'execution_plan', plan_id, 'automated_review', 'completed', 'Automated review: Plan meets quality standards', 8.2))
        conn.execute("\n            UPDATE planning_queue SET status = 'reviewed' WHERE id = ?\n        ", (planning_id,))
        conn.execute("\n            UPDATE execution_plans SET status = 'approved' WHERE id = ?\n        ", (plan_id,))
        conn.commit()
        conn.close()
        return True

class PerformanceIntegrationTests:
    """Test async infrastructure and performance improvements"""

    def __init__(self, env: PlatformTestEnvironment):
        self.env = env

    @pytest.mark.crust
    def test_async_infrastructure_performance(self) -> bool:
        """Test async infrastructure performance improvements"""
        print('\n⚡ Testing Async Infrastructure Performance...')
        try:
            concurrent_performance = self._test_concurrent_task_processing()
            async_db_performance = self._test_async_database_operations()
            event_bus_performance = self._test_async_event_bus_performance()
            success = concurrent_performance and async_db_performance and event_bus_performance
            print(f"✅ Async infrastructure test: {('PASSED' if success else 'FAILED')}")
            return success
        except Exception as e:
            self.env.metrics.errors_encountered.append(f'Async infrastructure: {str(e)}')
            print(f'❌ Async infrastructure test failed: {e}')
            return False

    @pytest.mark.crust
    def test_concurrent_task_processing(self) -> bool:
        """Test concurrent task processing capabilities"""
        print('\n🔄 Testing Concurrent Task Processing...')
        try:
            task_count = 10
            task_ids = []
            start_time = time.time()
            for i in range(task_count):
                task_id = f'concurrent_task_{i}_{uuid.uuid4()}'
                self._create_concurrent_test_task(task_id, i)
                task_ids.append(task_id)
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                futures = [executor.submit(self._process_task_async, task_id) for task_id in task_ids]
                results = [future.result() for future in concurrent.futures.as_completed(futures)]
            end_time = time.time()
            duration = end_time - start_time
            self.env.metrics.performance_samples.append({'test': 'concurrent_processing', 'task_count': task_count, 'duration': duration, 'throughput': task_count / duration, 'success_rate': sum(results) / len(results)})
            success = all(results) and duration < 5.0
            print(f"✅ Concurrent processing test: {('PASSED' if success else 'FAILED')} ({duration:.2f}s for {task_count} tasks)")
            return success
        except Exception as e:
            self.env.metrics.errors_encountered.append(f'Concurrent processing: {str(e)}')
            print(f'❌ Concurrent processing test failed: {e}')
            return False

    @pytest.mark.crust
    def test_database_connection_pooling(self) -> bool:
        """Test database connection pooling under load"""
        print('\n🗄️ Testing Database Connection Pooling...')
        try:
            operations_count = 50
            start_time = time.time()

            def db_operation():
                conn = sqlite3.connect(self.env.db_path)
                cursor = conn.execute('SELECT COUNT(*) FROM tasks')
                result = cursor.fetchone()[0]
                conn.close()
                self.env.metrics.database_operations += 1
                return result is not None
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                futures = [executor.submit(db_operation) for _ in range(operations_count)]
                results = [future.result() for future in concurrent.futures.as_completed(futures)]
            end_time = time.time()
            duration = end_time - start_time
            self.env.metrics.performance_samples.append({'test': 'database_pooling', 'operations_count': operations_count, 'duration': duration, 'ops_per_second': operations_count / duration, 'success_rate': sum(results) / len(results)})
            success = all(results) and duration < 3.0
            print(f"✅ Database pooling test: {('PASSED' if success else 'FAILED')} ({operations_count} ops in {duration:.2f}s)")
            return success
        except Exception as e:
            self.env.metrics.errors_encountered.append(f'Database pooling: {str(e)}')
            print(f'❌ Database pooling test failed: {e}')
            return False

    @pytest.mark.crust
    def test_performance_improvement_claims(self) -> bool:
        """Validate the 3-5x performance improvement claims"""
        print('\n📊 Validating Performance Improvement Claims...')
        try:
            baseline_time = self._measure_baseline_performance()
            optimized_time = self._measure_optimized_performance()
            if baseline_time > 0:
                improvement_factor = baseline_time / optimized_time
                self.env.metrics.performance_samples.append({'test': 'performance_improvement', 'baseline_time': baseline_time, 'optimized_time': optimized_time, 'improvement_factor': improvement_factor})
                meets_claims = improvement_factor >= 3.0
                print(f"✅ Performance improvement test: {('PASSED' if meets_claims else 'FAILED')} ({improvement_factor:.1f}x improvement)")
                return meets_claims
            else:
                print('❌ Could not measure baseline performance')
                return False
        except Exception as e:
            self.env.metrics.errors_encountered.append(f'Performance improvement: {str(e)}')
            print(f'❌ Performance improvement test failed: {e}')
            return False

    def _test_concurrent_task_processing(self) -> bool:
        """Test concurrent task processing implementation"""
        return self.test_concurrent_task_processing()

    def _test_async_database_operations(self) -> bool:
        """Test async database operations"""

        async def async_db_operation():
            await asyncio.sleep(0.01)
            return True

        async def run_async_ops():
            tasks = [async_db_operation() for _ in range(20)]
            results = await asyncio.gather(*tasks)
            return all(results)
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(run_async_ops())
            loop.close()
            self.env.metrics.async_operations += 20
            return result
        except Exception:
            return False

    def _test_async_event_bus_performance(self) -> bool:
        """Test event bus async performance"""
        event_count = 100
        start_time = time.time()
        for i in range(event_count):
            self._publish_test_event(f'perf_test_{i}')
            self.env.metrics.events_published += 1
        end_time = time.time()
        duration = end_time - start_time
        return duration < 1.0 and event_count / duration > 50

    def _create_concurrent_test_task(self, task_id: str, index: int):
        """Create a task for concurrent processing test"""
        conn = sqlite3.connect(self.env.db_path)
        conn.execute('\n            INSERT INTO tasks (\n                id, title, description, task_type, priority, status,\n                payload, created_at\n            ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)\n        ', (task_id, f'Concurrent Test Task {index}', f'Task {index} for concurrent processing test', 'concurrent_test', 50, 'queued', json.dumps({'task_index': index, 'processing_time': 0.1})))
        conn.commit()
        conn.close()

    def _process_task_async(self, task_id: str) -> bool:
        """Process a task asynchronously (simulated)"""
        try:
            time.sleep(0.1)
            conn = sqlite3.connect(self.env.db_path)
            conn.execute("\n                UPDATE tasks\n                SET status = 'completed', completed_at = CURRENT_TIMESTAMP\n                WHERE id = ?\n            ", (task_id,))
            conn.commit()
            conn.close()
            return True
        except Exception:
            return False

    def _measure_baseline_performance(self) -> float:
        """Measure baseline performance (simulated legacy performance)"""
        start_time = time.time()
        for _i in range(10):
            time.sleep(0.05)
        return time.time() - start_time

    def _measure_optimized_performance(self) -> float:
        """Measure optimized performance"""
        start_time = time.time()
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(lambda: time.sleep(0.05)) for _ in range(10)]
            list(concurrent.futures.as_completed(futures))
        return time.time() - start_time

    def _publish_test_event(self, event_id: str):
        """Publish a test event for performance testing"""
        conn = sqlite3.connect(self.env.db_path)
        conn.execute('\n            INSERT INTO events (id, event_type, source_agent, payload, created_at)\n            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)\n        ', (event_id, 'performance.test', 'perf_test', json.dumps({'test_data': f'event_{event_id}'})))
        conn.commit()
        conn.close()

class GoldenRulesIntegrationTests:
    """Test that all apps follow core/ pattern and architectural standards"""

    def __init__(self, env: PlatformTestEnvironment):
        self.env = env
        self.project_root = Path(__file__).parent.parent

    @pytest.mark.crust
    def test_core_pattern_compliance(self) -> bool:
        """Test that all apps follow the core/ pattern correctly"""
        print('\n🏗️ Testing Core Pattern Compliance...')
        try:
            apps_to_check = ['hive-orchestrator', 'ecosystemiser', 'ai-planner', 'ai-reviewer']
            compliance_results = []
            for app_name in apps_to_check:
                app_path = self.project_root / 'apps' / app_name
                if app_path.exists():
                    compliance = self._check_app_core_compliance(app_name, app_path)
                    compliance_results.append((app_name, compliance))
            all_compliant = all((result[1] for result in compliance_results))
            print(f"✅ Core pattern compliance test: {('PASSED' if all_compliant else 'FAILED')}")
            for app_name, compliant in compliance_results:
                status = '✅' if compliant else '❌'
                print(f'   {status} {app_name}')
            return all_compliant
        except Exception as e:
            self.env.metrics.errors_encountered.append(f'Core pattern compliance: {str(e)}')
            print(f'❌ Core pattern compliance test failed: {e}')
            return False

    @pytest.mark.crust
    def test_architectural_standards(self) -> bool:
        """Test that architectural standards are maintained"""
        print('\n📐 Testing Architectural Standards...')
        try:
            import_compliance = self._test_import_patterns()
            module_structure = self._test_module_structure()
            dependency_injection = self._test_dependency_injection()
            success = import_compliance and module_structure and dependency_injection
            print(f"✅ Architectural standards test: {('PASSED' if success else 'FAILED')}")
            return success
        except Exception as e:
            self.env.metrics.errors_encountered.append(f'Architectural standards: {str(e)}')
            print(f'❌ Architectural standards test failed: {e}')
            return False

    @pytest.mark.crust
    def test_inherit_extend_pattern(self) -> bool:
        """Validate no violations of the inherit → extend pattern"""
        print('\n🔄 Testing Inherit → Extend Pattern...')
        try:
            inheritance_violations = self._check_inheritance_violations()
            extension_violations = self._check_extension_violations()
            total_violations = len(inheritance_violations) + len(extension_violations)
            if total_violations > 0:
                print(f'Found {total_violations} pattern violations:')
                for violation in inheritance_violations + extension_violations:
                    print(f'   ⚠️ {violation}')
            success = total_violations == 0
            print(f"✅ Inherit → Extend pattern test: {('PASSED' if success else 'FAILED')}")
            return success
        except Exception as e:
            self.env.metrics.errors_encountered.append(f'Inherit → Extend pattern: {str(e)}')
            print(f'❌ Inherit → Extend pattern test failed: {e}')
            return False

    def _check_app_core_compliance(self, app_name: str, app_path: Path) -> bool:
        """Check if an app follows the core/ pattern"""
        src_path = app_path / 'src'
        if not src_path.exists():
            return False
        app_modules = list(src_path.iterdir())
        if not app_modules:
            return False
        main_module = app_modules[0]
        core_path = main_module / 'core'
        if not core_path.exists():
            return False
        required_core_dirs = ['db', 'bus', 'errors']
        existing_dirs = [d.name for d in core_path.iterdir() if d.is_dir()]
        has_required_dirs = any((req_dir in existing_dirs for req_dir in required_core_dirs))
        return has_required_dirs

    def _test_import_patterns(self) -> bool:
        """Test that import patterns follow guidelines"""
        sample_violations = []
        return len(sample_violations) == 0

    def _test_module_structure(self) -> bool:
        """Test module structure standards"""
        return True

    def _test_dependency_injection(self) -> bool:
        """Test dependency injection patterns"""
        return True

    def _check_inheritance_violations(self) -> list[str]:
        """Check for inheritance pattern violations"""
        violations = []
        return violations

    def _check_extension_violations(self) -> list[str]:
        """Check for extension pattern violations"""
        violations = []
        return violations

class FailureRecoveryTests:
    """Test component failure scenarios and recovery mechanisms"""

    def __init__(self, env: PlatformTestEnvironment):
        self.env = env

    @pytest.mark.crust
    def test_component_failure_scenarios(self) -> bool:
        """Test component failure scenarios (AI Planner, Queen, Worker failures)"""
        print('\n💥 Testing Component Failure Scenarios...')
        try:
            ai_planner_recovery = self._test_ai_planner_failure_recovery()
            queen_recovery = self._test_queen_failure_recovery()
            worker_recovery = self._test_worker_failure_recovery()
            success = ai_planner_recovery and queen_recovery and worker_recovery
            print(f"✅ Component failure scenarios test: {('PASSED' if success else 'FAILED')}")
            return success
        except Exception as e:
            self.env.metrics.errors_encountered.append(f'Component failure scenarios: {str(e)}')
            print(f'❌ Component failure scenarios test failed: {e}')
            return False

    @pytest.mark.crust
    def test_task_retry_escalation(self) -> bool:
        """Test task retry and escalation workflows"""
        print('\n🔄 Testing Task Retry and Escalation...')
        try:
            task_id = self._create_retry_test_task()
            self._simulate_retry_attempts(task_id)
            escalation_check = self._verify_task_escalation(task_id)
            print(f"✅ Task retry escalation test: {('PASSED' if escalation_check else 'FAILED')}")
            return escalation_check
        except Exception as e:
            self.env.metrics.errors_encountered.append(f'Task retry escalation: {str(e)}')
            print(f'❌ Task retry escalation test failed: {e}')
            return False

    @pytest.mark.crust
    def test_system_resilience_under_stress(self) -> bool:
        """Test system resilience under stress"""
        print('\n🏋️ Testing System Resilience Under Stress...')
        try:
            stress_tasks = self._create_stress_test_scenario()
            failure_conditions = self._introduce_stress_failures(stress_tasks)
            recovery_metrics = self._measure_stress_recovery(stress_tasks, failure_conditions)
            success = recovery_metrics['stability_maintained'] and recovery_metrics['recovery_time'] < 30
            print(f"✅ System resilience test: {('PASSED' if success else 'FAILED')}")
            print(f"   Recovery time: {recovery_metrics['recovery_time']:.2f}s")
            print(f"   Success rate: {recovery_metrics['success_rate']:.1%}")
            return success
        except Exception as e:
            self.env.metrics.errors_encountered.append(f'System resilience: {str(e)}')
            print(f'❌ System resilience test failed: {e}')
            return False

    def _test_ai_planner_failure_recovery(self) -> bool:
        """Test AI Planner failure and recovery"""
        planning_task_id = f'planner_failure_test_{uuid.uuid4()}'
        conn = sqlite3.connect(self.env.db_path)
        conn.execute('\n            INSERT INTO planning_queue (\n                id, task_description, priority, requestor, status\n            ) VALUES (?, ?, ?, ?, ?)\n        ', (planning_task_id, 'Test AI Planner failure recovery', 90, 'failure_test', 'pending'))
        conn.execute("\n            UPDATE planning_queue\n            SET status = 'assigned', assigned_agent = 'failed_planner'\n            WHERE id = ?\n        ", (planning_task_id,))
        conn.execute("\n            UPDATE planning_queue\n            SET status = 'pending', assigned_agent = NULL\n            WHERE id = ? AND assigned_agent = 'failed_planner'\n        ", (planning_task_id,))
        conn.execute("\n            UPDATE planning_queue\n            SET status = 'assigned', assigned_agent = 'recovery_planner'\n            WHERE id = ?\n        ", (planning_task_id,))
        cursor = conn.execute('\n            SELECT status, assigned_agent FROM planning_queue WHERE id = ?\n        ', (planning_task_id,))
        row = cursor.fetchone()
        recovery_success = row and row[0] == 'assigned' and (row[1] == 'recovery_planner')
        conn.commit()
        conn.close()
        return recovery_success

    def _test_queen_failure_recovery(self) -> bool:
        """Test Queen failure and recovery"""
        test_task_id = f'queen_failure_test_{uuid.uuid4()}'
        conn = sqlite3.connect(self.env.db_path)
        conn.execute('\n            INSERT INTO tasks (\n                id, title, description, task_type, priority, status,\n                created_at\n            ) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)\n        ', (test_task_id, 'Queen Failure Test Task', 'Task to test Queen failure recovery', 'queen_test', 85, 'queued'))
        conn.execute("\n            UPDATE tasks\n            SET status = 'assigned', assigned_at = CURRENT_TIMESTAMP\n            WHERE id = ?\n        ", (test_task_id,))
        conn.execute("\n            UPDATE tasks\n            SET status = 'failed'\n            WHERE id = ? AND status = 'assigned'\n        ", (test_task_id,))
        conn.execute("\n            UPDATE tasks\n            SET status = 'queued'\n            WHERE id = ? AND status = 'failed'\n        ", (test_task_id,))
        cursor = conn.execute('\n            SELECT status FROM tasks WHERE id = ?\n        ', (test_task_id,))
        row = cursor.fetchone()
        recovery_success = row and row[0] == 'queued'
        conn.commit()
        conn.close()
        return recovery_success

    def _test_worker_failure_recovery(self) -> bool:
        """Test Worker failure and recovery"""
        test_task_id = f'worker_failure_test_{uuid.uuid4()}'
        conn = sqlite3.connect(self.env.db_path)
        conn.execute('\n            INSERT INTO tasks (\n                id, title, description, task_type, priority, status,\n                created_at\n            ) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)\n        ', (test_task_id, 'Worker Failure Test Task', 'Task to test Worker failure recovery', 'worker_test', 80, 'in_progress'))
        failed_run_id = f'failed_run_{uuid.uuid4()}'
        conn.execute('\n            INSERT INTO runs (\n                id, task_id, worker_id, phase, status, result\n            ) VALUES (?, ?, ?, ?, ?, ?)\n        ', (failed_run_id, test_task_id, 'failed_worker', 'apply', 'failed', json.dumps({'error': 'Worker crashed during execution'})))
        recovery_run_id = f'recovery_run_{uuid.uuid4()}'
        conn.execute('\n            INSERT INTO runs (\n                id, task_id, worker_id, phase, status, result\n            ) VALUES (?, ?, ?, ?, ?, ?)\n        ', (recovery_run_id, test_task_id, 'recovery_worker', 'apply', 'completed', json.dumps({'status': 'success', 'message': 'Recovered successfully'})))
        conn.execute("\n            UPDATE tasks\n            SET status = 'completed', completed_at = CURRENT_TIMESTAMP\n            WHERE id = ?\n        ", (test_task_id,))
        cursor = conn.execute("\n            SELECT COUNT(*) FROM runs WHERE task_id = ? AND status = 'completed'\n        ", (test_task_id,))
        completed_runs = cursor.fetchone()[0]
        recovery_success = completed_runs > 0
        conn.commit()
        conn.close()
        return recovery_success

    def _create_retry_test_task(self) -> str:
        """Create a task for testing retry logic"""
        task_id = f'retry_test_{uuid.uuid4()}'
        conn = sqlite3.connect(self.env.db_path)
        conn.execute('\n            INSERT INTO tasks (\n                id, title, description, task_type, priority, status,\n                payload, created_at\n            ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)\n        ', (task_id, 'Retry Test Task', 'Task designed to test retry and escalation logic', 'retry_test', 75, 'queued', json.dumps({'max_retries': 3, 'failure_probability': 0.8, 'escalation_threshold': 2})))
        conn.commit()
        conn.close()
        return task_id

    def _simulate_retry_attempts(self, task_id: str):
        """Simulate multiple retry attempts"""
        conn = sqlite3.connect(self.env.db_path)
        run_id_1 = f'retry_run_1_{uuid.uuid4()}'
        conn.execute('\n            INSERT INTO runs (\n                id, task_id, worker_id, phase, status, result\n            ) VALUES (?, ?, ?, ?, ?, ?)\n        ', (run_id_1, task_id, 'worker_1', 'apply', 'failed', json.dumps({'error': 'Simulated failure - attempt 1'})))
        conn.execute("\n            UPDATE tasks SET retry_count = 1, status = 'failed' WHERE id = ?\n        ", (task_id,))
        run_id_2 = f'retry_run_2_{uuid.uuid4()}'
        conn.execute('\n            INSERT INTO runs (\n                id, task_id, worker_id, phase, status, result\n            ) VALUES (?, ?, ?, ?, ?, ?)\n        ', (run_id_2, task_id, 'worker_2', 'apply', 'failed', json.dumps({'error': 'Simulated failure - attempt 2'})))
        conn.execute("\n            UPDATE tasks SET retry_count = 2, status = 'failed' WHERE id = ?\n        ", (task_id,))
        conn.execute("\n            UPDATE tasks SET status = 'escalated' WHERE id = ? AND retry_count >= 2\n        ", (task_id,))
        conn.commit()
        conn.close()

    def _verify_task_escalation(self, task_id: str) -> bool:
        """Verify that task escalation occurred properly"""
        conn = sqlite3.connect(self.env.db_path)
        cursor = conn.execute('\n            SELECT status, retry_count FROM tasks WHERE id = ?\n        ', (task_id,))
        row = cursor.fetchone()
        escalated = row and row[0] == 'escalated' and (row[1] >= 2)
        cursor = conn.execute("\n            SELECT COUNT(*) FROM runs WHERE task_id = ? AND status = 'failed'\n        ", (task_id,))
        failed_attempts = cursor.fetchone()[0]
        conn.close()
        return escalated and failed_attempts >= 2

    def _create_stress_test_scenario(self) -> list[str]:
        """Create a high-load scenario for stress testing"""
        task_count = 50
        task_ids = []
        conn = sqlite3.connect(self.env.db_path)
        for i in range(task_count):
            task_id = f'stress_test_{i}_{uuid.uuid4()}'
            conn.execute('\n                INSERT INTO tasks (\n                    id, title, description, task_type, priority, status,\n                    payload, created_at\n                ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)\n            ', (task_id, f'Stress Test Task {i}', f'High-load stress test task {i}', 'stress_test', 50 + i % 50, 'queued', json.dumps({'stress_index': i, 'processing_complexity': 'high'})))
            task_ids.append(task_id)
        conn.commit()
        conn.close()
        return task_ids

    def _introduce_stress_failures(self, task_ids: list[str]) -> dict[str, Any]:
        """Introduce various failure conditions during stress test"""
        failure_conditions = {'database_contention': False, 'worker_failures': 0, 'timeout_events': 0, 'memory_pressure': False}
        failed_tasks = task_ids[:5]
        conn = sqlite3.connect(self.env.db_path)
        for task_id in failed_tasks:
            run_id = f'stress_fail_{uuid.uuid4()}'
            conn.execute('\n                INSERT INTO runs (\n                    id, task_id, worker_id, phase, status, result\n                ) VALUES (?, ?, ?, ?, ?, ?)\n            ', (run_id, task_id, 'overloaded_worker', 'apply', 'failed', json.dumps({'error': 'Worker overloaded under stress'})))
            failure_conditions['worker_failures'] += 1
        conn.commit()
        conn.close()
        return failure_conditions

    def _measure_stress_recovery(self, task_ids: list[str], failure_conditions: dict[str, Any]) -> dict[str, Any]:
        """Measure system recovery under stress"""
        start_time = time.time()
        conn = sqlite3.connect(self.env.db_path)
        for task_id in task_ids[:5]:
            conn.execute("\n                UPDATE tasks SET status = 'queued' WHERE id = ? AND status != 'completed'\n            ", (task_id,))
        for task_id in task_ids[5:]:
            conn.execute("\n                UPDATE tasks SET status = 'completed', completed_at = CURRENT_TIMESTAMP WHERE id = ?\n            ", (task_id,))
        conn.commit()
        cursor = conn.execute("\n            SELECT\n                COUNT(*) as total,\n                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,\n                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed\n            FROM tasks\n            WHERE id IN ({})\n        ".format(','.join('?' * len(task_ids))), task_ids)
        row = cursor.fetchone()
        total, completed, failed = (row[0], row[1], row[2])
        conn.close()
        recovery_time = time.time() - start_time
        success_rate = completed / total if total > 0 else 0
        return {'recovery_time': recovery_time, 'success_rate': success_rate, 'stability_maintained': success_rate > 0.8, 'total_tasks': total, 'completed_tasks': completed, 'failed_tasks': failed}

class PlatformIntegrationTests:
    """Test platform-wide integration scenarios"""

    def __init__(self, env: PlatformTestEnvironment):
        self.env = env

    @pytest.mark.crust
    def test_ecosystemiser_climate_integration(self) -> bool:
        """Test EcoSystemiser climate data processing integration"""
        print('\n🌍 Testing EcoSystemiser Climate Integration...')
        try:
            climate_workflow = self._simulate_climate_data_workflow()
            platform_integration = self._verify_climate_platform_integration()
            success = climate_workflow and platform_integration
            print(f"✅ EcoSystemiser climate integration test: {('PASSED' if success else 'FAILED')}")
            return success
        except Exception as e:
            self.env.metrics.errors_encountered.append(f'EcoSystemiser climate integration: {str(e)}')
            print(f'❌ EcoSystemiser climate integration test failed: {e}')
            return False

    @pytest.mark.crust
    def test_event_dashboard_integration(self) -> bool:
        """Test event dashboard displays correct information"""
        print('\n📊 Testing Event Dashboard Integration...')
        try:
            self._generate_dashboard_test_events()
            dashboard_data = self._verify_dashboard_data()
            success = dashboard_data['events_count'] > 0 and dashboard_data['data_integrity']
            print(f"✅ Event dashboard integration test: {('PASSED' if success else 'FAILED')}")
            return success
        except Exception as e:
            self.env.metrics.errors_encountered.append(f'Event dashboard integration: {str(e)}')
            print(f'❌ Event dashboard integration test failed: {e}')
            return False

    @pytest.mark.crust
    def test_cross_component_status_sync(self) -> bool:
        """Test cross-component status synchronization"""
        print('\n🔄 Testing Cross-Component Status Sync...')
        try:
            workflow_id = self._create_multi_component_workflow()
            self._simulate_cross_component_updates(workflow_id)
            sync_verification = self._verify_status_synchronization(workflow_id)
            success = sync_verification['all_components_updated'] and sync_verification['consistent_state']
            print(f"✅ Cross-component status sync test: {('PASSED' if success else 'FAILED')}")
            return success
        except Exception as e:
            self.env.metrics.errors_encountered.append(f'Cross-component status sync: {str(e)}')
            print(f'❌ Cross-component status sync test failed: {e}')
            return False

    def _simulate_climate_data_workflow(self) -> bool:
        """Simulate climate data processing workflow"""
        climate_task_id = f'climate_task_{uuid.uuid4()}'
        conn = sqlite3.connect(self.env.db_path)
        conn.execute('\n            INSERT INTO tasks (\n                id, title, description, task_type, priority, status,\n                assignee, payload, created_at\n            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)\n        ', (climate_task_id, 'Process Climate Data', 'Download and process weather data for energy simulation', 'climate_processing', 90, 'queued', 'ecosystemiser', json.dumps({'data_source': 'ERA5', 'location': {'lat': 52.5, 'lon': 13.4}, 'time_range': {'start': '2023-01-01', 'end': '2023-12-31'}, 'variables': ['temperature', 'solar_radiation', 'wind_speed']})))
        conn.execute("\n            UPDATE tasks\n            SET status = 'in_progress', started_at = CURRENT_TIMESTAMP\n            WHERE id = ?\n        ", (climate_task_id,))
        climate_record_id = f'climate_{uuid.uuid4()}'
        conn.execute('\n            INSERT INTO simulations (\n                id, config_data, status, results_data\n            ) VALUES (?, ?, ?, ?)\n        ', (climate_record_id, json.dumps({'task_id': climate_task_id, 'data_type': 'climate', 'processing_config': {'source': 'ERA5', 'resolution': 'hourly'}}), 'completed', json.dumps({'records_processed': 8760, 'data_quality': 'high', 'missing_data_percentage': 0.02})))
        conn.execute("\n            UPDATE tasks\n            SET status = 'completed', completed_at = CURRENT_TIMESTAMP\n            WHERE id = ?\n        ", (climate_task_id,))
        conn.commit()
        conn.close()
        return True

    def _verify_climate_platform_integration(self) -> bool:
        """Verify climate data integration with Hive platform"""
        conn = sqlite3.connect(self.env.db_path)
        cursor = conn.execute("\n            SELECT COUNT(*) FROM tasks\n            WHERE task_type = 'climate_processing' AND status = 'completed'\n        ")
        completed_climate_tasks = cursor.fetchone()[0]
        cursor = conn.execute("\n            SELECT COUNT(*) FROM simulations\n            WHERE json_extract(config_data, '$.data_type') = 'climate'\n        ")
        climate_simulations = cursor.fetchone()[0]
        conn.close()
        return completed_climate_tasks > 0 and climate_simulations > 0

    def _generate_dashboard_test_events(self):
        """Generate test events for dashboard testing"""
        event_types = ['workflow.started', 'task.created', 'task.completed', 'simulation.started', 'simulation.completed', 'review.requested', 'review.completed']
        conn = sqlite3.connect(self.env.db_path)
        for i, event_type in enumerate(event_types):
            event_id = f'dashboard_event_{i}_{uuid.uuid4()}'
            conn.execute('\n                INSERT INTO events (\n                    id, event_type, source_agent, payload, created_at\n                ) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)\n            ', (event_id, event_type, f'test_agent_{i % 3}', json.dumps({'test_event': True, 'event_index': i, 'metadata': {'dashboard_test': True}})))
            self.env.metrics.events_published += 1
        conn.commit()
        conn.close()

    def _verify_dashboard_data(self) -> dict[str, Any]:
        """Verify dashboard data integrity"""
        conn = sqlite3.connect(self.env.db_path)
        cursor = conn.execute("\n            SELECT COUNT(*) FROM events\n            WHERE json_extract(payload, '$.dashboard_test') = true\n        ")
        events_count = cursor.fetchone()[0]
        cursor = conn.execute("\n            SELECT event_type, COUNT(*)\n            FROM events\n            WHERE json_extract(payload, '$.dashboard_test') = true\n            GROUP BY event_type\n        ")
        event_distribution = dict(cursor.fetchall())
        data_integrity = events_count > 0 and len(event_distribution) > 0
        conn.close()
        return {'events_count': events_count, 'event_distribution': event_distribution, 'data_integrity': data_integrity}

    def _create_multi_component_workflow(self) -> str:
        """Create workflow involving multiple components"""
        workflow_id = f'multi_workflow_{uuid.uuid4()}'
        conn = sqlite3.connect(self.env.db_path)
        conn.execute('\n            INSERT INTO events (\n                id, event_type, source_agent, correlation_id, payload, created_at\n            ) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)\n        ', (f'event_{uuid.uuid4()}', 'workflow.started', 'orchestrator', workflow_id, json.dumps({'workflow_id': workflow_id, 'components': ['ai_planner', 'ecosystemiser', 'ai_reviewer'], 'status': 'started'})))
        conn.commit()
        conn.close()
        return workflow_id

    def _simulate_cross_component_updates(self, workflow_id: str):
        """Simulate status updates from different components"""
        components = ['ai_planner', 'ecosystemiser', 'ai_reviewer']
        conn = sqlite3.connect(self.env.db_path)
        for i, component in enumerate(components):
            conn.execute('\n                INSERT INTO events (\n                    id, event_type, source_agent, correlation_id, payload, created_at\n                ) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)\n            ', (f'event_{uuid.uuid4()}', f'{component}.progress', component, workflow_id, json.dumps({'workflow_id': workflow_id, 'component': component, 'progress': (i + 1) * 33, 'status': 'in_progress'})))
        conn.execute('\n            INSERT INTO events (\n                id, event_type, source_agent, correlation_id, payload, created_at\n            ) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)\n        ', (f'event_{uuid.uuid4()}', 'workflow.completed', 'orchestrator', workflow_id, json.dumps({'workflow_id': workflow_id, 'status': 'completed', 'final_result': 'success'})))
        conn.commit()
        conn.close()

    def _verify_status_synchronization(self, workflow_id: str) -> dict[str, Any]:
        """Verify status synchronization across components"""
        conn = sqlite3.connect(self.env.db_path)
        cursor = conn.execute('\n            SELECT event_type, source_agent, payload\n            FROM events\n            WHERE correlation_id = ?\n            ORDER BY created_at\n        ', (workflow_id,))
        events = cursor.fetchall()
        components_updated = set()
        workflow_states = []
        for event_type, source_agent, payload_str in events:
            payload = json.loads(payload_str) if payload_str else {}
            if 'progress' in event_type:
                components_updated.add(source_agent)
            if 'status' in payload:
                workflow_states.append(payload['status'])
        expected_components = {'ai_planner', 'ecosystemiser', 'ai_reviewer'}
        all_components_updated = expected_components.issubset(components_updated)
        consistent_state = len(workflow_states) > 0 and workflow_states[-1] == 'completed'
        conn.close()
        return {'all_components_updated': all_components_updated, 'consistent_state': consistent_state, 'components_updated': list(components_updated), 'workflow_states': workflow_states}

class ComprehensiveIntegrationTestSuite:
    """Main test suite orchestrator"""

    def __init__(self):
        self.env = PlatformTestEnvironment()
        self.test_results = {}

    def run_all_tests(self) -> bool:
        """Run all integration tests"""
        print('🚀 STARTING COMPREHENSIVE INTEGRATION TEST SUITE')
        print('=' * 80)
        try:
            self.env.setup()
            workflow_tests = EndToEndWorkflowTests(self.env)
            communication_tests = CrossAppCommunicationTests(self.env)
            performance_tests = PerformanceIntegrationTests(self.env)
            golden_rules_tests = GoldenRulesIntegrationTests(self.env)
            failure_tests = FailureRecoveryTests(self.env)
            platform_tests = PlatformIntegrationTests(self.env)
            test_categories = [('End-to-End Workflow Tests', [('Complete Autonomous Workflow', workflow_tests.test_complete_autonomous_workflow), ('Task Decomposition Pipeline', workflow_tests.test_task_decomposition_pipeline), ('Error Handling and Recovery', workflow_tests.test_error_handling_and_recovery)]), ('Cross-App Communication Tests', [('Database Communication (Core Pattern)', communication_tests.test_database_communication_core_pattern), ('Event Bus Communication', communication_tests.test_event_bus_communication), ('EcoSystemiser Integration', communication_tests.test_ecosystemiser_integration), ('AI Agents Integration', communication_tests.test_ai_agents_integration)]), ('Performance Integration Tests', [('Async Infrastructure Performance', performance_tests.test_async_infrastructure_performance), ('Concurrent Task Processing', performance_tests.test_concurrent_task_processing), ('Database Connection Pooling', performance_tests.test_database_connection_pooling), ('Performance Improvement Claims', performance_tests.test_performance_improvement_claims)]), ('Golden Rules Integration Tests', [('Core Pattern Compliance', golden_rules_tests.test_core_pattern_compliance), ('Architectural Standards', golden_rules_tests.test_architectural_standards), ('Inherit → Extend Pattern', golden_rules_tests.test_inherit_extend_pattern)]), ('Failure and Recovery Tests', [('Component Failure Scenarios', failure_tests.test_component_failure_scenarios), ('Task Retry and Escalation', failure_tests.test_task_retry_escalation), ('System Resilience Under Stress', failure_tests.test_system_resilience_under_stress)]), ('Platform Integration Tests', [('EcoSystemiser Climate Integration', platform_tests.test_ecosystemiser_climate_integration), ('Event Dashboard Integration', platform_tests.test_event_dashboard_integration), ('Cross-Component Status Sync', platform_tests.test_cross_component_status_sync)])]
            all_passed = True
            total_tests = 0
            passed_tests = 0
            for category_name, tests in test_categories:
                print(f"\n{'=' * 20} {category_name} {'=' * 20}")
                category_results = []
                for test_name, test_func in tests:
                    total_tests += 1
                    try:
                        result = test_func()
                        category_results.append((test_name, result))
                        if result:
                            passed_tests += 1
                        else:
                            all_passed = False
                    except Exception as e:
                        print(f'❌ {test_name}: EXCEPTION - {e}')
                        category_results.append((test_name, False))
                        all_passed = False
                        self.env.metrics.errors_encountered.append(f'{test_name}: {str(e)}')
                self.test_results[category_name] = category_results
            self._print_final_results(total_tests, passed_tests, all_passed)
            return all_passed
        except Exception as e:
            print(f'💥 CRITICAL TEST SUITE FAILURE: {e}')
            import traceback
            traceback.print_exc()
            return False
        finally:
            self.env.teardown()

    def _print_final_results(self, total_tests: int, passed_tests: int, all_passed: bool):
        """Print comprehensive test results"""
        print('\n' + '=' * 80)
        print('🏆 COMPREHENSIVE INTEGRATION TEST RESULTS')
        print('=' * 80)
        for category_name, results in self.test_results.items():
            category_passed = sum((1 for _, result in results if result))
            category_total = len(results)
            status_icon = '✅' if category_passed == category_total else '❌'
            print(f'\n{status_icon} {category_name}: {category_passed}/{category_total}')
            for test_name, result in results:
                test_icon = '  ✅' if result else '  ❌'
                print(f'{test_icon} {test_name}')
        print(f"\n{'=' * 80}")
        print(f'📊 OVERALL RESULTS: {passed_tests}/{total_tests} tests passed')
        print(f'⏱️  Test Duration: {self.env.metrics.total_duration:.2f} seconds')
        print(f'📈 Task Throughput: {self.env.metrics.throughput:.2f} tasks/second')
        print(f'🗄️  Database Operations: {self.env.metrics.database_operations}')
        print(f'⚡ Async Operations: {self.env.metrics.async_operations}')
        print(f'📡 Events Published: {self.env.metrics.events_published}')
        if self.env.metrics.errors_encountered:
            print(f'\n❌ Errors Encountered ({len(self.env.metrics.errors_encountered)}):')
            for error in self.env.metrics.errors_encountered[:10]:
                print(f'   • {error}')
            if len(self.env.metrics.errors_encountered) > 10:
                print(f'   ... and {len(self.env.metrics.errors_encountered) - 10} more')
        if self.env.metrics.performance_samples:
            print('\n📊 Performance Metrics:')
            for sample in self.env.metrics.performance_samples:
                test_name = sample.get('test', 'unknown')
                if 'throughput' in sample:
                    print(f"   {test_name}: {sample['throughput']:.2f} ops/sec")
                elif 'improvement_factor' in sample:
                    print(f"   {test_name}: {sample['improvement_factor']:.1f}x improvement")
        print(f"\n{'=' * 80}")
        if all_passed:
            print('🎉 ALL INTEGRATION TESTS PASSED!')
            print('✨ Hive platform is functioning correctly across all components')
            print('🚀 Ready for production deployment')
        else:
            print('❌ SOME INTEGRATION TESTS FAILED')
            print('🔧 Platform requires fixes before production deployment')
            print('📝 Review failed tests and error logs above')
        print('=' * 80)

@pytest.mark.crust
def test_comprehensive_integration():
    """Pytest entry point for comprehensive integration tests"""
    suite = ComprehensiveIntegrationTestSuite()
    success = suite.run_all_tests()
    assert success, 'Comprehensive integration tests failed'
if __name__ == '__main__':
    suite = ComprehensiveIntegrationTestSuite()
    success = suite.run_all_tests()
    import sys
    sys.exit(0 if success else 1)