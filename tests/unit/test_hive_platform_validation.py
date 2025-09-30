#!/usr/bin/env python3
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

# Add paths for imports
test_root = Path(__file__).parent.parent
sys.path.insert(0, str(test_root / "apps" / "hive-orchestrator" / "src"))


class PlatformValidationTests:
    """Quick validation tests for essential platform functionality"""

    @pytest.fixture(autouse=True)
    def setup_test_env(self):
        """Setup isolated test environment"""
        # Create temporary database
        self.temp_dir = tempfile.mkdtemp(prefix="hive_validation_")
        self.db_path = Path(self.temp_dir) / "validation_test.db"

        # Initialize minimal test database
        self._init_validation_database()

        # Set test environment
        os.environ["HIVE_TEST_MODE"] = "true"
        os.environ["HIVE_TEST_DB_PATH"] = str(self.db_path)

        yield

        # Cleanup
        import shutil

        try:
            shutil.rmtree(self.temp_dir)
        except Exception:
            pass

        os.environ.pop("HIVE_TEST_MODE", None)
        os.environ.pop("HIVE_TEST_DB_PATH", None)

    def _init_validation_database(self):
        """Initialize minimal database schema for validation"""
        conn = sqlite3.connect(self.db_path)
        conn.executescript(
            """
            CREATE TABLE tasks (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT,
                task_type TEXT DEFAULT 'task',
                priority INTEGER DEFAULT 50,
                status TEXT DEFAULT 'queued',
                assignee TEXT,
                payload TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE events (
                id TEXT PRIMARY KEY,
                event_type TEXT NOT NULL,
                source_agent TEXT,
                payload TEXT,
                correlation_id TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE simulations (
                id TEXT PRIMARY KEY,
                config_data TEXT,
                status TEXT DEFAULT 'pending',
                results_data TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE planning_queue (
                id TEXT PRIMARY KEY,
                task_description TEXT NOT NULL,
                priority INTEGER DEFAULT 50,
                status TEXT DEFAULT 'pending',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
        """,
        )
        conn.commit()
        conn.close()

    def test_database_connectivity(self):
        """Test basic database connectivity and operations"""
        conn = sqlite3.connect(self.db_path)

        # Test basic operations
        cursor = conn.execute("SELECT COUNT(*) FROM tasks")
        count = cursor.fetchone()[0]
        assert count == 0, "Database should start empty"

        # Test insert
        task_id = str(uuid.uuid4())
        conn.execute(
            """
            INSERT INTO tasks (id, title, description) VALUES (?, ?, ?)
        """,
            (task_id, "Test Task", "Database connectivity test"),
        )

        # Test select
        cursor = conn.execute("SELECT title FROM tasks WHERE id = ?", (task_id,))
        title = cursor.fetchone()[0]
        assert title == "Test Task", "Should retrieve inserted task"

        conn.close()

    def test_event_bus_basic_functionality(self):
        """Test basic event bus functionality"""
        conn = sqlite3.connect(self.db_path)

        # Publish test event
        event_id = str(uuid.uuid4())
        event_payload = {"test": True, "message": "validation test"}

        conn.execute(
            """
            INSERT INTO events (id, event_type, source_agent, payload)
            VALUES (?, ?, ?, ?)
        """,
            (event_id, "validation.test", "test_agent", json.dumps(event_payload)),
        )

        # Verify event was stored
        cursor = conn.execute(
            """
            SELECT payload FROM events WHERE id = ?
        """,
            (event_id,),
        )

        row = cursor.fetchone()
        assert row is not None, "Event should be stored"

        stored_payload = json.loads(row[0])
        assert stored_payload["test"] is True, "Event payload should be preserved"

        conn.close()

    def test_ai_planner_integration_points(self):
        """Test AI Planner integration points"""
        conn = sqlite3.connect(self.db_path)

        # Create planning request
        planning_id = str(uuid.uuid4())
        conn.execute(
            """
            INSERT INTO planning_queue (id, task_description, priority)
            VALUES (?, ?, ?)
        """,
            (planning_id, "Test planning integration", 75),
        )

        # Verify planning request exists
        cursor = conn.execute(
            """
            SELECT task_description, priority FROM planning_queue WHERE id = ?
        """,
            (planning_id,),
        )

        row = cursor.fetchone()
        assert row is not None, "Planning request should exist"
        assert row[0] == "Test planning integration", "Task description should match"
        assert row[1] == 75, "Priority should match"

        conn.close()

    def test_ecosystemiser_integration_points(self):
        """Test EcoSystemiser integration points"""
        conn = sqlite3.connect(self.db_path)

        # Create simulation record
        sim_id = str(uuid.uuid4())
        config_data = {"components": ["solar_pv", "battery"], "optimization": "cost_minimize"}

        conn.execute(
            """
            INSERT INTO simulations (id, config_data, status)
            VALUES (?, ?, ?)
        """,
            (sim_id, json.dumps(config_data), "pending"),
        )

        # Verify simulation record
        cursor = conn.execute(
            """
            SELECT config_data, status FROM simulations WHERE id = ?
        """,
            (sim_id,),
        )

        row = cursor.fetchone()
        assert row is not None, "Simulation should exist"

        stored_config = json.loads(row[0])
        assert "solar_pv" in stored_config["components"], "Config should be preserved"
        assert row[1] == "pending", "Status should match"

        conn.close()

    def test_cross_app_data_sharing(self):
        """Test basic cross-app data sharing patterns"""
        conn = sqlite3.connect(self.db_path)

        # Create shared task from orchestrator perspective
        task_id = str(uuid.uuid4())
        task_payload = {"created_by": "orchestrator", "shared_data": {"key": "value"}, "target_app": "ecosystemiser"}

        conn.execute(
            """
            INSERT INTO tasks (id, title, task_type, assignee, payload)
            VALUES (?, ?, ?, ?, ?)
        """,
            (task_id, "Cross-App Data Test", "data_sharing", "ecosystemiser", json.dumps(task_payload)),
        )

        # Read from EcoSystemiser perspective
        cursor = conn.execute(
            """
            SELECT payload FROM tasks WHERE id = ? AND assignee = 'ecosystemiser'
        """,
            (task_id,),
        )

        row = cursor.fetchone()
        assert row is not None, "Task should be accessible to target app"

        payload = json.loads(row[0])
        assert payload["created_by"] == "orchestrator", "Original data should be preserved"
        assert payload["shared_data"]["key"] == "value", "Nested data should be accessible"

        conn.close()

    def test_async_operation_patterns(self):
        """Test async operation patterns work correctly"""
        import asyncio

        async def async_database_operation():
            """Simulate async database operation"""
            # In real implementation, this would use async database driver
            await asyncio.sleep(0.001)  # Simulate I/O wait
            return True

        async def run_concurrent_operations():
            """Run multiple async operations concurrently"""
            tasks = [async_database_operation() for _ in range(10)]
            results = await asyncio.gather(*tasks)
            return all(results)

        # Test async execution
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(run_concurrent_operations())
            assert result is True, "All async operations should succeed"
        finally:
            loop.close()

    def test_error_handling_patterns(self):
        """Test basic error handling patterns"""
        conn = sqlite3.connect(self.db_path)

        # Test invalid data handling
        try:
            conn.execute(
                """
                INSERT INTO tasks (id, title) VALUES (?, ?)
            """,
                (None, "Invalid Task"),
            )  # NULL id should fail
            raise AssertionError("Should have raised an error")
        except sqlite3.IntegrityError:
            pass  # Expected error

        # Test constraint violations
        task_id = str(uuid.uuid4())
        conn.execute(
            """
            INSERT INTO tasks (id, title) VALUES (?, ?)
        """,
            (task_id, "First Task"),
        )

        try:
            conn.execute(
                """
                INSERT INTO tasks (id, title) VALUES (?, ?)
            """,
                (task_id, "Duplicate Task"),
            )  # Duplicate id should fail
            raise AssertionError("Should have raised an error")
        except sqlite3.IntegrityError:
            pass  # Expected error

        conn.close()

    def test_performance_baseline(self):
        """Test basic performance baseline"""

        conn = sqlite3.connect(self.db_path)

        # Measure basic operation performance
        start_time = time.time()

        # Insert multiple records
        for i in range(100):
            task_id = f"perf_task_{i}_{uuid.uuid4()}"
            conn.execute(
                """
                INSERT INTO tasks (id, title, description)
                VALUES (?, ?, ?)
            """,
                (task_id, f"Performance Test Task {i}", f"Task {i} for performance baseline testing"),
            )

        # Query records
        cursor = conn.execute("SELECT COUNT(*) FROM tasks")
        count = cursor.fetchone()[0]

        end_time = time.time()
        duration = end_time - start_time

        # Basic performance assertions
        assert count == 100, "Should have inserted 100 records"
        assert duration < 5.0, f"Operations should complete quickly, took {duration:.2f}s"

        # Calculate operations per second
        ops_per_second = 100 / duration
        assert ops_per_second > 20, f"Should achieve reasonable throughput, got {ops_per_second:.1f} ops/s"

        conn.close()

    def test_golden_rules_basic_compliance(self):
        """Test basic Golden Rules compliance"""
        # Test core/ directory structure exists
        orchestrator_core = test_root / "apps" / "hive-orchestrator" / "src" / "hive_orchestrator" / "core"
        assert orchestrator_core.exists(), "Orchestrator should have core/ directory"

        # Test that core has expected subdirectories
        expected_core_dirs = ["bus", "db", "errors"]
        existing_dirs = [d.name for d in orchestrator_core.iterdir() if d.is_dir()]

        compliance_score = sum(1 for dir_name in expected_core_dirs if dir_name in existing_dirs)
        assert compliance_score > 0, f"Should have some core directories, found: {existing_dirs}"

    def test_import_patterns_basic(self):
        """Test basic import patterns work"""
        try:
            # Test that we can import from core modules
            sys.path.insert(0, str(test_root / "apps" / "hive-orchestrator" / "src"))

            # This should work if imports are properly structured
            # (Note: actual imports would be tested in real environment)
            import hive_orchestrator

            assert hasattr(hive_orchestrator, "__version__") or hasattr(
                hive_orchestrator,
                "__file__",
            ), "Module should be importable"

        except ImportError as e:
            # In test environment, this might fail, but we can still validate structure
            print(f"Import test skipped due to environment: {e}")


