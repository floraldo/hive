"""System-level performance monitoring with real-time metrics."""

import asyncio
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

import psutil
from hive_logging import get_logger

logger = get_logger(__name__)


@dataclass
class SystemMetrics:
    """Container for system performance metrics."""

    # CPU metrics
    cpu_percent: float = 0.0
    cpu_count: int = 0
    cpu_freq: float = 0.0
    load_average: List[float] = field(default_factory=list)

    # Memory metrics
    memory_total: int = 0
    memory_available: int = 0
    memory_used: int = 0
    memory_percent: float = 0.0
    swap_total: int = 0
    swap_used: int = 0
    swap_percent: float = 0.0

    # Disk metrics
    disk_total: int = 0
    disk_used: int = 0
    disk_free: int = 0
    disk_percent: float = 0.0
    disk_read_bytes: int = 0
    disk_write_bytes: int = 0
    disk_read_count: int = 0
    disk_write_count: int = 0

    # Network metrics
    network_bytes_sent: int = 0
    network_bytes_recv: int = 0
    network_packets_sent: int = 0
    network_packets_recv: int = 0
    network_errors_in: int = 0
    network_errors_out: int = 0

    # Process metrics
    process_count: int = 0
    thread_count: int = 0
    open_files: int = 0
    connections: int = 0

    # Python-specific metrics
    python_memory_rss: int = 0
    python_memory_vms: int = 0
    python_cpu_percent: float = 0.0
    python_threads: int = 0
    python_open_files: int = 0

    # Async metrics
    active_tasks: int = 0
    pending_tasks: int = 0
    running_loops: int = 0

    # Metadata
    timestamp: datetime = field(default_factory=datetime.utcnow)
    hostname: str = ""
    platform: str = ""


