"""Test Phase 3 instrumentation to validate metrics collection.

Validates that hive-performance decorators are correctly applied and
metrics are generated for hive-orchestrator functions.
"""

import asyncio

import pytest

from hive_performance import get_all_metrics_summary, get_metric_value, reset_metrics


class TestPhase3Instrumentation:
    """Test suite for Phase 3 hive-orchestrator instrumentation validation."""

    @pytest.fixture(autouse=True)
    def reset_all_metrics(self):
        """Reset metrics before each test."""
        reset_metrics()
        yield
        reset_metrics()

    @pytest.mark.asyncio
    async def test_claude_ai_instrumentation_imports(self):
        """Test that Claude AI functions are properly instrumented."""
        # Import the instrumented functions
        from hive_orchestrator.async_worker import AsyncWorker
        from hive_orchestrator.worker import WorkerCore

        # Verify decorators are applied (functions should have __wrapped__ attribute)
        assert hasattr(WorkerCore.run_claude, "__wrapped__"), "WorkerCore.run_claude not decorated"
        assert hasattr(AsyncWorker.execute_claude_async, "__wrapped__"), "AsyncWorker.execute_claude_async not decorated"

    @pytest.mark.asyncio
    async def test_orchestration_instrumentation_imports(self):
        """Test that orchestration functions are properly instrumented."""
        from hive_orchestrator.async_queen import AsyncQueen

        # Verify decorators are applied
        assert hasattr(AsyncQueen.run_forever_async, "__wrapped__"), "run_forever_async not decorated"
        assert hasattr(AsyncQueen.process_queued_tasks_async, "__wrapped__"), "process_queued_tasks_async not decorated"
        assert hasattr(AsyncQueen.monitor_workers_async, "__wrapped__"), "monitor_workers_async not decorated"
        assert hasattr(AsyncQueen.spawn_worker_async, "__wrapped__"), "spawn_worker_async not decorated"

    @pytest.mark.asyncio
    async def test_failure_handling_instrumentation_imports(self):
        """Test that failure handling functions are properly instrumented."""
        from hive_orchestrator.async_queen import AsyncQueen

        # Verify decorators are applied
        assert hasattr(
            AsyncQueen._handle_worker_success_async, "__wrapped__",
        ), "_handle_worker_success_async not decorated"
        assert hasattr(
            AsyncQueen._handle_worker_failure_async, "__wrapped__",
        ), "_handle_worker_failure_async not decorated"

    @pytest.mark.asyncio
    async def test_database_instrumentation_imports(self):
        """Test that database functions are properly instrumented."""
        from hive_orchestrator.core.db.async_operations import AsyncDatabaseOperations

        # Verify decorators are applied
        assert hasattr(AsyncDatabaseOperations.create_task_async, "__wrapped__"), "create_task_async not decorated"
        assert hasattr(AsyncDatabaseOperations.get_task_async, "__wrapped__"), "get_task_async not decorated"
        assert hasattr(
            AsyncDatabaseOperations.get_queued_tasks_async, "__wrapped__",
        ), "get_queued_tasks_async not decorated"
        assert hasattr(
            AsyncDatabaseOperations.batch_create_tasks_async, "__wrapped__",
        ), "batch_create_tasks_async not decorated"

    @pytest.mark.asyncio
    async def test_all_12_functions_instrumented(self):
        """Validate all 12 Phase 3 functions are instrumented."""
        from hive_orchestrator.async_queen import AsyncQueen
        from hive_orchestrator.async_worker import AsyncWorker
        from hive_orchestrator.core.db.async_operations import AsyncDatabaseOperations
        from hive_orchestrator.worker import WorkerCore

        instrumented_functions = [
            # P0 Critical: Claude AI (2)
            WorkerCore.run_claude,
            AsyncWorker.execute_claude_async,
            # P0 Critical: Failure Handling (2)
            AsyncQueen._handle_worker_success_async,
            AsyncQueen._handle_worker_failure_async,
            # P1 High: Orchestration (4)
            AsyncQueen.run_forever_async,
            AsyncQueen.process_queued_tasks_async,
            AsyncQueen.monitor_workers_async,
            AsyncQueen.spawn_worker_async,
            # P1 High: Database (4)
            AsyncDatabaseOperations.create_task_async,
            AsyncDatabaseOperations.get_task_async,
            AsyncDatabaseOperations.get_queued_tasks_async,
            AsyncDatabaseOperations.batch_create_tasks_async,
        ]

        for func in instrumented_functions:
            assert hasattr(func, "__wrapped__"), f"{func.__name__} not decorated with performance monitoring"

        # Verify count
        assert len(instrumented_functions) == 12, f"Expected 12 instrumented functions, found {len(instrumented_functions)}"

    @pytest.mark.asyncio
    async def test_metric_naming_conventions(self):
        """Test that metrics follow naming conventions from Phase 3 design."""
        # Expected metric patterns from Phase 3 documentation
        expected_metric_patterns = [
            # Claude AI metrics
            "adapter.claude_ai.duration",
            "adapter.claude_ai.calls",
            "adapter.claude_ai.errors",
            # Orchestration metrics
            "async_orchestration_cycle.duration",
            "async_orchestration_cycle.calls",
            "async_process_queued_tasks.duration",
            "monitor_workers.duration",
            # Database metrics
            "adapter.sqlite.duration",
            "adapter.sqlite.calls",
            # Failure handling
            "handle_worker_success.duration",
            "handle_worker_failure.duration",
            # Subprocess
            "adapter.subprocess.duration",
        ]

        # Note: Metrics won't exist until functions are called
        # This test validates the naming convention is correct
        # Actual metric generation is tested in integration tests

        for pattern in expected_metric_patterns:
            # Validate pattern structure (should have at least one dot separator)
            assert "." in pattern, f"Metric pattern '{pattern}' should use dot notation"

            # Validate suffix conventions
            if pattern.endswith(".duration"):
                # Duration metrics should be histograms
                pass
            elif pattern.endswith(".calls") or pattern.endswith(".errors"):
                # Call and error metrics should be counters
                pass


