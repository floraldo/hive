#!/usr/bin/env python3
"""
AsyncAIReviewer - High-Performance Async AI Review Agent for V4.2

Fully async AI reviewer agent with non-blocking operations, concurrent review processing,
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

from hive_logging import get_logger

# V4.0 Async infrastructure imports
from hive_orchestrator.core.db import (
    AsyncDatabaseOperations,
    get_async_db_operations,
)
from hive_orchestrator.core.bus import (
    get_async_event_bus,
    publish_event_async,
    TaskEventType,
    create_task_event,
)

# Import existing review components
from ai_reviewer.reviewer import ReviewDecision, ReviewEngine
from ai_reviewer.database_adapter import DatabaseAdapter

logger = get_logger(__name__)


class ReviewPriority(Enum):
    """Review priority levels"""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


class AsyncReviewEngine:
    """
    Async version of review engine for non-blocking code analysis
    """

    def __init__(self, config=None):
        self.config = config or {}
        self.mock_mode = self.config.get("mock_mode", True)
        self._review_semaphore = asyncio.Semaphore(3)  # Limit concurrent reviews

    async def review_task_async(
        self,
        task: Dict[str, Any],
        run_data: Dict[str, Any],
        context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Perform async code review of a completed task

        Args:
            task: Task data from database
            run_data: Execution run data and results
            context: Additional context for review

        Returns:
            Dict containing review decision and detailed analysis
        """
        async with self._review_semaphore:
            task_id = task.get("id", "unknown")
            logger.info(f"Starting async review for task {task_id}")

            # Simulate review time based on complexity
            complexity = task.get("complexity", "medium")
            review_time = {"low": 0.5, "medium": 1.0, "high": 2.0}.get(complexity, 1.0)

            if self.mock_mode:
                await asyncio.sleep(review_time)
                return await self._generate_mock_review(task, run_data)
            else:
                # TODO: Implement actual Claude-based review
                return await self._perform_real_review(task, run_data, context)

    async def _generate_mock_review(
        self,
        task: Dict[str, Any],
        run_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate realistic mock review result"""
        task_id = task.get("id", "unknown")
        status = run_data.get("status", "unknown")
        files_created = run_data.get("files", {}).get("created", [])
        files_modified = run_data.get("files", {}).get("modified", [])

        # Determine review decision based on execution results
        if status == "success" and (files_created or files_modified):
            # High probability of approval for successful tasks with file changes
            decision = ReviewDecision.APPROVE if time.time() % 4 != 0 else ReviewDecision.REWORK
        elif status == "success":
            # Moderate probability for successful tasks without file changes
            decision = ReviewDecision.APPROVE if time.time() % 3 != 0 else ReviewDecision.REWORK
        else:
            # Failed tasks need rework
            decision = ReviewDecision.REWORK

        # Generate detailed review analysis
        analysis = {
            "code_quality": {
                "score": 85 if decision == ReviewDecision.APPROVE else 65,
                "issues": [] if decision == ReviewDecision.APPROVE else [
                    "Code structure could be improved",
                    "Missing error handling in some areas"
                ],
                "strengths": [
                    "Clear variable naming",
                    "Good separation of concerns"
                ] if decision == ReviewDecision.APPROVE else []
            },
            "test_coverage": {
                "score": 80 if decision == ReviewDecision.APPROVE else 45,
                "missing_tests": [] if decision == ReviewDecision.APPROVE else [
                    "Edge case testing",
                    "Error handling tests"
                ]
            },
            "security": {
                "score": 90,
                "vulnerabilities": [],
                "recommendations": ["Use parameterized queries", "Validate input data"]
            },
            "performance": {
                "score": 75,
                "bottlenecks": [],
                "optimizations": ["Consider caching", "Optimize database queries"]
            }
        }

        # Generate review summary
        if decision == ReviewDecision.APPROVE:
            summary = f"Task {task_id} meets quality standards and is approved for completion."
            feedback = "Good implementation with clean code structure. Minor optimizations suggested."
        else:
            summary = f"Task {task_id} requires rework to meet quality standards."
            feedback = "Implementation needs improvements in code quality and test coverage."

        return {
            "decision": decision,
            "confidence": 0.85 if decision == ReviewDecision.APPROVE else 0.75,
            "summary": summary,
            "feedback": feedback,
            "analysis": analysis,
            "review_time": time.time() - (time.time() - 1.0),  # Mock review time
            "files_reviewed": len(files_created) + len(files_modified),
            "reviewer_id": "async-ai-reviewer",
            "review_timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def _perform_real_review(
        self,
        task: Dict[str, Any],
        run_data: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Perform real Claude-based review (placeholder)"""
        # TODO: Implement actual Claude integration for code review
        raise NotImplementedError("Real Claude review integration not yet implemented")


class AsyncAIReviewer:
    """
    High-performance async AI reviewer agent with V4.2 optimizations

    Features:
    - Non-blocking review processing
    - Concurrent code analysis
    - Async database operations
    - Event-driven coordination
    - Performance metrics tracking
    """

    def __init__(self, mock_mode: bool = False):
        self.agent_id = f"async-ai-reviewer-{uuid.uuid4().hex[:8]}"
        self.running = False
        self.mock_mode = mock_mode

        # Async components
        self.db_ops: Optional[AsyncDatabaseOperations] = None
        self.event_bus = None
        self.review_engine = None

        # Configuration
        self.poll_interval = 10.0  # seconds
        self.max_review_time = 600  # 10 minutes max per review
        self.max_concurrent_reviews = 2  # Max concurrent review operations

        # State tracking
        self.active_reviews: Set[str] = set()
        self.review_semaphore = asyncio.Semaphore(self.max_concurrent_reviews)

        # Performance metrics
        self.metrics = {
            "reviews_completed": 0,
            "approved": 0,
            "rejected": 0,
            "rework_requested": 0,
            "total_review_time": 0,
            "average_review_time": 0,
            "concurrent_peak": 0,
            "errors": 0,
        }

        # Graceful shutdown
        self.shutdown_event = asyncio.Event()
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    async def initialize_async(self):
        """Initialize all async components"""
        logger.info(f"Initializing AsyncAIReviewer {self.agent_id}")

        # Initialize async database operations
        self.db_ops = await get_async_db_operations()
        logger.info("Async database operations initialized")

        # Initialize async event bus
        self.event_bus = await get_async_event_bus()
        logger.info("Async event bus initialized")

        # Initialize async review engine
        config = {"mock_mode": self.mock_mode}
        self.review_engine = AsyncReviewEngine(config=config)
        logger.info("Async review engine initialized")

        # Register agent in database
        await self._register_agent()

        # Start performance monitoring
        asyncio.create_task(self._monitor_performance())

    async def _register_agent(self):
        """Register agent in the database"""
        try:
            await self.db_ops.register_worker_async(
                worker_id=self.agent_id,
                role="ai_reviewer",
                capabilities=[
                    "async_review",
                    "code_analysis",
                    "quality_assurance",
                    "automated_feedback",
                ],
                metadata={
                    "version": "4.2.0",
                    "type": "AsyncAIReviewer",
                    "max_concurrent": self.max_concurrent_reviews,
                    "performance": "3-5x",
                }
            )
            logger.info("AsyncAIReviewer registered as worker")
        except Exception as e:
            logger.warning(f"Failed to register agent: {e}")

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        logger.info(f"Received signal {signum}, initiating graceful shutdown")
        self.shutdown_event.set()

    async def get_next_review_task_async(self) -> Optional[Dict[str, Any]]:
        """Get the next task requiring review"""
        try:
            # Get tasks needing review
            review_tasks = await self.db_ops.get_tasks_concurrent_async(
                status="review_pending",
                limit=10
            )

            if not review_tasks:
                return None

            # Sort by priority and creation time
            review_tasks.sort(
                key=lambda t: (
                    -t.get("priority", 1),
                    t.get("updated_at", "")
                )
            )

            # Return highest priority task not currently being reviewed
            for task in review_tasks:
                if task["id"] not in self.active_reviews:
                    return task

            return None

        except Exception as e:
            logger.error(f"Error getting next review task: {e}")
            return None

    async def perform_review_async(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Perform async review of a completed task"""
        task_id = task["id"]

        async with self.review_semaphore:
            try:
                # Track active review
                self.active_reviews.add(task_id)
                start_time = time.time()

                # Update metrics
                self.metrics["concurrent_peak"] = max(
                    self.metrics["concurrent_peak"],
                    len(self.active_reviews)
                )

                logger.info(f"Starting async review for task {task_id}")

                # Mark task as under review
                await self.db_ops.update_task_status_async(
                    task_id,
                    "review_in_progress",
                    {
                        "reviewer_id": self.agent_id,
                        "review_start": datetime.now(timezone.utc).isoformat()
                    }
                )

                # Get run data for review
                run_data = await self._get_task_run_data(task_id)
                if not run_data:
                    logger.warning(f"No run data found for task {task_id}")
                    run_data = {"status": "unknown", "files": {}}

                # Perform review with timeout
                review_result = await asyncio.wait_for(
                    self.review_engine.review_task_async(
                        task=task,
                        run_data=run_data,
                        context={"reviewer_id": self.agent_id}
                    ),
                    timeout=self.max_review_time
                )

                # Process review decision
                decision = review_result["decision"]
                review_time = time.time() - start_time

                # Update task based on review decision
                if decision == ReviewDecision.APPROVE:
                    new_status = "review_approved"
                    self.metrics["approved"] += 1
                elif decision == ReviewDecision.REJECT:
                    new_status = "review_rejected"
                    self.metrics["rejected"] += 1
                else:  # REWORK
                    new_status = "queued"  # Send back for rework
                    self.metrics["rework_requested"] += 1

                await self.db_ops.update_task_status_async(
                    task_id,
                    new_status,
                    {
                        "review_decision": decision.value,
                        "review_summary": review_result["summary"],
                        "review_feedback": review_result["feedback"],
                        "review_analysis": review_result["analysis"],
                        "review_time": review_time,
                        "reviewer_id": self.agent_id,
                        "reviewed_at": datetime.now(timezone.utc).isoformat(),
                    }
                )

                # Update metrics
                self.metrics["reviews_completed"] += 1
                self.metrics["total_review_time"] += review_time
                self.metrics["average_review_time"] = (
                    self.metrics["total_review_time"] / self.metrics["reviews_completed"]
                )

                # Publish review completion event
                await self.event_bus.publish_async(
                    event_type="task.review_completed",
                    task_id=task_id,
                    priority=2,
                    payload={
                        "review_decision": decision.value,
                        "review_summary": review_result["summary"],
                        "review_time": review_time,
                        "reviewer_id": self.agent_id,
                        "confidence": review_result.get("confidence", 0.8),
                    }
                )

                logger.info(
                    f"# OK Review completed for {task_id}: "
                    f"{decision.value} in {review_time:.1f}s"
                )

                return {
                    "success": True,
                    "decision": decision.value,
                    "review_time": review_time,
                    "confidence": review_result.get("confidence", 0.8),
                }

            except asyncio.TimeoutError:
                logger.error(f"Review timeout for task {task_id}")
                await self.db_ops.update_task_status_async(
                    task_id,
                    "review_failed",
                    {"error": "Review timeout", "reviewer_id": self.agent_id}
                )
                self.metrics["errors"] += 1
                return {"success": False, "error": "timeout"}

            except Exception as e:
                logger.error(f"Review failed for task {task_id}: {e}")
                await self.db_ops.update_task_status_async(
                    task_id,
                    "review_failed",
                    {"error": str(e), "reviewer_id": self.agent_id}
                )
                self.metrics["errors"] += 1
                return {"success": False, "error": str(e)}

            finally:
                # Remove from active reviews
                self.active_reviews.discard(task_id)

    async def _get_task_run_data(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get the most recent run data for a task"""
        try:
            # Get runs for this task
            runs = await self.db_ops.get_runs_for_task_async(task_id)
            if not runs:
                return None

            # Return the most recent run
            latest_run = max(runs, key=lambda r: r.get("created_at", ""))
            return latest_run.get("result_data", {})

        except Exception as e:
            logger.error(f"Error getting run data for task {task_id}: {e}")
            return None

    async def process_review_queue_async(self):
        """Process the review queue with concurrent execution"""
        review_tasks = []

        # Get available slots
        available_slots = self.max_concurrent_reviews - len(self.active_reviews)

        # Start reviews for available tasks
        for _ in range(available_slots):
            task = await self.get_next_review_task_async()
            if task:
                review_task = asyncio.create_task(
                    self.perform_review_async(task)
                )
                review_tasks.append(review_task)
            else:
                break

        # Wait for all review tasks to complete
        if review_tasks:
            results = await asyncio.gather(*review_tasks, return_exceptions=True)

            successful_reviews = len([
                r for r in results
                if isinstance(r, dict) and r.get("success")
            ])

            if successful_reviews > 0:
                logger.info(f"Completed {successful_reviews} reviews concurrently")

    async def _monitor_performance(self):
        """Background performance monitoring"""
        while not self.shutdown_event.is_set():
            await asyncio.sleep(60)  # Every minute

            logger.info(
                f"[METRICS] Reviews: {self.metrics['reviews_completed']} | "
                f"Approved: {self.metrics['approved']} | "
                f"Rework: {self.metrics['rework_requested']} | "
                f"Avg Time: {self.metrics['average_review_time']:.1f}s | "
                f"Active: {len(self.active_reviews)} | "
                f"Errors: {self.metrics['errors']}"
            )

    async def run_forever_async(self):
        """Main async review loop"""
        logger.info("AsyncAIReviewer starting main loop")

        # Initialize components
        await self.initialize_async()

        self.running = True

        try:
            while self.running and not self.shutdown_event.is_set():
                # Process review queue
                await self.process_review_queue_async()

                # Check for shutdown
                if self.shutdown_event.is_set():
                    break

                # Non-blocking sleep
                try:
                    await asyncio.wait_for(
                        self.shutdown_event.wait(),
                        timeout=self.poll_interval
                    )
                    break  # Shutdown signal received
                except asyncio.TimeoutError:
                    pass  # Normal timeout, continue loop

        except Exception as e:
            logger.error(f"Fatal error in main loop: {e}")
            self.metrics["errors"] += 1

        finally:
            await self._shutdown_async()

    async def _shutdown_async(self):
        """Graceful async shutdown"""
        logger.info("AsyncAIReviewer shutting down...")

        self.running = False

        # Wait for active reviews to complete
        if self.active_reviews:
            logger.info(f"Waiting for {len(self.active_reviews)} active reviews to complete...")
            while self.active_reviews and len(self.active_reviews) > 0:
                await asyncio.sleep(1)

        # Close async resources
        if self.db_ops:
            await self.db_ops.close()

        # Final metrics
        approval_rate = (
            self.metrics["approved"] / max(self.metrics["reviews_completed"], 1) * 100
        )
        logger.info(
            f"Shutdown complete. Final metrics: "
            f"Reviews: {self.metrics['reviews_completed']}, "
            f"Approval Rate: {approval_rate:.1f}%, "
            f"Avg Time: {self.metrics['average_review_time']:.1f}s, "
            f"Errors: {self.metrics['errors']}"
        )


async def main():
    """Main entry point for AsyncAIReviewer"""
    import argparse

    parser = argparse.ArgumentParser(description="AsyncAIReviewer - V4.2 High-Performance Review Agent")
    parser.add_argument("--mock", action="store_true", help="Run in mock mode")
    parser.add_argument("--test", action="store_true", help="Run in test mode")

    args = parser.parse_args()

    # Configure logging
    from hive_logging import setup_logging
    setup_logging(
        name="async-ai-reviewer",
        log_to_file=True,
        log_file_path="logs/async-ai-reviewer.log"
    )

    # Create and run reviewer
    reviewer = AsyncAIReviewer(mock_mode=args.mock)

    try:
        await reviewer.run_forever_async()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())