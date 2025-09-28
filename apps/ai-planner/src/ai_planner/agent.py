#!/usr/bin/env python3
"""
AI Planner Agent - Intelligent Task Planning and Workflow Generation

Core autonomous agent that monitors the planning_queue and generates
executable plans for complex tasks submitted to the Hive system.
"""

import time
from hive_logging import get_logger
import sqlite3
import json
import uuid
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, List
import signal
import sys
from enum import Enum

# Use orchestrator's core database functions
try:
    from hive_orchestrator.core.db import (
        get_connection, create_task, get_async_connection,
        create_task_async, get_tasks_by_status_async, update_task_status_async
    )
    ASYNC_AVAILABLE = True
except ImportError:
    # Fallback to basic functions if async not available
    from hive_orchestrator.core.db import get_connection, create_task
    ASYNC_AVAILABLE = False
# Claude bridge functionality has been moved to individual apps
# For now, create mock classes until proper implementation
class ClaudeService:
    def __init__(self, config=None, rate_config=None):
        self.mock_mode = getattr(config, 'mock_mode', True)

    def generate_execution_plan(self, task_description: str, context_data: Dict[str, Any], priority: int, requestor: str, use_cache: bool = True) -> Dict[str, Any]:
        # Mock implementation - replace with actual Claude integration
        return {
            'plan_id': f"plan_{uuid.uuid4().hex[:8]}",
            'plan_name': f"Generated Plan for: {task_description[:50]}",
            'sub_tasks': [{
                'id': f"subtask_{uuid.uuid4().hex[:8]}",
                'title': 'Analyze requirements',
                'description': 'Analyze the task requirements and gather context',
                'assignee': 'auto',
                'complexity': 'medium',
                'estimated_duration': 30,
                'workflow_phase': 'analysis',
                'required_skills': ['analysis'],
                'deliverables': ['requirements_doc'],
                'dependencies': []
            }],
            'metrics': {
                'total_estimated_duration': 30,
                'complexity_breakdown': {'medium': 1},
                'confidence_score': 0.8
            }
        }

class RateLimitConfig:
    def __init__(self, max_calls_per_minute=20, max_calls_per_hour=500):
        self.max_calls_per_minute = max_calls_per_minute
        self.max_calls_per_hour = max_calls_per_hour

class ClaudeBridgeConfig:
    def __init__(self, mock_mode=True):
        self.mock_mode = mock_mode

def get_claude_service(config: Optional[Dict[str, Any]] = None, rate_config: Optional[Dict[str, Any]] = None) -> ClaudeService:
    """Get a Claude service instance with optional configuration.

    Args:
        config: Optional Claude service configuration
        rate_config: Optional rate limiting configuration

    Returns:
        Configured Claude service instance
    """
    return ClaudeService(config, rate_config)
# Import error classes from our core module following the "inherit -> extend" pattern
from ai_planner.core.errors import (
    PlannerError,
    TaskProcessingError,
    TaskValidationError,
    TaskQueueError,
    PlanGenerationError,
    ClaudeServiceError,
    PlanValidationError,
    DatabaseConnectionError,
    get_error_reporter
)

# Import recovery strategies from core module (follows "inherit -> extend" pattern)
from ai_planner.core.errors import ExponentialBackoffStrategy, with_recovery

# Initialize error reporter following the pattern
ErrorReporter = get_error_reporter  # Use the core error reporter

# Database imports - use orchestrator's extended database layer for Hive schema
try:
    # Import the orchestrator's Hive-specific database layer (extends hive-db-utils)
    from hive_orchestrator.core.db import get_connection, get_pooled_connection
    DATABASE_AVAILABLE = True
except ImportError:
    # Fallback to generic database utilities if orchestrator not available
    from hive_config import get_config
    DATABASE_AVAILABLE = False

# Note: AI Planner communicates with orchestrator through shared database
# This maintains app independence while accessing Hive-specific schema

