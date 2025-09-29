"""
Advanced telemetry and observability for AI operations.

Provides comprehensive monitoring, tracing, and analytics for
AI model usage, performance, and behavior patterns.
"""

import asyncio
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

from hive_logging import get_logger

logger = get_logger(__name__)


class TelemetryLevel(Enum):
    """Telemetry collection levels."""

    DISABLED = "disabled"
    BASIC = "basic"
    DETAILED = "detailed"
    COMPREHENSIVE = "comprehensive"


class EventType(Enum):
    """Types of telemetry events."""

    MODEL_REQUEST = "model_request"
    MODEL_RESPONSE = "model_response"
    EMBEDDING_GENERATION = "embedding_generation"
    VECTOR_OPERATION = "vector_operation"
    AGENT_EXECUTION = "agent_execution"
    WORKFLOW_STEP = "workflow_step"
    ERROR_OCCURRENCE = "error_occurrence"
    PERFORMANCE_METRIC = "performance_metric"
    COST_EVENT = "cost_event"
    SECURITY_EVENT = "security_event"


@dataclass
class TelemetryEvent:
    """Single telemetry event with comprehensive metadata."""

    event_id: str
    event_type: EventType
    timestamp: datetime
    component: str
    operation: str
    duration_ms: Optional[float] = None
    success: bool = True
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Model-specific fields
    model_name: Optional[str] = None
    provider: Optional[str] = None
    tokens_used: Optional[int] = None
    estimated_cost: Optional[float] = None

    # Performance fields
    memory_usage_mb: Optional[float] = None
    cpu_percent: Optional[float] = None
    network_latency_ms: Optional[float] = None

    # Security fields
    security_risk_level: Optional[str] = None
    validation_result: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for serialization."""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "timestamp": self.timestamp.isoformat(),
            "component": self.component,
            "operation": self.operation,
            "duration_ms": self.duration_ms,
            "success": self.success,
            "error_message": self.error_message,
            "metadata": self.metadata,
            "model_name": self.model_name,
            "provider": self.provider,
            "tokens_used": self.tokens_used,
            "estimated_cost": self.estimated_cost,
            "memory_usage_mb": self.memory_usage_mb,
            "cpu_percent": self.cpu_percent,
            "network_latency_ms": self.network_latency_ms,
            "security_risk_level": self.security_risk_level,
            "validation_result": self.validation_result,
        }


class TelemetryBuffer:
    """High-performance circular buffer for telemetry events."""

    def __init__(self, max_size: int = 10000):
        """Initialize telemetry buffer.

        Args:
            max_size: Maximum number of events to buffer.
        """
        self.max_size = max_size
        self.events: List[TelemetryEvent] = []
        self.current_index = 0
        self.total_events = 0
        self._lock = asyncio.Lock()

    async def add_event_async(self, event: TelemetryEvent) -> None:
        """Add event to buffer with thread safety.

        Args:
            event: Telemetry event to add.
        """
        async with self._lock:
            if len(self.events) < self.max_size:
                self.events.append(event)
            else:
                # Circular buffer behavior
                self.events[self.current_index] = event
                self.current_index = (self.current_index + 1) % self.max_size

            self.total_events += 1

    async def get_recent_events_async(
        self, count: int = 100, event_type: Optional[EventType] = None
    ) -> List[TelemetryEvent]:
        """Get recent events from buffer.

        Args:
            count: Maximum number of events to return.
            event_type: Filter by specific event type.

        Returns:
            List of recent telemetry events.
        """
        async with self._lock:
            events = self.events.copy()

        # Filter by event type if specified
        if event_type:
            events = [e for e in events if e.event_type == event_type]

        # Sort by timestamp and return most recent
        events.sort(key=lambda e: e.timestamp, reverse=True)
        return events[:count]

    async def get_buffer_stats_async(self) -> Dict[str, Any]:
        """Get buffer statistics.

        Returns:
            Dictionary with buffer statistics.
        """
        async with self._lock:
            event_count = len(self.events)
            if event_count == 0:
                return {"event_count": 0, "total_events": self.total_events, "buffer_utilization": 0.0}

            # Calculate event type distribution
            type_counts = {}
            for event in self.events:
                event_type = event.event_type.value
                type_counts[event_type] = type_counts.get(event_type, 0) + 1

            # Calculate time range
            timestamps = [e.timestamp for e in self.events]
            time_range_hours = 0
            if len(timestamps) > 1:
                time_range = max(timestamps) - min(timestamps)
                time_range_hours = time_range.total_seconds() / 3600

            return {
                "event_count": event_count,
                "total_events": self.total_events,
                "buffer_utilization": event_count / self.max_size,
                "event_types": type_counts,
                "time_range_hours": time_range_hours,
                "events_per_hour": event_count / max(time_range_hours, 0.1),
            }


class TelemetryCollector:
    """Advanced telemetry collection and analysis system."""

    def __init__(
        self,
        level: TelemetryLevel = TelemetryLevel.BASIC,
        buffer_size: int = 10000,
        export_interval_seconds: int = 300,
        export_path: Optional[Path] = None,
    ):
        """Initialize telemetry collector.

        Args:
            level: Telemetry collection level.
            buffer_size: Maximum events in buffer.
            export_interval_seconds: How often to export events.
            export_path: Path for exporting telemetry data.
        """
        self.level = level
        self.buffer = TelemetryBuffer(buffer_size)
        self.export_interval = export_interval_seconds
        self.export_path = export_path or Path("telemetry_export")

        # Event handlers
        self.event_handlers: List[Callable[[TelemetryEvent], None]] = []

        # Background export task
        self.export_task: Optional[asyncio.Task] = None
        self.running = False

        # Performance tracking
        self.collection_start_time = datetime.utcnow()
        self.events_collected = 0

    async def start_async(self) -> None:
        """Start telemetry collection."""
        if self.level == TelemetryLevel.DISABLED:
            logger.info("Telemetry collection disabled")
            return

        self.running = True
        self.collection_start_time = datetime.utcnow()

        # Start background export task
        if self.export_interval > 0:
            self.export_task = asyncio.create_task(self._export_loop_async())

        logger.info(f"Telemetry collection started (level: {self.level.value})")

    async def stop_async(self) -> None:
        """Stop telemetry collection."""
        self.running = False

        if self.export_task:
            self.export_task.cancel()
            try:
                await self.export_task
            except asyncio.CancelledError:
                pass

        # Final export
        await self.export_events_async()
        logger.info("Telemetry collection stopped")

    async def record_event_async(self, event: TelemetryEvent) -> None:
        """Record a telemetry event.

        Args:
            event: Event to record.
        """
        if self.level == TelemetryLevel.DISABLED or not self.running:
            return

        # Add to buffer
        await self.buffer.add_event_async(event)
        self.events_collected += 1

        # Notify handlers
        for handler in self.event_handlers:
            try:
                handler(event)
            except Exception as e:
                logger.warning(f"Event handler failed: {e}")

    async def record_model_request_async(
        self,
        component: str,
        model_name: str,
        provider: str,
        prompt_length: int,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Record model request event.

        Args:
            component: Component making the request.
            model_name: Name of the model.
            provider: Model provider.
            prompt_length: Length of input prompt.
            metadata: Additional metadata.

        Returns:
            Event ID for correlation.
        """
        event_id = f"req_{int(time.time() * 1000)}_{id(self)}"

        event = TelemetryEvent(
            event_id=event_id,
            event_type=EventType.MODEL_REQUEST,
            timestamp=datetime.utcnow(),
            component=component,
            operation="model_request",
            model_name=model_name,
            provider=provider,
            metadata={"prompt_length": prompt_length, **(metadata or {})},
        )

        await self.record_event_async(event)
        return event_id

    async def record_model_response_async(
        self,
        request_id: str,
        component: str,
        model_name: str,
        provider: str,
        duration_ms: float,
        tokens_used: int,
        estimated_cost: float,
        success: bool = True,
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record model response event.

        Args:
            request_id: Correlation ID from request.
            component: Component that made the request.
            model_name: Name of the model.
            provider: Model provider.
            duration_ms: Request duration in milliseconds.
            tokens_used: Number of tokens consumed.
            estimated_cost: Estimated cost of the request.
            success: Whether the request succeeded.
            error_message: Error message if failed.
            metadata: Additional metadata.
        """
        event = TelemetryEvent(
            event_id=f"resp_{request_id}",
            event_type=EventType.MODEL_RESPONSE,
            timestamp=datetime.utcnow(),
            component=component,
            operation="model_response",
            duration_ms=duration_ms,
            success=success,
            error_message=error_message,
            model_name=model_name,
            provider=provider,
            tokens_used=tokens_used,
            estimated_cost=estimated_cost,
            metadata={"request_id": request_id, **(metadata or {})},
        )

        await self.record_event_async(event)

    async def record_performance_metric_async(
        self,
        component: str,
        operation: str,
        duration_ms: float,
        memory_usage_mb: Optional[float] = None,
        cpu_percent: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record performance metric event.

        Args:
            component: Component being measured.
            operation: Operation being measured.
            duration_ms: Operation duration.
            memory_usage_mb: Memory usage in MB.
            cpu_percent: CPU usage percentage.
            metadata: Additional metadata.
        """
        event = TelemetryEvent(
            event_id=f"perf_{int(time.time() * 1000)}_{id(self)}",
            event_type=EventType.PERFORMANCE_METRIC,
            timestamp=datetime.utcnow(),
            component=component,
            operation=operation,
            duration_ms=duration_ms,
            memory_usage_mb=memory_usage_mb,
            cpu_percent=cpu_percent,
            metadata=metadata or {},
        )

        await self.record_event_async(event)

    async def record_security_event_async(
        self,
        component: str,
        operation: str,
        risk_level: str,
        validation_result: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record security event.

        Args:
            component: Component where security event occurred.
            operation: Security operation performed.
            risk_level: Risk level (low, medium, high).
            validation_result: Result of validation.
            metadata: Additional metadata.
        """
        event = TelemetryEvent(
            event_id=f"sec_{int(time.time() * 1000)}_{id(self)}",
            event_type=EventType.SECURITY_EVENT,
            timestamp=datetime.utcnow(),
            component=component,
            operation=operation,
            security_risk_level=risk_level,
            validation_result=validation_result,
            metadata=metadata or {},
        )

        await self.record_event_async(event)

    async def get_analytics_async(self, time_window_hours: int = 24) -> Dict[str, Any]:
        """Get comprehensive analytics for time window.

        Args:
            time_window_hours: Time window for analysis.

        Returns:
            Analytics dictionary with insights.
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=time_window_hours)

        # Get events in time window
        all_events = await self.buffer.get_recent_events_async(count=10000)
        window_events = [e for e in all_events if e.timestamp >= cutoff_time]

        if not window_events:
            return {"message": "No events in time window"}

        # Calculate analytics
        analytics = {
            "time_window_hours": time_window_hours,
            "total_events": len(window_events),
            "event_types": self._analyze_event_types(window_events),
            "performance": self._analyze_performance(window_events),
            "model_usage": self._analyze_model_usage(window_events),
            "error_rates": self._analyze_errors(window_events),
            "cost_analysis": self._analyze_costs(window_events),
            "security_summary": self._analyze_security(window_events),
        }

        return analytics

    def _analyze_event_types(self, events: List[TelemetryEvent]) -> Dict[str, Any]:
        """Analyze event type distribution."""
        type_counts = {}
        for event in events:
            event_type = event.event_type.value
            type_counts[event_type] = type_counts.get(event_type, 0) + 1

        total = len(events)
        return {"counts": type_counts, "percentages": {k: (v / total) * 100 for k, v in type_counts.items()}}

    def _analyze_performance(self, events: List[TelemetryEvent]) -> Dict[str, Any]:
        """Analyze performance metrics."""
        perf_events = [e for e in events if e.duration_ms is not None]

        if not perf_events:
            return {"message": "No performance data available"}

        durations = [e.duration_ms for e in perf_events]

        # Calculate percentiles
        durations.sort()
        n = len(durations)

        return {
            "total_operations": len(perf_events),
            "avg_duration_ms": sum(durations) / n,
            "median_duration_ms": durations[n // 2],
            "p95_duration_ms": durations[int(n * 0.95)] if n > 0 else 0,
            "p99_duration_ms": durations[int(n * 0.99)] if n > 0 else 0,
            "min_duration_ms": min(durations),
            "max_duration_ms": max(durations),
        }

    def _analyze_model_usage(self, events: List[TelemetryEvent]) -> Dict[str, Any]:
        """Analyze model usage patterns."""
        model_events = [e for e in events if e.model_name is not None]

        if not model_events:
            return {"message": "No model usage data available"}

        # Model usage counts
        model_counts = {}
        provider_counts = {}
        total_tokens = 0

        for event in model_events:
            model_counts[event.model_name] = model_counts.get(event.model_name, 0) + 1
            if event.provider:
                provider_counts[event.provider] = provider_counts.get(event.provider, 0) + 1
            if event.tokens_used:
                total_tokens += event.tokens_used

        return {
            "total_requests": len(model_events),
            "total_tokens": total_tokens,
            "model_distribution": model_counts,
            "provider_distribution": provider_counts,
            "avg_tokens_per_request": total_tokens / len(model_events) if model_events else 0,
        }

    def _analyze_errors(self, events: List[TelemetryEvent]) -> Dict[str, Any]:
        """Analyze error patterns."""
        total_events = len(events)
        error_events = [e for e in events if not e.success]

        if not error_events:
            return {"error_rate": 0.0, "total_errors": 0, "message": "No errors in time window"}

        # Error analysis
        error_components = {}
        error_operations = {}

        for event in error_events:
            error_components[event.component] = error_components.get(event.component, 0) + 1
            error_operations[event.operation] = error_operations.get(event.operation, 0) + 1

        return {
            "error_rate": (len(error_events) / total_events) * 100,
            "total_errors": len(error_events),
            "error_by_component": error_components,
            "error_by_operation": error_operations,
        }

    def _analyze_costs(self, events: List[TelemetryEvent]) -> Dict[str, Any]:
        """Analyze cost patterns."""
        cost_events = [e for e in events if e.estimated_cost is not None]

        if not cost_events:
            return {"message": "No cost data available"}

        total_cost = sum(e.estimated_cost for e in cost_events)
        cost_by_model = {}

        for event in cost_events:
            if event.model_name:
                cost_by_model[event.model_name] = cost_by_model.get(event.model_name, 0) + event.estimated_cost

        return {
            "total_cost": total_cost,
            "cost_by_model": cost_by_model,
            "avg_cost_per_request": total_cost / len(cost_events),
        }

    def _analyze_security(self, events: List[TelemetryEvent]) -> Dict[str, Any]:
        """Analyze security events."""
        security_events = [e for e in events if e.event_type == EventType.SECURITY_EVENT]

        if not security_events:
            return {"message": "No security events in time window"}

        risk_levels = {}
        for event in security_events:
            risk_level = event.security_risk_level or "unknown"
            risk_levels[risk_level] = risk_levels.get(risk_level, 0) + 1

        return {"total_security_events": len(security_events), "risk_level_distribution": risk_levels}

    async def export_events_async(self) -> Path:
        """Export events to file.

        Returns:
            Path to exported file.
        """
        if self.level == TelemetryLevel.DISABLED:
            return None

        # Get all events
        events = await self.buffer.get_recent_events_async(count=10000)

        # Create export data
        export_data = {
            "export_timestamp": datetime.utcnow().isoformat(),
            "collection_level": self.level.value,
            "events_count": len(events),
            "events": [event.to_dict() for event in events],
        }

        # Ensure export directory exists
        self.export_path.mkdir(parents=True, exist_ok=True)

        # Export to timestamped file
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        export_file = self.export_path / f"telemetry_{timestamp}.json"

        with open(export_file, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2)

        logger.info(f"Exported {len(events)} telemetry events to {export_file}")
        return export_file

    async def _export_loop_async(self) -> None:
        """Background export loop."""
        while self.running:
            try:
                await asyncio.sleep(self.export_interval)
                if self.running:
                    await self.export_events_async()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Export loop error: {e}")

    def add_event_handler(self, handler: Callable[[TelemetryEvent], None]) -> None:
        """Add event handler for real-time processing.

        Args:
            handler: Function to call for each event.
        """
        self.event_handlers.append(handler)

    async def get_collector_stats_async(self) -> Dict[str, Any]:
        """Get collector statistics.

        Returns:
            Dictionary with collector statistics.
        """
        buffer_stats = await self.buffer.get_buffer_stats_async()

        uptime = datetime.utcnow() - self.collection_start_time

        return {
            "telemetry_level": self.level.value,
            "running": self.running,
            "uptime_hours": uptime.total_seconds() / 3600,
            "events_collected": self.events_collected,
            "events_per_hour": self.events_collected / max(uptime.total_seconds() / 3600, 0.1),
            "buffer_stats": buffer_stats,
            "export_interval_seconds": self.export_interval,
            "export_path": str(self.export_path),
        }


# Global telemetry collector instance
_global_collector: Optional[TelemetryCollector] = None


def get_telemetry_collector() -> Optional[TelemetryCollector]:
    """Get global telemetry collector instance.

    Returns:
        Global collector or None if not initialized.
    """
    return _global_collector


def initialize_telemetry(level: TelemetryLevel = TelemetryLevel.BASIC, **kwargs) -> TelemetryCollector:
    """Initialize global telemetry collector.

    Args:
        level: Telemetry collection level.
        **kwargs: Additional collector arguments.

    Returns:
        Initialized telemetry collector.
    """
    global _global_collector

    _global_collector = TelemetryCollector(level=level, **kwargs)
    logger.info(f"Global telemetry collector initialized (level: {level.value})")

    return _global_collector


async def start_telemetry_async() -> None:
    """Start global telemetry collection."""
    if _global_collector:
        await _global_collector.start_async()


async def stop_telemetry_async() -> None:
    """Stop global telemetry collection."""
    if _global_collector:
        await _global_collector.stop_async()
