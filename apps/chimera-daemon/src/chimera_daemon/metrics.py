"""Enhanced metrics collection for ExecutorPool with percentiles and trend analysis.

Provides production-grade monitoring with:
- Percentile-based latency distribution (P50/P95/P99)
- Sliding window trend analysis
- Queue depth tracking and trends
- Failure pattern detection by phase
"""

from __future__ import annotations

import statistics
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class WorkflowMetrics:
    """Individual workflow execution metrics."""

    workflow_id: str
    duration_ms: float
    success: bool
    phase: str | None
    timestamp: datetime
    retry_count: int = 0


@dataclass
class PoolMetrics:
    """Comprehensive pool metrics with percentiles and trends."""

    # Pool utilization
    pool_size: int
    active_workflows: int
    available_slots: int
    pool_utilization_pct: float
    peak_utilization_pct: float

    # Queue metrics
    queue_depth: int
    queue_depth_trend: str  # "increasing" | "stable" | "decreasing"
    avg_slot_wait_time_ms: float

    # Throughput metrics
    total_workflows_processed: int
    total_workflows_succeeded: int
    total_workflows_failed: int
    success_rate: float

    # Latency percentiles
    p50_workflow_duration_ms: float
    p95_workflow_duration_ms: float
    p99_workflow_duration_ms: float
    avg_workflow_duration_ms: float

    # Failure analysis
    failure_rate_by_phase: dict[str, float]
    retry_success_rate: float

    # Trend indicators
    throughput_trend: str  # "increasing" | "stable" | "decreasing"
    latency_trend: str  # "improving" | "stable" | "degrading"


