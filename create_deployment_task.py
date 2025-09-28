#!/usr/bin/env python3
"""
Create a deployment task for the currency conversion API to validate the end-to-end pipeline
"""

import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

def create_deployment_task():
    """Create a deployment task in the hive database"""

    # Database path
    db_path = Path("apps/hive-orchestrator/hive/db/hive-internal.db")

    if not db_path.exists():
        print(f"Database not found at {db_path}")
        return False

    # Task data for currency conversion API
    task_data = {
        "project_name": "currency-service",
        "description": "Build a standalone FastAPI application with GET /convert endpoint",
        "requirements": {
            "framework": "FastAPI",
            "endpoints": [
                {
                    "path": "/convert",
                    "method": "GET",
                    "parameters": ["from", "to", "amount"],
                    "description": "Convert currency using external exchange rate API"
                }
            ],
            "features": [
                "External exchange rate API integration",
                "Input validation and error handling",
                "Docker containerization",
                "Health check endpoint"
            ]
        },
        "deployment": {
            "strategy": "docker",
            "environment": "test",
            "auto_deploy": True
        }
    }

    metadata = {
        "source": "zero_touch_validation",
        "mission": "end_to_end_autonomous_pipeline",
        "priority": "high",
        "created_by": "claude_code_validation"
    }

    try:
        # Connect to database
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # Check if tasks table exists
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='tasks'
        """)

        if not cursor.fetchone():
            print("Tasks table does not exist. Creating it...")
            cursor.execute("""
                CREATE TABLE tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    worker_id TEXT,
                    priority INTEGER DEFAULT 5,
                    task_data TEXT,
                    metadata TEXT,
                    status TEXT DEFAULT 'pending',
                    estimated_duration INTEGER
                )
            """)

        # Insert the deployment task
        now = datetime.now().isoformat()

        cursor.execute("""
            INSERT INTO tasks (
                title, description, created_at, updated_at,
                priority, task_data, metadata, status, estimated_duration
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "Create and Deploy Currency Conversion API",
            "Build a standalone FastAPI application 'currency-service' with GET /convert endpoint (from, to, amount parameters). Use external exchange rate API. Include Docker containerization and automated deployment.",
            now,
            now,
            9,  # High priority
            json.dumps(task_data),
            json.dumps(metadata),
            "deployment_pending",
            3600  # 1 hour estimated
        ))

        task_id = cursor.lastrowid
        conn.commit()

        print(f"Successfully created deployment task with ID: {task_id}")
        print(f"Task title: Create and Deploy Currency Conversion API")
        print(f"Status: deployment_pending")
        print(f"Priority: 9 (High)")

        # Verify the task was created
        cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        task = cursor.fetchone()
        if task:
            print(f"Task verification successful")
            return True
        else:
            print("Task verification failed")
            return False

    except Exception as e:
        print(f"Error creating deployment task: {e}")
        return False

    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    success = create_deployment_task()
    sys.exit(0 if success else 1)