"""Distributed Tracing for Workflow Execution.

Implements trace_id propagation across workflow phases for end-to-end observability.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from hive_logging import get_logger

logger = get_logger(__name__)


class SpanStatus(Enum):
    """Span execution status."""

    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    ERROR = "error"


@dataclass
class Span:
    """A single traced operation within a workflow.

    Represents a phase or operation with timing, status, and metadata.
    """

    span_id: str
    trace_id: str
    parent_span_id: str | None
    operation: str
    started_at: datetime
    ended_at: datetime | None = None
    status: SpanStatus = SpanStatus.IN_PROGRESS
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def duration_ms(self) -> float:
        """Get span duration in milliseconds."""
        if self.ended_at is None:
            return (datetime.now() - self.started_at).total_seconds() * 1000
        return (self.ended_at - self.started_at).total_seconds() * 1000

    def finish(self, status: SpanStatus = SpanStatus.SUCCESS, error: str | None = None) -> None:
        """Mark span as finished.

        Args:
            status: Final status (SUCCESS or ERROR)
            error: Error message if status is ERROR
        """
        self.ended_at = datetime.now()
        self.status = status
        self.error = error


@dataclass
class Trace:
    """Complete trace of a workflow execution.

    Contains all spans and provides trace-level metrics.
    """

    trace_id: str
    workflow_id: str
    started_at: datetime
    ended_at: datetime | None = None
    spans: list[Span] = field(default_factory=list)

    @property
    def total_duration_ms(self) -> float:
        """Get total trace duration in milliseconds."""
        if self.ended_at is None:
            return (datetime.now() - self.started_at).total_seconds() * 1000
        return (self.ended_at - self.started_at).total_seconds() * 1000

    @property
    def is_complete(self) -> bool:
        """Check if all spans are finished."""
        return all(span.ended_at is not None for span in self.spans)

    @property
    def has_errors(self) -> bool:
        """Check if any span has errors."""
        return any(span.status == SpanStatus.ERROR for span in self.spans)

    def get_critical_path(self) -> list[Span]:
        """Get the critical path (longest sequential chain) through the trace.

        Returns:
            List of spans representing the critical path
        """
        if not self.spans:
            return []

        # Build parent-child relationships
        children_map: dict[str | None, list[Span]] = defaultdict(list)
        for span in self.spans:
            children_map[span.parent_span_id].append(span)

        def get_path_duration(span: Span) -> float:
            """Recursively calculate path duration from this span."""
            child_paths = [get_path_duration(child) for child in children_map.get(span.span_id, [])]
            max_child_duration = max(child_paths) if child_paths else 0.0
            return span.duration_ms + max_child_duration

        # Find root spans (no parent)
        root_spans = children_map[None]
        if not root_spans:
            return []

        # Find the root span with longest critical path
        critical_root = max(root_spans, key=get_path_duration)

        # Build the critical path
        path = [critical_root]
        current = critical_root
        while children_map.get(current.span_id):
            children = children_map[current.span_id]
            # Pick child with longest path
            current = max(children, key=get_path_duration)
            path.append(current)

        return path


class WorkflowTracer:
    """Distributed tracing for workflow execution.

    Manages trace and span lifecycle with automatic context propagation.

    Example:
        tracer = WorkflowTracer()

        # Start workflow trace
        trace_id = tracer.start_trace(workflow_id="wf_123")

        # Start phase span
        span_id = tracer.start_span(
            trace_id=trace_id,
            operation="e2e_analysis",
            metadata={"feature": "login form"}
        )

        try:
            # ... execute phase
            tracer.finish_span(span_id, status=SpanStatus.SUCCESS)
        except Exception as e:
            tracer.finish_span(span_id, status=SpanStatus.ERROR, error=str(e))

        # Finish trace
        trace = tracer.finish_trace(trace_id)
    """

    def __init__(self, auto_cleanup: bool = True, max_completed_traces: int = 100, cleanup_interval: int = 100):
        """Initialize workflow tracer.
        
        Args:
            auto_cleanup: Enable automatic cleanup of old traces (default: True)
            max_completed_traces: Maximum number of completed traces to keep (default: 100)
            cleanup_interval: Cleanup every N traces (default: 100)
        """
        self._traces: dict[str, Trace] = {}
        self._spans: dict[str, Span] = {}
        self._active_spans: dict[str, str] = {}  # trace_id -> active_span_id
        self.logger = logger

        # Automatic cleanup configuration
        self._auto_cleanup = auto_cleanup
        self._max_completed_traces = max_completed_traces
        self._cleanup_interval = cleanup_interval
        self._trace_counter = 0

    def start_trace(self, workflow_id: str, trace_id: str | None = None) -> str:
        """Start a new trace for a workflow.

        Args:
            workflow_id: Unique workflow identifier
            trace_id: Optional trace ID (auto-generated if not provided)

        Returns:
            Trace ID for this workflow execution
        """
        if trace_id is None:
            trace_id = str(uuid.uuid4())

        trace = Trace(
            trace_id=trace_id,
            workflow_id=workflow_id,
            started_at=datetime.now(),
        )

        self._traces[trace_id] = trace
        self.logger.info(f"Started trace: {trace_id} for workflow: {workflow_id}")

        return trace_id

    def start_span(
        self,
        trace_id: str,
        operation: str,
        parent_span_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Start a new span within a trace.

        Args:
            trace_id: Trace ID to attach this span to
            operation: Operation name (e.g., "e2e_analysis", "code_generation")
            parent_span_id: Parent span ID for nested operations
            metadata: Additional context metadata

        Returns:
            Span ID for this operation
        """
        if trace_id not in self._traces:
            raise ValueError(f"Trace {trace_id} not found")

        span_id = str(uuid.uuid4())

        # Use active span as parent if not specified
        if parent_span_id is None:
            parent_span_id = self._active_spans.get(trace_id)

        span = Span(
            span_id=span_id,
            trace_id=trace_id,
            parent_span_id=parent_span_id,
            operation=operation,
            started_at=datetime.now(),
            metadata=metadata or {},
        )

        self._spans[span_id] = span
        self._traces[trace_id].spans.append(span)
        self._active_spans[trace_id] = span_id

        self.logger.debug(
            f"Started span: {operation}",
            extra={
                "trace_id": trace_id,
                "span_id": span_id,
                "parent_span_id": parent_span_id,
            },
        )

        return span_id

    def finish_span(
        self,
        span_id: str,
        status: SpanStatus = SpanStatus.SUCCESS,
        error: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Finish a span.

        Args:
            span_id: Span ID to finish
            status: Final status (SUCCESS or ERROR)
            error: Error message if status is ERROR
            metadata: Additional metadata to add to span
        """
        if span_id not in self._spans:
            raise ValueError(f"Span {span_id} not found")

        span = self._spans[span_id]
        span.finish(status=status, error=error)

        if metadata:
            span.metadata.update(metadata)

        # Clear active span if this was it
        if self._active_spans.get(span.trace_id) == span_id:
            # Revert to parent span
            self._active_spans[span.trace_id] = span.parent_span_id

        self.logger.debug(
            f"Finished span: {span.operation} ({span.duration_ms:.0f}ms)",
            extra={
                "trace_id": span.trace_id,
                "span_id": span_id,
                "status": status.value,
                "duration_ms": span.duration_ms,
            },
        )

    def finish_trace(self, trace_id: str) -> Trace:
        """Finish a trace and return complete trace data.

        Args:
            trace_id: Trace ID to finish

        Returns:
            Complete Trace object with all spans
        """
        if trace_id not in self._traces:
            raise ValueError(f"Trace {trace_id} not found")

        trace = self._traces[trace_id]
        trace.ended_at = datetime.now()

        # Clean up active span tracking
        self._active_spans.pop(trace_id, None)

        self.logger.info(
            f"Finished trace: {trace_id} ({trace.total_duration_ms:.0f}ms, "
            f"{len(trace.spans)} spans, errors: {trace.has_errors})"
        )

        # Automatic cleanup check
        if self._auto_cleanup:
            self._trace_counter += 1
            if self._trace_counter >= self._cleanup_interval:
                self.clear_completed_traces(keep_count=self._max_completed_traces)
                self._trace_counter = 0

        return trace

    def get_trace(self, trace_id: str) -> Trace | None:
        """Get a trace by ID.

        Args:
            trace_id: Trace ID to retrieve

        Returns:
            Trace object or None if not found
        """
        return self._traces.get(trace_id)

    def get_span(self, span_id: str) -> Span | None:
        """Get a span by ID.

        Args:
            span_id: Span ID to retrieve

        Returns:
            Span object or None if not found
        """
        return self._spans.get(span_id)

    def get_active_traces(self) -> list[Trace]:
        """Get all active (unfinished) traces.

        Returns:
            List of active traces
        """
        return [trace for trace in self._traces.values() if trace.ended_at is None]

    def get_memory_usage(self) -> dict[str, int]:
        """Get current memory usage statistics.
        
        Returns:
            Dictionary with trace and span counts
        """
        completed_count = sum(1 for t in self._traces.values() if t.ended_at is not None)
        active_count = sum(1 for t in self._traces.values() if t.ended_at is None)

        return {
            "total_traces": len(self._traces),
            "active_traces": active_count,
            "completed_traces": completed_count,
            "total_spans": len(self._spans),
        }

    def clear_completed_traces(self, keep_count: int = 100) -> int:
        """Remove old completed traces to prevent memory growth.

        Args:
            keep_count: Number of recent completed traces to keep

        Returns:
            Number of traces removed
        """
        completed = [
            (trace_id, trace)
            for trace_id, trace in self._traces.items()
            if trace.ended_at is not None
        ]

        # Sort by completion time (newest first)
        completed.sort(key=lambda x: x[1].ended_at, reverse=True)

        # Remove old traces
        to_remove = completed[keep_count:]
        removed_count = 0

        for trace_id, trace in to_remove:
            # Remove trace
            del self._traces[trace_id]

            # Remove associated spans
            for span in trace.spans:
                if span.span_id in self._spans:
                    del self._spans[span.span_id]

            removed_count += 1

        if removed_count > 0:
            self.logger.debug(f"Cleared {removed_count} completed traces")

        return removed_count

    def get_trace_summary(self, trace_id: str) -> dict[str, Any]:
        """Get a summary of trace metrics.

        Args:
            trace_id: Trace ID to summarize

        Returns:
            Dictionary with trace summary metrics
        """
        trace = self.get_trace(trace_id)
        if trace is None:
            return {}

        critical_path = trace.get_critical_path()
        critical_path_duration = sum(span.duration_ms for span in critical_path)

        # Calculate phase breakdown
        phase_durations: dict[str, float] = {}
        for span in trace.spans:
            phase_durations[span.operation] = phase_durations.get(span.operation, 0.0) + span.duration_ms

        return {
            "trace_id": trace_id,
            "workflow_id": trace.workflow_id,
            "total_duration_ms": trace.total_duration_ms,
            "span_count": len(trace.spans),
            "is_complete": trace.is_complete,
            "has_errors": trace.has_errors,
            "critical_path_duration_ms": critical_path_duration,
            "critical_path_length": len(critical_path),
            "phase_durations": phase_durations,
            "error_spans": [
                {"operation": span.operation, "error": span.error}
                for span in trace.spans
                if span.status == SpanStatus.ERROR
            ],
        }


__all__ = ["WorkflowTracer", "Trace", "Span", "SpanStatus"]
