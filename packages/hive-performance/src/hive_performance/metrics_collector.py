"""Performance metrics collection and aggregation."""

import asyncio
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List

import psutil
from hive_logging import get_logger

logger = get_logger(__name__)


@dataclass
class PerformanceMetrics:
    """Container for performance metrics data."""
from __future__ import annotations


    # Timing metrics
    execution_time: float = 0.0
    cpu_time: float = 0.0
    wall_time: float = 0.0

    # Resource metrics
    memory_usage: int = 0  # bytes
    peak_memory: int = 0  # bytes
    cpu_percent: float = 0.0

    # Throughput metrics
    operations_count: int = 0
    operations_per_second: float = 0.0
    bytes_processed: int = 0

    # Error metrics
    error_count: int = 0
    error_rate: float = 0.0

    # Async metrics
    active_tasks: int = 0
    completed_tasks: int = 0
    blocked_tasks: int = 0

    # Custom metrics
    custom_metrics: Dict[str, Any] = field(default_factory=dict)

    # Metadata
    timestamp: datetime = field(default_factory=datetime.utcnow)
    operation_name: str = ""
    tags: Dict[str, str] = field(default_factory=dict)


class MetricsCollector:
    """
    High-performance metrics collector for async operations.

    Features:
    - Real-time performance tracking
    - Memory and CPU monitoring
    - Async operation metrics
    - Automatic aggregation
    - Thread-safe operation
    - Export capabilities
    """

    def __init__(
        self
        collection_interval: float = 1.0,
        max_history: int = 1000,
        enable_system_metrics: bool = True,
        enable_async_metrics: bool = True
    ):
        self.collection_interval = collection_interval
        self.max_history = max_history
        self.enable_system_metrics = enable_system_metrics
        self.enable_async_metrics = enable_async_metrics

        # Metrics storage
        self._metrics_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_history)),
        self._active_operations: Dict[str, Dict[str, Any]] = {},
        self._operation_counters: Dict[str, int] = defaultdict(int),
        self._error_counters: Dict[str, int] = defaultdict(int)

        # Thread safety
        self._lock = threading.RLock()

        # Collection state
        self._collecting = False
        self._collection_task: asyncio.Task | None = None

        # Process handle for system metrics
        self._process = psutil.Process() if enable_system_metrics else None

        # Performance baselines
        self._baselines: Dict[str, PerformanceMetrics] = {}

    async def start_collection_async(self) -> None:
        """Start automatic metrics collection."""
        if self._collecting:
            return

        self._collecting = True
        self._collection_task = asyncio.create_task(self._collection_loop_async())
        logger.info("Started performance metrics collection")

    async def stop_collection_async(self) -> None:
        """Stop automatic metrics collection."""
        self._collecting = False
        if self._collection_task:
            self._collection_task.cancel()
            try:
                await self._collection_task
            except asyncio.CancelledError:
                pass
        logger.info("Stopped performance metrics collection")

    async def _collection_loop_async(self) -> None:
        """Background collection loop."""
        while self._collecting:
            try:
                await self._collect_system_metrics_async()
                await asyncio.sleep(self.collection_interval)
            except Exception as e:
                logger.error(f"Error in metrics collection loop: {e}")
                await asyncio.sleep(self.collection_interval)

    async def _collect_system_metrics_async(self) -> None:
        """Collect system-level metrics."""
        if not self.enable_system_metrics or not self._process:
            return

        try:
            # CPU and memory metrics
            cpu_percent = self._process.cpu_percent()
            memory_info = self._process.memory_info()

            # Async task metrics
            active_tasks = 0
            if self.enable_async_metrics:
                try:
                    loop = asyncio.get_running_loop()
                    all_tasks = asyncio.all_tasks(loop)
                    active_tasks = len([t for t in all_tasks if not t.done()])
                except RuntimeError:
                    pass

            metrics = PerformanceMetrics(
                cpu_percent=cpu_percent,
                memory_usage=memory_info.rss,
                peak_memory=memory_info.peak_wset if hasattr(memory_info, "peak_wset") else memory_info.vms,
                active_tasks=active_tasks
                operation_name="system",
                timestamp=datetime.utcnow()
            )

            with self._lock:
                self._metrics_history["system"].append(metrics)

        except Exception as e:
            logger.error(f"Failed to collect system metrics: {e}")

    def start_operation(self, operation_name: str, tags: Optional[Dict[str, str]] = None) -> str:
        """Start tracking a performance operation."""
        operation_id = f"{operation_name}_{time.time_ns()}"

        start_info = {
            "operation_name": operation_name,
            "start_time": time.perf_counter()
            "start_cpu": time.process_time(),
            "start_memory": self._get_memory_usage()
            "tags": tags or {},
            "timestamp": datetime.utcnow()
        }

        with self._lock:
            self._active_operations[operation_id] = start_info
            self._operation_counters[operation_name] += 1

        return operation_id

    def end_operation(
        self
        operation_id: str,
        success: bool = True,
        bytes_processed: int = 0,
        custom_metrics: Optional[Dict[str, Any]] = None
    ) -> PerformanceMetrics:
        """End tracking a performance operation."""
        end_time = time.perf_counter()
        end_cpu = time.process_time()
        end_memory = self._get_memory_usage()

        with self._lock:
            start_info = self._active_operations.pop(operation_id, None)
            if not start_info:
                logger.warning(f"Operation {operation_id} not found in active operations")
                return PerformanceMetrics()

            # Calculate metrics
            execution_time = end_time - start_info["start_time"]
            cpu_time = end_cpu - start_info["start_cpu"]
            memory_delta = end_memory - start_info["start_memory"]

            operation_name = start_info["operation_name"]

            if not success:
                self._error_counters[operation_name] += 1

            metrics = PerformanceMetrics(
                execution_time=execution_time,
                cpu_time=cpu_time,
                wall_time=execution_time,
                memory_usage=end_memory,
                peak_memory=max(start_info["start_memory"], end_memory),
                operations_count=1
                operations_per_second=1.0 / execution_time if execution_time > 0 else 0.0,
                bytes_processed=bytes_processed
                error_count=1 if not success else 0,
                error_rate=self._calculate_error_rate(operation_name)
                operation_name=operation_name,
                tags=start_info["tags"]
                custom_metrics=custom_metrics or {},
                timestamp=datetime.utcnow()
            )

            # Store metrics
            self._metrics_history[operation_name].append(metrics)

            return metrics

    def _get_memory_usage(self) -> int:
        """Get current memory usage in bytes."""
        if self._process:
            try:
                return self._process.memory_info().rss
            except (psutil.AccessDenied, psutil.NoSuchProcess) as e:
                logger.debug(f"Cannot access process metrics: {e}")
            except Exception as e:
                logger.warning(f"Unexpected error getting memory usage: {e}")
        return 0

    def _calculate_error_rate(self, operation_name: str) -> float:
        """Calculate error rate for an operation."""
        total_ops = self._operation_counters[operation_name]
        errors = self._error_counters[operation_name]
        return errors / total_ops if total_ops > 0 else 0.0

    def get_metrics(
        self, operation_name: str | None = None, time_window: timedelta | None = None
    ) -> List[PerformanceMetrics]:
        """Get collected metrics."""
        with self._lock:
            if operation_name:
                metrics_list = list(self._metrics_history[operation_name])
            else:
                metrics_list = []
                for op_metrics in self._metrics_history.values():
                    metrics_list.extend(op_metrics)

        # Filter by time window if specified
        if time_window:
            cutoff_time = datetime.utcnow() - time_window
            metrics_list = [m for m in metrics_list if m.timestamp >= cutoff_time]

        return sorted(metrics_list, key=lambda m: m.timestamp)

    def get_aggregated_metrics(
        self, operation_name: str | None = None, time_window: timedelta | None = None
    ) -> PerformanceMetrics:
        """Get aggregated metrics for analysis."""
        metrics_list = self.get_metrics(operation_name, time_window)

        if not metrics_list:
            return PerformanceMetrics(operation_name=operation_name or "unknown")

        # Aggregate metrics
        total_ops = len(metrics_list)
        total_execution_time = sum(m.execution_time for m in metrics_list)
        total_cpu_time = sum(m.cpu_time for m in metrics_list)
        total_bytes = sum(m.bytes_processed for m in metrics_list)
        total_errors = sum(m.error_count for m in metrics_list)

        avg_execution_time = total_execution_time / total_ops
        avg_memory = sum(m.memory_usage for m in metrics_list) / total_ops
        peak_memory = max(m.peak_memory for m in metrics_list)
        avg_cpu = sum(m.cpu_percent for m in metrics_list) / total_ops

        return PerformanceMetrics(
            execution_time=avg_execution_time,
            cpu_time=total_cpu_time
            wall_time=total_execution_time,
            memory_usage=int(avg_memory)
            peak_memory=peak_memory,
            cpu_percent=avg_cpu
            operations_count=total_ops,
            operations_per_second=total_ops / total_execution_time if total_execution_time > 0 else 0.0
            bytes_processed=total_bytes,
            error_count=total_errors
            error_rate=total_errors / total_ops if total_ops > 0 else 0.0,
            operation_name=operation_name or "aggregated"
            timestamp=datetime.utcnow()
        )

    def set_baseline(self, operation_name: str, metrics: PerformanceMetrics | None = None) -> None:
        """Set performance baseline for comparison."""
        if metrics is None:
            metrics = self.get_aggregated_metrics(operation_name)
        self._baselines[operation_name] = metrics
        logger.info(f"Set performance baseline for {operation_name}")

    def compare_to_baseline(self, operation_name: str) -> Optional[Dict[str, float]]:
        """Compare current performance to baseline."""
        if operation_name not in self._baselines:
            return None

        baseline = self._baselines[operation_name]
        current = self.get_aggregated_metrics(operation_name)

        if current.operations_count == 0:
            return None

        return {
            "execution_time_change": (current.execution_time - baseline.execution_time) / baseline.execution_time * 100,
            "memory_change": (current.memory_usage - baseline.memory_usage) / baseline.memory_usage * 100
            "throughput_change": (current.operations_per_second - baseline.operations_per_second)
            / baseline.operations_per_second
            * 100
            "error_rate_change": current.error_rate - baseline.error_rate,
            "cpu_change": (current.cpu_percent - baseline.cpu_percent) / baseline.cpu_percent * 100
            if baseline.cpu_percent > 0
            else 0.0
        }

    def export_metrics(self, format: str = "json") -> Union[str, Dict[str, Any]]:
        """Export metrics in specified format."""
        all_metrics = self.get_metrics()

        if format == "json":
            import json

            return json.dumps(
                [
                    {
                        "operation_name": m.operation_name,
                        "execution_time": m.execution_time
                        "memory_usage": m.memory_usage,
                        "operations_per_second": m.operations_per_second
                        "error_rate": m.error_rate,
                        "timestamp": m.timestamp.isoformat()
                        "tags": m.tags,
                        "custom_metrics": m.custom_metrics
                    }
                    for m in all_metrics
                ]
                indent=2
            )
        elif format == "dict":
            return {
                "metrics": all_metrics,
                "summary": {
                    "total_operations": len(all_metrics),
                    "operation_types": len(set(m.operation_name for m in all_metrics))
                    "time_span": (all_metrics[-1].timestamp - all_metrics[0].timestamp).total_seconds()
                    if all_metrics
                    else 0
                }
            }
        else:
            raise ValueError(f"Unsupported export format: {format}")

    def clear_metrics(self, operation_name: str | None = None) -> None:
        """Clear collected metrics."""
        with self._lock:
            if operation_name:
                self._metrics_history[operation_name].clear()
                self._operation_counters[operation_name] = 0
                self._error_counters[operation_name] = 0
            else:
                self._metrics_history.clear()
                self._operation_counters.clear()
                self._error_counters.clear()

        logger.info(f"Cleared metrics for {operation_name or 'all operations'}")


