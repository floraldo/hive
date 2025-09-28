#!/usr/bin/env python3
"""
Create a deployment task for the hello-service to test the autonomous workflow
"""

import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

def create_hello_service_task():
    """Create a deployment task for hello-service in the hive database"""

    # Database path
    db_path = Path("apps/hive-orchestrator/hive/db/hive-internal.db")

    if not db_path.exists():
        print(f"Database not found at {db_path}")
        return False

    # Task data for hello-service - VERY SIMPLE
    task_data = {
        "project_name": "hello-service",
        "description": "Build a minimal Flask web service for testing autonomous workflow",
        "requirements": {
            "framework": "Flask",
            "endpoints": [
                {
                    "path": "/",
                    "method": "GET",
                    "response": {"message": "Hello, World!", "service": "hello-service"}
                },
                {
                    "path": "/health",
                    "method": "GET",
                    "response": {"status": "healthy"}
                }
            ],
            "features": [
                "Simple JSON responses",
                "Health check endpoint",
                "Docker containerization"
            ]
        },
        "deployment": {
            "strategy": "docker",
            "environment": "test",
            "port": 5000,
            "auto_deploy": True
        }
    }

    metadata = {
        "source": "autonomous_workflow_test",
        "purpose": "validate_agent_pipeline",
        "complexity": "minimal",
        "priority": "high",
        "created_by": "workflow_validation"
    }

    try:
        # Connect to database
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # Insert the deployment task
        now = datetime.now().isoformat()

        cursor.execute("""
            INSERT INTO tasks (
                title, description, created_at, updated_at,
                priority, task_data, metadata, status, estimated_duration
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "Build Hello Service - Autonomous Workflow Test",
            "Create a minimal Flask web service with hello and health endpoints. This is a test of the autonomous AI agent workflow.",
            now,
            now,
            9,  # High priority for quick processing
            json.dumps(task_data),
            json.dumps(metadata),
            "deployment_pending",
            1800  # 30 minutes estimated
        ))

        task_id = cursor.lastrowid
        conn.commit()

        print(f"Successfully created hello-service deployment task with ID: {task_id}")
        print(f"Task title: Build Hello Service - Autonomous Workflow Test")
        print(f"Status: deployment_pending")
        print(f"Priority: 9 (High)")
        print(f"")
        print(f"The AI agents should now pick up this task and:")
        print(f"1. AI Planner: Analyze requirements and create implementation plan")
        print(f"2. Queen/Workers: Generate Flask application code")
        print(f"3. AI Reviewer: Review code quality and functionality")
        print(f"4. AI Deployer: Package and deploy the service")
        print(f"")
        print(f"This will test the complete autonomous workflow!")

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
        print(f"Error creating hello-service task: {e}")
        return False

    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    success = create_hello_service_task()
    sys.exit(0 if success else 1)