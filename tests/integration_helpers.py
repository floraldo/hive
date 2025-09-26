#!/usr/bin/env python3
"""
Helper functions for integration testing
"""

import json
import sqlite3
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "packages" / "hive-core-db" / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent / "packages" / "hive-utils" / "src"))

import hive_core_db
from hive_utils.paths import DB_PATH


def create_test_task(
    task_id: str,
    title: str,
    description: str = "",
    task_type: str = "test",
    priority: int = 1,
    status: str = "queued",
    assigned_worker: Optional[str] = None,
    current_phase: str = "start",
    payload: Optional[Dict[str, Any]] = None
) -> str:
    """
    Create a test task with specific ID and status for integration testing.

    This bypasses the normal create_task API which doesn't support
    setting ID or initial status.
    """
    # Initialize database
    hive_core_db.init_db()

    # Prepare payload
    if payload:
        payload_json = json.dumps(payload)
    else:
        payload_json = "{}"

    # Direct database insertion for testing
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO tasks (
                id, title, description, task_type, priority, status,
                current_phase, payload, created_at, updated_at, assigned_worker
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            task_id,
            title,
            description,
            task_type,
            priority,
            status,
            current_phase,
            payload_json,
            datetime.now(timezone.utc).isoformat(),
            datetime.now(timezone.utc).isoformat(),
            assigned_worker
        ))

        conn.commit()
        return task_id

    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def update_task_with_payload(task_id: str, payload: Dict[str, Any]) -> bool:
    """Update task payload directly in database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Get existing payload
        cursor.execute("SELECT payload FROM tasks WHERE id = ?", (task_id,))
        result = cursor.fetchone()

        if result:
            existing_payload = json.loads(result[0] or "{}")
            # Merge payloads
            existing_payload.update(payload)

            # Update task
            cursor.execute("""
                UPDATE tasks
                SET payload = ?, updated_at = ?
                WHERE id = ?
            """, (
                json.dumps(existing_payload),
                datetime.now(timezone.utc).isoformat(),
                task_id
            ))

            conn.commit()
            return cursor.rowcount > 0
        return False

    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def clear_test_tasks():
    """Clear all test tasks from database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Delete test tasks
        cursor.execute("DELETE FROM tasks WHERE id LIKE 'integration-test-%'")
        cursor.execute("DELETE FROM tasks WHERE id LIKE 'test-%'")
        conn.commit()

    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def get_task_details(task_id: str) -> Optional[Dict[str, Any]]:
    """Get complete task details including payload."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
    row = cursor.fetchone()

    if row:
        task = dict(row)
        # Parse payload
        if task.get('payload'):
            task['payload'] = json.loads(task['payload'])
        return task
    return None