# Configure logging using hive-logging following golden rule 9
from hive_logging import setup_logging
setup_logging(name='ai-planner', level="INFO", log_to_file=True, log_file_path="ai-planner.log")
logger = get_logger('ai-planner')

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

        # Initialize event bus for explicit agent communication
        try:
            self.event_bus = get_event_bus()
            logger.info("Event bus initialized for explicit agent communication")
        except Exception as e:
            logger.warning(f"Event bus initialization failed: {e} - continuing without events")
            self.event_bus = None

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

    def _publish_workflow_event(self, event_type: WorkflowEventType, task_id: str,
                               workflow_id: str = None, correlation_id: str = None,
                               **additional_payload) -> str:
        """Publish workflow events for explicit agent communication

        Args:
            event_type: Type of workflow event
            task_id: Associated task ID
            workflow_id: Workflow identifier (auto-generated if not provided)
            correlation_id: Correlation ID for workflow tracking
            **additional_payload: Additional event data

        Returns:
            Published event ID or empty string if publishing failed
        """
        if not self.event_bus:
            return ""

        try:
            if not workflow_id:
                workflow_id = f"plan_{task_id}"

            event = create_workflow_event(
                event_type=event_type,
                workflow_id=workflow_id,
                task_id=task_id,
                source_agent="ai-planner",
                **additional_payload
            )

            event_id = self.event_bus.publish(event, correlation_id=correlation_id)
            logger.debug(f"Published workflow event {event_type} for task {task_id}: {event_id}")
            return event_id

        except Exception as e:
            logger.warning(f"Failed to publish workflow event {event_type} for task {task_id}: {e}")
            return ""

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

                # Publish plan generation failure event
                self._publish_workflow_event(
                    WorkflowEventType.BLOCKED,
                    task['id'],
                    workflow_id=f"plan_{task['id']}",
                    correlation_id=task.get('correlation_id'),
                    failure_reason="Claude bridge returned empty response",
                    error_type="EmptyClaudeResponse"
                )

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

            # Publish plan generation success event
            self._publish_workflow_event(
                WorkflowEventType.PLAN_GENERATED,
                task['id'],
                workflow_id=f"plan_{task['id']}",
                correlation_id=task.get('correlation_id'),
                plan_name=enhanced_plan.get('plan_name'),
                subtask_count=len(enhanced_plan.get('sub_tasks', [])),
                estimated_duration=enhanced_plan.get('metrics', {}).get('total_estimated_duration', 0),
                confidence_score=enhanced_plan.get('metadata', {}).get('claude_confidence', 0.0)
            )

            return enhanced_plan

        except Exception as e:
            error = PlanGenerationError(
                message="Failed to generate execution plan",
                task_id=task['id'],
                task_description=task['task_description'],
                original_error=e
            )
            self.error_reporter.report_error(error)

            # Publish plan generation failure event
            self._publish_workflow_event(
                WorkflowEventType.BLOCKED,
                task['id'],
                workflow_id=f"plan_{task['id']}",
                correlation_id=task.get('correlation_id'),
                failure_reason=str(e),
                error_type=type(e).__name__
            )

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

            # Publish planning started event
            self._publish_workflow_event(
                WorkflowEventType.PHASE_STARTED,
                task['id'],
                workflow_id=f"plan_{task['id']}",
                correlation_id=task.get('correlation_id'),
                phase="planning",
                task_description=task['task_description'][:100]
            )

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

            # Publish planning completion event
            self._publish_workflow_event(
                WorkflowEventType.PHASE_COMPLETED,
                task['id'],
                workflow_id=f"plan_{task['id']}",
                correlation_id=task.get('correlation_id'),
                phase="planning",
                plan_id=plan['plan_id'],
                plan_name=plan.get('plan_name', 'Unknown Plan')
            )

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

            # Publish planning failure event
            self._publish_workflow_event(
                WorkflowEventType.BLOCKED,
                task['id'],
                workflow_id=f"plan_{task['id']}",
                correlation_id=task.get('correlation_id'),
                phase="planning",
                failure_reason=str(e),
                error_type=type(e).__name__
            )

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

    # ================================================================================
    # ASYNC OPERATIONS - Phase 4.1 Implementation
    # ================================================================================

    if ASYNC_AVAILABLE and ASYNC_EVENTS_AVAILABLE:
        async def _publish_workflow_event_async(self, event_type: WorkflowEventType, task_id: str,
                                                workflow_id: str = None, correlation_id: str = None,
                                                **additional_payload) -> str:
            """Async version of workflow event publishing."""
            if not self.event_bus:
                return ""

            try:
                if not workflow_id:
                    workflow_id = f"plan_{task_id}"

                event = create_workflow_event(
                    event_type=event_type,
                    workflow_id=workflow_id,
                    task_id=task_id,
                    source_agent="ai-planner",
                    **additional_payload
                )

                event_id = await publish_event_async(event, correlation_id=correlation_id)
                logger.debug(f"Published async workflow event {event_type} for task {task_id}: {event_id}")
                return event_id

            except Exception as e:
                logger.warning(f"Failed to publish async workflow event {event_type} for task {task_id}: {e}")
                return ""

        async def get_next_task_async(self) -> Optional[Dict[str, Any]]:
            """
            Async version of get_next_task for non-blocking database operations.

            Returns:
                Dict containing task information or None if no tasks available
            """
            try:
                async with get_async_connection() as conn:
                    cursor = await conn.execute("""
                        SELECT id, task_description, priority, requestor, context_data,
                               complexity_estimate, created_at
                        FROM planning_queue
                        WHERE status = 'pending'
                        ORDER BY priority DESC, created_at ASC
                        LIMIT 1
                    """)

                    result = await cursor.fetchone()
                    if result:
                        # Convert row to dictionary
                        columns = ['id', 'task_description', 'priority', 'requestor',
                                  'context_data', 'complexity_estimate', 'created_at']
                        task = dict(zip(columns, result))

                        # Parse JSON context_data if present
                        if task['context_data']:
                            try:
                                task['context_data'] = json.loads(task['context_data'])
                            except json.JSONDecodeError:
                                logger.warning(f"Invalid JSON in context_data for task {task['id']}")
                                task['context_data'] = {}
                        else:
                            task['context_data'] = {}

                        logger.debug(f"Retrieved async task: {task['id']} - {task['task_description'][:50]}...")
                        return task

                    return None

            except Exception as e:
                logger.error(f"Error retrieving async task from planning_queue: {e}")
                return None

        async def update_task_status_async(self, task_id: str, status: str,
                                          completion_data: Optional[Dict] = None) -> bool:
            """
            Async version of update_task_status.

            Args:
                task_id: Task identifier
                status: New status ('planned', 'failed', etc.)
                completion_data: Optional completion information

            Returns:
                True if updated successfully, False otherwise
            """
            try:
                async with get_async_connection() as conn:
                    if status == 'planned':
                        await conn.execute("""
                            UPDATE planning_queue
                            SET status = ?, completed_at = ?
                            WHERE id = ?
                        """, (status, datetime.now(timezone.utc).isoformat(), task_id))
                    else:
                        await conn.execute("""
                            UPDATE planning_queue
                            SET status = ?
                            WHERE id = ?
                        """, (status, task_id))

                    await conn.commit()
                    logger.info(f"Async task {task_id} status updated to: {status}")
                    return True

            except Exception as e:
                logger.error(f"Error updating async task status to {status}: {e}")
                return False

        async def process_task_async(self, task: Dict[str, Any]) -> bool:
            """
            Async version of process_task for non-blocking task processing.

            Args:
                task: Task to process

            Returns:
                True if processed successfully, False otherwise
            """
            try:
                logger.info(f"Processing async task: {task['id']} - {task['task_description'][:100]}...")

                # Publish planning started event asynchronously
                await self._publish_workflow_event_async(
                    WorkflowEventType.PHASE_STARTED,
                    task['id'],
                    workflow_id=f"plan_{task['id']}",
                    correlation_id=task.get('correlation_id'),
                    phase="planning",
                    task_description=task['task_description'][:100]
                )

                # Generate execution plan (this can remain sync as it's CPU-bound)
                plan = self.generate_execution_plan(task)
                if not plan:
                    logger.error(f"Failed to generate plan for async task: {task['id']}")
                    await self.update_task_status_async(task['id'], 'failed')
                    return False

                # Save execution plan (async version would need to be implemented)
                # For now, use sync version but update this in future enhancement
                if not self.save_execution_plan(plan):
                    logger.error(f"Failed to save plan for async task: {task['id']}")
                    await self.update_task_status_async(task['id'], 'failed')
                    return False

                # Mark task as planned asynchronously
                await self.update_task_status_async(task['id'], 'planned')

                # Publish planning completion event asynchronously
                await self._publish_workflow_event_async(
                    WorkflowEventType.PHASE_COMPLETED,
                    task['id'],
                    workflow_id=f"plan_{task['id']}",
                    correlation_id=task.get('correlation_id'),
                    phase="planning",
                    plan_id=plan['plan_id'],
                    plan_name=plan.get('plan_name', 'Unknown Plan')
                )

                logger.info(f"Successfully planned async task: {task['id']} with plan: {plan['plan_id']}")
                return True

            except Exception as e:
                logger.error(f"Unexpected error during async task processing: {e}")
                await self.update_task_status_async(task['id'], 'failed')

                # Publish planning failure event asynchronously
                await self._publish_workflow_event_async(
                    WorkflowEventType.BLOCKED,
                    task['id'],
                    workflow_id=f"plan_{task['id']}",
                    correlation_id=task.get('correlation_id'),
                    phase="planning",
                    failure_reason=str(e),
                    error_type=type(e).__name__
                )

                return False

        async def run_async(self):
            """Async version of main agent execution loop for 3-5x performance improvement."""
            logger.info("AI Planner Agent starting in async mode...")

            # Connect to database (use sync for initialization)
            if not self.connect_database():
                logger.error("Failed to establish database connection. Exiting.")
                return 1

            logger.info("AI Planner Agent is running in async mode. Monitoring planning_queue...")

            try:
                while self.running:
                    # Check for new tasks asynchronously
                    task = await self.get_next_task_async()

                    if task:
                        # Process the task asynchronously
                        success = await self.process_task_async(task)
                        if success:
                            logger.info(f"Async task {task['id']} processed successfully")
                        else:
                            logger.warning(f"Async task {task['id']} processing failed")
                    else:
                        # No tasks available, wait before next poll (non-blocking)
                        await asyncio.sleep(self.poll_interval)

            except KeyboardInterrupt:
                logger.info("Received keyboard interrupt, shutting down async mode...")
            except Exception as e:
                logger.error(f"Unexpected error in async processing loop: {e}")
            finally:
                # Cleanup
                if self.db_connection:
                    self.db_connection.close()
                    logger.info("Database connection closed")

                logger.info("AI Planner Agent async shutdown complete")
                return 0


