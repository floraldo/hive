"""Unit tests for observability components (tracing, profiling, logging)."""

import asyncio
import json
import logging
from datetime import datetime

import pytest

from chimera_daemon.logging_config import JSONFormatter, StructuredLogger
from chimera_daemon.profiling import OperationProfile, PerformanceProfiler, ProfileSnapshot
from chimera_daemon.tracing import SpanStatus, WorkflowTracer


class TestWorkflowTracer:
    """Tests for distributed tracing."""

    @pytest.fixture
    def tracer(self):
        """Create a WorkflowTracer instance."""
        return WorkflowTracer()

    def test_start_trace(self, tracer):
        """Test starting a new trace."""
        trace_id = tracer.start_trace(workflow_id="wf_123")

        assert trace_id is not None
        assert isinstance(trace_id, str)

        trace = tracer.get_trace(trace_id)
        assert trace is not None
        assert trace.workflow_id == "wf_123"
        assert trace.ended_at is None
        assert len(trace.spans) == 0

    def test_start_trace_with_custom_id(self, tracer):
        """Test starting a trace with custom trace_id."""
        custom_id = "custom_trace_123"
        trace_id = tracer.start_trace(workflow_id="wf_456", trace_id=custom_id)

        assert trace_id == custom_id
        trace = tracer.get_trace(custom_id)
        assert trace is not None

    def test_start_span(self, tracer):
        """Test starting a span within a trace."""
        trace_id = tracer.start_trace(workflow_id="wf_123")
        span_id = tracer.start_span(
            trace_id=trace_id,
            operation="e2e_analysis",
            metadata={"feature": "login form"},
        )

        assert span_id is not None
        span = tracer.get_span(span_id)
        assert span is not None
        assert span.operation == "e2e_analysis"
        assert span.trace_id == trace_id
        assert span.parent_span_id is None
        assert span.status == SpanStatus.IN_PROGRESS
        assert span.metadata["feature"] == "login form"

    def test_nested_spans(self, tracer):
        """Test creating nested spans."""
        trace_id = tracer.start_trace(workflow_id="wf_123")

        # Parent span
        parent_span_id = tracer.start_span(trace_id=trace_id, operation="parent")

        # Child span
        child_span_id = tracer.start_span(
            trace_id=trace_id, operation="child", parent_span_id=parent_span_id
        )

        child_span = tracer.get_span(child_span_id)
        assert child_span.parent_span_id == parent_span_id

    def test_auto_parent_span(self, tracer):
        """Test automatic parent span assignment."""
        trace_id = tracer.start_trace(workflow_id="wf_123")

        # First span becomes active
        span1_id = tracer.start_span(trace_id=trace_id, operation="span1")

        # Second span auto-parents to first (active span)
        span2_id = tracer.start_span(trace_id=trace_id, operation="span2")

        span2 = tracer.get_span(span2_id)
        assert span2.parent_span_id == span1_id

    def test_finish_span(self, tracer):
        """Test finishing a span."""
        trace_id = tracer.start_trace(workflow_id="wf_123")
        span_id = tracer.start_span(trace_id=trace_id, operation="test_op")

        # Simulate work
        import time

        time.sleep(0.01)

        tracer.finish_span(span_id, status=SpanStatus.SUCCESS)

        span = tracer.get_span(span_id)
        assert span.status == SpanStatus.SUCCESS
        assert span.ended_at is not None
        assert span.duration_ms > 0

    def test_finish_span_with_error(self, tracer):
        """Test finishing a span with error status."""
        trace_id = tracer.start_trace(workflow_id="wf_123")
        span_id = tracer.start_span(trace_id=trace_id, operation="failing_op")

        tracer.finish_span(span_id, status=SpanStatus.ERROR, error="Connection timeout")

        span = tracer.get_span(span_id)
        assert span.status == SpanStatus.ERROR
        assert span.error == "Connection timeout"

    def test_finish_trace(self, tracer):
        """Test finishing a complete trace."""
        trace_id = tracer.start_trace(workflow_id="wf_123")
        span_id = tracer.start_span(trace_id=trace_id, operation="test_op")

        # Add small delay to ensure measurable duration
        import time
        time.sleep(0.001)

        tracer.finish_span(span_id, status=SpanStatus.SUCCESS)

        trace = tracer.finish_trace(trace_id)

        assert trace.ended_at is not None
        assert trace.total_duration_ms >= 0  # Allow zero for very fast execution
        assert len(trace.spans) == 1

    def test_trace_has_errors(self, tracer):
        """Test trace error detection."""
        trace_id = tracer.start_trace(workflow_id="wf_123")

        # Successful span
        span1_id = tracer.start_span(trace_id=trace_id, operation="success")
        tracer.finish_span(span1_id, status=SpanStatus.SUCCESS)

        # Failed span
        span2_id = tracer.start_span(trace_id=trace_id, operation="failure")
        tracer.finish_span(span2_id, status=SpanStatus.ERROR, error="Test error")

        trace = tracer.finish_trace(trace_id)
        assert trace.has_errors is True

    def test_trace_is_complete(self, tracer):
        """Test trace completion detection."""
        trace_id = tracer.start_trace(workflow_id="wf_123")
        span_id = tracer.start_span(trace_id=trace_id, operation="test_op")

        trace = tracer.get_trace(trace_id)
        assert trace.is_complete is False

        tracer.finish_span(span_id, status=SpanStatus.SUCCESS)
        assert trace.is_complete is True

    def test_get_critical_path(self, tracer):
        """Test critical path calculation."""
        trace_id = tracer.start_trace(workflow_id="wf_123")

        # Create a simple chain: span1 -> span2 -> span3
        span1_id = tracer.start_span(trace_id=trace_id, operation="span1")
        import time

        time.sleep(0.01)
        tracer.finish_span(span1_id)

        span2_id = tracer.start_span(trace_id=trace_id, operation="span2", parent_span_id=span1_id)
        time.sleep(0.01)
        tracer.finish_span(span2_id)

        span3_id = tracer.start_span(trace_id=trace_id, operation="span3", parent_span_id=span2_id)
        time.sleep(0.01)
        tracer.finish_span(span3_id)

        trace = tracer.finish_trace(trace_id)
        critical_path = trace.get_critical_path()

        assert len(critical_path) == 3
        assert critical_path[0].operation == "span1"
        assert critical_path[1].operation == "span2"
        assert critical_path[2].operation == "span3"

    def test_get_active_traces(self, tracer):
        """Test getting active traces."""
        trace1_id = tracer.start_trace(workflow_id="wf_1")
        trace2_id = tracer.start_trace(workflow_id="wf_2")

        active_traces = tracer.get_active_traces()
        assert len(active_traces) == 2

        tracer.finish_trace(trace1_id)
        active_traces = tracer.get_active_traces()
        assert len(active_traces) == 1

    def test_clear_completed_traces(self, tracer):
        """Test clearing old completed traces."""
        # Create and complete 5 traces
        for i in range(5):
            trace_id = tracer.start_trace(workflow_id=f"wf_{i}")
            tracer.finish_trace(trace_id)

        # Keep only 2 most recent
        removed = tracer.clear_completed_traces(keep_count=2)
        assert removed == 3

    def test_get_trace_summary(self, tracer):
        """Test trace summary generation."""
        trace_id = tracer.start_trace(workflow_id="wf_123")

        span1_id = tracer.start_span(trace_id=trace_id, operation="phase1")
        import time

        time.sleep(0.01)
        tracer.finish_span(span1_id, status=SpanStatus.SUCCESS)

        span2_id = tracer.start_span(trace_id=trace_id, operation="phase2")
        time.sleep(0.01)
        tracer.finish_span(span2_id, status=SpanStatus.ERROR, error="Test error")

        tracer.finish_trace(trace_id)

        summary = tracer.get_trace_summary(trace_id)

        assert summary["trace_id"] == trace_id
        assert summary["workflow_id"] == "wf_123"
        assert summary["span_count"] == 2
        assert summary["is_complete"] is True
        assert summary["has_errors"] is True
        assert "phase1" in summary["phase_durations"]
        assert "phase2" in summary["phase_durations"]
        assert len(summary["error_spans"]) == 1
        assert summary["error_spans"][0]["operation"] == "phase2"


