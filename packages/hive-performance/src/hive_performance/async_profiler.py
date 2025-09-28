"""Async operation profiler with detailed task analysis."""

import asyncio
import time
import traceback
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set, Tuple, Callable
from datetime import datetime, timedelta
import weakref
from hive_logging import get_logger

logger = get_logger(__name__)


@dataclass
class TaskProfile:
    """Profile data for an individual async task."""

    task_id: str
    task_name: str
    coro_name: str
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    state: str = "pending"  # pending, running, done, cancelled, failed
    exception: Optional[Exception] = None
    stack_trace: Optional[str] = None

    # Timing metrics
    queue_time: float = 0.0  # Time waiting to start
    execution_time: float = 0.0  # Time actually running
    total_time: float = 0.0  # Total lifetime

    # Resource metrics
    peak_memory: int = 0
    cpu_time: float = 0.0

    # Dependencies
    waited_for: List[str] = field(default_factory=list)
    waited_by: List[str] = field(default_factory=list)

    # Custom metadata
    tags: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProfileReport:
    """Comprehensive async profile report."""

    # Summary statistics
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    cancelled_tasks: int = 0
    active_tasks: int = 0

    # Timing statistics
    avg_queue_time: float = 0.0
    avg_execution_time: float = 0.0
    max_execution_time: float = 0.0
    min_execution_time: float = 0.0

    # Performance metrics
    throughput: float = 0.0  # tasks per second
    concurrency_level: float = 0.0  # average concurrent tasks

    # Task analysis
    slowest_tasks: List[TaskProfile] = field(default_factory=list)
    failed_tasks: List[TaskProfile] = field(default_factory=list)
    long_running_tasks: List[TaskProfile] = field(default_factory=list)

    # Patterns and insights
    task_types: Dict[str, int] = field(default_factory=dict)
    bottlenecks: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)

    # Metadata
    profile_start: datetime = field(default_factory=datetime.utcnow)
    profile_end: datetime = field(default_factory=datetime.utcnow)
    profile_duration: float = 0.0


