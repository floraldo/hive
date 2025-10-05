"""Performance Profiling for Workflow Execution.

Provides detailed CPU, memory, and I/O profiling capabilities with minimal overhead.
"""

from __future__ import annotations

import asyncio
import functools
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from hive_logging import get_logger

logger = get_logger(__name__)

# Optional dependency - profiling only enabled if available
try:
    import psutil

    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    logger.warning("psutil not available - resource profiling disabled")


@dataclass
class ProfileSnapshot:
    """Resource usage snapshot at a point in time."""

    timestamp: datetime
    cpu_percent: float
    memory_mb: float
    memory_percent: float
    io_read_mb: float = 0.0
    io_write_mb: float = 0.0
    thread_count: int = 0


@dataclass
class OperationProfile:
    """Profiling data for a single operation.

    Tracks timing, resource usage, and execution metadata.
    """

    operation: str
    started_at: datetime
    ended_at: datetime | None = None
    wall_time_ms: float = 0.0
    cpu_time_ms: float = 0.0
    snapshots: list[ProfileSnapshot] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def duration_ms(self) -> float:
        """Get operation duration in milliseconds."""
        if self.ended_at is None:
            return (datetime.now() - self.started_at).total_seconds() * 1000
        return self.wall_time_ms

    @property
    def avg_cpu_percent(self) -> float:
        """Get average CPU usage during operation."""
        if not self.snapshots:
            return 0.0
        return sum(s.cpu_percent for s in self.snapshots) / len(self.snapshots)

    @property
    def peak_memory_mb(self) -> float:
        """Get peak memory usage during operation."""
        if not self.snapshots:
            return 0.0
        return max(s.memory_mb for s in self.snapshots)

    @property
    def avg_memory_mb(self) -> float:
        """Get average memory usage during operation."""
        if not self.snapshots:
            return 0.0
        return sum(s.memory_mb for s in self.snapshots) / len(self.snapshots)

    @property
    def total_io_mb(self) -> float:
        """Get total I/O (read + write) during operation."""
        if not self.snapshots:
            return 0.0
        first = self.snapshots[0]
        last = self.snapshots[-1]
        read_delta = last.io_read_mb - first.io_read_mb
        write_delta = last.io_write_mb - first.io_write_mb
        return read_delta + write_delta


