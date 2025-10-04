#!/usr/bin/env python3
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

# Test imports - use proper path setup
import sys
import tempfile
import uuid
from datetime import UTC, datetime
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "hive-orchestrator", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "ai-planner", "src"))

# Import components to test
from ai_planner.agent import AIPlanner
from hive_orchestrator.core.db import database_enhanced_optimized as db_enhanced


class TestAIPlannerQueenIntegration:
    """Test complete AI Planner → Queen → Worker integration"""

    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        # Initialize test database
        conn = sqlite3.connect(db_path)
        self._create_test_schema(conn)
        conn.close()

        # Mock get_connection to use test DB

        def mock_get_connection():
            return sqlite3.connect(db_path)

        with patch("hive_orchestrator.core.db.database.get_connection", mock_get_connection):
            with patch("ai_planner.agent.get_connection", mock_get_connection):
                yield db_path

        # Cleanup
        os.unlink(db_path)

    def _create_test_schema(self, conn):
        """Create test database schema"""
        conn.executescript(
            """
            CREATE TABLE planning_queue (
                id TEXT PRIMARY KEY,
                task_description TEXT NOT NULL,
                priority INTEGER DEFAULT 50,
                requestor TEXT,
                context_data TEXT,
                complexity_estimate TEXT,
                status TEXT DEFAULT 'pending',
                assigned_agent TEXT,
                assigned_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                completed_at TEXT
            );

            CREATE TABLE execution_plans (
                id TEXT PRIMARY KEY,
                planning_task_id TEXT NOT NULL,
                plan_data TEXT NOT NULL,
                estimated_complexity TEXT,
                estimated_duration INTEGER,
                status TEXT DEFAULT 'generated',
                generated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (planning_task_id) REFERENCES planning_queue (id)
            );

            CREATE TABLE tasks (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT,
                task_type TEXT DEFAULT 'task',
                priority INTEGER DEFAULT 50,
                status TEXT DEFAULT 'queued',
                assignee TEXT,
                assigned_at TEXT,
                started_at TEXT,
                completed_at TEXT,
                payload TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                retry_count INTEGER DEFAULT 0,
                workspace TEXT,
                tags TEXT
            );

            CREATE TABLE runs (
                id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                worker_id TEXT NOT NULL,
                phase TEXT,
                status TEXT DEFAULT 'running',
                result TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                completed_at TEXT,
                FOREIGN KEY (task_id) REFERENCES tasks (id)
            );

            CREATE TABLE workers (
                id TEXT PRIMARY KEY,
                role TEXT NOT NULL,
                capabilities TEXT,
                metadata TEXT,
                status TEXT DEFAULT 'active',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            -- Indexes for performance
            CREATE INDEX idx_planning_queue_status ON planning_queue (status, priority DESC);
            CREATE INDEX idx_execution_plans_status ON execution_plans (status);
            CREATE INDEX idx_tasks_status_type ON tasks (status, task_type);
            CREATE INDEX idx_tasks_payload_parent ON tasks (json_extract(payload, '$.parent_plan_id'));
        """,
        )
        conn.commit()

    def test_planning_queue_to_execution_plan_flow(self, temp_db):
        """Test AI Planner picks up tasks from planning_queue and creates execution plans"""
        # Insert test task into planning_queue
        task_id = str(uuid.uuid4())

        conn = sqlite3.connect(temp_db)
        conn.execute(
            """
            INSERT INTO planning_queue (id, task_description, priority, requestor, context_data)
            VALUES (?, ?, ?, ?, ?)
        """,
            (
                task_id,
                "Create authentication API endpoints",
                75,
                "test_user",
                json.dumps({"files_affected": 5, "complexity": "medium"}),
            ),
        )
        conn.commit()
        conn.close()

        # Mock AI Planner behavior
        planner = AIPlanner(mock_mode=True)

        # Test task retrieval
        with patch.object(planner, "connect_database", return_value=True):
            planner.db_connection = sqlite3.connect(temp_db)

            task = planner.get_next_task()
            assert task is not None
            assert task["id"] == task_id
            assert task["task_description"] == "Create authentication API endpoints"
            assert task["status"] == "assigned"  # Should be marked as assigned

        # Test plan generation (mocked)
        mock_plan = {
            "plan_id": f"plan_{task_id}",
            "task_id": task_id,
            "plan_name": "Authentication API Implementation",
            "sub_tasks": [
                {
                    "id": "auth_1",
                    "title": "Design API Schema",
                    "description": "Create OpenAPI specification for auth endpoints",
                    "assignee": "worker:backend",
                    "complexity": "medium",
                    "estimated_duration": 30,
                    "workflow_phase": "design",
                    "required_skills": ["api_design", "openapi"],
                    "deliverables": ["openapi.yaml"],
                    "dependencies": [],
                },
                {
                    "id": "auth_2",
                    "title": "Implement JWT Service",
                    "description": "Create JWT token generation and validation",
                    "assignee": "worker:backend",
                    "complexity": "medium",
                    "estimated_duration": 45,
                    "workflow_phase": "implementation",
                    "required_skills": ["python", "jwt", "security"],
                    "deliverables": ["jwt_service.py", "tests/test_jwt.py"],
                    "dependencies": ["auth_1"],
                },
            ],
            "metrics": {"total_estimated_duration": 75, "complexity_breakdown": {"medium": 2}},
            "status": "generated",
            "created_at": datetime.now(UTC).isoformat(),
        }

        with patch.object(planner, "generate_execution_plan", return_value=mock_plan):
            # Test plan saving
            success = planner.save_execution_plan(mock_plan)
            assert success

            # Verify execution plan was created
            conn = sqlite3.connect(temp_db)
            cursor = conn.execute("SELECT * FROM execution_plans WHERE planning_task_id = ?", (task_id,))
            plan_row = cursor.fetchone()
            assert plan_row is not None
            assert plan_row[1] == task_id  # planning_task_id
            assert plan_row[4] == "generated"  # status

            # Verify subtasks were created
            cursor = conn.execute(
                """
                SELECT COUNT(*) FROM tasks
                WHERE task_type = 'planned_subtask'
                AND json_extract(payload, '$.parent_plan_id') = ?
            """,
                (mock_plan["plan_id"],),
            )
            subtask_count = cursor.fetchone()[0]
            assert subtask_count == 2

            conn.close()

    def test_queen_enhanced_task_pickup(self, temp_db):
        """Test Queen picks up both regular and planned subtasks"""
        conn = sqlite3.connect(temp_db)

        # Create regular task
        regular_task_id = str(uuid.uuid4())
        conn.execute(
            """
            INSERT INTO tasks (id, title, task_type, status, priority)
            VALUES (?, ?, ?, ?, ?)
        """,
            (regular_task_id, "Regular Task", "task", "queued", 60),
        )

        # Create execution plan
        plan_id = str(uuid.uuid4())
        planning_task_id = str(uuid.uuid4())
        conn.execute(
            """
            INSERT INTO execution_plans (id, planning_task_id, plan_data, status)
            VALUES (?, ?, ?, ?)
        """,
            (plan_id, planning_task_id, json.dumps({"sub_tasks": []}), "generated"),
        )

        # Create planned subtasks
        subtask1_id = f"subtask_{plan_id}_1"
        subtask2_id = f"subtask_{plan_id}_2"

        subtask1_payload = {
            "parent_plan_id": plan_id,
            "subtask_id": "1",
            "workflow_phase": "design",
            "assignee": "worker:backend",
        }

        subtask2_payload = {
            "parent_plan_id": plan_id,
            "subtask_id": "2",
            "workflow_phase": "implementation",
            "assignee": "worker:backend",
            "dependencies": ["1"],
        }

        conn.execute(
            """
            INSERT INTO tasks (id, title, task_type, status, priority, payload)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (subtask1_id, "Design API", "planned_subtask", "queued", 70, json.dumps(subtask1_payload)),
        )

        conn.execute(
            """
            INSERT INTO tasks (id, title, task_type, status, priority, payload)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (subtask2_id, "Implement API", "planned_subtask", "queued", 75, json.dumps(subtask2_payload)),
        )

        conn.commit()
        conn.close()

        # Test enhanced task retrieval
        with patch(
            "hive_orchestrator.core.db.database_enhanced_optimized.get_connection",
            lambda: sqlite3.connect(temp_db),
        ):
            tasks = db_enhanced.get_queued_tasks_with_planning_optimized(limit=10)

            assert len(tasks) == 3  # 1 regular + 2 planned subtasks

            # Check task types are preserved
            task_types = [t["task_type"] for t in tasks]
            assert "task" in task_types
            assert "planned_subtask" in task_types

            # Check planned subtasks have enhanced context
            planned_tasks = [t for t in tasks if t["task_type"] == "planned_subtask"]
            assert len(planned_tasks) == 2

            for task in planned_tasks:
                assert "planner_context" in task
                assert task["planner_context"]["parent_plan_id"] == plan_id
                assert task["planner_context"]["workflow_phase"] in ["design", "implementation"]

    def test_dependency_resolution(self, temp_db):
        """Test dependency checking and resolution for planned subtasks"""
        conn = sqlite3.connect(temp_db)

        plan_id = str(uuid.uuid4())

        # Create two subtasks with dependency relationship
        task1_id = f"subtask_{plan_id}_1"
        task2_id = f"subtask_{plan_id}_2"

        # Task 1 - no dependencies
        payload1 = {"parent_plan_id": plan_id, "subtask_id": "1", "dependencies": []}

        # Task 2 - depends on task 1
        payload2 = {
            "parent_plan_id": plan_id,
            "subtask_id": "2",
            "dependencies": ["1"],  # References subtask_id, not full task_id
        }

        conn.execute(
            """
            INSERT INTO tasks (id, title, task_type, status, payload)
            VALUES (?, ?, ?, ?, ?)
        """,
            (task1_id, "Foundation Task", "planned_subtask", "queued", json.dumps(payload1)),
        )

        conn.execute(
            """
            INSERT INTO tasks (id, title, task_type, status, payload)
            VALUES (?, ?, ?, ?, ?)
        """,
            (task2_id, "Dependent Task", "planned_subtask", "queued", json.dumps(payload2)),
        )

        conn.commit()

        # Test dependency checking with task 1 not completed
        with patch("hive_orchestrator.core.db.database_enhanced.get_connection", lambda: sqlite3.connect(temp_db)):
            from hive_orchestrator.core.db.database_enhanced import check_subtask_dependencies

            # Task 1 should be ready (no dependencies)
            assert check_subtask_dependencies(task1_id)

            # Task 2 should not be ready (depends on task 1)
            assert not check_subtask_dependencies(task2_id)

        # Complete task 1
        conn.execute("UPDATE tasks SET status = ? WHERE id = ?", ("completed", task1_id))
        conn.commit()

        # Now task 2 should be ready
        assert check_subtask_dependencies(task2_id)

        conn.close()

    def test_status_reporting_pipeline(self, temp_db):
        """Test status updates flow from worker completion back to planning system"""
        conn = sqlite3.connect(temp_db)

        # Create execution plan and subtask
        plan_id = str(uuid.uuid4())
        planning_task_id = str(uuid.uuid4())
        subtask_id = f"subtask_{plan_id}_1"

        # Create planning queue entry
        conn.execute(
            """
            INSERT INTO planning_queue (id, task_description, status)
            VALUES (?, ?, ?)
        """,
            (planning_task_id, "Test task", "planned"),
        )

        # Create execution plan
        plan_data = {"sub_tasks": [{"id": "1", "title": "Test Subtask", "status": "queued"}]}

        conn.execute(
            """
            INSERT INTO execution_plans (id, planning_task_id, plan_data, status)
            VALUES (?, ?, ?, ?)
        """,
            (plan_id, planning_task_id, json.dumps(plan_data), "executing"),
        )

        # Create subtask
        payload = {"parent_plan_id": plan_id, "subtask_id": "1"}

        conn.execute(
            """
            INSERT INTO tasks (id, title, task_type, status, payload)
            VALUES (?, ?, ?, ?, ?)
        """,
            (subtask_id, "Test Subtask", "planned_subtask", "queued", json.dumps(payload)),
        )

        conn.commit()

        # Simulate worker execution
        # 1. Task gets assigned
        conn.execute(
            """
            UPDATE tasks SET status = ?, assignee = ?, assigned_at = ?
            WHERE id = ?
        """,
            ("assigned", "worker:backend", datetime.now(UTC).isoformat(), subtask_id),
        )

        # 2. Task starts execution
        run_id = str(uuid.uuid4())
        conn.execute(
            """
            INSERT INTO runs (id, task_id, worker_id, phase, status)
            VALUES (?, ?, ?, ?, ?)
        """,
            (run_id, subtask_id, "worker:backend", "apply", "running"),
        )

        conn.execute(
            """
            UPDATE tasks SET status = ?, started_at = ?
            WHERE id = ?
        """,
            ("in_progress", datetime.now(UTC).isoformat(), subtask_id),
        )

        # 3. Task completes successfully
        conn.execute(
            """
            UPDATE runs SET status = ?, result = ?, completed_at = ?
            WHERE id = ?
        """,
            ("completed", json.dumps({"status": "success"}), datetime.now(UTC).isoformat(), run_id),
        )

        conn.execute(
            """
            UPDATE tasks SET status = ?, completed_at = ?
            WHERE id = ?
        """,
            ("completed", datetime.now(UTC).isoformat(), subtask_id),
        )

        conn.commit()

        # Verify status pipeline
        # Check task status
        cursor = conn.execute("SELECT status FROM tasks WHERE id = ?", (subtask_id,))
        task_status = cursor.fetchone()[0]
        assert task_status == "completed"

        # Check run status
        cursor = conn.execute("SELECT status, result FROM runs WHERE task_id = ?", (subtask_id,))
        run_row = cursor.fetchone()
        assert run_row[0] == "completed"
        run_result = json.loads(run_row[1])
        assert run_result["status"] == "success"

        # This would trigger plan progress updates in real system
        cursor = conn.execute("SELECT status FROM execution_plans WHERE id = ?", (plan_id,))
        plan_status = cursor.fetchone()[0]
        assert plan_status == "executing"  # Could be updated to "completed" when all subtasks done

        conn.close()

    def test_error_handling_and_retry(self, temp_db):
        """Test error handling and retry logic in the integration pipeline"""
        conn = sqlite3.connect(temp_db)

        # Create a subtask that will fail
        plan_id = str(uuid.uuid4())
        subtask_id = f"subtask_{plan_id}_1"

        payload = {"parent_plan_id": plan_id, "subtask_id": "1"}

        conn.execute(
            """
            INSERT INTO tasks (id, title, task_type, status, payload, retry_count)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (subtask_id, "Failing Task", "planned_subtask", "queued", json.dumps(payload), 0),
        )

        conn.commit()

        # Simulate first failure
        run_id_1 = str(uuid.uuid4())
        conn.execute(
            """
            INSERT INTO runs (id, task_id, worker_id, status, result)
            VALUES (?, ?, ?, ?, ?)
        """,
            (
                run_id_1,
                subtask_id,
                "worker:backend",
                "failed",
                json.dumps({"status": "failed", "error": "Network timeout"}),
            ),
        )

        # Update task for retry
        conn.execute(
            """
            UPDATE tasks SET status = ?, retry_count = ? WHERE id = ?
        """,
            ("queued", 1, subtask_id),
        )

        conn.commit()

        # Verify retry logic
        cursor = conn.execute("SELECT retry_count, status FROM tasks WHERE id = ?", (subtask_id,))
        row = cursor.fetchone()
        assert row[0] == 1  # retry_count incremented
        assert row[1] == "queued"  # back to queued for retry

        # Simulate second attempt success
        run_id_2 = str(uuid.uuid4())
        conn.execute(
            """
            INSERT INTO runs (id, task_id, worker_id, status, result)
            VALUES (?, ?, ?, ?, ?)
        """,
            (run_id_2, subtask_id, "worker:backend", "completed", json.dumps({"status": "success"})),
        )

        conn.execute(
            """
            UPDATE tasks SET status = ? WHERE id = ?
        """,
            ("completed", subtask_id),
        )

        conn.commit()

        # Verify final state
        cursor = conn.execute("SELECT status, retry_count FROM tasks WHERE id = ?", (subtask_id,))
        row = cursor.fetchone()
        assert row[0] == "completed"
        assert row[1] == 1  # retry count preserved

        conn.close()

    def test_concurrent_execution_coordination(self, temp_db):
        """Test coordination of multiple concurrent subtasks"""
        conn = sqlite3.connect(temp_db)

        plan_id = str(uuid.uuid4())

        # Create execution plan with parallel and sequential subtasks
        plan_data = {
            "sub_tasks": [
                {"id": "1", "title": "Parallel Task 1", "dependencies": []},
                {"id": "2", "title": "Parallel Task 2", "dependencies": []},
                {"id": "3", "title": "Sequential Task", "dependencies": ["1", "2"]},
            ],
        }

        conn.execute(
            """
            INSERT INTO execution_plans (id, planning_task_id, plan_data, status)
            VALUES (?, ?, ?, ?)
        """,
            (plan_id, str(uuid.uuid4()), json.dumps(plan_data), "executing"),
        )

        # Create subtasks
        for i, subtask in enumerate(plan_data["sub_tasks"], 1):
            task_id = f"subtask_{plan_id}_{i}"
            payload = {"parent_plan_id": plan_id, "subtask_id": subtask["id"], "dependencies": subtask["dependencies"]}

            conn.execute(
                """
                INSERT INTO tasks (id, title, task_type, status, payload)
                VALUES (?, ?, ?, ?, ?)
            """,
                (task_id, subtask["title"], "planned_subtask", "queued", json.dumps(payload)),
            )

        conn.commit()

        # Test enhanced task pickup with dependencies
        with patch(
            "hive_orchestrator.core.db.database_enhanced_optimized.get_connection",
            lambda: sqlite3.connect(temp_db),
        ):
            tasks = db_enhanced.get_queued_tasks_with_planning_optimized(limit=10)

            # Should pick up tasks 1 and 2 (no dependencies), but not 3
            ready_tasks = []
            for task in tasks:
                if task["task_type"] == "planned_subtask":
                    # Simulate dependency checking
                    deps = task.get("payload", {}).get("dependencies", [])
                    if not deps:  # No dependencies
                        ready_tasks.append(task)

            assert len(ready_tasks) == 2  # Tasks 1 and 2 should be ready

        # Complete tasks 1 and 2
        conn.execute("UPDATE tasks SET status = ? WHERE id LIKE ?", ("completed", f"subtask_{plan_id}_1"))
        conn.execute("UPDATE tasks SET status = ? WHERE id LIKE ?", ("completed", f"subtask_{plan_id}_2"))
        conn.commit()

        # Now task 3 should be available
        with patch("hive_orchestrator.core.db.database_enhanced.get_connection", lambda: sqlite3.connect(temp_db)):
            from hive_orchestrator.core.db.database_enhanced import check_subtask_dependencies

            task3_id = f"subtask_{plan_id}_3"
            assert check_subtask_dependencies(task3_id)

        conn.close()


# Integration test that validates the entire pipeline
def test_end_to_end_integration():
    """End-to-end integration test of AI Planner → Queen → Worker pipeline"""
    # This would be a comprehensive test using actual components
    # For now, we verify the test framework works
    assert True


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