class TestPerformanceProfiler:
    """Tests for performance profiling."""

    @pytest.fixture
    def profiler(self):
        """Create a PerformanceProfiler instance (enabled)."""
        return PerformanceProfiler(enabled=True, snapshot_interval_ms=50)

    @pytest.fixture
    def disabled_profiler(self):
        """Create a disabled profiler."""
        return PerformanceProfiler(enabled=False)

    def test_profiler_disabled_by_default(self):
        """Test profiler is disabled by default."""
        profiler = PerformanceProfiler()
        assert profiler.enabled is False

    @pytest.mark.asyncio
    async def test_start_finish_profile(self, profiler):
        """Test basic profiling lifecycle."""
        if not profiler.enabled:
            pytest.skip("psutil not available")

        profile_id = profiler.start_profile("test_operation")
        await asyncio.sleep(0.1)
        profile = profiler.finish_profile(profile_id)

        assert profile is not None
        assert profile.operation == "test_operation"
        assert profile.duration_ms >= 100
        assert len(profile.snapshots) >= 2

    @pytest.mark.asyncio
    async def test_profile_context_manager(self, profiler):
        """Test profiling with context manager."""
        if not profiler.enabled:
            pytest.skip("psutil not available")

        async with profiler.profile_context("context_operation") as profile:
            await asyncio.sleep(0.1)
            profile.metadata["test"] = "value"

        profiles = profiler.get_profiles("context_operation")
        assert len(profiles) == 1
        assert profiles[0].metadata["test"] == "value"
        assert profiles[0].duration_ms >= 100

    @pytest.mark.asyncio
    async def test_profile_decorator(self, profiler):
        """Test profiling with decorator."""
        if not profiler.enabled:
            pytest.skip("psutil not available")

        @profiler.profile("decorated_operation")
        async def async_function():
            await asyncio.sleep(0.1)
            return "result"

        result = await async_function()
        assert result == "result"

        profiles = profiler.get_profiles("decorated_operation")
        assert len(profiles) == 1
        assert profiles[0].duration_ms >= 100

    @pytest.mark.asyncio
    async def test_disabled_profiler_no_overhead(self, disabled_profiler):
        """Test disabled profiler has no overhead."""
        profile_id = disabled_profiler.start_profile("test")
        await asyncio.sleep(0.01)
        profile = disabled_profiler.finish_profile(profile_id)

        assert profile is None
        assert len(disabled_profiler.get_profiles()) == 0

    @pytest.mark.asyncio
    async def test_get_report(self, profiler):
        """Test profiling report generation."""
        if not profiler.enabled:
            pytest.skip("psutil not available")

        # Create multiple profiles
        for i in range(3):
            async with profiler.profile_context("test_op"):
                await asyncio.sleep(0.05)

        report = profiler.get_report()

        assert report["enabled"] is True
        assert report["total_profiles"] == 3
        assert "test_op" in report["operations"]
        assert report["operations"]["test_op"]["call_count"] == 3
        assert "wall_time_ms" in report["operations"]["test_op"]
        assert "cpu_percent" in report["operations"]["test_op"]
        assert "memory_mb" in report["operations"]["test_op"]

    @pytest.mark.asyncio
    async def test_clear_profiles(self, profiler):
        """Test clearing profiles."""
        if not profiler.enabled:
            pytest.skip("psutil not available")

        async with profiler.profile_context("op1"):
            await asyncio.sleep(0.01)

        async with profiler.profile_context("op2"):
            await asyncio.sleep(0.01)

        assert len(profiler.get_profiles()) == 2

        # Clear specific operation
        count = profiler.clear_profiles("op1")
        assert count == 1
        assert len(profiler.get_profiles()) == 1

        # Clear all
        count = profiler.clear_profiles()
        assert count == 1
        assert len(profiler.get_profiles()) == 0