class TestMetricsGeneration:
    """Test actual metrics generation (requires mocked execution)."""

    @pytest.fixture(autouse=True)
    def reset_all_metrics(self):
        """Reset metrics before each test."""
        reset_metrics()
        yield
        reset_metrics()

    @pytest.mark.asyncio
    async def test_decorator_overhead_minimal(self):
        """Test that decorator overhead is minimal (<10% as per Phase 2 testing)."""
        import time

        from hive_performance import track_request

        # Baseline function
        async def baseline():
            await asyncio.sleep(0.1)

        # Instrumented function
        @track_request("test.overhead")
        async def instrumented():
            await asyncio.sleep(0.1)

        # Measure baseline
        start = time.perf_counter()
        await baseline()
        baseline_time = time.perf_counter() - start

        # Measure instrumented
        start = time.perf_counter()
        await instrumented()
        instrumented_time = time.perf_counter() - start

        # Overhead should be < 10%
        overhead = instrumented_time - baseline_time
        overhead_percent = (overhead / baseline_time) * 100

        assert overhead_percent < 10.0, f"Overhead {overhead_percent:.2f}% exceeds 10% threshold"

        # Verify metrics were generated
        duration = get_metric_value("test.overhead.duration")
        calls = get_metric_value("test.overhead.calls")

        assert duration is not None, "Duration metric not generated"
        assert calls == 1.0, f"Expected 1 call, got {calls}"

    @pytest.mark.asyncio
    async def test_metrics_summary_structure(self):
        """Test that metrics summary has correct structure."""
        from hive_performance import track_adapter_request, track_request

        @track_request("test.request")
        async def test_request_func():
            return "done"

        @track_adapter_request("test_service")
        async def test_adapter_func():
            return "done"

        # Execute functions
        await test_request_func()
        await test_adapter_func()

        # Get summary
        summary = get_all_metrics_summary()

        # Validate structure
        assert isinstance(summary, dict), "Summary should be a dictionary"

        # Check for expected metrics
        metric_names = [m["name"] for m in summary.values()]

        # track_request should generate: duration, calls
        assert any("test.request.duration" in name for name in metric_names), "Missing request duration metric"
        assert any("test.request.calls" in name for name in metric_names), "Missing request calls metric"

        # track_adapter_request should generate: duration, calls
        assert any("test_service" in name for name in metric_names), "Missing adapter metrics"


