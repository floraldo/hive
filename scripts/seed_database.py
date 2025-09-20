#!/usr/bin/env python3
"""
Database Seeding Script for Hive

Creates clean, sample tasks directly in the database following the "Fresh Start" approach.
This replaces the old JSON-based task files with database-native task creation.
"""

import sys
import os
from pathlib import Path

# Add hive-core-db to path
sys.path.insert(0, str(Path(__file__).parent.parent / "packages" / "hive-core-db" / "src"))
import hive_core_db

# Add hive-logging to path
sys.path.insert(0, str(Path(__file__).parent.parent / "packages" / "hive-logging" / "src"))
from hive_logging import setup_logging, get_logger

def setup_sample_tasks():
    """Create sample tasks for testing the Hive system."""

    # Initialize logging
    setup_logging("hive_seeder")
    logger = get_logger(__name__)

    # Initialize database
    hive_core_db.init_db()
    logger.info("Database initialized")

    # Sample tasks representing typical Hive workloads
    sample_tasks = [
        {
            "title": "Implement user authentication API",
            "description": "Create JWT-based authentication system with login/logout endpoints",
            "task_type": "backend",
            "priority": 3,
            "max_retries": 3,
            "tags": ["api", "auth", "security"],
            "payload": {
                "requirements": ["JWT tokens", "Password hashing", "Session management"],
                "endpoints": ["/api/auth/login", "/api/auth/logout", "/api/auth/refresh"],
                "framework": "Flask",
                "database": "PostgreSQL"
            }
        },
        {
            "title": "Build responsive login form component",
            "description": "Create accessible React login form with validation and error handling",
            "task_type": "frontend",
            "priority": 2,
            "max_retries": 2,
            "tags": ["react", "forms", "accessibility"],
            "payload": {
                "components": ["LoginForm", "InputField", "ErrorMessage"],
                "validation": ["email format", "password strength", "required fields"],
                "accessibility": ["ARIA labels", "keyboard navigation", "screen reader support"],
                "framework": "React"
            }
        },
        {
            "title": "Setup CI/CD pipeline with Docker",
            "description": "Configure automated deployment pipeline with testing and containerization",
            "task_type": "infra",
            "priority": 1,
            "max_retries": 3,
            "tags": ["docker", "ci-cd", "deployment"],
            "payload": {
                "stages": ["build", "test", "deploy"],
                "containers": ["backend", "frontend", "database"],
                "platforms": ["GitHub Actions", "Docker Hub"],
                "environments": ["staging", "production"]
            }
        },
        {
            "title": "Implement user profile management",
            "description": "Full-stack user profile CRUD operations with file upload support",
            "task_type": "backend",
            "priority": 2,
            "max_retries": 2,
            "tags": ["crud", "profiles", "file-upload"],
            "payload": {
                "operations": ["create", "read", "update", "delete"],
                "features": ["avatar upload", "profile validation", "privacy settings"],
                "storage": "AWS S3",
                "api_endpoints": ["/api/users/profile", "/api/users/avatar"]
            }
        },
        {
            "title": "Create dashboard analytics component",
            "description": "Interactive dashboard with charts and real-time data visualization",
            "task_type": "frontend",
            "priority": 2,
            "max_retries": 2,
            "tags": ["dashboard", "charts", "analytics"],
            "payload": {
                "charts": ["line", "bar", "pie", "metrics"],
                "data_sources": ["REST API", "WebSocket"],
                "libraries": ["Chart.js", "React"],
                "features": ["real-time updates", "data filtering", "export options"]
            }
        }
    ]

    # Create tasks in database
    created_tasks = []
    for task_data in sample_tasks:
        try:
            task_id = hive_core_db.create_task(
                title=task_data["title"],
                task_type=task_data["task_type"],
                description=task_data["description"],
                payload=task_data["payload"],
                priority=task_data["priority"],
                max_retries=task_data["max_retries"],
                tags=task_data["tags"]
            )
            created_tasks.append(task_id)
            logger.info(f"Created task: {task_id} - {task_data['title']}")
        except Exception as e:
            logger.error(f"Failed to create task '{task_data['title']}': {e}")

    logger.info(f"Database seeding completed. Created {len(created_tasks)} tasks.")
    return created_tasks

def clear_all_tasks():
    """Clear all tasks from the database for fresh start."""
    logger = get_logger(__name__)

    try:
        # This would require a new function in hive-core-db
        # For now, we'll note this as a TODO
        logger.warning("clear_all_tasks() not yet implemented - would need database truncate function")
        # TODO: Add clear_all_tasks() function to hive-core-db
    except Exception as e:
        logger.error(f"Failed to clear tasks: {e}")

def main():
    """Main seeding script entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Hive Database Seeding Script")
    parser.add_argument("--clear", action="store_true", help="Clear all existing tasks first")
    parser.add_argument("--sample", action="store_true", help="Create sample tasks")

    args = parser.parse_args()

    if not args.clear and not args.sample:
        parser.print_help()
        return

    if args.clear:
        print("Clearing existing tasks...")
        clear_all_tasks()

    if args.sample:
        print("Creating sample tasks...")
        created_tasks = setup_sample_tasks()
        print(f"Successfully created {len(created_tasks)} sample tasks")
        for task_id in created_tasks:
            print(f"  - {task_id}")

if __name__ == "__main__":
    main()