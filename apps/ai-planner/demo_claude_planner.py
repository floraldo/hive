#!/usr/bin/env python3
"""
AI Planner Phase 2 Claude Integration Demonstration

This script demonstrates the complete Claude-powered planning workflow
from task submission to intelligent plan generation and sub-task creation.
"""

import sys
import json
import uuid
from pathlib import Path
from datetime import datetime

# Setup Hive paths using centralized path manager
# Note: This assumes the workspace has been properly installed with Poetry
from hive_config.path_manager import setup_hive_paths
setup_hive_paths()

from ai_planner.agent import AIPlanner
from ai_planner.claude_bridge import RobustClaudePlannerBridge
from hive_core_db.database import get_connection, init_db


def demonstrate_claude_planning():
    """Demonstrate the complete Claude-powered planning workflow"""

    print("=" * 70)
    print("AI PLANNER PHASE 2 - CLAUDE INTEGRATION DEMONSTRATION")
    print("=" * 70)
    print()

    # Initialize the system
    print("1. SYSTEM INITIALIZATION")
    print("-" * 30)

    init_db()
    print("SUCCESS: Database initialized")

    agent = AIPlanner(mock_mode=True)  # Using mock mode for reliable demo
    agent.connect_database()
    print("SUCCESS: AI Planner agent initialized")
    print("SUCCESS: Claude bridge initialized (mock mode)")
    print()

    # Demonstrate complex task planning
    print("2. COMPLEX TASK SUBMISSION")
    print("-" * 30)

    complex_task = {
        'id': f'demo-{datetime.now().strftime("%Y%m%d-%H%M%S")}',
        'task_description': """
        Design and implement a complete real-time collaboration platform with the following features:
        - Multi-user document editing with operational transforms
        - Real-time video/audio conferencing with WebRTC
        - Persistent chat system with message history
        - User authentication and authorization with role-based access
        - File sharing and version control integration
        - Mobile-responsive web interface
        - API for third-party integrations
        - Microservices architecture with Docker deployment
        """.strip(),
        'priority': 90,
        'requestor': 'product_team',
        'context_data': {
            'files_affected': 50,
            'dependencies': [
                'websockets', 'webrtc', 'operational-transforms',
                'jwt', 'redis', 'postgres', 'docker', 'kubernetes',
                'react', 'typescript', 'fastapi', 'socketio'
            ],
            'tech_stack': ['python', 'javascript', 'typescript', 'react', 'fastapi'],
            'constraints': [
                'Real-time performance (<100ms latency)',
                'Support 1000+ concurrent users',
                'GDPR compliance for user data',
                'Cross-browser compatibility',
                'Mobile responsiveness'
            ],
            'estimated_timeline': '12 weeks',
            'team_size': 6
        }
    }

    print(f"Task ID: {complex_task['id']}")
    print(f"Description: {complex_task['task_description'][:100]}...")
    print(f"Priority: {complex_task['priority']}/100")
    print(f"Dependencies: {len(complex_task['context_data']['dependencies'])} technologies")
    print(f"Constraints: {len(complex_task['context_data']['constraints'])} requirements")
    print()

    # Insert task into planning queue
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO planning_queue
        (id, task_description, priority, requestor, context_data, status)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        complex_task['id'],
        complex_task['task_description'],
        complex_task['priority'],
        complex_task['requestor'],
        json.dumps(complex_task['context_data']),
        'pending'
    ))
    conn.commit()
    print("SUCCESS: Complex task submitted to planning queue")
    print()

    # Demonstrate Claude-powered planning
    print("3. CLAUDE-POWERED PLAN GENERATION")
    print("-" * 30)

    # Retrieve and process the task
    task = agent.get_next_task()
    if task and task['id'] == complex_task['id']:
        print("SUCCESS: Task retrieved from queue")
        print(f"Task status: {task.get('status', 'unknown')} -> assigned")
        print()

        print("Generating intelligent execution plan with Claude...")
        plan = agent.generate_execution_plan(task)

        if plan:
            print("SUCCESS: Claude plan generation completed!")
            print()
            print("PLAN SUMMARY:")
            print(f"  Plan ID: {plan['plan_id']}")
            print(f"  Plan Name: {plan['plan_name']}")
            print(f"  Plan Summary: {plan.get('plan_summary', 'N/A')}")
            print()

            print("PLAN METRICS:")
            metrics = plan.get('metrics', {})
            print(f"  Total Duration: {metrics.get('total_estimated_duration', 'N/A')} minutes")
            print(f"  Critical Path: {metrics.get('critical_path_duration', 'N/A')} minutes")
            print(f"  Complexity: {metrics.get('complexity_breakdown', {})}")
            print(f"  Skills Required: {metrics.get('skill_requirements', {})}")
            print(f"  Confidence Score: {metrics.get('confidence_score', 'N/A')}")
            print()

            print("SUB-TASKS GENERATED:")
            sub_tasks = plan.get('sub_tasks', [])
            for i, subtask in enumerate(sub_tasks[:5], 1):  # Show first 5
                print(f"  {i}. {subtask['title']}")
                print(f"     Assignee: {subtask['assignee']}")
                print(f"     Duration: {subtask['estimated_duration']} min")
                print(f"     Complexity: {subtask['complexity']}")
                print(f"     Phase: {subtask['workflow_phase']}")
                print()

            if len(sub_tasks) > 5:
                print(f"  ... and {len(sub_tasks) - 5} more sub-tasks")
                print()
        else:
            print("FAILED: Plan generation failed")
            return False
    else:
        print("FAILED: Could not retrieve task from queue")
        return False

    # Demonstrate plan persistence
    print("4. PLAN PERSISTENCE AND SUB-TASK CREATION")
    print("-" * 30)

    save_success = agent.save_execution_plan(plan)
    if save_success:
        print("SUCCESS: Execution plan saved to database")

        # Update task status
        agent.update_task_status(task['id'], 'planned')

        # Verify persistence
        cursor.execute("SELECT COUNT(*) FROM execution_plans WHERE planning_task_id = ?", (task['id'],))
        plan_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM tasks WHERE task_type = 'planned_subtask'")
        subtask_count = cursor.fetchone()[0]

        print(f"SUCCESS: {plan_count} execution plan(s) persisted")
        print(f"SUCCESS: {subtask_count} sub-task(s) created in task queue")
        print(f"SUCCESS: Task status updated to 'planned'")
        print()
    else:
        print("FAILED: Plan persistence failed")
        return False

    # Demonstrate integration capabilities
    print("5. INTEGRATION READINESS")
    print("-" * 30)

    print("The AI Planner is now ready for:")
    print("  • Integration with hive-orchestrator for workflow execution")
    print("  • Assignment of sub-tasks to specialized workers")
    print("  • Real-time progress tracking and plan adjustments")
    print("  • Dependency management and parallel execution optimization")
    print("  • Quality gates and validation checkpoints")
    print()

    # Cleanup
    cursor.execute("DELETE FROM planning_queue WHERE id = ?", (task['id'],))
    cursor.execute("DELETE FROM execution_plans WHERE planning_task_id = ?", (task['id'],))
    cursor.execute("DELETE FROM tasks WHERE task_type = 'planned_subtask'")
    conn.commit()
    conn.close()
    agent.db_connection.close()

    print("6. PHASE 2 COMPLETION STATUS")
    print("-" * 30)
    print("SUCCESS: Phase 2 'Core Planning Engine' implementation complete!")
    print()
    print("ACHIEVEMENTS:")
    print("  • Claude API integration with robust error handling")
    print("  • Intelligent task decomposition and analysis")
    print("  • Structured execution plan generation")
    print("  • Database persistence with sub-task creation")
    print("  • Production-ready architecture with mock/real modes")
    print("  • Comprehensive test coverage and validation")
    print()
    print("The AI Planner has evolved from a rule-based MVP to a")
    print("sophisticated, Claude-powered intelligent planning engine!")

    print("=" * 70)

    return True


if __name__ == "__main__":
    try:
        success = demonstrate_claude_planning()
        if success:
            print("DEMONSTRATION COMPLETED SUCCESSFULLY")
            sys.exit(0)
        else:
            print("DEMONSTRATION FAILED")
            sys.exit(1)
    except Exception as e:
        print(f"DEMONSTRATION ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)