class SystemMonitor:
    """
    Real-time system performance monitor.

    Features:
    - Comprehensive system metrics collection
    - Real-time monitoring with configurable intervals
    - Threshold-based alerting
    - Historical data retention
    - Performance trend analysis
    - Resource usage prediction
    """

    def __init__(
        self,
        collection_interval: float = 1.0,
        max_history: int = 3600,  # 1 hour at 1-second intervals
        enable_alerts: bool = True,
        alert_thresholds: Optional[Dict[str, float]] = None,
    ):
        self.collection_interval = collection_interval
        self.max_history = max_history
        self.enable_alerts = enable_alerts

        # Default alert thresholds
        self.alert_thresholds = alert_thresholds or {
            "cpu_percent": 80.0,
            "memory_percent": 85.0,
            "disk_percent": 90.0,
            "swap_percent": 50.0,
        }

        # Metrics storage
        self._metrics_history: deque = deque(maxlen=max_history)
        self._alert_callbacks: List[Callable] = []

        # Monitoring state
        self._monitoring = False
        self._monitor_task: Optional[asyncio.Task] = None

        # System information
        self._hostname = psutil.os.getpid()
        self._platform = psutil.os.name
        self._boot_time = psutil.boot_time()

        # Process handle for Python-specific metrics
        self._process = psutil.Process()

        # Previous values for rate calculations
        self._prev_disk_io: Optional[Any] = None
        self._prev_network_io: Optional[Any] = None
        self._prev_timestamp: Optional[float] = None

    async def start_monitoring_async(self) -> None:
        """Start real-time system monitoring."""
        if self._monitoring:
            return

        self._monitoring = True
        self._monitor_task = asyncio.create_task(self._monitoring_loop_async())
        logger.info(f"Started system monitoring with {self.collection_interval}s interval")

    async def stop_monitoring_async(self) -> None:
        """Stop system monitoring."""
        self._monitoring = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        logger.info("Stopped system monitoring")

    async def _monitoring_loop_async(self) -> None:
        """Main monitoring loop."""
        while self._monitoring:
            try:
                metrics = await self._collect_system_metrics_async()
                self._metrics_history.append(metrics)

                if self.enable_alerts:
                    await self._check_alerts_async(metrics)

                await asyncio.sleep(self.collection_interval)

            except Exception as e:
                logger.error(f"Error in system monitoring loop: {e}")
                await asyncio.sleep(self.collection_interval)

    async def _collect_system_metrics_async(self) -> SystemMetrics:
        """Collect comprehensive system metrics."""
        current_time = time.time()

        # CPU metrics
        cpu_percent = psutil.cpu_percent(interval=None)
        cpu_count = psutil.cpu_count()
        cpu_freq = psutil.cpu_freq().current if psutil.cpu_freq() else 0.0

        try:
            load_avg = list(psutil.getloadavg()) if hasattr(psutil, "getloadavg") else []
        except AttributeError:
            load_avg = []

        # Memory metrics
        memory = psutil.virtual_memory()
        swap = psutil.swap_memory()

        # Disk metrics
        disk_usage = psutil.disk_usage("/")
        disk_io = psutil.disk_io_counters()

        # Calculate disk rates
        disk_read_rate = 0
        disk_write_rate = 0
        if self._prev_disk_io and self._prev_timestamp:
            time_delta = current_time - self._prev_timestamp
            if time_delta > 0:
                disk_read_rate = (disk_io.read_bytes - self._prev_disk_io.read_bytes) / time_delta
                disk_write_rate = (disk_io.write_bytes - self._prev_disk_io.write_bytes) / time_delta

        # Network metrics
        network_io = psutil.net_io_counters()

        # Process metrics
        process_count = len(psutil.pids())

        # Python process metrics
        python_memory = self._process.memory_info()
        python_cpu = self._process.cpu_percent()

        try:
            python_threads = self._process.num_threads()
            python_open_files = len(self._process.open_files())
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            python_threads = 0
            python_open_files = 0

        # Async metrics
        active_tasks = 0
        pending_tasks = 0
        running_loops = 0

        try:
            loop = asyncio.get_running_loop()
            all_tasks = asyncio.all_tasks(loop)
            active_tasks = len([t for t in all_tasks if not t.done()])
            pending_tasks = len([t for t in all_tasks if not t.done() and not t.cancelled()])
            running_loops = 1
        except RuntimeError:
            pass

        # Create metrics object
        metrics = SystemMetrics(
            # CPU
            cpu_percent=cpu_percent,
            cpu_count=cpu_count,
            cpu_freq=cpu_freq,
            load_average=load_avg,
            # Memory
            memory_total=memory.total,
            memory_available=memory.available,
            memory_used=memory.used,
            memory_percent=memory.percent,
            swap_total=swap.total,
            swap_used=swap.used,
            swap_percent=swap.percent,
            # Disk
            disk_total=disk_usage.total,
            disk_used=disk_usage.used,
            disk_free=disk_usage.free,
            disk_percent=disk_usage.used / disk_usage.total * 100,
            disk_read_bytes=disk_io.read_bytes,
            disk_write_bytes=disk_io.write_bytes,
            disk_read_count=disk_io.read_count,
            disk_write_count=disk_io.write_count,
            # Network
            network_bytes_sent=network_io.bytes_sent,
            network_bytes_recv=network_io.bytes_recv,
            network_packets_sent=network_io.packets_sent,
            network_packets_recv=network_io.packets_recv,
            network_errors_in=network_io.errin,
            network_errors_out=network_io.errout,
            # Process
            process_count=process_count,
            thread_count=sum(p.num_threads() for p in psutil.process_iter(["num_threads"]) if p.info["num_threads"]),
            # Python process
            python_memory_rss=python_memory.rss,
            python_memory_vms=python_memory.vms,
            python_cpu_percent=python_cpu,
            python_threads=python_threads,
            python_open_files=python_open_files,
            # Async
            active_tasks=active_tasks,
            pending_tasks=pending_tasks,
            running_loops=running_loops,
            # Metadata
            timestamp=datetime.utcnow(),
            hostname=str(self._hostname),
            platform=self._platform,
        )

        # Update previous values
        self._prev_disk_io = disk_io
        self._prev_network_io = network_io
        self._prev_timestamp = current_time

        return metrics

    async def _check_alerts_async(self, metrics: SystemMetrics) -> None:
        """Check metrics against alert thresholds."""
        alerts = []

        if metrics.cpu_percent > self.alert_thresholds.get("cpu_percent", 80.0):
            alerts.append(f"High CPU usage: {metrics.cpu_percent:.1f}%")

        if metrics.memory_percent > self.alert_thresholds.get("memory_percent", 85.0):
            alerts.append(f"High memory usage: {metrics.memory_percent:.1f}%")

        if metrics.disk_percent > self.alert_thresholds.get("disk_percent", 90.0):
            alerts.append(f"High disk usage: {metrics.disk_percent:.1f}%")

        if metrics.swap_percent > self.alert_thresholds.get("swap_percent", 50.0):
            alerts.append(f"High swap usage: {metrics.swap_percent:.1f}%")

        if alerts:
            await self._trigger_alerts_async(alerts, metrics)

    async def _trigger_alerts_async(self, alerts: List[str], metrics: SystemMetrics) -> None:
        """Trigger alert callbacks."""
        for callback in self._alert_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(alerts, metrics)
                else:
                    callback(alerts, metrics)
            except Exception as e:
                logger.error(f"Error in alert callback: {e}")

    def add_alert_callback(self, callback: Callable) -> None:
        """Add alert callback function."""
        self._alert_callbacks.append(callback)
        logger.info(f"Added alert callback: {callback.__name__}")

    def get_current_metrics(self) -> Optional[SystemMetrics]:
        """Get the most recent system metrics."""
        return self._metrics_history[-1] if self._metrics_history else None

    def get_metrics_history(
        self, time_window: Optional[timedelta] = None, max_points: Optional[int] = None
    ) -> List[SystemMetrics]:
        """Get historical metrics data."""
        metrics_list = list(self._metrics_history)

        # Filter by time window
        if time_window:
            cutoff_time = datetime.utcnow() - time_window
            metrics_list = [m for m in metrics_list if m.timestamp >= cutoff_time]

        # Limit number of points
        if max_points and len(metrics_list) > max_points:
            step = len(metrics_list) // max_points
            metrics_list = metrics_list[::step]

        return metrics_list

    def get_average_metrics(self, time_window: timedelta) -> Optional[SystemMetrics]:
        """Get average metrics over a time window."""
        metrics_list = self.get_metrics_history(time_window)

        if not metrics_list:
            return None

        count = len(metrics_list)

        return SystemMetrics(
            cpu_percent=sum(m.cpu_percent for m in metrics_list) / count,
            memory_percent=sum(m.memory_percent for m in metrics_list) / count,
            disk_percent=sum(m.disk_percent for m in metrics_list) / count,
            swap_percent=sum(m.swap_percent for m in metrics_list) / count,
            active_tasks=sum(m.active_tasks for m in metrics_list) / count,
            python_cpu_percent=sum(m.python_cpu_percent for m in metrics_list) / count,
            python_memory_rss=int(sum(m.python_memory_rss for m in metrics_list) / count),
            timestamp=datetime.utcnow(),
            hostname=metrics_list[0].hostname,
            platform=metrics_list[0].platform,
        )

    def get_peak_metrics(self, time_window: timedelta) -> Optional[SystemMetrics]:
        """Get peak metrics over a time window."""
        metrics_list = self.get_metrics_history(time_window)

        if not metrics_list:
            return None

        peak_cpu = max(m.cpu_percent for m in metrics_list)
        peak_memory = max(m.memory_percent for m in metrics_list)
        peak_disk = max(m.disk_percent for m in metrics_list)
        peak_tasks = max(m.active_tasks for m in metrics_list)

        # Find the metric with peak CPU for timestamp
        peak_metric = max(metrics_list, key=lambda m: m.cpu_percent)

        return SystemMetrics(
            cpu_percent=peak_cpu,
            memory_percent=peak_memory,
            disk_percent=peak_disk,
            active_tasks=peak_tasks,
            timestamp=peak_metric.timestamp,
            hostname=peak_metric.hostname,
            platform=peak_metric.platform,
        )

    def analyze_trends(self, time_window: timedelta) -> Dict[str, float]:
        """Analyze performance trends over time."""
        metrics_list = self.get_metrics_history(time_window)

        if len(metrics_list) < 2:
            return {}

        # Calculate trends (simple linear regression slope)
        def calculate_trend(values: List[float]) -> float:
            n = len(values)
            if n < 2:
                return 0.0

            x_sum = sum(range(n))
            y_sum = sum(values)
            xy_sum = sum(i * values[i] for i in range(n))
            x2_sum = sum(i * i for i in range(n))

            return (n * xy_sum - x_sum * y_sum) / (n * x2_sum - x_sum * x_sum)

        return {
            "cpu_trend": calculate_trend([m.cpu_percent for m in metrics_list]),
            "memory_trend": calculate_trend([m.memory_percent for m in metrics_list]),
            "disk_trend": calculate_trend([m.disk_percent for m in metrics_list]),
            "tasks_trend": calculate_trend([float(m.active_tasks) for m in metrics_list]),
        }

    def predict_resource_exhaustion(self, time_window: timedelta) -> Dict[str, Optional[datetime]]:
        """Predict when resources might be exhausted based on trends."""
        trends = self.analyze_trends(time_window)
        current = self.get_current_metrics()

        if not current:
            return {}

        predictions = {}

        # CPU prediction
        cpu_trend = trends.get("cpu_trend", 0)
        if cpu_trend > 0 and current.cpu_percent < 100:
            time_to_100 = (100 - current.cpu_percent) / cpu_trend
            predictions["cpu_exhaustion"] = current.timestamp + timedelta(seconds=time_to_100)
        else:
            predictions["cpu_exhaustion"] = None

        # Memory prediction
        memory_trend = trends.get("memory_trend", 0)
        if memory_trend > 0 and current.memory_percent < 100:
            time_to_100 = (100 - current.memory_percent) / memory_trend
            predictions["memory_exhaustion"] = current.timestamp + timedelta(seconds=time_to_100)
        else:
            predictions["memory_exhaustion"] = None

        # Disk prediction
        disk_trend = trends.get("disk_trend", 0)
        if disk_trend > 0 and current.disk_percent < 100:
            time_to_100 = (100 - current.disk_percent) / disk_trend
            predictions["disk_exhaustion"] = current.timestamp + timedelta(seconds=time_to_100)
        else:
            predictions["disk_exhaustion"] = None

        return predictions

    def export_metrics(self, time_window: Optional[timedelta] = None, format: str = "json") -> str:
        """Export metrics data in specified format."""
        metrics_list = self.get_metrics_history(time_window)

        if format == "json":
            import json

            return json.dumps(
                [
                    {
                        "timestamp": m.timestamp.isoformat(),
                        "cpu_percent": m.cpu_percent,
                        "memory_percent": m.memory_percent,
                        "disk_percent": m.disk_percent,
                        "active_tasks": m.active_tasks,
                        "python_memory_mb": m.python_memory_rss // (1024 * 1024),
                    }
                    for m in metrics_list
                ],
                indent=2,
            )
        elif format == "csv":
            import csv
            import io

            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(["timestamp", "cpu_percent", "memory_percent", "disk_percent", "active_tasks"])
            for m in metrics_list:
                writer.writerow(
                    [m.timestamp.isoformat(), m.cpu_percent, m.memory_percent, m.disk_percent, m.active_tasks]
                )
            return output.getvalue()
        else:
            raise ValueError(f"Unsupported export format: {format}")

    def clear_history(self) -> None:
        """Clear metrics history."""
        self._metrics_history.clear()
        logger.info("Cleared system metrics history")