# Mock event bus functionality (to be replaced with proper implementation)
class WorkflowEventType(Enum):
    """Types of workflow events"""
    PHASE_STARTED = "phase_started"
    PHASE_COMPLETED = "phase_completed"
    PLAN_GENERATED = "plan_generated"
    BLOCKED = "blocked"

def create_workflow_event(event_type: WorkflowEventType, workflow_id: str, task_id: str, source_agent: str, **kwargs) -> Dict[str, Any]:
    """Create a workflow event.

    Args:
        event_type: Type of workflow event
        workflow_id: Unique workflow identifier
        task_id: Task ID associated with the event
        source_agent: Agent creating the event
        **kwargs: Additional event data

    Returns:
        Workflow event dictionary
    """
    return {
        "event_type": event_type.value,
        "workflow_id": workflow_id,
        "task_id": task_id,
        "source_agent": source_agent,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **kwargs
    }

class MockEventBus:
    """Mock event bus for development"""
    def publish(self, event, correlation_id=None):
        # Mock implementation - just log the event
        logger.debug(f"Mock event published: {event['event_type']} for task {event.get('task_id', 'unknown')}")
        return f"mock_event_{int(time.time())}"

def get_event_bus() -> MockEventBus:
    """Get event bus instance.

    Returns:
        Mock event bus for development
    """
    return MockEventBus()