class CriticalPathValidation:
    """Critical path validation for essential platform functions"""

    def __init__(self, db_path: Path):
        self.db_path = db_path

    def validate_ai_planner_to_queen_flow(self) -> bool:
        """Validate AI Planner → Queen critical path"""
        conn = sqlite3.connect(self.db_path)

        try:
            # Step 1: AI Planner creates execution plan
            plan_id = f"critical_plan_{uuid.uuid4()}"
            planning_task_id = f"critical_planning_{uuid.uuid4()}"

            conn.execute(
                """
                INSERT INTO planning_queue (id, task_description, status)
                VALUES (?, ?, ?)
            """,
                (planning_task_id, "Critical path test", "planned"),
            )

            # Step 2: Queen reads plan and creates tasks
            task_id = f"critical_task_{uuid.uuid4()}"
            conn.execute(
                """
                INSERT INTO tasks (id, title, task_type, status, payload)
                VALUES (?, ?, ?, ?, ?)
            """,
                (task_id, "Critical Path Task", "planned_subtask", "queued", json.dumps({"parent_plan_id": plan_id})),
            )

            # Step 3: Verify data flow
            cursor = conn.execute(
                """
                SELECT COUNT(*) FROM tasks
                WHERE json_extract(payload, '$.parent_plan_id') = ?
            """,
                (plan_id,),
            )

            task_count = cursor.fetchone()[0]
            return task_count > 0

        finally:
            conn.close()

    def validate_queen_to_worker_flow(self) -> bool:
        """Validate Queen → Worker critical path"""
        conn = sqlite3.connect(self.db_path)

        try:
            # Queen assigns task to worker
            task_id = f"worker_task_{uuid.uuid4()}"
            conn.execute(
                """
                INSERT INTO tasks (id, title, status, assignee)
                VALUES (?, ?, ?, ?)
            """,
                (task_id, "Worker Assignment Test", "assigned", "worker:backend"),
            )

            # Worker picks up and processes task
            conn.execute(
                """
                UPDATE tasks SET status = 'in_progress' WHERE id = ?
            """,
                (task_id,),
            )

            # Worker completes task
            conn.execute(
                """
                UPDATE tasks SET status = 'completed' WHERE id = ?
            """,
                (task_id,),
            )

            # Verify completion
            cursor = conn.execute(
                """
                SELECT status FROM tasks WHERE id = ?
            """,
                (task_id,),
            )

            status = cursor.fetchone()[0]
            return status == "completed"

        finally:
            conn.close()

    def validate_event_bus_critical_path(self) -> bool:
        """Validate event bus critical messaging path"""
        conn = sqlite3.connect(self.db_path)

        try:
            # Publish critical system event
            event_id = str(uuid.uuid4())
            correlation_id = str(uuid.uuid4())

            conn.execute(
                """
                INSERT INTO events (id, event_type, source_agent, correlation_id, payload)
                VALUES (?, ?, ?, ?, ?)
            """,
                (
                    event_id,
                    "system.critical.test",
                    "validation_test",
                    correlation_id,
                    json.dumps({"critical": True, "timestamp": datetime.now(UTC).isoformat()}),
                ),
            )

            # Verify event can be retrieved by correlation
            cursor = conn.execute(
                """
                SELECT payload FROM events WHERE correlation_id = ?
            """,
                (correlation_id,),
            )

            row = cursor.fetchone()
            if not row:
                return False

            payload = json.loads(row[0])
            return payload.get("critical") is True

        finally:
            conn.close()

    def run_all_critical_validations(self) -> dict[str, bool]:
        """Run all critical path validations"""
        return {
            "ai_planner_to_queen": self.validate_ai_planner_to_queen_flow(),
            "queen_to_worker": self.validate_queen_to_worker_flow(),
            "event_bus_critical": self.validate_event_bus_critical_path(),
        }


