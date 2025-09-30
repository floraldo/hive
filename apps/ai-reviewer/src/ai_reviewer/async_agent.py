#!/usr/bin/env python3
"""
AsyncAIReviewer - High-Performance Async AI Review Agent for V4.2

Fully async AI reviewer agent with non-blocking operations, concurrent review processing
and integration with the V4.0 async infrastructure.
"""

from __future__ import annotations

import asyncio
import json
import signal
import sys
import time
import uuid
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

from hive_orchestrator.core.bus import get_async_event_bus

# V4.0 Async infrastructure imports
from hive_orchestrator.core.db import AsyncDatabaseOperations, get_async_db_operations

# Import existing review components
from ai_reviewer.reviewer import ReviewDecision
from hive_logging import get_logger

logger = get_logger(__name__)


class ReviewPriority(Enum):
    """Review priority levels"""

    LOW = (1,)
    MEDIUM = (2,)
    HIGH = (3,)
    CRITICAL = 4


class AsyncReviewEngine:
    """
    Async version of review engine for non-blocking code analysis
    """

    def __init__(self, config) -> None:
        self.config = config or {}
        self.mock_mode = self.config.get("mock_mode", True)
        self._review_semaphore = asyncio.Semaphore(3)  # Limit concurrent reviews

    async def review_task_async(
        self,
        task: dict[str, Any],
        run_data: dict[str, Any],
        context: dict[str, Any] = None,
    ) -> dict[str, Any]:
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
                return await self._generate_mock_review_async(task, run_data)
            else:
                # TODO: Implement actual Claude-based review
                return await self._perform_real_review_async(task, run_data, context)

    async def _generate_mock_review_async(self, task: dict[str, Any], run_data: dict[str, Any]) -> dict[str, Any]:
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
                "issues": (
                    []
                    if decision == ReviewDecision.APPROVE
                    else ["Code structure could be improved", "Missing error handling in some areas"]
                ),
                "strengths": (
                    ["Clear variable naming", "Good separation of concerns"]
                    if decision == ReviewDecision.APPROVE
                    else []
                ),
            },
            "test_coverage": {
                "score": 80 if decision == ReviewDecision.APPROVE else 45,
                "missing_tests": (
                    [] if decision == ReviewDecision.APPROVE else ["Edge case testing", "Error handling tests"]
                ),
            },
            "security": {
                "score": 90,
                "vulnerabilities": [],
                "recommendations": ["Use parameterized queries", "Validate input data"],
            },
            "performance": {
                "score": 75,
                "bottlenecks": [],
                "optimizations": ["Consider caching", "Optimize database queries"],
            },
        }

        # Generate review summary
        if decision == ReviewDecision.APPROVE:
            summary = (f"Task {task_id} meets quality standards and is approved for completion.",)
            feedback = "Good implementation with clean code structure. Minor optimizations suggested."
        else:
            summary = (f"Task {task_id} requires rework to meet quality standards.",)
            feedback = "Implementation needs improvements in code quality and test coverage."

        return {
            "decision": decision,
            "confidence": 0.85 if decision == ReviewDecision.APPROVE else 0.75,
            "summary": summary,
            "feedback": feedback,
            "analysis": analysis,
            "review_time": time.time() - (time.time() - 1.0),  # Mock review time,
            "files_reviewed": len(files_created) + len(files_modified),
            "reviewer_id": "async-ai-reviewer",
            "review_timestamp": datetime.now(UTC).isoformat(),
        }

    async def _perform_real_review_async(
        self,
        task: dict[str, Any],
        run_data: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Perform real Claude-based review using async subprocess"""

        task_id = task.get("id", "unknown")
        task_description = task.get("instruction", task.get("description", "No description"))

        logger.info(f"Performing real Claude review for task {task_id}")

        try:
            # Get code files from run data
            code_files = await self._extract_code_files_async(task, run_data)

            # Prepare review context
            test_results = run_data.get("test_results")
            objective_analysis = run_data.get("analysis")
            transcript = run_data.get("transcript")

            # Use async version of Claude bridge
            review_result = await self._call_claude_async(
                task_id=task_id,
                task_description=task_description,
                code_files=code_files,
                test_results=test_results,
                objective_analysis=objective_analysis,
                transcript=transcript,
            )

            # Convert to expected format
            return self._convert_claude_response_to_review_format(review_result)

        except Exception as e:
            logger.error(f"Claude review failed for task {task_id}: {e}")
            # Fallback to escalation
            return {
                "decision": "escalate",
                "confidence": 0.0,
                "summary": f"Review failed: {str(e)}",
                "feedback": "Manual review required due to Claude integration error",
                "analysis": {
                    "code_quality": {"score": 0, "issues": [str(e)]},
                    "test_coverage": {"score": 0, "missing_tests": []},
                    "security": {"score": 0, "vulnerabilities": [], "recommendations": []},
                    "performance": {"score": 0, "bottlenecks": [], "optimizations": []},
                },
                "review_time": 0,
                "files_reviewed": 0,
                "reviewer_id": "async-ai-reviewer-claude",
                "review_timestamp": datetime.now(UTC).isoformat(),
            }

    async def _extract_code_files_async(self, task: dict[str, Any], run_data: dict[str, Any]) -> dict[str, str]:
        """Extract code files from task and run data"""
        code_files = {}

        # Get files from run data
        files_data = run_data.get("files", {})
        created_files = files_data.get("created", [])
        modified_files = files_data.get("modified", [])

        # Combine all files
        all_files = list(set(created_files + modified_files))

        # Read file contents (limit to prevent huge prompts)
        for file_path in all_files[:10]:  # Limit to 10 files max
            try:
                if Path(file_path).exists():
                    with open(file_path, encoding="utf-8") as f:
                        content = f.read()
                        # Limit file content size
                        if len(content) > 5000:
                            content = content[:5000] + "\n... (truncated)"
                        code_files[file_path] = content
            except Exception as e:
                logger.warning(f"Could not read file {file_path}: {e}")
                code_files[file_path] = f"# Error reading file: {e}"

        return code_files

    async def _call_claude_async(
        self,
        task_id: str,
        task_description: str,
        code_files: dict[str, str],
        test_results: dict[str, Any] | None = None,
        objective_analysis: dict[str, Any] | None = None,
        transcript: str | None = None,
    ) -> dict[str, Any]:
        """Call Claude CLI asynchronously for code review"""

        # Find Claude CLI
        claude_cmd = await self._find_claude_cmd_async()
        if not claude_cmd:
            raise RuntimeError("Claude CLI not found")

        # Create prompt
        prompt = self._create_claude_prompt(task_description, code_files, test_results, objective_analysis, transcript)

        # Execute Claude CLI asynchronously with timeout
        try:
            process = await asyncio.create_subprocess_exec(
                claude_cmd,
                "--print",
                "--dangerously-skip-permissions",
                prompt,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                stdin=asyncio.subprocess.DEVNULL,
            )

            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=45)

            if process.returncode != 0:
                error_msg = stderr.decode("utf-8") if stderr else "Unknown error"
                raise RuntimeError(f"Claude CLI failed with code {process.returncode}: {error_msg}")

            claude_output = stdout.decode("utf-8").strip()

            # Parse and validate response
            return self._parse_claude_response(claude_output)

        except TimeoutError:
            logger.error("Claude CLI timed out")
            raise RuntimeError("Claude CLI timeout after 45 seconds")

    async def _find_claude_cmd_async(self) -> str | None:
        """Find Claude CLI command asynchronously"""
        # Check common locations first (fast path)
        possible_paths = [
            Path.home() / ".npm-global" / "claude.cmd",
            Path.home() / ".npm-global" / "claude",
            Path("claude.cmd"),
            Path("claude"),
        ]

        for path in possible_paths:
            if path.exists():
                return str(path)

        # Check system PATH asynchronously
        try:
            process = await asyncio.create_subprocess_exec(
                "where" if sys.platform == "win32" else "which",
                "claude",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                claude_path = stdout.decode("utf-8").strip().split("\n")[0]
                if claude_path:
                    return claude_path
        except Exception as e:
            logger.debug(f"Error checking PATH for claude: {e}")

        return None

    def _create_claude_prompt(
        self,
        task_description: str,
        code_files: dict[str, str],
        test_results: dict[str, Any] | None,
        objective_analysis: dict[str, Any] | None,
        transcript: str | None,
    ) -> str:
        """Create comprehensive prompt for Claude review"""

        # Prepare code context,
        code_context = ("",)
        for filename, content in code_files.items():
            code_context += f"\n=== {filename} ===\n{content}\n"

        # Prepare additional context,
        test_context = ("",)
        if test_results:
            test_context = f"\nTest Results: {json.dumps(test_results, indent=2)[:500]}"

        objective_context = ("",)
        if objective_analysis and not objective_analysis.get("error"):
            metrics = objective_analysis.get("metrics", {})
            objective_context = (f"\nObjective Metrics: {json.dumps(metrics, indent=2)}",)

        prompt = f"""You are an automated code review agent. Your response MUST be valid JSON and nothing else.

Task: {task_description}

Code Files:
{code_context}
{test_context}
{objective_context}

CRITICAL: Respond with ONLY a JSON object matching this exact structure:
{{
  "decision": "approve" or "reject" or "rework" or "escalate",
  "summary": "One sentence summary of your review",
  "issues": ["List of specific issues found", "Or empty list if none"],
  "suggestions": ["List of improvement suggestions", "Or empty list if none"],
  "quality_score": 75,
  "metrics": {{
    "code_quality": 80,
    "security": 85,
    "testing": 70,
    "architecture": 75,
    "documentation": 60,
  }},
  "confidence": 0.8,
}}

Decision guidelines:
- approve: score >= 80, no critical issues,
- rework: score 50-79, minor issues,
- reject: score < 50, major issues,
- escalate: complex cases needing human review

Respond with ONLY the JSON object, no other text."""

        return prompt

    def _parse_claude_response(self, output: str) -> dict[str, Any]:
        """Parse Claude response and extract JSON"""
        import re

        # Strategy 1: Try pure JSON
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            pass

        # Strategy 2: Extract from code blocks
        code_block_patterns = [r"```json\s*(.*?)\s*```", r"```\s*(.*?)\s*```", r"`(.*?)`"]

        for pattern in code_block_patterns:
            matches = re.findall(pattern, output, re.DOTALL)
            for match in matches:
                try:
                    return json.loads(match)
                except json.JSONDecodeError:
                    continue

        # Strategy 3: Find JSON object
        json_pattern = r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}"
        matches = re.findall(json_pattern, output, re.DOTALL)

        for match in matches:
            try:
                cleaned = match.replace("\n", " ").replace("\\n", " ")
                return json.loads(cleaned)
            except json.JSONDecodeError:
                continue

        # Fallback: create minimal response
        logger.warning("Could not parse Claude response, using fallback")
        return {
            "decision": "escalate",
            "summary": "Failed to parse review response",
            "issues": ["Invalid response format"],
            "suggestions": ["Manual review required"],
            "quality_score": 0,
            "metrics": {"code_quality": 0, "security": 0, "testing": 0, "architecture": 0, "documentation": 0},
            "confidence": 0.0,
        }

    def _convert_claude_response_to_review_format(self, claude_response: dict[str, Any]) -> dict[str, Any]:
        """Convert Claude response to expected review format"""
        from ai_reviewer.reviewer import ReviewDecision

        # Map decision strings to ReviewDecision enum
        decision_map = {
            "approve": ReviewDecision.APPROVE,
            "reject": ReviewDecision.REJECT,
            "rework": ReviewDecision.REWORK,
            "escalate": ReviewDecision.REWORK,  # Treat escalate as rework for now
        }

        decision_str = claude_response.get("decision", "rework")
        decision = decision_map.get(decision_str, ReviewDecision.REWORK)

        metrics = claude_response.get("metrics", {})

        return {
            "decision": decision,
            "confidence": claude_response.get("confidence", 0.8),
            "summary": claude_response.get("summary", "Claude review completed"),
            "feedback": claude_response.get("summary", "Claude review completed"),
            "analysis": {
                "code_quality": {
                    "score": metrics.get("code_quality", 75),
                    "issues": claude_response.get("issues", []),
                    "strengths": claude_response.get("suggestions", []),
                },
                "test_coverage": {
                    "score": metrics.get("testing", 70),
                    "missing_tests": [issue for issue in claude_response.get("issues", []) if "test" in issue.lower()],
                },
                "security": {
                    "score": metrics.get("security", 85),
                    "vulnerabilities": [
                        issue for issue in claude_response.get("issues", []) if "security" in issue.lower()
                    ],
                    "recommendations": claude_response.get("suggestions", []),
                },
                "performance": {
                    "score": metrics.get("architecture", 75),
                    "bottlenecks": [
                        issue for issue in claude_response.get("issues", []) if "performance" in issue.lower()
                    ],
                    "optimizations": claude_response.get("suggestions", []),
                },
            },
            "review_time": time.time() - (time.time() - 2.0),
            "files_reviewed": len(claude_response.get("files", [])) if "files" in claude_response else 1,
            "reviewer_id": "async-ai-reviewer-claude",
            "review_timestamp": datetime.now(UTC).isoformat(),
        }


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

    def __init__(self, mock_mode: bool = False) -> None:
        self.agent_id = f"async-ai-reviewer-{uuid.uuid4().hex[:8]}"
        self.running = False
        self.mock_mode = mock_mode

        # Async components
        self.db_ops: AsyncDatabaseOperations | None = None
        self.event_bus = None
        self.review_engine = None

        # Configuration
        self.poll_interval = 10.0  # seconds
        self.max_review_time = 600  # 10 minutes max per review
        self.max_concurrent_reviews = 2  # Max concurrent review operations

        # State tracking
        self.active_reviews: set[str] = set()
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

    async def initialize_async(self) -> None:
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
        await self._register_agent_async()

        # Start performance monitoring
        asyncio.create_task(self._monitor_performance_async())

    async def _register_agent_async(self) -> None:
        """Register agent in the database"""
        try:
            await self.db_ops.register_worker_async(
                worker_id=self.agent_id,
                role="ai_reviewer",
                capabilities=["async_review", "code_analysis", "quality_assurance", "automated_feedback"],
                metadata={
                    "version": "4.2.0",
                    "type": "AsyncAIReviewer",
                    "max_concurrent": self.max_concurrent_reviews,
                    "performance": "3-5x",
                },
            )
            logger.info("AsyncAIReviewer registered as worker")
        except Exception as e:
            logger.warning(f"Failed to register agent: {e}")

    def _signal_handler(self, signum, frame) -> None:
        """Handle shutdown signals gracefully"""
        logger.info(f"Received signal {signum}, initiating graceful shutdown")
        self.shutdown_event.set()

    async def get_next_review_task_async(self) -> dict[str, Any] | None:
        """Get the next task requiring review"""
        try:
            # Get tasks needing review
            review_tasks = await self.db_ops.get_tasks_concurrent_async(status="review_pending", limit=10)

            if not review_tasks:
                return None

            # Sort by priority and creation time
            review_tasks.sort(key=lambda t: (-t.get("priority", 1), t.get("updated_at", "")))

            # Return highest priority task not currently being reviewed
            for task in review_tasks:
                if task["id"] not in self.active_reviews:
                    return task

            return None

        except Exception as e:
            logger.error(f"Error getting next review task: {e}")
            return None

    async def perform_review_async(self, task: dict[str, Any]) -> dict[str, Any]:
        """Perform async review of a completed task"""
        task_id = task["id"]

        async with self.review_semaphore:
            try:
                # Track active review
                self.active_reviews.add(task_id)
                start_time = time.time()

                # Update metrics
                self.metrics["concurrent_peak"] = max(self.metrics["concurrent_peak"], len(self.active_reviews))

                logger.info(f"Starting async review for task {task_id}")

                # Mark task as under review
                await self.db_ops.update_task_status_async(
                    task_id,
                    "review_in_progress",
                    {"reviewer_id": self.agent_id, "review_start": datetime.now(UTC).isoformat()},
                )

                # Get run data for review
                run_data = await self._get_task_run_data_async(task_id)
                if not run_data:
                    logger.warning(f"No run data found for task {task_id}")
                    run_data = {"status": "unknown", "files": {}}

                # Perform review with timeout
                review_result = await asyncio.wait_for(
                    self.review_engine.review_task_async(
                        task=task,
                        run_data=run_data,
                        context={"reviewer_id": self.agent_id},
                    ),
                    timeout=self.max_review_time,
                )

                # Process review decision
                decision = (review_result["decision"],)
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
                        "reviewed_at": datetime.now(UTC).isoformat(),
                    },
                )

                # Update metrics
                self.metrics["reviews_completed"] += 1
                self.metrics["total_review_time"] += review_time
                self.metrics["average_review_time"] = (
                    self.metrics["total_review_time"] / self.metrics["reviews_completed"],
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
                    },
                )

                logger.info(f"# OK Review completed for {task_id}: {decision.value} in {review_time:.1f}s")

                return {
                    "success": True,
                    "decision": decision.value,
                    "review_time": review_time,
                    "confidence": review_result.get("confidence", 0.8),
                }

            except TimeoutError:
                logger.error(f"Review timeout for task {task_id}")
                await self.db_ops.update_task_status_async(
                    task_id,
                    "review_failed",
                    {"error": "Review timeout", "reviewer_id": self.agent_id},
                )
                self.metrics["errors"] += 1
                return {"success": False, "error": "timeout"}

            except Exception as e:
                logger.error(f"Review failed for task {task_id}: {e}")
                await self.db_ops.update_task_status_async(
                    task_id,
                    "review_failed",
                    {"error": str(e), "reviewer_id": self.agent_id},
                )
                self.metrics["errors"] += 1
                return {"success": False, "error": str(e)}

            finally:
                # Remove from active reviews
                self.active_reviews.discard(task_id)

    async def _get_task_run_data_async(self, task_id: str) -> dict[str, Any] | None:
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

    async def process_review_queue_async(self) -> None:
        """Process the review queue with concurrent execution"""
        review_tasks = []

        # Get available slots
        available_slots = self.max_concurrent_reviews - len(self.active_reviews)

        # Start reviews for available tasks
        for _ in range(available_slots):
            task = await self.get_next_review_task_async()
            if task:
                review_task = asyncio.create_task(self.perform_review_async(task))
                review_tasks.append(review_task)
            else:
                break

        # Wait for all review tasks to complete
        if review_tasks:
            results = (await asyncio.gather(*review_tasks, return_exceptions=True),)

            successful_reviews = len([r for r in results if isinstance(r, dict) and r.get("success")])

            if successful_reviews > 0:
                logger.info(f"Completed {successful_reviews} reviews concurrently")

    async def _monitor_performance_async(self) -> None:
        """Background performance monitoring"""
        while not self.shutdown_event.is_set():
            await asyncio.sleep(60)  # Every minute

            logger.info(
                f"[METRICS] Reviews: {self.metrics['reviews_completed']} | ",
                f"Approved: {self.metrics['approved']} | ",
                f"Rework: {self.metrics['rework_requested']} | ",
                f"Avg Time: {self.metrics['average_review_time']:.1f}s | ",
                f"Active: {len(self.active_reviews)} | ",
                f"Errors: {self.metrics['errors']}",
            )

    async def run_forever_async(self) -> None:
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
                    await asyncio.wait_for(self.shutdown_event.wait(), timeout=self.poll_interval)
                    break  # Shutdown signal received
                except TimeoutError:
                    pass  # Normal timeout, continue loop

        except Exception as e:
            logger.error(f"Fatal error in main loop: {e}")
            self.metrics["errors"] += 1

        finally:
            await self._shutdown_async()

    async def _shutdown_async(self) -> None:
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
        approval_rate = self.metrics["approved"] / max(self.metrics["reviews_completed"], 1) * 100
        logger.info(
            "Shutdown complete. Final metrics: ",
            f"Reviews: {self.metrics['reviews_completed']}, ",
            f"Approval Rate: {approval_rate:.1f}%, ",
            f"Avg Time: {self.metrics['average_review_time']:.1f}s, ",
            f"Errors: {self.metrics['errors']}",
        )


async def main_async() -> None:
    """Main entry point for AsyncAIReviewer"""
    import argparse

    parser = argparse.ArgumentParser(description="AsyncAIReviewer - V4.2 High-Performance Review Agent")
    parser.add_argument("--mock", action="store_true", help="Run in mock mode")
    (parser.add_argument("--test", action="store_true", help="Run in test mode"),)

    args = parser.parse_args()

    # Configure logging
    from hive_logging import setup_logging

    setup_logging(name="async-ai-reviewer", log_to_file=True, log_file_path="logs/async-ai-reviewer.log")

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
    asyncio.run(main_async())