class AsyncProfiler:
    """
    Advanced async operation profiler.

    Features:
    - Real-time task monitoring
    - Performance bottleneck detection
    - Task dependency analysis
    - Resource usage tracking
    - Comprehensive reporting
    - Memory-efficient profiling
    """

    def __init__(
        self,
        max_task_history: int = 10000,
        enable_stack_traces: bool = False,
        enable_memory_tracking: bool = True,
        sample_rate: float = 1.0  # 0.0-1.0, for performance
    ):
        self.max_task_history = max_task_history
        self.enable_stack_traces = enable_stack_traces
        self.enable_memory_tracking = enable_memory_tracking
        self.sample_rate = sample_rate

        # Task tracking
        self._task_profiles: Dict[int, TaskProfile] = {}
        self._completed_profiles: deque = deque(maxlen=max_task_history)
        self._active_tasks: Set[int] = set()

        # Profiling state
        self._profiling = False
        self._profile_start: Optional[datetime] = None
        self._monitor_task: Optional[asyncio.Task] = None

        # Statistics
        self._task_counter = 0
        self._completion_times: deque = deque(maxlen=1000)
        self._concurrency_samples: deque = deque(maxlen=1000)

        # Event hooks
        self._original_task_factory: Optional[Callable] = None
        self._hooked_loop: Optional[asyncio.AbstractEventLoop] = None

    async def start_profiling(self) -> None:
        """Start async profiling."""
        if self._profiling:
            return

        self._profiling = True
        self._profile_start = datetime.utcnow()

        # Hook into the event loop
        loop = asyncio.get_running_loop()
        self._hooked_loop = loop
        self._original_task_factory = loop.get_task_factory()
        loop.set_task_factory(self._task_factory)

        # Start monitoring task
        self._monitor_task = asyncio.create_task(self._monitoring_loop())

        logger.info("Started async profiling")

    async def stop_profiling(self) -> None:
        """Stop async profiling."""
        if not self._profiling:
            return

        self._profiling = False

        # Restore original task factory
        if self._hooked_loop and self._original_task_factory:
            self._hooked_loop.set_task_factory(self._original_task_factory)

        # Stop monitoring
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass

        logger.info("Stopped async profiling")

    def _task_factory(self, loop: asyncio.AbstractEventLoop, coro) -> asyncio.Task:
        """Custom task factory for profiling."""
        # Sample based on sample_rate
        if self.sample_rate < 1.0:
            import random
            if random.random() > self.sample_rate:
                return asyncio.Task(coro, loop=loop)

        # Create task with profiling
        task = asyncio.Task(coro, loop=loop)
        self._register_task(task)
        return task

    def _register_task(self, task: asyncio.Task) -> None:
        """Register a new task for profiling."""
        task_id = id(task)
        self._task_counter += 1

        # Extract coroutine name
        coro_name = getattr(task.get_coro(), '__name__', 'unknown')
        task_name = getattr(task, 'get_name', lambda: f"Task-{self._task_counter}")()

        # Create profile
        profile = TaskProfile(
            task_id=str(task_id),
            task_name=task_name,
            coro_name=coro_name,
            created_at=datetime.utcnow(),
            state="pending"
        )

        # Capture stack trace if enabled
        if self.enable_stack_traces:
            profile.stack_trace = ''.join(traceback.format_stack())

        self._task_profiles[task_id] = profile
        self._active_tasks.add(task_id)

        # Add completion callback
        task.add_done_callback(self._task_completed)

    def _task_completed(self, task: asyncio.Task) -> None:
        """Handle task completion."""
        task_id = id(task)
        profile = self._task_profiles.get(task_id)

        if not profile:
            return

        # Update profile
        profile.completed_at = datetime.utcnow()
        profile.total_time = (profile.completed_at - profile.created_at).total_seconds()

        if task.cancelled():
            profile.state = "cancelled"
        elif task.exception():
            profile.state = "failed"
            profile.exception = task.exception()
        else:
            profile.state = "done"

        # Calculate execution time (approximation)
        if profile.started_at:
            profile.execution_time = (profile.completed_at - profile.started_at).total_seconds()
            profile.queue_time = (profile.started_at - profile.created_at).total_seconds()
        else:
            profile.execution_time = profile.total_time
            profile.queue_time = 0.0

        # Move to completed profiles
        self._completed_profiles.append(profile)
        self._completion_times.append(profile.execution_time)

        # Clean up
        self._task_profiles.pop(task_id, None)
        self._active_tasks.discard(task_id)

    async def _monitoring_loop(self) -> None:
        """Monitor active tasks."""
        while self._profiling:
            try:
                await self._update_active_tasks()
                self._sample_concurrency()
                await asyncio.sleep(0.1)  # 100ms sampling

            except Exception as e:
                logger.error(f"Error in profiling monitor: {e}")
                await asyncio.sleep(1.0)

    async def _update_active_tasks(self) -> None:
        """Update status of active tasks."""
        current_time = datetime.utcnow()

        for task_id in list(self._active_tasks):
            profile = self._task_profiles.get(task_id)
            if not profile:
                continue

            # Mark as started if not already
            if profile.state == "pending" and profile.started_at is None:
                profile.started_at = current_time
                profile.state = "running"

    def _sample_concurrency(self) -> None:
        """Sample current concurrency level."""
        self._concurrency_samples.append(len(self._active_tasks))

    def get_active_tasks(self) -> List[TaskProfile]:
        """Get currently active task profiles."""
        return [profile for profile in self._task_profiles.values()]

    def get_completed_tasks(
        self,
        limit: Optional[int] = None,
        time_window: Optional[timedelta] = None
    ) -> List[TaskProfile]:
        """Get completed task profiles."""
        profiles = list(self._completed_profiles)

        # Filter by time window
        if time_window:
            cutoff_time = datetime.utcnow() - time_window
            profiles = [p for p in profiles if p.completed_at and p.completed_at >= cutoff_time]

        # Apply limit
        if limit:
            profiles = profiles[-limit:]

        return profiles

    def analyze_performance(self, time_window: Optional[timedelta] = None) -> ProfileReport:
        """Generate comprehensive performance analysis."""
        completed_tasks = self.get_completed_tasks(time_window=time_window)
        active_tasks = self.get_active_tasks()

        if not completed_tasks and not active_tasks:
            return ProfileReport(
                profile_start=self._profile_start or datetime.utcnow(),
                profile_end=datetime.utcnow()
            )

        # Basic statistics
        total_tasks = len(completed_tasks) + len(active_tasks)
        completed_count = len([t for t in completed_tasks if t.state == "done"])
        failed_count = len([t for t in completed_tasks if t.state == "failed"])
        cancelled_count = len([t for t in completed_tasks if t.state == "cancelled"])

        # Timing statistics
        execution_times = [t.execution_time for t in completed_tasks if t.execution_time > 0]
        avg_execution = sum(execution_times) / len(execution_times) if execution_times else 0.0
        max_execution = max(execution_times) if execution_times else 0.0
        min_execution = min(execution_times) if execution_times else 0.0

        queue_times = [t.queue_time for t in completed_tasks if t.queue_time > 0]
        avg_queue = sum(queue_times) / len(queue_times) if queue_times else 0.0

        # Throughput calculation
        if completed_tasks and len(completed_tasks) > 1:
            time_span = (completed_tasks[-1].completed_at - completed_tasks[0].created_at).total_seconds()
            throughput = len(completed_tasks) / time_span if time_span > 0 else 0.0
        else:
            throughput = 0.0

        # Concurrency level
        avg_concurrency = sum(self._concurrency_samples) / len(self._concurrency_samples) if self._concurrency_samples else 0.0

        # Identify problematic tasks
        slowest_tasks = sorted(completed_tasks, key=lambda t: t.execution_time, reverse=True)[:10]
        failed_tasks = [t for t in completed_tasks if t.state == "failed"]
        long_running_tasks = [t for t in active_tasks if (datetime.utcnow() - t.created_at).total_seconds() > 30]

        # Task type analysis
        task_types = defaultdict(int)
        for task in completed_tasks + active_tasks:
            task_types[task.coro_name] += 1

        # Generate insights
        bottlenecks, recommendations = self._analyze_bottlenecks(completed_tasks, active_tasks)

        # Profile duration
        profile_end = datetime.utcnow()
        profile_duration = (profile_end - (self._profile_start or profile_end)).total_seconds()

        return ProfileReport(
            total_tasks=total_tasks,
            completed_tasks=completed_count,
            failed_tasks=failed_count,
            cancelled_tasks=cancelled_count,
            active_tasks=len(active_tasks),
            avg_queue_time=avg_queue,
            avg_execution_time=avg_execution,
            max_execution_time=max_execution,
            min_execution_time=min_execution,
            throughput=throughput,
            concurrency_level=avg_concurrency,
            slowest_tasks=slowest_tasks,
            failed_tasks=failed_tasks,
            long_running_tasks=long_running_tasks,
            task_types=dict(task_types),
            bottlenecks=bottlenecks,
            recommendations=recommendations,
            profile_start=self._profile_start or datetime.utcnow(),
            profile_end=profile_end,
            profile_duration=profile_duration
        )

    def _analyze_bottlenecks(
        self,
        completed_tasks: List[TaskProfile],
        active_tasks: List[TaskProfile]
    ) -> Tuple[List[str], List[str]]:
        """Analyze performance bottlenecks and generate recommendations."""
        bottlenecks = []
        recommendations = []

        if not completed_tasks:
            return bottlenecks, recommendations

        # High queue times indicate event loop congestion
        avg_queue_time = sum(t.queue_time for t in completed_tasks) / len(completed_tasks)
        if avg_queue_time > 0.1:  # 100ms threshold
            bottlenecks.append(f"High queue times (avg: {avg_queue_time:.3f}s)")
            recommendations.append("Consider reducing task creation rate or optimizing task execution")

        # Many failed tasks
        failure_rate = len([t for t in completed_tasks if t.state == "failed"]) / len(completed_tasks)
        if failure_rate > 0.05:  # 5% threshold
            bottlenecks.append(f"High failure rate ({failure_rate:.1%})")
            recommendations.append("Review error handling and task robustness")

        # Long-running tasks
        if active_tasks:
            long_running = [t for t in active_tasks if (datetime.utcnow() - t.created_at).total_seconds() > 30]
            if long_running:
                bottlenecks.append(f"{len(long_running)} long-running tasks detected")
                recommendations.append("Review tasks for potential deadlocks or inefficient operations")

        # Slow task types
        task_times = defaultdict(list)
        for task in completed_tasks:
            task_times[task.coro_name].append(task.execution_time)

        for task_type, times in task_times.items():
            if len(times) > 5:  # Significant sample size
                avg_time = sum(times) / len(times)
                if avg_time > 1.0:  # 1 second threshold
                    bottlenecks.append(f"Slow task type: {task_type} (avg: {avg_time:.3f}s)")
                    recommendations.append(f"Optimize {task_type} implementation")

        return bottlenecks, recommendations

    def export_report(self, format: str = "json", time_window: Optional[timedelta] = None) -> str:
        """Export performance report in specified format."""
        report = self.analyze_performance(time_window)

        if format == "json":
            import json
            return json.dumps({
                "summary": {
                    "total_tasks": report.total_tasks,
                    "completed_tasks": report.completed_tasks,
                    "failed_tasks": report.failed_tasks,
                    "active_tasks": report.active_tasks,
                    "throughput": report.throughput,
                    "avg_execution_time": report.avg_execution_time,
                    "concurrency_level": report.concurrency_level,
                },
                "bottlenecks": report.bottlenecks,
                "recommendations": report.recommendations,
                "task_types": report.task_types,
                "profile_duration": report.profile_duration,
            }, indent=2)

        elif format == "text":
            lines = [
                "=== Async Performance Report ===",
                f"Profile Duration: {report.profile_duration:.2f}s",
                f"Total Tasks: {report.total_tasks}",
                f"Completed: {report.completed_tasks}, Failed: {report.failed_tasks}, Active: {report.active_tasks}",
                f"Throughput: {report.throughput:.2f} tasks/sec",
                f"Avg Execution Time: {report.avg_execution_time:.3f}s",
                f"Concurrency Level: {report.concurrency_level:.1f}",
                "",
                "=== Bottlenecks ===",
            ]
            lines.extend(f"- {bottleneck}" for bottleneck in report.bottlenecks)
            lines.extend([
                "",
                "=== Recommendations ===",
            ])
            lines.extend(f"- {rec}" for rec in report.recommendations)

            return "\n".join(lines)

        else:
            raise ValueError(f"Unsupported export format: {format}")

    def clear_history(self) -> None:
        """Clear profiling history."""
        self._completed_profiles.clear()
        self._completion_times.clear()
        self._concurrency_samples.clear()
        logger.info("Cleared async profiling history")


# Context manager for profiling code blocks
class profile_async_block:
    """Context manager for profiling async code blocks."""

    def __init__(self, profiler: AsyncProfiler, block_name: str):
        self.profiler = profiler
        self.block_name = block_name
        self._original_profiling = False

    async def __aenter__(self) -> ProfileReport:
        self._original_profiling = self.profiler._profiling
        if not self._original_profiling:
            await self.profiler.start_profiling()
        return await self.__aexit__(None, None, None)

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if not self._original_profiling:
            await self.profiler.stop_profiling()
        return self.profiler.analyze_performance()


# Decorator for profiling async functions
def profile_async(profiler: AsyncProfiler) -> Callable:
    """Decorator for profiling async functions."""

    def decorator(func: Callable) -> Callable:
        async def wrapper(*args, **kwargs):
            was_profiling = profiler._profiling
            if not was_profiling:
                await profiler.start_profiling()

            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                if not was_profiling:
                    await profiler.stop_profiling()

        return wrapper
    return decorator