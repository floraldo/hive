"""Test intelligence analysis engine.

Provides statistical analysis, trend detection, flaky test identification,
and failure pattern clustering.
"""
import re
from collections import defaultdict
from datetime import datetime, timedelta
from statistics import mean
from typing import Any

from .models import FailurePattern, FlakyTestResult, PackageHealthReport, TestResult, TestStatus
from .storage import TestIntelligenceStorage


class TestIntelligenceAnalyzer:
    """Analyzes test history to generate actionable insights."""

    def __init__(self, storage: TestIntelligenceStorage | None = None):
        """Initialize analyzer with storage.

        Args:
            storage: Test intelligence storage instance

        """
        self.storage = storage or TestIntelligenceStorage()

    def detect_flaky_tests(self, min_runs: int = 10, threshold: float = 0.2) -> list[FlakyTestResult]:
        """Detect tests with intermittent failures (flaky tests).

        Args:
            min_runs: Minimum number of runs to consider
            threshold: Minimum fail rate to flag as flaky (default 0.2 = 20%)

        Returns:
            List of flaky test results

        """
        # Get recent runs
        recent_runs = self.storage.get_recent_runs(limit=30)
        if len(recent_runs) < min_runs:
            return []

        # Collect all test IDs
        test_histories: dict[str, list[TestResult]] = defaultdict(list)

        for run in recent_runs:
            results = self.storage.get_test_results_for_run(run.id)
            for result in results:
                test_histories[result.test_id].append(result)

        # Analyze each test for flakiness
        flaky_tests = []

        for test_id, history in test_histories.items():
            if len(history) < min_runs:
                continue

            # Count outcomes
            passed_count = sum(1 for r in history if r.status == TestStatus.PASSED)
            failed_count = sum(1 for r in history if r.status == TestStatus.FAILED)
            error_count = sum(1 for r in history if r.status == TestStatus.ERROR)
            total = len(history)

            fail_rate = (failed_count + error_count) / total

            # Check if flaky (fails sometimes but not always)
            if 0.1 < fail_rate < 0.9 and fail_rate >= threshold:
                error_messages = [r.error_message for r in history if r.error_message]

                flaky_tests.append(
                    FlakyTestResult(
                        test_id=test_id,
                        total_runs=total,
                        passed_runs=passed_count,
                        failed_runs=failed_count,
                        error_runs=error_count,
                        fail_rate=fail_rate,
                        first_seen=min(r.id for r in history),  # Simplified - use run timestamp
                        last_seen=max(r.id for r in history),
                        error_messages=list(set(error_messages)),
                    ),
                )

        # Sort by fail rate (most flaky first)
        flaky_tests.sort(key=lambda x: abs(x.fail_rate - 0.5))
        return flaky_tests

    def analyze_package_health(self, days: int = 7) -> list[PackageHealthReport]:
        """Analyze health trends for each package.

        Args:
            days: Number of days to analyze

        Returns:
            List of package health reports

        """
        cutoff_date = datetime.now() - timedelta(days=days)
        recent_runs = self.storage.get_recent_runs(limit=100)

        # Filter to runs within time window
        recent_runs = [run for run in recent_runs if run.timestamp >= cutoff_date]

        if not recent_runs:
            return []

        # Group results by package
        package_stats: dict[str, dict[str, Any]] = defaultdict(lambda: {"results": [], "durations": []})

        for run in recent_runs:
            results = self.storage.get_test_results_for_run(run.id)
            for result in results:
                package_stats[result.package_name]["results"].append(result)
                package_stats[result.package_name]["durations"].append(result.duration_ms)

        # Generate health reports
        health_reports = []

        for package_name, stats in package_stats.items():
            results = stats["results"]
            durations = stats["durations"]

            if not results:
                continue

            # Calculate pass rate
            passed = sum(1 for r in results if r.status == TestStatus.PASSED)
            total = len(results)
            pass_rate = (passed / total) * 100 if total > 0 else 0

            # Calculate average duration
            avg_duration = mean(durations) if durations else 0

            # Detect flaky tests for this package
            package_flaky = [ft for ft in self.detect_flaky_tests() if ft.test_id.startswith(f"packages/{package_name}")]

            # Calculate trend (simplified - compare first half vs second half)
            mid_point = len(results) // 2
            if mid_point > 0:
                first_half = results[:mid_point]
                second_half = results[mid_point:]

                first_pass_rate = sum(1 for r in first_half if r.status == TestStatus.PASSED) / len(first_half) * 100
                second_pass_rate = (
                    sum(1 for r in second_half if r.status == TestStatus.PASSED) / len(second_half) * 100
                )

                trend_pct = second_pass_rate - first_pass_rate

                if trend_pct > 5:
                    trend_direction = "improving"
                elif trend_pct < -5:
                    trend_direction = "degrading"
                else:
                    trend_direction = "stable"
            else:
                trend_direction = "stable"
                trend_pct = 0.0

            health_reports.append(
                PackageHealthReport(
                    package_name=package_name,
                    total_tests=total,
                    pass_rate=pass_rate,
                    avg_duration_ms=avg_duration,
                    flaky_count=len(package_flaky),
                    trend_direction=trend_direction,
                    trend_percentage=trend_pct,
                ),
            )

        # Sort by pass rate (worst first)
        health_reports.sort(key=lambda x: x.pass_rate)
        return health_reports

    def detect_slow_tests(self, top_n: int = 20) -> list[tuple[str, float]]:
        """Identify slowest tests by average duration.

        Args:
            top_n: Number of slow tests to return

        Returns:
            List of (test_id, avg_duration_ms) tuples

        """
        recent_runs = self.storage.get_recent_runs(limit=30)

        # Collect duration data for each test
        test_durations: dict[str, list[float]] = defaultdict(list)

        for run in recent_runs:
            results = self.storage.get_test_results_for_run(run.id)
            for result in results:
                test_durations[result.test_id].append(result.duration_ms)

        # Calculate averages
        avg_durations = [(test_id, mean(durations)) for test_id, durations in test_durations.items()]

        # Sort by duration and return top N
        avg_durations.sort(key=lambda x: x[1], reverse=True)
        return avg_durations[:top_n]

    def cluster_failure_patterns(self) -> list[FailurePattern]:
        """Cluster similar failure messages to identify common root causes.

        Returns:
            List of failure patterns

        """
        recent_runs = self.storage.get_recent_runs(limit=30)

        # Collect all failure messages
        failure_data: dict[str, list[str]] = defaultdict(list)

        for run in recent_runs:
            results = self.storage.get_test_results_for_run(run.id)
            for result in results:
                if result.status in (TestStatus.FAILED, TestStatus.ERROR) and result.error_message:
                    # Normalize error message to create signature
                    signature = self._normalize_error_message(result.error_message)
                    failure_data[signature].append(result.test_id)

        # Create failure patterns
        patterns = []

        for signature, affected_tests in failure_data.items():
            if len(affected_tests) < 2:  # Only cluster if affects multiple tests
                continue

            # Extract package names
            packages = list({test.split("/")[1] if "/" in test else "unknown" for test in affected_tests})

            patterns.append(
                FailurePattern(
                    error_signature=signature,
                    affected_tests=list(set(affected_tests)),
                    occurrence_count=len(affected_tests),
                    first_seen=datetime.now(),  # Simplified
                    last_seen=datetime.now(),
                    packages_affected=packages,
                    suggested_root_cause=self._suggest_root_cause(signature),
                ),
            )

        # Sort by occurrence count
        patterns.sort(key=lambda x: x.occurrence_count, reverse=True)
        return patterns

    def _normalize_error_message(self, error_message: str) -> str:
        """Normalize error message to create signature."""
        # Remove line numbers, memory addresses, timestamps
        normalized = re.sub(r":\d+", "", error_message)  # Remove :123 line numbers
        normalized = re.sub(r"0x[0-9a-fA-F]+", "0xADDR", normalized)  # Remove memory addresses
        normalized = re.sub(r"\d{4}-\d{2}-\d{2}", "DATE", normalized)  # Remove dates
        normalized = re.sub(r"\d+\.\d+s", "Xs", normalized)  # Remove timing

        # Extract just the error type and first line
        lines = normalized.split("\n")
        if lines:
            return lines[0][:200]  # First 200 chars of first line
        return normalized[:200]

    def _suggest_root_cause(self, error_signature: str) -> str | None:
        """Suggest potential root cause based on error signature."""
        signature_lower = error_signature.lower()

        if "tuple" in signature_lower and "not support" in signature_lower:
            return "Possible Pydantic migration issue - check for tuple wrapping"
        if "modulenotfounderror" in signature_lower:
            return "Missing module - check package dependencies and editable installations"
        if "sqlite" in signature_lower and "locked" in signature_lower:
            return "Database concurrency issue - check for parallel test execution"
        if "timeout" in signature_lower:
            return "Performance issue - check for slow operations or deadlocks"
        if "validation" in signature_lower:
            return "Data validation failure - check model schemas and test data"

        return None