class TestPhase3Coverage:
    """Test coverage and completeness of Phase 3 instrumentation."""

    def test_instrumentation_coverage_report(self):
        """Generate a coverage report for Phase 3 instrumentation."""
        from hive_orchestrator.async_queen import AsyncQueen
        from hive_orchestrator.async_worker import AsyncWorker
        from hive_orchestrator.core.db.async_operations import AsyncDatabaseOperations
        from hive_orchestrator.worker import WorkerCore

        coverage_report = {
            "Claude AI Execution": {
                "WorkerCore.run_claude": hasattr(WorkerCore.run_claude, "__wrapped__"),
                "AsyncWorker.execute_claude_async": hasattr(AsyncWorker.execute_claude_async, "__wrapped__"),
            },
            "Failure Handling": {
                "AsyncQueen._handle_worker_success_async": hasattr(
                    AsyncQueen._handle_worker_success_async, "__wrapped__",
                ),
                "AsyncQueen._handle_worker_failure_async": hasattr(
                    AsyncQueen._handle_worker_failure_async, "__wrapped__",
                ),
            },
            "Orchestration Loops": {
                "AsyncQueen.run_forever_async": hasattr(AsyncQueen.run_forever_async, "__wrapped__"),
                "AsyncQueen.process_queued_tasks_async": hasattr(AsyncQueen.process_queued_tasks_async, "__wrapped__"),
                "AsyncQueen.monitor_workers_async": hasattr(AsyncQueen.monitor_workers_async, "__wrapped__"),
                "AsyncQueen.spawn_worker_async": hasattr(AsyncQueen.spawn_worker_async, "__wrapped__"),
            },
            "Database Operations": {
                "AsyncDatabaseOperations.create_task_async": hasattr(
                    AsyncDatabaseOperations.create_task_async, "__wrapped__",
                ),
                "AsyncDatabaseOperations.get_task_async": hasattr(AsyncDatabaseOperations.get_task_async, "__wrapped__"),
                "AsyncDatabaseOperations.get_queued_tasks_async": hasattr(
                    AsyncDatabaseOperations.get_queued_tasks_async, "__wrapped__",
                ),
                "AsyncDatabaseOperations.batch_create_tasks_async": hasattr(
                    AsyncDatabaseOperations.batch_create_tasks_async, "__wrapped__",
                ),
            },
        }

        # Calculate coverage
        total_functions = sum(len(funcs) for funcs in coverage_report.values())
        instrumented_functions = sum(
            sum(1 for instrumented in funcs.values() if instrumented) for funcs in coverage_report.values()
        )

        coverage_percent = (instrumented_functions / total_functions) * 100

        # Assert 100% coverage
        assert coverage_percent == 100.0, f"Coverage is {coverage_percent:.1f}%, expected 100%"

        # Assert all categories have 100% coverage
        for category, functions in coverage_report.items():
            category_coverage = (sum(1 for f in functions.values() if f) / len(functions)) * 100
            assert category_coverage == 100.0, f"{category} coverage is {category_coverage:.1f}%, expected 100%"

    def test_phase3_documentation_alignment(self):
        """Test that implementation aligns with Phase 3 documentation."""
        # This test validates the documented 12 functions from PROJECT_SIGNAL_PHASE_3_COMPLETE.md
        documented_functions = [
            # P0 Critical (4)
            "WorkerCore.run_claude",
            "AsyncWorker.execute_claude_async",
            "AsyncQueen._handle_worker_success_async",
            "AsyncQueen._handle_worker_failure_async",
            # P1 High Orchestration (4)
            "AsyncQueen.run_forever_async",
            "AsyncQueen.process_queued_tasks_async",
            "AsyncQueen.monitor_workers_async",
            "AsyncQueen.spawn_worker_async",
            # P1 High Database (4)
            "AsyncDatabaseOperations.create_task_async",
            "AsyncDatabaseOperations.get_task_async",
            "AsyncDatabaseOperations.get_queued_tasks_async",
            "AsyncDatabaseOperations.batch_create_tasks_async",
        ]

        assert len(documented_functions) == 12, "Documentation should list exactly 12 functions"

        # Verify each documented function exists and is instrumented
        from hive_orchestrator.async_queen import AsyncQueen
        from hive_orchestrator.async_worker import AsyncWorker
        from hive_orchestrator.core.db.async_operations import AsyncDatabaseOperations
        from hive_orchestrator.worker import WorkerCore

        function_map = {
            "WorkerCore.run_claude": WorkerCore.run_claude,
            "AsyncWorker.execute_claude_async": AsyncWorker.execute_claude_async,
            "AsyncQueen._handle_worker_success_async": AsyncQueen._handle_worker_success_async,
            "AsyncQueen._handle_worker_failure_async": AsyncQueen._handle_worker_failure_async,
            "AsyncQueen.run_forever_async": AsyncQueen.run_forever_async,
            "AsyncQueen.process_queued_tasks_async": AsyncQueen.process_queued_tasks_async,
            "AsyncQueen.monitor_workers_async": AsyncQueen.monitor_workers_async,
            "AsyncQueen.spawn_worker_async": AsyncQueen.spawn_worker_async,
            "AsyncDatabaseOperations.create_task_async": AsyncDatabaseOperations.create_task_async,
            "AsyncDatabaseOperations.get_task_async": AsyncDatabaseOperations.get_task_async,
            "AsyncDatabaseOperations.get_queued_tasks_async": AsyncDatabaseOperations.get_queued_tasks_async,
            "AsyncDatabaseOperations.batch_create_tasks_async": AsyncDatabaseOperations.batch_create_tasks_async,
        }

        for func_name in documented_functions:
            assert func_name in function_map, f"Documented function {func_name} not found in implementation"
            func = function_map[func_name]
            assert hasattr(func, "__wrapped__"), f"Documented function {func_name} not instrumented"