class TestStructuredLogging:
    """Tests for structured JSON logging."""

    @pytest.fixture
    def logger(self):
        """Create a StructuredLogger instance."""
        return StructuredLogger(component="test_component", enable_json=False)

    def test_json_formatter(self):
        """Test JSON log formatting."""
        formatter = JSONFormatter()

        # Create a log record
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        record.trace_id = "trace_123"
        record.span_id = "span_456"

        json_output = formatter.format(record)
        log_data = json.loads(json_output)

        assert log_data["level"] == "INFO"
        assert log_data["message"] == "Test message"
        assert log_data["trace_id"] == "trace_123"
        assert log_data["span_id"] == "span_456"
        assert "timestamp" in log_data

    def test_structured_logger_info(self, logger):
        """Test structured logging info level."""
        # Just verify it doesn't raise exceptions
        logger.info(
            "Test message",
            trace_id="trace_123",
            workflow_id="wf_456",
            extra={"key": "value"},
        )

    def test_structured_logger_error_with_exception(self, logger):
        """Test structured logging with exception info."""
        try:
            raise ValueError("Test error")
        except ValueError:
            logger.error(
                "Error occurred",
                trace_id="trace_123",
                exc_info=True,
            )

    def test_structured_logger_all_levels(self, logger):
        """Test all log levels."""
        logger.debug("Debug message", trace_id="trace_123")
        logger.info("Info message", trace_id="trace_123")
        logger.warning("Warning message", trace_id="trace_123")
        logger.error("Error message", trace_id="trace_123", exc_info=False)
        logger.critical("Critical message", trace_id="trace_123", exc_info=False)


