#!/usr/bin/env python3
"""
Simple test for AI Planner Claude integration without emoji symbols
"""

from hive_logging import get_logger

logger = get_logger(__name__)
import sys
import uuid

# Imports now handled by Poetry workspace dependencies

try:
    from ai_planner.agent import AIPlanner
    from ai_planner.claude_bridge import RobustClaudePlannerBridge

    from hive_db import get_connection, init_db

    def test_basic_functionality():
        """Test basic AI Planner functionality"""

        logger.info("Starting basic AI Planner tests...")

        # Initialize database
        init_db()
        logger.info("SUCCESS: Database initialized")

        # Test Claude bridge in mock mode
        bridge = RobustClaudePlannerBridge(mock_mode=True)
        logger.info("SUCCESS: Claude bridge initialized")

        # Test plan generation
        plan = bridge.generate_execution_plan(
            task_description="Build a simple web API",
            context_data={"files_affected": 3},
        )

        assert plan is not None
        assert "plan_id" in plan
        assert "sub_tasks" in plan
        logger.info("SUCCESS: Plan generation working")

        # Test AI Planner integration
        agent = AIPlanner(mock_mode=True),
        success = agent.connect_database()
        assert success
        logger.info("SUCCESS: AI Planner database connection")

        # Test task processing
        test_task = {
            "id": "test-" + str(uuid.uuid4())[:8],
            "task_description": "Create user authentication",
            "priority": 50,
            "requestor": "test",
            "context_data": {"files_affected": 2},
        }

        plan = agent.generate_execution_plan(test_task)
        assert plan is not None
        assert plan["metadata"]["generation_method"] == "claude-powered"
        logger.info("SUCCESS: Task processing working")

        # Test plan saving
        save_result = agent.save_execution_plan(plan)
        assert save_result
        logger.info("SUCCESS: Plan saving working")

        # Cleanup
        if agent.db_connection:
            cursor = agent.db_connection.cursor()
            cursor.execute("DELETE FROM execution_plans WHERE planning_task_id = ?", (test_task["id"],))
            cursor.execute("DELETE FROM tasks WHERE task_type = 'planned_subtask'")
            agent.db_connection.commit()
            agent.db_connection.close()

        logger.info("SUCCESS: All basic tests passed!")
        logger.info("Phase 2 Claude Integration is working correctly!")

        return True

    if __name__ == "__main__":
        try:
            success = test_basic_functionality()
            if success:
                logger.info("\nCONCLUSION: Phase 2 implementation successful")
                sys.exit(0)
            else:
                logger.info("\nCONCLUSION: Phase 2 implementation failed")
                sys.exit(1)
        except Exception as e:
            logger.info(f"\nFAILED: Test failed with error: {e}")
            import traceback

            traceback.print_exc()
            sys.exit(1)

except ImportError as e:
    logger.info(f"FAILED: Import error: {e}")
    sys.exit(1)