class PerformanceProfiler:
    """Performance profiler with CPU, memory, and I/O tracking.

    Provides decorators and context managers for profiling operations with
    minimal performance overhead.

    Example:
        profiler = PerformanceProfiler(enabled=True)

        # Decorator usage
        @profiler.profile("database_query")
        async def query_db():
            return await db.execute(query)

        # Context manager usage
        async with profiler.profile_context("api_call") as profile:
            result = await api.fetch_data()
            profile.metadata["record_count"] = len(result)

        # Get profiling report
        report = profiler.get_report()
    """

    def __init__(
        self,
        enabled: bool = False,
        snapshot_interval_ms: float = 100,
        auto_cleanup: bool = True,
        max_profiles_per_operation: int = 100,
        cleanup_interval: int = 100,
    ):
        """Initialize performance profiler.

        Args:
            enabled: Enable profiling (default: False for minimal overhead)
            snapshot_interval_ms: Interval between resource snapshots (default: 100ms)
            auto_cleanup: Enable automatic cleanup of old profiles (default: True)
            max_profiles_per_operation: Maximum profiles per operation (default: 100)
            cleanup_interval: Cleanup every N profiles (default: 100)
        """
        self.enabled = enabled and PSUTIL_AVAILABLE
        self.snapshot_interval_ms = snapshot_interval_ms
        self.logger = logger

        # Profiling data storage
        self._profiles: dict[str, list[OperationProfile]] = defaultdict(list)
        self._active_profiles: dict[str, OperationProfile] = {}

        # Automatic cleanup configuration
        self._auto_cleanup = auto_cleanup
        self._max_profiles_per_operation = max_profiles_per_operation
        self._cleanup_interval = cleanup_interval
        self._profile_counter = 0

        # Background task tracking
        self._snapshot_tasks: set[asyncio.Task] = set()

        # Process handle for resource monitoring
        if self.enabled:
            self._process = psutil.Process()
            self.logger.info("Performance profiling ENABLED")
        else:
            self._process = None
            if not PSUTIL_AVAILABLE:
                self.logger.info("Performance profiling DISABLED (psutil not available)")
            else:
                self.logger.info("Performance profiling DISABLED (not enabled)")

    def _get_resource_snapshot(self) -> ProfileSnapshot:
        """Capture current resource usage snapshot.

        Returns:
            ProfileSnapshot with current resource metrics
        """
        if not self.enabled or self._process is None:
            return ProfileSnapshot(
                timestamp=datetime.now(),
                cpu_percent=0.0,
                memory_mb=0.0,
                memory_percent=0.0,
            )

        try:
            # Get process metrics
            cpu_percent = self._process.cpu_percent()
            memory_info = self._process.memory_info()
            memory_mb = memory_info.rss / 1024 / 1024  # Convert bytes to MB
            memory_percent = self._process.memory_percent()

            # Get I/O stats (may not be available on all platforms)
            try:
                io_counters = self._process.io_counters()
                io_read_mb = io_counters.read_bytes / 1024 / 1024
                io_write_mb = io_counters.write_bytes / 1024 / 1024
            except (AttributeError, PermissionError):
                io_read_mb = 0.0
                io_write_mb = 0.0

            thread_count = self._process.num_threads()

            return ProfileSnapshot(
                timestamp=datetime.now(),
                cpu_percent=cpu_percent,
                memory_mb=memory_mb,
                memory_percent=memory_percent,
                io_read_mb=io_read_mb,
                io_write_mb=io_write_mb,
                thread_count=thread_count,
            )

        except Exception as e:
            self.logger.warning(f"Failed to capture resource snapshot: {e}")
            return ProfileSnapshot(
                timestamp=datetime.now(),
                cpu_percent=0.0,
                memory_mb=0.0,
                memory_percent=0.0,
            )

    async def _snapshot_loop(self, profile_id: str) -> None:
        """Background task to capture periodic resource snapshots.

        Args:
            profile_id: ID of profile to update with snapshots
        """
        while profile_id in self._active_profiles:
            snapshot = self._get_resource_snapshot()
            if profile_id in self._active_profiles:
                self._active_profiles[profile_id].snapshots.append(snapshot)
            await asyncio.sleep(self.snapshot_interval_ms / 1000.0)

    def start_profile(self, operation: str, metadata: dict[str, Any] | None = None) -> str:
        """Start profiling an operation.

        Args:
            operation: Operation name
            metadata: Additional metadata

        Returns:
            Profile ID for later finishing
        """
        if not self.enabled:
            return ""

        profile_id = f"{operation}_{id(object())}"

        profile = OperationProfile(
            operation=operation,
            started_at=datetime.now(),
            metadata=metadata or {},
        )

        # Initial snapshot
        profile.snapshots.append(self._get_resource_snapshot())

        self._active_profiles[profile_id] = profile

        # Start snapshot loop in background and track task
        task = asyncio.create_task(self._snapshot_loop(profile_id))
        self._snapshot_tasks.add(task)
        task.add_done_callback(self._snapshot_tasks.discard)

        return profile_id

    def finish_profile(
        self,
        profile_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> OperationProfile | None:
        """Finish profiling an operation.

        Args:
            profile_id: Profile ID from start_profile()
            metadata: Additional metadata to add

        Returns:
            Completed OperationProfile or None if not found
        """
        if not self.enabled or not profile_id:
            return None

        if profile_id not in self._active_profiles:
            return None

        profile = self._active_profiles.pop(profile_id)
        profile.ended_at = datetime.now()
        profile.wall_time_ms = (profile.ended_at - profile.started_at).total_seconds() * 1000

        # Final snapshot
        profile.snapshots.append(self._get_resource_snapshot())

        # Add metadata
        if metadata:
            profile.metadata.update(metadata)

        # Store completed profile
        self._profiles[profile.operation].append(profile)

        self.logger.debug(
            f"Profiled {profile.operation}: {profile.wall_time_ms:.1f}ms, "
            f"CPU: {profile.avg_cpu_percent:.1f}%, "
            f"Mem: {profile.peak_memory_mb:.1f}MB"
        )

        # Automatic cleanup check
        if self._auto_cleanup:
            self._profile_counter += 1
            if self._profile_counter >= self._cleanup_interval:
                self._cleanup_old_profiles()
                self._profile_counter = 0

        return profile

    def profile_context(self, operation: str, metadata: dict[str, Any] | None = None):
        """Context manager for profiling an operation.

        Args:
            operation: Operation name
            metadata: Additional metadata

        Returns:
            Context manager that yields the active profile

        Example:
            async with profiler.profile_context("api_call") as profile:
                result = await api.fetch()
                profile.metadata["count"] = len(result)
        """
        return _ProfileContext(self, operation, metadata)

    def profile(self, operation: str | None = None):
        """Decorator for profiling async functions.

        Args:
            operation: Operation name (defaults to function name)

        Returns:
            Decorated function

        Example:
            @profiler.profile("database_query")
            async def query_db():
                return await db.execute(query)
        """

        def decorator(func: Callable):
            op_name = operation or func.__name__

            @functools.wraps(func)
            async def wrapper(*args, **kwargs):
                if not self.enabled:
                    return await func(*args, **kwargs)

                profile_id = self.start_profile(op_name)
                try:
                    result = await func(*args, **kwargs)
                    self.finish_profile(profile_id)
                    return result
                except Exception as e:
                    self.finish_profile(profile_id, metadata={"error": str(e)})
                    raise

            return wrapper

        return decorator

    def _cleanup_old_profiles(self) -> int:
        """Remove old profiles to prevent memory growth.
        
        Returns:
            Number of profiles removed
        """
        removed_count = 0

        for operation in list(self._profiles.keys()):
            profiles = self._profiles[operation]
            if len(profiles) > self._max_profiles_per_operation:
                # Keep most recent profiles
                excess = len(profiles) - self._max_profiles_per_operation
                self._profiles[operation] = profiles[-self._max_profiles_per_operation:]
                removed_count += excess

        if removed_count > 0:
            self.logger.debug(f"Cleaned up {removed_count} old profiles")

        return removed_count

    def get_memory_usage(self) -> dict[str, int]:
        """Get current memory usage statistics.
        
        Returns:
            Dictionary with profile counts and snapshot tasks
        """
        total_profiles = sum(len(profiles) for profiles in self._profiles.values())
        total_snapshots = sum(
            sum(len(p.snapshots) for p in profiles)
            for profiles in self._profiles.values()
        )

        return {
            "total_profiles": total_profiles,
            "active_profiles": len(self._active_profiles),
            "operations": len(self._profiles),
            "total_snapshots": total_snapshots,
            "active_snapshot_tasks": len(self._snapshot_tasks),
        }

    async def cleanup_snapshot_tasks(self) -> int:
        """Cancel and cleanup all active snapshot tasks.
        
        Returns:
            Number of tasks cancelled
        """
        if not self._snapshot_tasks:
            return 0

        count = len(self._snapshot_tasks)
        for task in list(self._snapshot_tasks):
            if not task.done():
                task.cancel()

        # Wait for all cancellations
        if self._snapshot_tasks:
            await asyncio.gather(*self._snapshot_tasks, return_exceptions=True)
            self._snapshot_tasks.clear()

        self.logger.info(f"Cancelled {count} snapshot tasks")
        return count

    def get_profiles(self, operation: str | None = None) -> list[OperationProfile]:
        """Get completed profiles.

        Args:
            operation: Filter by operation name (all if None)

        Returns:
            List of completed profiles
        """
        if operation:
            return self._profiles.get(operation, [])
        else:
            all_profiles = []
            for profiles in self._profiles.values():
                all_profiles.extend(profiles)
            return all_profiles

    def get_report(self) -> dict[str, Any]:
        """Generate comprehensive profiling report.

        Returns:
            Dictionary with aggregated profiling metrics
        """
        if not self.enabled:
            return {"enabled": False, "message": "Profiling is disabled"}

        report: dict[str, Any] = {
            "enabled": True,
            "total_profiles": sum(len(profiles) for profiles in self._profiles.values()),
            "operations": {},
        }

        for operation, profiles in self._profiles.items():
            if not profiles:
                continue

            wall_times = [p.wall_time_ms for p in profiles]
            cpu_percents = [p.avg_cpu_percent for p in profiles]
            memory_peaks = [p.peak_memory_mb for p in profiles]
            io_totals = [p.total_io_mb for p in profiles]

            report["operations"][operation] = {
                "call_count": len(profiles),
                "wall_time_ms": {
                    "avg": sum(wall_times) / len(wall_times),
                    "min": min(wall_times),
                    "max": max(wall_times),
                    "total": sum(wall_times),
                },
                "cpu_percent": {
                    "avg": sum(cpu_percents) / len(cpu_percents) if cpu_percents else 0.0,
                    "max": max(cpu_percents) if cpu_percents else 0.0,
                },
                "memory_mb": {
                    "avg_peak": sum(memory_peaks) / len(memory_peaks) if memory_peaks else 0.0,
                    "max_peak": max(memory_peaks) if memory_peaks else 0.0,
                },
                "io_mb": {
                    "avg_total": sum(io_totals) / len(io_totals) if io_totals else 0.0,
                    "max_total": max(io_totals) if io_totals else 0.0,
                },
            }

        return report

    def clear_profiles(self, operation: str | None = None) -> int:
        """Clear completed profiles to free memory.

        Args:
            operation: Clear specific operation (all if None)

        Returns:
            Number of profiles cleared
        """
        if operation:
            count = len(self._profiles.get(operation, []))
            self._profiles.pop(operation, None)
            return count
        else:
            count = sum(len(profiles) for profiles in self._profiles.values())
            self._profiles.clear()
            return count


class _ProfileContext:
    """Context manager for profiling operations."""

    def __init__(
        self,
        profiler: PerformanceProfiler,
        operation: str,
        metadata: dict[str, Any] | None = None,
    ):
        self.profiler = profiler
        self.operation = operation
        self.metadata = metadata
        self.profile_id = ""
        self.profile: OperationProfile | None = None

    async def __aenter__(self) -> OperationProfile:
        """Start profiling."""
        self.profile_id = self.profiler.start_profile(self.operation, self.metadata)
        # Return a temporary profile object that can be updated
        if self.profiler.enabled and self.profile_id:
            self.profile = self.profiler._active_profiles[self.profile_id]
        else:
            # Create dummy profile for disabled profiler
            self.profile = OperationProfile(
                operation=self.operation,
                started_at=datetime.now(),
            )
        return self.profile

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Finish profiling."""
        metadata = {}
        if exc_type is not None:
            metadata["error"] = str(exc_val)
        self.profiler.finish_profile(self.profile_id, metadata)
        return False  # Don't suppress exceptions


__all__ = ["PerformanceProfiler", "OperationProfile", "ProfileSnapshot"]