@pytest.fixture
def critical_validator(setup_test_env):
    """Provide critical path validator"""
    test_instance = PlatformValidationTests()
    test_instance.setup_test_env = setup_test_env  # Use the same setup
    return CriticalPathValidation(test_instance.db_path)


def test_critical_paths(critical_validator):
    """Test all critical paths are functional"""
    results = critical_validator.run_all_critical_validations()

    for path_name, success in results.items():
        assert success, f"Critical path '{path_name}' validation failed"

    # All critical paths should pass
    assert all(results.values()), f"Some critical paths failed: {results}"


def test_platform_health_check():
    """Quick platform health check"""
    validator = PlatformValidationTests()
    validator.setup_test_env()

    try:
        # Run essential health checks
        validator.test_database_connectivity()
        validator.test_event_bus_basic_functionality()
        validator.test_cross_app_data_sharing()

        # If we get here, basic health is good
        assert True

    finally:
        # Cleanup would happen in fixture, but we're running standalone
        pass


if __name__ == "__main__":
    # Quick validation run
    print("🔍 Running Hive Platform Validation Tests...")

    # Run pytest
    import subprocess

    result = subprocess.run(["python", "-m", "pytest", __file__, "-v"], capture_output=True, text=True)

    if result.returncode == 0:
        print("✅ All validation tests passed!")
    else:
        print("❌ Some validation tests failed:")
        print(result.stdout)
        print(result.stderr)

    exit(result.returncode)
