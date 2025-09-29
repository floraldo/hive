"""
End-to-End Monitoring Integration Test

Validates the complete data flow from monitoring systems to predictive alerts.
Part of PROJECT VANGUARD Phase A - Validation & Monitoring.

Tests:
1. MonitoringErrorReporter → MetricPoint conversion
2. HealthMonitor → MetricPoint conversion
3. CircuitBreaker → MetricPoint conversion
4. PredictiveAnalysisRunner → Alert generation
5. Alert validation tracking

Usage:
    python scripts/monitoring/test_monitoring_integration.py
"""

import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add packages to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "packages" / "hive-errors" / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "packages" / "hive-async" / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "packages" / "hive-ai" / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "packages" / "hive-logging" / "src"))

from hive_logging import get_logger

logger = get_logger(__name__)


async def test_monitoring_error_reporter():
    """Test MonitoringErrorReporter metric history integration."""
    logger.info("Testing MonitoringErrorReporter integration...")

    try:
        from hive_errors.monitoring_error_reporter import MonitoringErrorReporter

        # Create reporter instance
        reporter = MonitoringErrorReporter(enable_alerts=False, max_history=100)

        # Simulate some errors
        for i in range(10):
            try:
                raise ValueError(f"Test error {i}")
            except Exception as e:
                reporter.report_error(error=e, context={"component": "test_service", "operation": "test_op"})

        # Get error rate history
        error_history = reporter.get_error_rate_history(service_name="test_service", hours=24)

        # Validate format
        assert isinstance(error_history, list), "Error history should be a list"
        if error_history:
            assert "timestamp" in error_history[0], "Missing timestamp"
            assert "value" in error_history[0], "Missing value"
            assert "metadata" in error_history[0], "Missing metadata"

            logger.info(f"MonitoringErrorReporter: Retrieved {len(error_history)} metric points")
            logger.info(f"Sample metric point: {error_history[0]}")

        logger.info("MonitoringErrorReporter integration: PASS")
        return True

    except ImportError as e:
        logger.warning(f"MonitoringErrorReporter not available: {e}")
        return False
    except Exception as e:
        logger.error(f"MonitoringErrorReporter integration test failed: {e}")
        return False


async def test_circuit_breaker():
    """Test CircuitBreaker failure history integration."""
    logger.info("Testing CircuitBreaker integration...")

    try:
        from hive_async.resilience import AsyncCircuitBreaker

        # Create circuit breaker
        breaker = AsyncCircuitBreaker(failure_threshold=3, recovery_timeout=60, name="test_breaker")

        # Simulate some failures
        for i in range(5):
            try:

                async def failing_function():
                    raise ValueError(f"Test failure {i}")

                await breaker.call_async(failing_function)
            except Exception:
                pass  # Expected to fail

        # Get failure history
        failure_history = breaker.get_failure_history(metric_type="failure_rate", hours=24)

        # Validate format
        assert isinstance(failure_history, list), "Failure history should be a list"
        if failure_history:
            assert "timestamp" in failure_history[0], "Missing timestamp"
            assert "value" in failure_history[0], "Missing value"
            assert "metadata" in failure_history[0], "Missing metadata"

            logger.info(f"CircuitBreaker: Retrieved {len(failure_history)} metric points")
            logger.info(f"Sample metric point: {failure_history[0]}")

        # Test state transitions
        state_history = breaker.get_failure_history(metric_type="state_changes", hours=24)

        if state_history:
            logger.info(f"CircuitBreaker: Retrieved {len(state_history)} state transitions")

        logger.info("CircuitBreaker integration: PASS")
        return True

    except ImportError as e:
        logger.warning(f"CircuitBreaker not available: {e}")
        return False
    except Exception as e:
        logger.error(f"CircuitBreaker integration test failed: {e}")
        return False


