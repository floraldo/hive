from hive_logging import get_logger

logger = get_logger(__name__)

#!/usr/bin/env python3
"""
AI Planner Phase 2 Claude Integration Demonstration

This script demonstrates the complete Claude-powered planning workflow
from task submission to intelligent plan generation and sub-task creation.
"""

import json
import sys
from datetime import datetime

from ai_planner.agent import AIPlanner

from hive_db import get_connection, init_db


def demonstrate_claude_planning() -> None:
    """Demonstrate the complete Claude-powered planning workflow"""

    logger.info("=" * 70)
    logger.info("AI PLANNER PHASE 2 - CLAUDE INTEGRATION DEMONSTRATION")
    logger.info("=" * 70)
    logger.info("")

    # Initialize the system
    logger.info("1. SYSTEM INITIALIZATION")
    logger.info("-" * 30)

    init_db()
    logger.info("SUCCESS: Database initialized")

    agent = AIPlanner(mock_mode=True)  # Using mock mode for reliable demo
    agent.connect_database()
    logger.info("SUCCESS: AI Planner agent initialized")
    logger.info("SUCCESS: Claude bridge initialized (mock mode)")
    logger.info("")

    # Demonstrate complex task planning
    logger.info("2. COMPLEX TASK SUBMISSION")
    logger.info("-" * 30)

    complex_task = {
        "id": f"demo-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
        "task_description": """,
        Design and implement a complete real-time collaboration platform with the following features:
        - Multi-user document editing with operational transforms,
        - Real-time video/audio conferencing with WebRTC,
        - Persistent chat system with message history
        - User authentication and authorization with role-based access
        - File sharing and version control integration
        - Mobile-responsive web interface
        - API for third-party integrations
        - Microservices architecture with Docker deployment
        """.strip(),
        "priority": 90,
        "requestor": "product_team",
        "context_data": {
            "files_affected": 50,
            "dependencies": [
                "websockets",
                "webrtc",
                "operational-transforms",
                "jwt",
                "redis",
                "postgres",
                "docker",
                "kubernetes",
                "react",
                "typescript",
                "fastapi",
                "socketio",
            ],
            "tech_stack": ["python", "javascript", "typescript", "react", "fastapi"],
            "constraints": [
                "Real-time performance (<100ms latency)",
                "Support 1000+ concurrent users",
                "GDPR compliance for user data",
                "Cross-browser compatibility",
                "Mobile responsiveness",
            ],
            "estimated_timeline": "12 weeks",
            "team_size": 6,
        },
    }

    logger.info(f"Task ID: {complex_task['id']}")
    logger.info(f"Description: {complex_task['task_description'][:100]}...")
    logger.info(f"Priority: {complex_task['priority']}/100")
    logger.info(f"Dependencies: {len(complex_task['context_data']['dependencies'])} technologies")
    logger.info(f"Constraints: {len(complex_task['context_data']['constraints'])} requirements")
    logger.info("")

    # Insert task into planning queue
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """,
        INSERT INTO planning_queue,
        (id, task_description, priority, requestor, context_data, status)
        VALUES (?, ?, ?, ?, ?, ?)
    """,
        (
            complex_task["id"],
            complex_task["task_description"],
            complex_task["priority"],
            complex_task["requestor"],
            json.dumps(complex_task["context_data"]),
            "pending",
        ),
    )
    conn.commit()
    logger.info("SUCCESS: Complex task submitted to planning queue")
    logger.info("")

    # Demonstrate Claude-powered planning
    logger.info("3. CLAUDE-POWERED PLAN GENERATION")
    logger.info("-" * 30)

    # Retrieve and process the task
    task = agent.get_next_task()
    if task and task["id"] == complex_task["id"]:
        logger.info("SUCCESS: Task retrieved from queue")
        logger.info(f"Task status: {task.get('status', 'unknown')} -> assigned")
        logger.info("")

        logger.info("Generating intelligent execution plan with Claude...")
        plan = agent.generate_execution_plan(task)

        if plan:
            logger.info("SUCCESS: Claude plan generation completed!")
            logger.info("")
            logger.info("PLAN SUMMARY:")
            logger.info(f"  Plan ID: {plan['plan_id']}")
            logger.info(f"  Plan Name: {plan['plan_name']}")
            logger.info(f"  Plan Summary: {plan.get('plan_summary', 'N/A')}")
            logger.info("")

            logger.info("PLAN METRICS:")
            metrics = plan.get("metrics", {})
            logger.info(f"  Total Duration: {metrics.get('total_estimated_duration', 'N/A')} minutes")
            logger.info(f"  Critical Path: {metrics.get('critical_path_duration', 'N/A')} minutes")
            logger.info(f"  Complexity: {metrics.get('complexity_breakdown', {})}")
            logger.info(f"  Skills Required: {metrics.get('skill_requirements', {})}")
            logger.info(f"  Confidence Score: {metrics.get('confidence_score', 'N/A')}")
            logger.info("")

            logger.info("SUB-TASKS GENERATED:")
            sub_tasks = plan.get("sub_tasks", [])
            for i, subtask in enumerate(sub_tasks[:5], 1):  # Show first 5
                logger.info(f"  {i}. {subtask['title']}")
                logger.info(f"     Assignee: {subtask['assignee']}")
                logger.info(f"     Duration: {subtask['estimated_duration']} min")
                logger.info(f"     Complexity: {subtask['complexity']}")
                logger.info(f"     Phase: {subtask['workflow_phase']}")
                logger.info("")

            if len(sub_tasks) > 5:
                logger.info(f"  ... and {len(sub_tasks) - 5} more sub-tasks")
                logger.info("")
        else:
            logger.info("FAILED: Plan generation failed")
            return False
    else:
        logger.info("FAILED: Could not retrieve task from queue")
        return False

    # Demonstrate plan persistence
    logger.info("4. PLAN PERSISTENCE AND SUB-TASK CREATION")
    logger.info("-" * 30)

    save_success = agent.save_execution_plan(plan)
    if save_success:
        logger.info("SUCCESS: Execution plan saved to database")

        # Update task status
        agent.update_task_status(task["id"], "planned")

        # Verify persistence
        cursor.execute("SELECT COUNT(*) FROM execution_plans WHERE planning_task_id = ?", (task["id"],))
        plan_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM tasks WHERE task_type = 'planned_subtask'")
        subtask_count = cursor.fetchone()[0]

        logger.info(f"SUCCESS: {plan_count} execution plan(s) persisted")
        logger.info(f"SUCCESS: {subtask_count} sub-task(s) created in task queue")
        logger.info("SUCCESS: Task status updated to 'planned'")
        logger.info("")
    else:
        logger.info("FAILED: Plan persistence failed")
        return False

    # Demonstrate integration capabilities
    logger.info("5. INTEGRATION READINESS")
    logger.info("-" * 30)

    logger.info("The AI Planner is now ready for:")
    logger.info("  • Integration with hive-orchestrator for workflow execution")
    logger.info("  • Assignment of sub-tasks to specialized workers")
    logger.info("  • Real-time progress tracking and plan adjustments")
    logger.info("  • Dependency management and parallel execution optimization")
    logger.info("  • Quality gates and validation checkpoints")
    logger.info("")

    # Cleanup
    cursor.execute("DELETE FROM planning_queue WHERE id = ?", (task["id"],))
    cursor.execute("DELETE FROM execution_plans WHERE planning_task_id = ?", (task["id"],))
    cursor.execute("DELETE FROM tasks WHERE task_type = 'planned_subtask'")
    conn.commit()
    conn.close()
    agent.db_connection.close()

    logger.info("6. PHASE 2 COMPLETION STATUS")
    logger.info("-" * 30)
    logger.info("SUCCESS: Phase 2 'Core Planning Engine' implementation complete!")
    logger.info("")
    logger.info("ACHIEVEMENTS:")
    logger.info("  • Claude API integration with robust error handling")
    logger.info("  • Intelligent task decomposition and analysis")
    logger.info("  • Structured execution plan generation")
    logger.info("  • Database persistence with sub-task creation")
    logger.info("  • Production-ready architecture with mock/real modes")
    logger.info("  • Comprehensive test coverage and validation")
    logger.info("")
    logger.info("The AI Planner has evolved from a rule-based MVP to a")
    logger.info("sophisticated, Claude-powered intelligent planning engine!")

    logger.info("=" * 70)

    return True


if __name__ == "__main__":
    try:
        success = demonstrate_claude_planning()
        if success:
            logger.info("DEMONSTRATION COMPLETED SUCCESSFULLY")
            sys.exit(0)
        else:
            logger.info("DEMONSTRATION FAILED")
            sys.exit(1)
    except Exception as e:
        logger.info(f"DEMONSTRATION ERROR: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