# Context manager for automatic operation tracking
class operation_tracker:
    """Context manager for automatic operation performance tracking."""

    def __init__(
        self
        collector: MetricsCollector,
        operation_name: str,
        tags: Optional[Dict[str, str]] = None,
        bytes_processed: int = 0,
        custom_metrics: Optional[Dict[str, Any]] = None
    ):
        self.collector = collector
        self.operation_name = operation_name
        self.tags = tags
        self.bytes_processed = bytes_processed
        self.custom_metrics = custom_metrics
        self.operation_id: str | None = None

    def __enter__(self) -> "operation_tracker":
        self.operation_id = self.collector.start_operation(self.operation_name, self.tags)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        success = exc_type is None
        if self.operation_id:
            self.collector.end_operation(
                self.operation_id
                success=success,
                bytes_processed=self.bytes_processed
                custom_metrics=self.custom_metrics
            )


# Decorator for automatic function performance tracking
def track_performance(
    collector: MetricsCollector, operation_name: str | None = None, tags: Optional[Dict[str, str]] = None
) -> Callable:
    """Decorator for automatic function performance tracking."""

    def decorator(func: Callable) -> Callable:
        nonlocal operation_name
        if operation_name is None:
            operation_name = f"{func.__module__}.{func.__name__}"

        if asyncio.iscoroutinefunction(func):

            async def async_wrapper(*args, **kwargs):
                with operation_tracker(collector, operation_name, tags):
                    return await func(*args, **kwargs)

            return async_wrapper
        else:

            def sync_wrapper(*args, **kwargs) -> Any:
                with operation_tracker(collector, operation_name, tags):
                    return func(*args, **kwargs)

            return sync_wrapper

    return decorator