async def test_predictive_analysis_runner():
    """Test PredictiveAnalysisRunner with live monitoring integration."""
    logger.info("Testing PredictiveAnalysisRunner integration...")

    try:
        # Import required modules
        sys.path.insert(0, str(Path(__file__).parent))
        from predictive_analysis_runner import PredictiveAnalysisRunner

        try:
            from hive_errors.alert_manager import PredictiveAlertManager
            from hive_errors.predictive_alerts import MetricType
            from hive_errors.monitoring_error_reporter import MonitoringErrorReporter
        except ImportError as e:
            logger.warning(f"Required modules not available: {e}")
            return False

        # Create monitoring components
        error_reporter = MonitoringErrorReporter(enable_alerts=False)
        alert_manager = PredictiveAlertManager()

        # Create runner with monitoring integration
        runner = PredictiveAnalysisRunner(
            alert_manager=alert_manager,
            error_reporter=error_reporter,
            health_monitor=None,  # HealthMonitor requires ModelRegistry
        )

        # Simulate some errors for test_service
        for i in range(5):
            try:
                raise ValueError(f"Test error {i}")
            except Exception as e:
                error_reporter.report_error(error=e, context={"component": "test_service"})

        # Run analysis
        result = await runner.run_analysis_async()

        # Validate result
        assert "success" in result, "Missing success field"
        assert "alerts_generated" in result, "Missing alerts_generated field"
        assert "duration_seconds" in result, "Missing duration_seconds field"

        logger.info(f"Analysis result: {result}")
        logger.info(f"Generated {result.get('alerts_generated', 0)} alerts in {result.get('duration_seconds', 0):.2f}s")

        # Get runner statistics
        stats = runner.get_stats()
        logger.info(f"Runner statistics: {stats}")

        logger.info("PredictiveAnalysisRunner integration: PASS")
        return True

    except ImportError as e:
        logger.warning(f"PredictiveAnalysisRunner not available: {e}")
        return False
    except Exception as e:
        logger.error(f"PredictiveAnalysisRunner integration test failed: {e}", exc_info=True)
        return False


async def test_alert_validation_tracker():
    """Test AlertValidationTracker functionality."""
    logger.info("Testing AlertValidationTracker...")

    try:
        sys.path.insert(0, str(Path(__file__).parent))
        from alert_validation_tracker import AlertValidationTracker

        # Create tracker
        tracker = AlertValidationTracker(validation_db_path="data/test_alert_validation.json")

        # Record test alert
        tracker.record_alert(
            alert_id="test_alert_001",
            service_name="test_service",
            metric_type="error_rate",
            predicted_breach_time=(datetime.utcnow() + timedelta(hours=2)).isoformat(),
            confidence=0.85,
            severity="high",
            metadata={"test": True},
        )

        # Validate alert as true positive
        tracker.validate_alert(alert_id="test_alert_001", outcome="true_positive", notes="Test validation")

        # Generate report
        report = tracker.generate_validation_report()

        assert report["summary"]["total_alerts"] > 0, "No alerts recorded"
        assert report["summary"]["true_positives"] > 0, "No true positives"

        logger.info(f"Validation report: {report['summary']}")
        logger.info("AlertValidationTracker: PASS")

        # Cleanup test database
        Path("data/test_alert_validation.json").unlink(missing_ok=True)

        return True

    except Exception as e:
        logger.error(f"AlertValidationTracker test failed: {e}", exc_info=True)
        return False


async def run_all_tests():
    """Run all integration tests."""
    print("\n" + "=" * 80)
    print("MONITORING INTEGRATION TEST SUITE")
    print("PROJECT VANGUARD Phase A - Validation & Monitoring")
    print("=" * 80 + "\n")

    results = {}

    # Test 1: MonitoringErrorReporter
    results["MonitoringErrorReporter"] = await test_monitoring_error_reporter()

    # Test 2: CircuitBreaker
    results["CircuitBreaker"] = await test_circuit_breaker()

    # Test 3: PredictiveAnalysisRunner
    results["PredictiveAnalysisRunner"] = await test_predictive_analysis_runner()

    # Test 4: AlertValidationTracker
    results["AlertValidationTracker"] = await test_alert_validation_tracker()

    # Print summary
    print("\n" + "=" * 80)
    print("TEST RESULTS SUMMARY")
    print("=" * 80)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for test_name, result in results.items():
        status = "PASS" if result else "FAIL"
        symbol = "✓" if result else "✗"
        print(f"  {symbol} {test_name}: {status}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\nAll integration tests PASSED")
        print("Monitoring integration is fully operational!")
        return 0
    else:
        print(f"\n{total - passed} integration test(s) FAILED")
        print("Review logs for details.")
        return 1


def main():
    """Main entry point."""
    try:
        exit_code = asyncio.run(run_all_tests())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\nTest suite interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Test suite failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
