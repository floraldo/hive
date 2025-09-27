#!/usr/bin/env python3
"""
Master Plan Task Seeder - Grand Integration Test

Creates a high-level task for the AI Planner to decompose and the
Hive Orchestrator to execute, demonstrating the complete autonomous workflow.
"""

import sys
import json
import uuid
from pathlib import Path
from datetime import datetime, timezone

# Add packages path for hive-core-db
hive_root = Path(__file__).parent.parent
sys.path.insert(0, str(hive_root / "packages" / "hive-core-db" / "src"))

from hive_core_db.database import get_connection, init_db
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('master-seeder')


def create_master_plan_task():
    """Create the master planning task for Grand Integration Test"""

    print("=" * 80)
    print("HIVE V2.1 GRAND INTEGRATION TEST - MASTER TASK SEEDER")
    print("=" * 80)
    print()

    # Initialize database
    try:
        init_db()
        logger.info("Database initialized for Grand Integration Test")
    except Exception as e:
        logger.warning(f"Database initialization warning: {e}")
        # Continue anyway - database may already be initialized

    # Create the master task
    master_task_id = f"master-todo-app-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

    task_description = """
Develop a Simple To-Do List Application

Create a complete web application with the following specifications:

FRONTEND REQUIREMENTS:
- Modern, responsive user interface using React or similar framework
- Add new to-do items with text input and submit button
- Display list of existing to-do items with clear formatting
- Mark items as completed with checkbox or button interaction
- Delete items with confirmation to prevent accidental removal
- Filter/view options (all items, completed, pending)
- Clean, intuitive user experience with proper error handling

BACKEND REQUIREMENTS:
- RESTful API with proper HTTP methods (GET, POST, PUT, DELETE)
- Endpoints for CRUD operations on to-do items
- Data persistence using SQLite database
- Proper error handling and status codes
- Input validation and sanitization
- API documentation with clear endpoint descriptions

DATA MODEL:
- To-do item structure: id, text, completed_status, created_date, updated_date
- Database schema with proper indexing for performance
- Data validation for required fields and data types

TECHNICAL REQUIREMENTS:
- Backend: Python with Flask/FastAPI framework
- Frontend: React with TypeScript for type safety
- Database: SQLite with proper migration scripts
- Testing: Unit tests for backend API endpoints
- Testing: Frontend component testing with Jest/Testing Library
- Documentation: README with setup and usage instructions
- Deployment: Docker containerization for easy deployment

QUALITY STANDARDS:
- Code should follow PEP 8 (Python) and ESLint (JavaScript) standards
- Comprehensive error handling for network failures and edge cases
- Responsive design that works on desktop and mobile devices
- Accessibility compliance with ARIA labels and keyboard navigation
- Performance optimization for smooth user interactions
""".strip()

    context_data = {
        "project_type": "full_stack_web_application",
        "estimated_complexity": "medium",
        "technologies": [
            "python", "flask", "fastapi", "sqlite", "react", "typescript",
            "html", "css", "javascript", "docker", "jest", "testing-library"
        ],
        "components": [
            "backend_api", "frontend_ui", "database_schema",
            "test_suite", "documentation", "deployment"
        ],
        "estimated_files": 25,
        "estimated_duration_hours": 40,
        "quality_requirements": [
            "unit_testing", "integration_testing", "code_review",
            "documentation", "error_handling", "accessibility"
        ],
        "deliverables": [
            "working_web_application", "api_documentation",
            "test_suite", "deployment_instructions", "user_guide"
        ],
        "constraints": [
            "use_sqlite_only", "responsive_design_required",
            "accessibility_compliance", "comprehensive_testing"
        ]
    }

    # Insert master task into planning_queue
    try:
        conn = get_connection()
        cursor = conn.cursor()
    except Exception as e:
        logger.error(f"Failed to get database connection: {e}")
        return None

    cursor.execute("""
        INSERT INTO planning_queue
        (id, task_description, priority, requestor, context_data, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        master_task_id,
        task_description,
        95,  # High priority for integration test
        "integration_test_suite",
        json.dumps(context_data),
        "pending",
        datetime.now(timezone.utc).isoformat()
    ))

    conn.commit()

    print("MASTER TASK CREATED:")
    print(f"  Task ID: {master_task_id}")
    print(f"  Description: Complete To-Do List Application")
    print(f"  Priority: 95/100 (High)")
    print(f"  Technologies: {len(context_data['technologies'])} required")
    print(f"  Components: {len(context_data['components'])} to build")
    print(f"  Estimated Duration: {context_data['estimated_duration_hours']} hours")
    print(f"  Status: pending (ready for AI Planner)")
    print()

    # Verify task creation
    cursor.execute("SELECT COUNT(*) FROM planning_queue WHERE id = ?", (master_task_id,))
    count = cursor.fetchone()[0]

    if count == 1:
        print("SUCCESS: Master task successfully inserted into planning_queue")
        print()
        print("NEXT STEPS:")
        print("1. Launch AI Planner daemon to process this task")
        print("2. Launch Hive Orchestrator (Queen) to execute generated sub-tasks")
        print("3. Run monitor_master_plan.py to track progress")
        print()
        print("EXPECTED WORKFLOW:")
        print("  planning_queue (pending) -> AI Planner -> execution_plans + sub-tasks")
        print("  sub-tasks (queued) -> Queen -> apply -> inspect -> review -> test")
        print()

        # Create monitoring metadata file
        metadata = {
            "master_task_id": master_task_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "test_scenario": "grand_integration_test",
            "expected_workflow": [
                "ai_planner_processing",
                "plan_generation",
                "subtask_creation",
                "queen_execution",
                "lifecycle_completion"
            ],
            "monitoring_targets": {
                "planning_queue_status": "pending -> assigned -> planned",
                "execution_plans_count": ">= 1",
                "tasks_created": ">= 3",
                "tasks_lifecycle": "queued -> in_progress -> completed"
            }
        }

        metadata_path = hive_root / "integration_test_metadata.json"
        metadata_path.write_text(json.dumps(metadata, indent=2))

        print(f"SUCCESS: Test metadata saved to {metadata_path}")
        print()
        print("=" * 80)
        print("GRAND INTEGRATION TEST READY TO BEGIN")
        print("=" * 80)

        conn.close()
        return master_task_id

    else:
        print("FAILED: Master task creation failed")
        conn.close()
        return None


def verify_prerequisites():
    """Verify all prerequisites for Grand Integration Test"""

    print("VERIFYING PREREQUISITES:")
    print("-" * 40)

    # Check database
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Check required tables exist
        tables_to_check = ['planning_queue', 'execution_plans', 'tasks', 'runs']
        for table in tables_to_check:
            cursor.execute(f"SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='{table}'")
            if cursor.fetchone()[0] == 0:
                print(f"FAILED: Required table '{table}' not found")
                return False

        print("SUCCESS: All required database tables present")
        conn.close()

    except Exception as e:
        print(f"FAILED: Database check failed: {e}")
        return False

    # Check for ai-planner
    ai_planner_path = hive_root / "apps" / "ai-planner"
    if not ai_planner_path.exists():
        print("FAILED: AI Planner app not found")
        return False

    print("SUCCESS: AI Planner app present")

    # Check for hive-orchestrator components
    orchestrator_path = hive_root / "packages" / "hive-orchestrator"
    if not orchestrator_path.exists():
        print("WARNING: Hive Orchestrator package not found (may be in different location)")
    else:
        print("SUCCESS: Hive Orchestrator package present")

    print("SUCCESS: All prerequisites verified")
    print()

    return True


if __name__ == "__main__":
    try:
        # Verify prerequisites
        if not verify_prerequisites():
            print("FAILED: Prerequisites not met")
            sys.exit(1)

        # Create master task
        task_id = create_master_plan_task()

        if task_id:
            print(f"Master task created successfully: {task_id}")
            sys.exit(0)
        else:
            print("Failed to create master task")
            sys.exit(1)

    except Exception as e:
        logger.error(f"Seeder failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)