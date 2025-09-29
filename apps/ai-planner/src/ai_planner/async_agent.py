#!/usr/bin/env python3
"""
AsyncAIPlanner - High-Performance Async AI Planning Agent for V4.2

Fully async AI planner agent with non-blocking operations, concurrent task processing,
and integration with the V4.0 async infrastructure.
"""

import asyncio
import json
import signal
import sys
import time
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

# Import recovery strategies
from ai_planner.core.errors import (
    ClaudeServiceError,
    DatabaseConnectionError,
    ExponentialBackoffStrategy,
    PlanGenerationError,
    PlannerError,
    PlanValidationError,
    TaskProcessingError,
    TaskQueueError,
    TaskValidationError,
    get_error_reporter,
    with_recovery,
)
from hive_logging import get_logger
from hive_orchestrator.core.bus import (
    TaskEventType,
    WorkflowEventType,
    create_task_event,
    create_workflow_event,
    get_async_event_bus,
    publish_event_async,
)

# V4.0 Async infrastructure imports
from hive_orchestrator.core.db import AsyncDatabaseOperations, get_async_db_operations

logger = get_logger(__name__)


class PlanningPriority(Enum):
    """Task planning priority levels"""

    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


class AsyncClaudeService:
    """
    Async version of Claude service for non-blocking plan generation
    """

    def __init__(self, config=None, rate_config=None) -> None:
        self.mock_mode = getattr(config, "mock_mode", True)
        self.max_calls_per_minute = getattr(rate_config, "max_calls_per_minute", 20)
        self.max_calls_per_hour = getattr(rate_config, "max_calls_per_hour", 500)
        self._call_timestamps = []
        self._semaphore = asyncio.Semaphore(5)  # Limit concurrent calls

    async def generate_execution_plan_async(
        self,
        task_description: str,
        context_data: Dict[str, Any],
        priority: int,
        requestor: str,
        use_cache: bool = True,
    ) -> Dict[str, Any]:
        """
        Generate an execution plan asynchronously

        Args:
            task_description: Description of the task to plan
            context_data: Additional context and metadata for planning
            priority: Task priority (0-100)
            requestor: ID of the requesting entity
            use_cache: Whether to use cached plans if available

        Returns:
            Dict containing plan_id, plan_name, sub_tasks, and metrics
        """
        async with self._semaphore:
            # Rate limiting check
            await self._check_rate_limits_async()

            # Record call timestamp
            now = time.time()
            self._call_timestamps.append(now)

            if self.mock_mode:
                # Simulate planning time
                await asyncio.sleep(0.5 + (priority / 100))

                # Generate realistic mock plan
                plan_id = f"plan_{uuid.uuid4().hex[:8]}"
                complexity = self._determine_complexity(task_description)

                sub_tasks = await self._generate_mock_subtasks_async(task_description, complexity, priority)

                return {
                    "plan_id": plan_id,
                    "plan_name": f"Async Generated Plan: {task_description[:50]}",
                    "sub_tasks": sub_tasks,
                    "metrics": {
                        "total_estimated_duration": sum(task.get("estimated_duration", 30) for task in sub_tasks),
                        "complexity_breakdown": self._analyze_complexity(sub_tasks),
                        "confidence_score": 0.85 + (priority / 200),
                        "generation_time": 0.5 + (priority / 100),
                        "async_generated": True,
                    },
                    "context": {
                        "requestor": requestor,
                        "priority": priority,
                        "cache_used": use_cache,
                        "generation_timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                }
            else:
                # TODO: Implement actual Claude API integration
                raise NotImplementedError("Real Claude integration not yet implemented")

    async def _check_rate_limits_async(self) -> None:
        """Check and enforce rate limits"""
        now = time.time()

        # Clean old timestamps (older than 1 hour)
        self._call_timestamps = [ts for ts in self._call_timestamps if now - ts < 3600]

        # Check minute limit
        minute_calls = len([ts for ts in self._call_timestamps if now - ts < 60])
        if minute_calls >= self.max_calls_per_minute:
            wait_time = 60 - (now - min(self._call_timestamps[-minute_calls:]))
            logger.warning(f"Rate limit reached, waiting {wait_time:.1f}s")
            await asyncio.sleep(wait_time)

        # Check hour limit
        if len(self._call_timestamps) >= self.max_calls_per_hour:
            wait_time = 3600 - (now - self._call_timestamps[0])
            logger.warning(f"Hourly rate limit reached, waiting {wait_time:.1f}s")
            await asyncio.sleep(wait_time)

    def _determine_complexity(self, task_description: str) -> str:
        """Determine task complexity based on description"""
        desc_lower = task_description.lower()

        if any(word in desc_lower for word in ["simple", "basic", "quick", "small"]):
            return "low"
        elif any(word in desc_lower for word in ["complex", "advanced", "large", "system"]):
            return "high"
        else:
            return "medium"

    async def _generate_mock_subtasks_async(
        self, task_description: str, complexity: str, priority: int
    ) -> List[Dict[str, Any]]:
        """Generate realistic mock subtasks"""
        base_tasks = [
            {
                "title": "Analyze requirements and context",
                "description": f"Analyze requirements for: {task_description}",
                "workflow_phase": "analysis",
                "required_skills": ["analysis", "planning"],
                "estimated_duration": 15 if complexity == "low" else 30,
            },
            {
                "title": "Design implementation approach",
                "description": "Design the technical approach and architecture",
                "workflow_phase": "design",
                "required_skills": ["architecture", "design"],
                "estimated_duration": 20 if complexity == "low" else 45,
            },
            {
                "title": "Implement core functionality",
                "description": "Implement the main functionality",
                "workflow_phase": "implementation",
                "required_skills": ["development", "coding"],
                "estimated_duration": 30 if complexity == "low" else 90,
            },
        ]

        if complexity == "high":
            base_tasks.extend(
                [
                    {
                        "title": "Create comprehensive tests",
                        "description": "Create unit and integration tests",
                        "workflow_phase": "testing",
                        "required_skills": ["testing", "quality_assurance"],
                        "estimated_duration": 45,
                    },
                    {
                        "title": "Performance optimization",
                        "description": "Optimize performance and scalability",
                        "workflow_phase": "optimization",
                        "required_skills": ["performance", "optimization"],
                        "estimated_duration": 30,
                    },
                ]
            )

        # Add IDs and metadata
        for i, task in enumerate(base_tasks):
            task.update(
                {
                    "id": f"subtask_{uuid.uuid4().hex[:8]}",
                    "assignee": "auto",
                    "complexity": complexity,
                    "deliverables": [f"{task['workflow_phase']}_output"],
                    "dependencies": [base_tasks[i - 1]["id"]] if i > 0 else [],
                    "priority": max(1, priority - 10),  # Slightly lower than parent
                }
            )

        return base_tasks

    def _analyze_complexity(self, sub_tasks: List[Dict[str, Any]]) -> Dict[str, int]:
        """Analyze complexity breakdown of subtasks"""
        breakdown = {"low": 0, "medium": 0, "high": 0}
        for task in sub_tasks:
            complexity = task.get("complexity", "medium")
            breakdown[complexity] = breakdown.get(complexity, 0) + 1
        return breakdown


class AsyncAIPlanner:
    """
    High-performance async AI planner agent with V4.2 optimizations

    Features:
    - Non-blocking task processing
    - Concurrent plan generation
    - Async database operations
    - Event-driven coordination
    - Performance metrics tracking
    """

    def __init__(self, mock_mode: bool = False) -> None:
        self.agent_id = f"async-ai-planner-{uuid.uuid4().hex[:8]}"
        self.running = False
        self.mock_mode = mock_mode

        # Async components
        self.db_ops: Optional[AsyncDatabaseOperations] = None
        self.event_bus = None
        self.claude_service = None

        # Configuration
        self.poll_interval = 5.0  # seconds
        self.max_planning_time = 300  # 5 minutes max per task
        self.max_concurrent_plans = 3  # Max concurrent planning operations

        # State tracking
        self.active_plans: Set[str] = set()
        self.planning_semaphore = asyncio.Semaphore(self.max_concurrent_plans)

        # Performance metrics
        self.metrics = {
            "plans_generated": 0,
            "total_planning_time": 0,
            "average_planning_time": 0,
            "concurrent_peak": 0,
            "errors": 0,
            "cache_hits": 0,
        }

        # Error handling
        self.error_reporter = get_error_reporter(component_name="async-ai-planner")
        self.retry_strategy = ExponentialBackoffStrategy(max_retries=3, base_delay=1.0, max_delay=10.0)

        # Graceful shutdown
        self.shutdown_event = asyncio.Event()
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    async def initialize_async(self) -> None:
        """Initialize all async components"""
        logger.info(f"Initializing AsyncAIPlanner {self.agent_id}")

        # Initialize async database operations
        self.db_ops = await get_async_db_operations()
        logger.info("Async database operations initialized")

        # Initialize async event bus
        self.event_bus = await get_async_event_bus()
        logger.info("Async event bus initialized")

        # Initialize async Claude service
        from ai_planner.core.config import get_claude_config, get_rate_limit_config

        config = get_claude_config(mock_mode=self.mock_mode)
        rate_config = get_rate_limit_config()
        self.claude_service = AsyncClaudeService(config=config, rate_config=rate_config)
        logger.info("Async Claude service initialized")

        # Register agent in database
        await self._register_agent_async()

        # Start performance monitoring
        asyncio.create_task(self._monitor_performance_async())

    async def _register_agent_async(self) -> None:
        """Register agent in the database"""
        try:
            await self.db_ops.register_worker_async(
                worker_id=self.agent_id,
                role="ai_planner",
                capabilities=[
                    "async_planning",
                    "task_decomposition",
                    "workflow_generation",
                    "intelligent_analysis",
                ],
                metadata={
                    "version": "4.2.0",
                    "type": "AsyncAIPlanner",
                    "max_concurrent": self.max_concurrent_plans,
                    "performance": "3-5x",
                },
            )
            logger.info("AsyncAIPlanner registered as worker")
        except Exception as e:
            logger.warning(f"Failed to register agent: {e}")

    def _signal_handler(self, signum, frame) -> None:
        """Handle shutdown signals gracefully"""
        logger.info(f"Received signal {signum}, initiating graceful shutdown")
        self.shutdown_event.set()

    async def get_next_planning_task_async(self) -> Optional[Dict[str, Any]]:
        """Get the next task requiring planning"""
        try:
            # Get tasks needing planning
            planning_tasks = await self.db_ops.get_tasks_concurrent_async(status="planning_pending", limit=10)

            if not planning_tasks:
                return None

            # Sort by priority and creation time
            planning_tasks.sort(key=lambda t: (-t.get("priority", 1), t.get("created_at", "")))

            # Return highest priority task not currently being planned
            for task in planning_tasks:
                if task["id"] not in self.active_plans:
                    return task

            return None

        except Exception as e:
            logger.error(f"Error getting next planning task: {e}")
            return None

    async def generate_plan_async(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Generate execution plan for a task asynchronously"""
        task_id = task["id"]

        async with self.planning_semaphore:
            try:
                # Track active planning
                self.active_plans.add(task_id)
                start_time = time.time()

                # Update metrics
                self.metrics["concurrent_peak"] = max(self.metrics["concurrent_peak"], len(self.active_plans))

                logger.info(f"Starting async plan generation for task {task_id}")

                # Mark task as in planning
                await self.db_ops.update_task_status_async(
                    task_id,
                    "planning_in_progress",
                    {"planner_id": self.agent_id, "planning_start": datetime.now(timezone.utc).isoformat()},
                )

                # Generate plan using async Claude service
                context_data = {
                    "task_type": task.get("task_type", "unknown"),
                    "complexity": task.get("complexity", "medium"),
                    "existing_context": task.get("context", {}),
                    "dependencies": task.get("depends_on", []),
                }

                plan_result = await asyncio.wait_for(
                    self.claude_service.generate_execution_plan_async(
                        task_description=task.get("description", ""),
                        context_data=context_data,
                        priority=task.get("priority", 50),
                        requestor=task.get("created_by", "system"),
                        use_cache=True,
                    ),
                    timeout=self.max_planning_time,
                )

                # Create subtasks in database
                subtask_ids = []
                for subtask in plan_result["sub_tasks"]:
                    subtask_id = await self.db_ops.create_task_async(
                        title=subtask["title"],
                        description=subtask["description"],
                        task_type="planned_subtask",
                        priority=subtask.get("priority", task.get("priority", 50)),
                        metadata={
                            "parent_task_id": task_id,
                            "plan_id": plan_result["plan_id"],
                            "workflow_phase": subtask.get("workflow_phase"),
                            "required_skills": subtask.get("required_skills", []),
                            "estimated_duration": subtask.get("estimated_duration"),
                            "deliverables": subtask.get("deliverables", []),
                        },
                        depends_on=subtask.get("dependencies", []),
                        assignee=subtask.get("assignee", "auto"),
                    )
                    subtask_ids.append(subtask_id)

                # Update parent task with plan
                planning_time = time.time() - start_time
                await self.db_ops.update_task_status_async(
                    task_id,
                    "planned",
                    {
                        "plan_id": plan_result["plan_id"],
                        "plan_name": plan_result["plan_name"],
                        "subtask_ids": subtask_ids,
                        "planning_time": planning_time,
                        "planning_metrics": plan_result["metrics"],
                        "planned_at": datetime.now(timezone.utc).isoformat(),
                        "planner_id": self.agent_id,
                    },
                )

                # Update metrics
                self.metrics["plans_generated"] += 1
                self.metrics["total_planning_time"] += planning_time
                self.metrics["average_planning_time"] = (
                    self.metrics["total_planning_time"] / self.metrics["plans_generated"]
                )

                # Publish planning completion event
                await self.event_bus.publish_async(
                    event_type="workflow.plan_generated",
                    task_id=task_id,
                    priority=2,
                    payload={
                        "plan_id": plan_result["plan_id"],
                        "plan_name": plan_result["plan_name"],
                        "subtask_count": len(subtask_ids),
                        "planning_time": planning_time,
                        "planner_id": self.agent_id,
                    },
                )

                logger.info(
                    f"# OK Plan generated for {task_id}: " f"{len(subtask_ids)} subtasks in {planning_time:.1f}s"
                )

                return {
                    "success": True,
                    "plan_id": plan_result["plan_id"],
                    "subtask_count": len(subtask_ids),
                    "planning_time": planning_time,
                }

            except asyncio.TimeoutError:
                logger.error(f"Planning timeout for task {task_id}")
                await self.db_ops.update_task_status_async(
                    task_id, "planning_failed", {"error": "Planning timeout", "planner_id": self.agent_id}
                )
                self.metrics["errors"] += 1
                return {"success": False, "error": "timeout"}

            except Exception as e:
                logger.error(f"Planning failed for task {task_id}: {e}")
                await self.db_ops.update_task_status_async(
                    task_id, "planning_failed", {"error": str(e), "planner_id": self.agent_id}
                )
                self.metrics["errors"] += 1
                return {"success": False, "error": str(e)}

            finally:
                # Remove from active planning
                self.active_plans.discard(task_id)

    async def process_planning_queue_async(self) -> None:
        """Process the planning queue with concurrent execution"""
        planning_tasks = []

        # Get available slots
        available_slots = self.max_concurrent_plans - len(self.active_plans)

        # Start planning for available tasks
        for _ in range(available_slots):
            task = await self.get_next_planning_task_async()
            if task:
                planning_task = asyncio.create_task(self.generate_plan_async(task))
                planning_tasks.append(planning_task)
            else:
                break

        # Wait for all planning tasks to complete
        if planning_tasks:
            results = await asyncio.gather(*planning_tasks, return_exceptions=True)

            successful_plans = len([r for r in results if isinstance(r, dict) and r.get("success")])

            if successful_plans > 0:
                logger.info(f"Completed {successful_plans} plans concurrently")

    async def _monitor_performance_async(self) -> None:
        """Background performance monitoring"""
        while not self.shutdown_event.is_set():
            await asyncio.sleep(60)  # Every minute

            logger.info(
                f"[METRICS] Plans: {self.metrics['plans_generated']} | "
                f"Avg Time: {self.metrics['average_planning_time']:.1f}s | "
                f"Active: {len(self.active_plans)} | "
                f"Peak: {self.metrics['concurrent_peak']} | "
                f"Errors: {self.metrics['errors']}"
            )

    async def run_forever_async(self) -> None:
        """Main async planning loop"""
        logger.info("AsyncAIPlanner starting main loop")

        # Initialize components
        await self.initialize_async()

        self.running = True

        try:
            while self.running and not self.shutdown_event.is_set():
                # Process planning queue
                await self.process_planning_queue_async()

                # Check for shutdown
                if self.shutdown_event.is_set():
                    break

                # Non-blocking sleep
                try:
                    await asyncio.wait_for(self.shutdown_event.wait(), timeout=self.poll_interval)
                    break  # Shutdown signal received
                except asyncio.TimeoutError:
                    pass  # Normal timeout, continue loop

        except Exception as e:
            logger.error(f"Fatal error in main loop: {e}")
            self.metrics["errors"] += 1

        finally:
            await self._shutdown_async()

    async def _shutdown_async(self) -> None:
        """Graceful async shutdown"""
        logger.info("AsyncAIPlanner shutting down...")

        self.running = False

        # Wait for active planning tasks to complete
        if self.active_plans:
            logger.info(f"Waiting for {len(self.active_plans)} active plans to complete...")
            while self.active_plans and len(self.active_plans) > 0:
                await asyncio.sleep(1)

        # Close async resources
        if self.db_ops:
            await self.db_ops.close()

        # Final metrics
        logger.info(
            f"Shutdown complete. Final metrics: "
            f"Plans: {self.metrics['plans_generated']}, "
            f"Avg Time: {self.metrics['average_planning_time']:.1f}s, "
            f"Errors: {self.metrics['errors']}"
        )


async def main_async() -> None:
    """Main entry point for AsyncAIPlanner"""
    import argparse

    parser = argparse.ArgumentParser(description="AsyncAIPlanner - V4.2 High-Performance Planning Agent")
    parser.add_argument("--mock", action="store_true", help="Run in mock mode")
    parser.add_argument("--test", action="store_true", help="Run in test mode")

    args = parser.parse_args()

    # Configure logging
    from hive_logging import setup_logging

    setup_logging(name="async-ai-planner", log_to_file=True, log_file_path="logs/async-ai-planner.log")

    # Create and run planner
    planner = AsyncAIPlanner(mock_mode=args.mock)

    try:
        await planner.run_forever_async()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main_async())