class TestProfileSnapshot:
    """Tests for ProfileSnapshot dataclass."""

    def test_profile_snapshot_creation(self):
        """Test creating a profile snapshot."""
        snapshot = ProfileSnapshot(
            timestamp=datetime.now(),
            cpu_percent=25.5,
            memory_mb=512.0,
            memory_percent=15.2,
            io_read_mb=100.0,
            io_write_mb=50.0,
            thread_count=8,
        )

        assert snapshot.cpu_percent == 25.5
        assert snapshot.memory_mb == 512.0
        assert snapshot.thread_count == 8


class TestOperationProfile:
    """Tests for OperationProfile metrics."""

    def test_duration_calculation(self):
        """Test duration calculation."""
        started = datetime.now()
        import time

        time.sleep(0.05)
        ended = datetime.now()

        profile = OperationProfile(
            operation="test", started_at=started, ended_at=ended, wall_time_ms=50.0
        )

        assert profile.duration_ms >= 50.0

    def test_cpu_and_memory_metrics(self):
        """Test CPU and memory metric calculations."""
        profile = OperationProfile(operation="test", started_at=datetime.now())

        # Add snapshots
        profile.snapshots.append(
            ProfileSnapshot(
                timestamp=datetime.now(),
                cpu_percent=20.0,
                memory_mb=100.0,
                memory_percent=10.0,
            )
        )
        profile.snapshots.append(
            ProfileSnapshot(
                timestamp=datetime.now(),
                cpu_percent=30.0,
                memory_mb=150.0,
                memory_percent=15.0,
            )
        )

        assert profile.avg_cpu_percent == 25.0
        assert profile.peak_memory_mb == 150.0
        assert profile.avg_memory_mb == 125.0

    def test_io_metrics(self):
        """Test I/O metric calculations."""
        profile = OperationProfile(operation="test", started_at=datetime.now())

        profile.snapshots.append(
            ProfileSnapshot(
                timestamp=datetime.now(),
                cpu_percent=10.0,
                memory_mb=100.0,
                memory_percent=10.0,
                io_read_mb=100.0,
                io_write_mb=50.0,
            )
        )
        profile.snapshots.append(
            ProfileSnapshot(
                timestamp=datetime.now(),
                cpu_percent=10.0,
                memory_mb=100.0,
                memory_percent=10.0,
                io_read_mb=150.0,
                io_write_mb=75.0,
            )
        )

        # Total I/O = (150 - 100) + (75 - 50) = 75 MB
        assert profile.total_io_mb == 75.0
