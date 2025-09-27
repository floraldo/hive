#!/usr/bin/env python3
"""
AI Planner Agent - Intelligent Task Planning and Workflow Generation

Core autonomous agent that monitors the planning_queue and generates
executable plans for complex tasks submitted to the Hive system.
"""

import time
import logging
import sqlite3
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, List
import signal
import sys

from hive_core_db.database import get_connection, create_task
from hive_claude_bridge import (
    get_claude_service,
    ClaudeService,
    RateLimitConfig,
    ClaudeBridgeConfig
)
from hive_errors import (
    PlannerError,
    DatabaseConnectionError,
    TaskProcessingError,
    PlanGenerationError,
    ErrorReporter,
    RetryStrategy,
    ExponentialBackoffStrategy,
    with_recovery
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('ai-planner.log')
    ]
)
logger = logging.getLogger('ai-planner')

class AIPlanner:
    """
    AI Planner Agent - Autonomous task planning and workflow generation

    This agent continuously monitors the planning_queue for new tasks and
    generates structured execution plans that can be consumed by the
    hive-orchestrator and other system components.
    """

    def __init__(self, mock_mode: bool = False):
        self.running = True
        self.agent_id = f"ai-planner-{uuid.uuid4().hex[:8]}"
        self.db_connection = None
        self.poll_interval = 5  # seconds
        self.max_planning_time = 300  # 5 minutes max per task
        self.mock_mode = mock_mode

        # Initialize error reporter
        self.error_reporter = ErrorReporter(component_name="ai-planner")

        # Initialize recovery strategies
        self.db_retry_strategy = ExponentialBackoffStrategy(
            max_retries=3,
            base_delay=1.0,
            max_delay=10.0
        )
        self.claude_retry_strategy = RetryStrategy(
            max_retries=2,
            delay=2.0
        )

        # Initialize Claude service for intelligent planning
        config = ClaudeBridgeConfig(mock_mode=mock_mode)
        rate_config = RateLimitConfig(
            max_calls_per_minute=20,
            max_calls_per_hour=500
        )
        self.claude_service = get_claude_service(config=config, rate_config=rate_config)

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        logger.info(f"AI Planner Agent initialized: {self.agent_id} (mock_mode={mock_mode})")

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        self.running = False

    def connect_database(self) -> bool:
        """Establish database connection with retry logic"""
        try:
            def _connect():
                self.db_connection = get_connection()
                return self.db_connection

            # Use recovery strategy for database connection
            self.db_connection = with_recovery(
                self.db_retry_strategy,
                _connect
            )
            logger.info("Database connection established")
            return True
        except Exception as e:
            error = DatabaseConnectionError(
                message="Failed to establish database connection",
                original_error=e,
                retry_count=self.db_retry_strategy.max_retries
            )
            self.error_reporter.report_error(error)
            return False

    def get_next_task(self) -> Optional[Dict[str, Any]]:
        """
        Fetch the next high-priority task from planning_queue

        Returns:
            Dict containing task information or None if no tasks available
        """
        if not self.db_connection:
            return None

        try:
            cursor = self.db_connection.cursor()

            # Get highest priority pending task
            cursor.execute("""
                SELECT id, task_description, priority, requestor, context_data,
                       complexity_estimate, created_at
                FROM planning_queue
                WHERE status = 'pending'
                ORDER BY priority DESC, created_at ASC
                LIMIT 1
            """)

            result = cursor.fetchone()
            if not result:
                return None

            # Mark task as assigned to this agent
            task_id = result[0]
            cursor.execute("""
                UPDATE planning_queue
                SET status = 'assigned', assigned_at = ?, assigned_agent = ?
                WHERE id = ?
            """, (datetime.now(timezone.utc).isoformat(), self.agent_id, task_id))

            self.db_connection.commit()

            # Return task data as dictionary
            return {
                'id': result[0],
                'task_description': result[1],
                'priority': result[2],
                'requestor': result[3],
                'context_data': json.loads(result[4]) if result[4] else {},
                'complexity_estimate': result[5],
                'created_at': result[6]
            }

        except Exception as e:
            error = TaskProcessingError(
                message=f"Error fetching next task from planning queue",
                task_id=None,
                phase="task_retrieval",
                original_error=e
            )
            self.error_reporter.report_error(error)
            return None

    def analyze_task_complexity(self, task_description: str, context_data: Dict) -> str:
        """
        Analyze task complexity for initial estimation

        Args:
            task_description: The task to analyze
            context_data: Additional context information

        Returns:
            Complexity level: 'simple', 'medium', or 'complex'
        """
        # Simple heuristic-based complexity analysis
        # TODO: Replace with AI-powered analysis in Phase 2

        description_lower = task_description.lower()

        # Complex task indicators
        complex_keywords = [
            'architecture', 'design', 'refactor', 'migrate', 'integration',
            'security', 'performance', 'scalability', 'database', 'api'
        ]

        # Simple task indicators
        simple_keywords = [
            'fix', 'update', 'add', 'remove', 'change', 'copy', 'move'
        ]

        complex_score = sum(1 for keyword in complex_keywords if keyword in description_lower)
        simple_score = sum(1 for keyword in simple_keywords if keyword in description_lower)

        # Consider context data
        if context_data.get('files_affected', 0) > 10:
            complex_score += 2
        if context_data.get('dependencies', []):
            complex_score += 1

        if complex_score >= 2:
            return 'complex'
        elif simple_score >= 2 and complex_score == 0:
            return 'simple'
        else:
            return 'medium'

    def generate_execution_plan(self, task: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Generate a structured execution plan using Claude AI

        Args:
            task: Task information from planning_queue

        Returns:
            Execution plan dictionary or None if generation failed
        """
        try:
            logger.info(f"Generating Claude-powered plan for task: {task['id']}")

            # Use Claude service for intelligent planning with caching
            claude_response = self.claude_service.generate_execution_plan(
                task_description=task['task_description'],
                context_data=task['context_data'],
                priority=task['priority'],
                requestor=task['requestor'],
                use_cache=True  # Enable caching for similar planning requests
            )

            if not claude_response:
                error = PlanGenerationError(
                    message=f"Claude bridge returned empty response",
                    task_id=task['id'],
                    task_description=task['task_description'],
                    original_error=None
                )
                self.error_reporter.report_error(error)
                return None

            # Enhance the Claude response with additional metadata
            enhanced_plan = {
                **claude_response,
                'task_id': task['id'],
                'created_at': datetime.now(timezone.utc).isoformat(),
                'status': 'generated',
                'metadata': {
                    'generator': 'ai-planner-v2-claude',
                    'agent_id': self.agent_id,
                    'generation_method': 'claude-powered',
                    'claude_confidence': claude_response.get('metrics', {}).get('confidence_score', 0.0)
                }
            }

            logger.info(f"Claude plan generated: {enhanced_plan['plan_name']}")
            logger.info(f"Sub-tasks: {len(enhanced_plan['sub_tasks'])}, Duration: {enhanced_plan['metrics']['total_estimated_duration']}min")

            return enhanced_plan

        except Exception as e:
            error = PlanGenerationError(
                message="Failed to generate execution plan",
                task_id=task['id'],
                task_description=task['task_description'],
                original_error=e
            )
            self.error_reporter.report_error(error)
            return None

    def _estimate_duration(self, complexity: str) -> int:
        """Estimate task duration in minutes based on complexity"""
        duration_map = {
            'simple': 15,
            'medium': 60,
            'complex': 180
        }
        return duration_map.get(complexity, 60)

    def _estimate_resources(self, complexity: str) -> List[str]:
        """Estimate required resources based on complexity"""
        resource_map = {
            'simple': ['basic-compute'],
            'medium': ['standard-compute', 'database-access'],
            'complex': ['high-compute', 'database-access', 'external-apis', 'storage']
        }
        return resource_map.get(complexity, ['standard-compute'])

    def _generate_plan_steps(self, task: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Generate basic plan steps using rule-based approach

        Args:
            task: Task information

        Returns:
            List of plan steps
        """
        # Basic step generation - will be enhanced with AI in Phase 2
        description = task['task_description'].lower()

        steps = []
        step_id = 1

        # Always start with analysis
        steps.append({
            'step_id': step_id,
            'name': 'Task Analysis',
            'description': 'Analyze requirements and gather context',
            'type': 'analysis',
            'estimated_duration': 5,
            'dependencies': []
        })
        step_id += 1

        # Add domain-specific steps based on keywords
        if any(word in description for word in ['api', 'endpoint', 'service']):
            steps.append({
                'step_id': step_id,
                'name': 'API Design',
                'description': 'Design API interfaces and data structures',
                'type': 'design',
                'estimated_duration': 20,
                'dependencies': [1]
            })
            step_id += 1

        if any(word in description for word in ['frontend', 'ui', 'component']):
            steps.append({
                'step_id': step_id,
                'name': 'UI Implementation',
                'description': 'Create user interface components',
                'type': 'implementation',
                'estimated_duration': 30,
                'dependencies': [1]
            })
            step_id += 1

        if any(word in description for word in ['database', 'data', 'storage']):
            steps.append({
                'step_id': step_id,
                'name': 'Data Layer',
                'description': 'Implement data persistence and retrieval',
                'type': 'implementation',
                'estimated_duration': 25,
                'dependencies': [1]
            })
            step_id += 1

        # Always end with testing and validation
        steps.append({
            'step_id': step_id,
            'name': 'Testing & Validation',
            'description': 'Test implementation and validate requirements',
            'type': 'validation',
            'estimated_duration': 15,
            'dependencies': list(range(2, step_id))
        })

        return steps

    def save_execution_plan(self, plan: Dict[str, Any]) -> bool:
        """
        Save the generated execution plan and create sub-tasks

        Args:
            plan: Execution plan to save

        Returns:
            True if saved successfully, False otherwise
        """
        if not self.db_connection:
            return False

        try:
            cursor = self.db_connection.cursor()

            # Use autocommit mode to avoid nested transaction issues

            # Insert execution plan
            cursor.execute("""
                INSERT INTO execution_plans
                (id, planning_task_id, plan_data, estimated_complexity,
                 estimated_duration, status, generated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                plan['plan_id'],
                plan['task_id'],
                json.dumps(plan),
                plan.get('metrics', {}).get('complexity_breakdown', {}).get('complex', 0) > 0 and 'complex' or 'medium',
                plan.get('metrics', {}).get('total_estimated_duration', 60),
                plan['status'],
                plan['created_at']
            ))

            # Create individual sub-tasks in the main tasks table
            if 'sub_tasks' in plan:
                for sub_task in plan['sub_tasks']:
                    try:
                        # Create each sub-task using the hive-core-db function
                        task_id = create_task(
                            title=sub_task['title'],
                            task_type='planned_subtask',
                            description=sub_task['description'],
                            payload={
                                'parent_plan_id': plan['plan_id'],
                                'subtask_id': sub_task['id'],
                                'assignee': sub_task['assignee'],
                                'complexity': sub_task['complexity'],
                                'estimated_duration': sub_task['estimated_duration'],
                                'workflow_phase': sub_task['workflow_phase'],
                                'required_skills': sub_task['required_skills'],
                                'deliverables': sub_task['deliverables'],
                                'dependencies': sub_task['dependencies']
                            }
                        )
                        logger.debug(f"Created sub-task: {task_id} for {sub_task['title']}")
                    except Exception as sub_task_error:
                        error = TaskProcessingError(
                            message=f"Failed to create sub-task",
                            task_id=sub_task['id'],
                            phase="sub_task_creation",
                            original_error=sub_task_error
                        )
                        self.error_reporter.report_error(error, severity="WARNING")
                        # Continue with other sub-tasks rather than failing the entire operation

            # Commit all changes
            self.db_connection.commit()
            logger.info(f"Execution plan saved: {plan['plan_id']} with {len(plan.get('sub_tasks', []))} sub-tasks")
            return True

        except Exception as e:
            # Rollback on error
            if self.db_connection:
                try:
                    self.db_connection.rollback()
                except Exception as rollback_error:
                    logger.debug(f"Rollback failed: {rollback_error}")

            error = DatabaseConnectionError(
                message="Failed to save execution plan to database",
                original_error=e,
                retry_count=0
            )
            self.error_reporter.report_error(error)
            return False

    def update_task_status(self, task_id: str, status: str, completion_data: Optional[Dict] = None) -> bool:
        """
        Update task status in planning_queue

        Args:
            task_id: Task identifier
            status: New status ('planned', 'failed', etc.)
            completion_data: Optional completion information

        Returns:
            True if updated successfully, False otherwise
        """
        if not self.db_connection:
            return False

        try:
            cursor = self.db_connection.cursor()

            if status == 'planned':
                cursor.execute("""
                    UPDATE planning_queue
                    SET status = ?, completed_at = ?
                    WHERE id = ?
                """, (status, datetime.now(timezone.utc).isoformat(), task_id))
            else:
                cursor.execute("""
                    UPDATE planning_queue
                    SET status = ?
                    WHERE id = ?
                """, (status, task_id))

            self.db_connection.commit()
            logger.info(f"Task {task_id} status updated to: {status}")
            return True

        except Exception as e:
            error = DatabaseConnectionError(
                message=f"Failed to update task status to {status}",
                original_error=e,
                retry_count=0
            )
            self.error_reporter.report_error(error)
            return False

    def process_task(self, task: Dict[str, Any]) -> bool:
        """
        Process a single task through the planning pipeline

        Args:
            task: Task to process

        Returns:
            True if processed successfully, False otherwise
        """
        try:
            logger.info(f"Processing task: {task['id']} - {task['task_description'][:100]}...")

            # Generate execution plan
            plan = self.generate_execution_plan(task)
            if not plan:
                logger.error(f"Failed to generate plan for task: {task['id']}")
                self.update_task_status(task['id'], 'failed')
                return False

            # Save execution plan
            if not self.save_execution_plan(plan):
                logger.error(f"Failed to save plan for task: {task['id']}")
                self.update_task_status(task['id'], 'failed')
                return False

            # Mark task as planned
            self.update_task_status(task['id'], 'planned')

            logger.info(f"Successfully planned task: {task['id']} with plan: {plan['plan_id']}")
            return True

        except Exception as e:
            error = TaskProcessingError(
                message="Unexpected error during task processing",
                task_id=task['id'],
                phase="processing",
                original_error=e
            )
            self.error_reporter.report_error(error)
            self.update_task_status(task['id'], 'failed')
            return False

    def run(self):
        """Main agent execution loop"""
        logger.info("AI Planner Agent starting...")

        # Connect to database
        if not self.connect_database():
            logger.error("Failed to establish database connection. Exiting.")
            return 1

        logger.info("AI Planner Agent is running. Monitoring planning_queue...")

        while self.running:
            try:
                # Check for new tasks
                task = self.get_next_task()

                if task:
                    # Process the task
                    success = self.process_task(task)
                    if success:
                        logger.info(f"Task {task['id']} processed successfully")
                    else:
                        logger.warning(f"Task {task['id']} processing failed")
                else:
                    # No tasks available, wait before next poll
                    time.sleep(self.poll_interval)

            except KeyboardInterrupt:
                logger.info("Received keyboard interrupt, shutting down...")
                break
            except Exception as e:
                error = PlannerError(
                    message="Unexpected error in main processing loop",
                    original_error=e
                )
                self.error_reporter.report_error(error)
                time.sleep(self.poll_interval)

        # Cleanup
        if self.db_connection:
            self.db_connection.close()
            logger.info("Database connection closed")

        logger.info("AI Planner Agent shutdown complete")
        return 0


def main():
    """Entry point for AI Planner Agent"""
    import argparse

    parser = argparse.ArgumentParser(description='AI Planner Agent - Intelligent Task Planning')
    parser.add_argument('--mock', action='store_true', help='Run in mock mode for testing')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Debug logging enabled")

    try:
        agent = AIPlanner(mock_mode=args.mock)
        return agent.run()
    except Exception as e:
        logger.error(f"Failed to start AI Planner Agent: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())