class MetricsCollector:
    """Collect and analyze pool metrics with sliding window.

    Uses fixed-size deque for efficient sliding window analysis.
    Tracks last 100 workflows for trend detection.
    """

    def __init__(self, window_size: int = 100):
        """Initialize metrics collector.

        Args:
            window_size: Number of recent workflows to track (default: 100)
        """
        self.window_size = window_size

        # Sliding window of recent workflow metrics
        self._workflow_history: deque[WorkflowMetrics] = deque(maxlen=window_size)

        # Queue depth history for trend analysis
        self._queue_depth_history: deque[int] = deque(maxlen=20)

        # Peak tracking
        self._peak_utilization: float = 0.0

        # Cumulative counters
        self._total_processed = 0
        self._total_succeeded = 0
        self._total_failed = 0
        self._total_retry_attempts = 0
        self._total_retry_successes = 0

        # Percentile cache for performance optimization
        self._percentile_cache: tuple[float, float, float, float] | None = None
        self._cache_workflow_count: int = 0

    def record_workflow(
        self,
        workflow_id: str,
        duration_ms: float,
        success: bool,
        phase: str | None = None,
        retry_count: int = 0,
    ) -> None:
        """Record completed workflow metrics.

        Args:
            workflow_id: Unique workflow identifier
            duration_ms: Execution duration in milliseconds
            success: Whether workflow succeeded
            phase: Workflow phase if available
            retry_count: Number of retry attempts
        """
        metric = WorkflowMetrics(
            workflow_id=workflow_id,
            duration_ms=duration_ms,
            success=success,
            phase=phase,
            timestamp=datetime.now(),
            retry_count=retry_count,
        )

        self._workflow_history.append(metric)

        # Invalidate percentile cache
        self._percentile_cache = None

        # Update cumulative counters
        self._total_processed += 1
        if success:
            self._total_succeeded += 1
        else:
            self._total_failed += 1

        # Track retry success
        if retry_count > 0:
            self._total_retry_attempts += 1
            if success:
                self._total_retry_successes += 1

    def record_queue_depth(self, depth: int) -> None:
        """Record current queue depth for trend analysis.

        Args:
            depth: Current number of tasks in queue
        """
        self._queue_depth_history.append(depth)

    def update_peak_utilization(self, current_utilization: float) -> None:
        """Update peak utilization if current exceeds previous peak.

        Args:
            current_utilization: Current pool utilization percentage
        """
        if current_utilization > self._peak_utilization:
            self._peak_utilization = current_utilization

    def get_metrics(
        self,
        pool_size: int,
        active_workflows: int,
        queue_depth: int,
    ) -> PoolMetrics:
        """Calculate comprehensive pool metrics.

        Args:
            pool_size: Total pool capacity
            active_workflows: Currently executing workflows
            queue_depth: Current queue depth

        Returns:
            Comprehensive pool metrics with percentiles and trends
        """
        available_slots = pool_size - active_workflows
        utilization_pct = (active_workflows / pool_size * 100) if pool_size > 0 else 0.0

        # Update peak utilization
        self.update_peak_utilization(utilization_pct)

        # Record current queue depth
        self.record_queue_depth(queue_depth)

        # Calculate percentiles
        durations = [w.duration_ms for w in self._workflow_history]
        p50, p95, p99, avg = self._calculate_percentiles(durations)

        # Analyze failure patterns
        failure_by_phase = self._analyze_failure_patterns()

        # Calculate retry success rate
        retry_success_rate = (
            (self._total_retry_successes / self._total_retry_attempts * 100)
            if self._total_retry_attempts > 0
            else 0.0
        )

        # Detect trends
        queue_trend = self._detect_queue_trend()
        throughput_trend = self._detect_throughput_trend()
        latency_trend = self._detect_latency_trend()

        # Calculate success rate
        success_rate = (
            (self._total_succeeded / self._total_processed * 100) if self._total_processed > 0 else 0.0
        )

        return PoolMetrics(
            pool_size=pool_size,
            active_workflows=active_workflows,
            available_slots=available_slots,
            pool_utilization_pct=utilization_pct,
            peak_utilization_pct=self._peak_utilization,
            queue_depth=queue_depth,
            queue_depth_trend=queue_trend,
            avg_slot_wait_time_ms=0.0,  # TODO: Implement slot wait tracking
            total_workflows_processed=self._total_processed,
            total_workflows_succeeded=self._total_succeeded,
            total_workflows_failed=self._total_failed,
            success_rate=success_rate,
            p50_workflow_duration_ms=p50,
            p95_workflow_duration_ms=p95,
            p99_workflow_duration_ms=p99,
            avg_workflow_duration_ms=avg,
            failure_rate_by_phase=failure_by_phase,
            retry_success_rate=retry_success_rate,
            throughput_trend=throughput_trend,
            latency_trend=latency_trend,
        )

    def _calculate_percentiles(
        self, durations: list[float]
    ) -> tuple[float, float, float, float]:
        """Calculate P50, P95, P99 percentiles and average.

        Uses cache to avoid recalculating when workflow history hasn't changed.

        Args:
            durations: List of workflow durations in milliseconds

        Returns:
            Tuple of (P50, P95, P99, avg) in milliseconds
        """
        if not durations:
            return (0.0, 0.0, 0.0, 0.0)

        # Check cache validity
        current_count = len(self._workflow_history)
        if (
            self._percentile_cache is not None
            and self._cache_workflow_count == current_count
        ):
            return self._percentile_cache

        # Cache miss - calculate percentiles
        sorted_durations = sorted(durations)
        n = len(sorted_durations)

        # Calculate percentiles using linear interpolation
        p50 = statistics.median(sorted_durations)
        p95 = sorted_durations[int(n * 0.95)] if n > 0 else 0.0
        p99 = sorted_durations[int(n * 0.99)] if n > 0 else 0.0
        avg = statistics.mean(sorted_durations)

        # Update cache
        result = (p50, p95, p99, avg)
        self._percentile_cache = result
        self._cache_workflow_count = current_count

        return result

    def _analyze_failure_patterns(self) -> dict[str, float]:
        """Analyze failure rates by workflow phase.

        Returns:
            Dictionary mapping phase name to failure rate percentage
        """
        phase_totals: dict[str, int] = {}
        phase_failures: dict[str, int] = {}

        for workflow in self._workflow_history:
            phase = workflow.phase or "unknown"
            phase_totals[phase] = phase_totals.get(phase, 0) + 1
            if not workflow.success:
                phase_failures[phase] = phase_failures.get(phase, 0) + 1

        # Calculate failure rates
        failure_rates = {}
        for phase, total in phase_totals.items():
            failures = phase_failures.get(phase, 0)
            failure_rates[phase] = (failures / total * 100) if total > 0 else 0.0

        return failure_rates

    def _detect_queue_trend(self) -> str:
        """Detect queue depth trend from recent history.

        Returns:
            Trend indicator: "increasing", "stable", or "decreasing"
        """
        if len(self._queue_depth_history) < 5:
            return "stable"

        # Compare recent half vs older half
        mid = len(self._queue_depth_history) // 2
        older_avg = statistics.mean(list(self._queue_depth_history)[:mid])
        recent_avg = statistics.mean(list(self._queue_depth_history)[mid:])

        # Threshold: 20% change indicates trend
        threshold = 0.2
        if recent_avg > older_avg * (1 + threshold):
            return "increasing"
        elif recent_avg < older_avg * (1 - threshold):
            return "decreasing"
        else:
            return "stable"

    def _detect_throughput_trend(self) -> str:
        """Detect throughput trend from recent workflow timestamps.

        Returns:
            Trend indicator: "increasing", "stable", or "decreasing"
        """
        if len(self._workflow_history) < 20:
            return "stable"

        # Compare workflows per minute: recent vs older
        now = datetime.now()
        recent_window = now - timedelta(minutes=5)

        recent_count = sum(1 for w in self._workflow_history if w.timestamp >= recent_window)
        older_count = len(self._workflow_history) - recent_count

        # Normalize to per-minute rate
        recent_rate = recent_count / 5.0  # Last 5 minutes
        older_rate = older_count / 5.0 if older_count > 0 else 0.0  # Assume same window

        # Threshold: 30% change indicates trend
        threshold = 0.3
        if recent_rate > older_rate * (1 + threshold):
            return "increasing"
        elif recent_rate < older_rate * (1 - threshold) and older_rate > 0:
            return "decreasing"
        else:
            return "stable"

    def _detect_latency_trend(self) -> str:
        """Detect latency trend from recent workflow durations.

        Returns:
            Trend indicator: "improving", "stable", or "degrading"
        """
        if len(self._workflow_history) < 10:
            return "stable"

        # Compare recent half vs older half
        mid = len(self._workflow_history) // 2
        durations = [w.duration_ms for w in self._workflow_history]

        older_avg = statistics.mean(durations[:mid])
        recent_avg = statistics.mean(durations[mid:])

        # Threshold: 15% change indicates trend
        threshold = 0.15
        if recent_avg > older_avg * (1 + threshold):
            return "degrading"
        elif recent_avg < older_avg * (1 - threshold):
            return "improving"
        else:
            return "stable"

    def reset_peak_utilization(self) -> None:
        """Reset peak utilization counter (useful for time-windowed peaks)."""
        self._peak_utilization = 0.0


__all__ = ["WorkflowMetrics", "PoolMetrics", "MetricsCollector"]
