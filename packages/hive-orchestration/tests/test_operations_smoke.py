"""
Smoke tests for orchestration operations.

Tests basic operation functionality without requiring all dependencies.
"""
import os
import tempfile

import pytest


@pytest.mark.core
def test_database_schema():
    """Test database schema initialization."""
    from hive_orchestration.database.operations import get_connection
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    try:
        from hive_orchestration.database import transaction
        with transaction(db_path) as conn:
            conn.execute("\n                CREATE TABLE IF NOT EXISTS tasks (\n                    id TEXT PRIMARY KEY,\n                    title TEXT NOT NULL,\n                    status TEXT DEFAULT 'queued'\n                )\n            ")
        with get_connection(db_path) as conn:
            cursor = (conn.execute("SELECT name FROM sqlite_master WHERE type='table'"),)
            tables = [row[0] for row in cursor.fetchall()]
            assert 'tasks' in tables
    finally:
        import gc
        import time
        gc.collect()
        time.sleep(0.1)
        if os.path.exists(db_path):
            try:
                os.unlink(db_path)
            except PermissionError:
                pass

@pytest.mark.core
def test_operations_importable():
    """Test that all operation modules can be imported."""
    from hive_orchestration.operations.tasks import (
        create_task,
        delete_task,
        get_queued_tasks,
        get_task,
        get_tasks_by_status,
        update_task_status,
    )
    assert callable(create_task)
    assert callable(get_task)
    assert callable(update_task_status)
    assert callable(get_tasks_by_status)
    assert callable(get_queued_tasks)
    assert callable(delete_task)
    from hive_orchestration.operations.workers import (
        get_active_workers,
        get_worker,
        register_worker,
        unregister_worker,
        update_worker_heartbeat,
    )
    assert callable(register_worker)
    assert callable(update_worker_heartbeat)
    assert callable(get_active_workers)
    assert callable(get_worker)
    assert callable(unregister_worker)
    from hive_orchestration.operations.plans import (
        check_subtask_dependencies,
        create_planned_subtasks_from_plan,
        get_execution_plan_status,
        get_next_planned_subtask,
        mark_plan_execution_started,
    )
    assert callable(create_planned_subtasks_from_plan)
    assert callable(get_execution_plan_status)
    assert callable(check_subtask_dependencies)
    assert callable(get_next_planned_subtask)
    assert callable(mark_plan_execution_started)

@pytest.mark.core
def test_database_operations_importable():
    """Test database operations can be imported."""
    from hive_orchestration.database import get_connection, init_db, transaction
    assert callable(get_connection)
    assert callable(transaction)
    assert callable(init_db)
if __name__ == '__main__':
    import pytest
    pytest.main([__file__, '-v'])