# Async event functions (if needed)
ASYNC_EVENTS_AVAILABLE = False

async def publish_event_async(event: Dict[str, Any], correlation_id: Optional[str] = None) -> str:
    """Mock async event publishing.

    Args:
        event: Event data to publish
        correlation_id: Optional correlation ID for event tracking

    Returns:
        Mock event ID
    """
    return f"mock_async_event_{int(time.time())}"


def main() -> int:
    """Entry point for AI Planner Agent

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    import argparse

    parser = argparse.ArgumentParser(description='AI Planner Agent - Intelligent Task Planning')
    parser.add_argument('--mock', action='store_true', help='Run in mock mode for testing')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    parser.add_argument('--async-mode', action='store_true', help='Run in async mode for better performance')
    args = parser.parse_args()

    if args.debug:
        get_logger().setLevel(logging.DEBUG)
        logger.debug("Debug logging enabled")

    try:
        agent = AIPlanner(mock_mode=args.mock)

        # Check if async mode is requested and available
        if args.async_mode:
            if ASYNC_AVAILABLE and ASYNC_EVENTS_AVAILABLE:
                logger.info("Starting AI Planner in async mode for enhanced performance")
                return asyncio.run(agent.run_async())
            else:
                logger.warning("Async mode requested but not available, falling back to sync mode")
                return agent.run()
        else:
            return agent.run()

    except Exception as e:
        logger.error(f"Failed to start AI Planner Agent: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())